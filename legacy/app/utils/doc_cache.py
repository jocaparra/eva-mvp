"""Cache temporário em memória para contexto extraído de documentos (TTL 30 min)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.audit import log_action

TTL_MINUTES = 30

doc_cache: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_expired() -> None:
    now = _now()
    for phone in list(doc_cache.keys()):
        entry = doc_cache[phone]
        if entry["expires_at"] <= now:
            log_action(
                phone,
                "document_context_expired",
                resource_type="document",
                metadata={"doc_type": entry.get("doc_type")},
            )
            del doc_cache[phone]


def store_context(phone: str, text: str, doc_type: str) -> None:
    cleanup_expired()
    doc_cache[phone] = {
        "context": text,
        "expires_at": _now() + timedelta(minutes=TTL_MINUTES),
        "doc_type": doc_type,
    }


def get_context(phone: str) -> Optional[str]:
    cleanup_expired()
    entry = doc_cache.get(phone)
    if not entry:
        return None
    if entry["expires_at"] <= _now():
        log_action(
            phone,
            "document_context_expired",
            resource_type="document",
            metadata={"doc_type": entry.get("doc_type")},
        )
        del doc_cache[phone]
        return None
    return entry["context"]


def get_context_meta(phone: str) -> Optional[dict[str, Any]]:
    cleanup_expired()
    entry = doc_cache.get(phone)
    if not entry or entry["expires_at"] <= _now():
        return None
    return {"doc_type": entry.get("doc_type")}


def clear_context(phone: str) -> None:
    doc_cache.pop(phone, None)
