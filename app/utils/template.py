"""Templates por cliente via Supabase Storage."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.audit import log_action
from app.db import get_supabase

STORAGE_BUCKET = "templates"
TEMPLATE_FILENAME = "template.pptx"
TEMPLATES_ROOT = Path("templates")  # fallback local dev


def _sanitize_phone(phone: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", (phone or "default").strip())
    return safe or "default"


def _storage_path(phone: str) -> str:
    return f"{_sanitize_phone(phone)}/{TEMPLATE_FILENAME}"


def _local_path(phone: str) -> Path:
    return TEMPLATES_ROOT / _sanitize_phone(phone) / TEMPLATE_FILENAME


def client_has_own_template(phone: str) -> bool:
    client = get_supabase()
    if client:
        try:
            result = (
                client.table("client_templates")
                .select("phone")
                .eq("phone", _sanitize_phone(phone))
                .maybe_single()
                .execute()
            )
            if result.data:
                return True
        except Exception:
            pass

    return _local_path(phone).is_file()


def _upload_to_storage(phone: str, file_bytes: bytes, filename: str) -> str:
    client = get_supabase()
    if not client:
        dest = _local_path(phone)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes)
        return str(dest)

    path = _storage_path(phone)
    bucket = client.storage.from_(STORAGE_BUCKET)
    bucket.upload(
        path,
        file_bytes,
        file_options={
            "content-type": (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            "upsert": "true",
        },
    )

    client.table("client_templates").upsert(
        {
            "phone": _sanitize_phone(phone),
            "filename": filename or TEMPLATE_FILENAME,
            "storage_path": path,
        }
    ).execute()

    log_action(
        _sanitize_phone(phone),
        "template_received",
        resource_type="template",
        resource_id=path,
        metadata={"filename": filename},
    )
    return path


def save_client_template(phone: str, file_bytes: bytes, filename: str = TEMPLATE_FILENAME) -> str:
    """Salva template no Storage (ou disco local se Supabase ausente)."""
    return _upload_to_storage(phone, file_bytes, filename)


def _download_from_storage(storage_path: str, dest: Path) -> bool:
    client = get_supabase()
    if not client:
        return False
    try:
        data = client.storage.from_(STORAGE_BUCKET).download(storage_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as exc:
        print(f"[template] download failed: {type(exc).__name__}")
        return False


def _resolve_storage_path(phone: str) -> Optional[str]:
    client = get_supabase()
    if not client:
        return None

    for candidate in (_sanitize_phone(phone), "default"):
        try:
            result = (
                client.table("client_templates")
                .select("storage_path")
                .eq("phone", candidate)
                .maybe_single()
                .execute()
            )
            if result.data and result.data.get("storage_path"):
                return result.data["storage_path"]
        except Exception:
            continue
    return None


def get_template_path(phone_number: str, job_id: Optional[str] = None) -> str:
    """
    Baixa template para /tmp/{job_id}_template.pptx (ou path local em dev).
    Fallback: template default do mesmo phone/storage.
    """
    tmp_name = f"{job_id}_template.pptx" if job_id else "template.pptx"
    tmp_path = Path(f"/tmp/{tmp_name}")

    storage_path = _resolve_storage_path(phone_number)
    if storage_path and _download_from_storage(storage_path, tmp_path):
        return str(tmp_path)

    # fallback local filesystem (dev sem Supabase)
    for candidate in (_sanitize_phone(phone_number), "default"):
        local = _local_path(candidate)
        if local.is_file():
            if job_id:
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(local.read_bytes())
                return str(tmp_path)
            return str(local)

    return ""


def cleanup_temp_template(path: str) -> None:
    """Remove arquivo temporário baixado do Storage."""
    if not path or not path.startswith("/tmp/"):
        return
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
    except Exception:
        pass
