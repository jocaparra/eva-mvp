"""Upload efêmero de documentos via web — Storage temporário + doc_cache."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Optional

from app.audit import log_action
from app.db import get_supabase
from app.log_utils import mask_phone
from app.utils.doc_cache import TTL_MINUTES, store_context
from app.utils.doc_extractor import extract_document, is_allowed_document
from app.utils.template import _sanitize_phone

STORAGE_BUCKET = "client-documents"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _safe_filename(filename: str) -> str:
    name = Path(filename or "document").name
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    return safe or "document"


def _storage_path(phone: str, upload_id: str, filename: str) -> str:
    return f"{_sanitize_phone(phone)}/{upload_id}_{_safe_filename(filename)}"


def _content_type(filename: str, mime_type: str) -> str:
    if mime_type:
        return mime_type
    ext = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
    }.get(ext, "application/octet-stream")


def validate_upload(filename: str, mime_type: str, size: int) -> None:
    if size <= 0:
        raise ValueError("Arquivo vazio.")
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("Arquivo excede o limite de 50MB.")
    if not is_allowed_document(filename, mime_type):
        raise ValueError(
            "Tipo não suportado. Envie .pdf, .xlsx, .xls, .docx ou .csv."
        )


def process_web_document_upload(
    phone: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str = "",
) -> dict[str, Any]:
    """
    Upload temporário → extração → doc_cache → delete do Storage.
    Retorna metadados de resposta (sem conteúdo do documento).
    """
    validate_upload(filename, mime_type, len(file_bytes))

    upload_id = str(uuid.uuid4())
    storage_path = _storage_path(phone, upload_id, filename)
    size_kb = round(len(file_bytes) / 1024, 1)

    client = get_supabase()
    text: Optional[str] = None
    doc_type: Optional[str] = None

    try:
        if client:
            bucket = client.storage.from_(STORAGE_BUCKET)
            bucket.upload(
                storage_path,
                file_bytes,
                file_options={
                    "content-type": _content_type(filename, mime_type),
                    "upsert": "false",
                },
            )

        text, doc_type = extract_document(file_bytes, filename, mime_type)
        store_context(phone, text, doc_type)
    finally:
        del file_bytes
        if text is not None:
            del text

        if client:
            try:
                client.storage.from_(STORAGE_BUCKET).remove([storage_path])
            except Exception as exc:
                print(
                    f"[client_documents] falha ao deletar {storage_path}: "
                    f"{type(exc).__name__}"
                )

    log_action(
        phone,
        "document_received",
        resource_type="document",
        metadata={
            "doc_type": doc_type,
            "size_kb": size_kb,
            "source": "web",
        },
    )
    print(
        f"[client_documents] processado phone={mask_phone(phone)} "
        f"doc_type={doc_type} size_kb={size_kb}"
    )

    return {
        "status": "processed",
        "context_available": True,
        "expires_in": f"{TTL_MINUTES}min",
    }
