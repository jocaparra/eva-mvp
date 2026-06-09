"""Processamento efêmero de documentos confidenciais via WhatsApp."""

from __future__ import annotations

from typing import Any, Optional

from app.audit import log_action
from app.media import download_bytes
from app.utils.doc_cache import store_context
from app.utils.doc_extractor import extract_document
from app.whatsapp import send_message
from app.whatsapp_privacy import document_received_message
from app.whatsapp_templates import extract_document_info


def _is_analysis_document(filename: str, mime_type: str) -> bool:
    name = (filename or "").lower()
    mime = (mime_type or "").lower()

    if name.endswith(".pptx") or "presentationml" in mime:
        return False

    if name.endswith((".pdf", ".xlsx", ".xls", ".docx", ".csv")):
        return True

    if mime in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/csv",
        "application/csv",
    ):
        return True

    if "spreadsheetml" in mime or "wordprocessingml" in mime:
        return True

    return False


def handle_whatsapp_document_upload(data: dict[str, Any], phone: str) -> Optional[dict]:
    """
    Baixa documento para memória, extrai texto, descarta bytes originais.
    Retorna dict de status ou None se não for documento de análise.
    """
    url, filename, mime = extract_document_info(data)
    if not url or not _is_analysis_document(filename, mime):
        return None

    file_bytes: bytes | None = download_bytes(url)
    if not file_bytes:
        send_message(
            phone,
            "❌ Não consegui baixar o documento. Tente enviar novamente.",
        )
        return {"status": "document_download_failed"}

    size_kb = round(len(file_bytes) / 1024, 1)

    try:
        text, doc_type = extract_document(file_bytes, filename, mime)
    except Exception as exc:
        send_message(
            phone,
            f"❌ Não consegui processar o documento: {exc}",
        )
        return {"status": "document_extract_failed"}
    finally:
        del file_bytes

    store_context(phone, text, doc_type)
    del text

    log_action(
        phone,
        "document_received",
        resource_type="document",
        metadata={"doc_type": doc_type, "size_kb": size_kb},
    )

    send_message(phone, document_received_message())

    return {"status": "document_processed", "phone": phone, "doc_type": doc_type}
