import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.audit import log_action
from app.db import get_supabase

load_dotenv()

MONTHLY_LIMIT = int(os.getenv("MONTHLY_JOB_LIMIT", "30"))


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def check_access(phone: str) -> bool:
    """Verifica se o número tem assinatura ativa."""
    if os.getenv("WHATSAPP_OPEN_ACCESS", "").lower() in ("1", "true", "yes"):
        return True

    allowed = os.getenv("WHATSAPP_ALLOWED_PHONES", "")
    if allowed.strip():
        return phone in {p.strip() for p in allowed.split(",") if p.strip()}

    client = get_supabase()
    if not client:
        return True

    try:
        result = (
            client.table("subscriptions")
            .select("active")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )
        row = result.data
        if not row:
            log_action(
                phone,
                "access_blocked",
                resource_type="subscription",
                metadata={"reason": "no_subscription"},
            )
            return False
        if not row.get("active"):
            log_action(
                phone,
                "access_blocked",
                resource_type="subscription",
                metadata={"reason": "inactive"},
            )
            return False
        return True
    except Exception as exc:
        print(f"[access] check_access error: {type(exc).__name__}")
        return False


async def check_job_limit(phone: str) -> bool:
    """Verifica limite mensal de documentos."""
    client = get_supabase()
    if not client:
        return True

    month = _current_month()
    try:
        result = (
            client.table("subscriptions")
            .select("jobs_this_month, month")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )
        row = result.data
        if not row:
            return True
        if row.get("month") != month:
            return True
        return int(row.get("jobs_this_month") or 0) < MONTHLY_LIMIT
    except Exception as exc:
        print(f"[access] check_job_limit error: {type(exc).__name__}")
        return True


def record_job(phone: str) -> None:
    client = get_supabase()
    if not client:
        return

    month = _current_month()
    try:
        existing = (
            client.table("subscriptions")
            .select("jobs_this_month, month")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )
        row = existing.data
        if not row:
            client.table("subscriptions").upsert(
                {
                    "phone": phone,
                    "active": True,
                    "jobs_this_month": 1,
                    "month": month,
                }
            ).execute()
            return

        count = int(row.get("jobs_this_month") or 0)
        if row.get("month") != month:
            count = 0

        client.table("subscriptions").update(
            {"jobs_this_month": count + 1, "month": month}
        ).eq("phone", phone).execute()
    except Exception as exc:
        print(f"[access] record_job error: {type(exc).__name__}")
