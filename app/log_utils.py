"""Logs seguros — nunca expõe conteúdo de mensagens."""

from __future__ import annotations

import re


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 4:
        return f"...{digits[-4:]}"
    return "****"


def log_job_created(phone: str, document_type: str, job_id: str) -> None:
    print(
        f"job criado: {document_type} "
        f"phone: {mask_phone(phone)} job_id: {job_id}"
    )


def log_webhook_received(phone: str, event_type: str | None = None) -> None:
    kind = event_type or "unknown"
    print(f"webhook recebido: type={kind} phone: {mask_phone(phone)}")


def log_webhook_error(exc: Exception) -> None:
    print(f"erro no webhook: {type(exc).__name__}: {exc}")
