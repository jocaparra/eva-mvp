"""Audit log automático no Supabase."""

from __future__ import annotations

from typing import Any, Optional

from app.db import get_supabase
from app.log_utils import mask_phone


def log_action(
    phone: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    client = get_supabase()
    if not client:
        print(
            f"[audit] {action} phone={mask_phone(phone)} "
            f"resource={resource_type} id={resource_id}"
        )
        return

    try:
        client.table("audit_logs").insert(
            {
                "phone": phone,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception as exc:
        print(f"[audit] falha ao registrar {action}: {type(exc).__name__}")
