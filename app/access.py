import os
from datetime import datetime
from app.db import get_supabase

MONTHLY_LIMIT = int(os.getenv("MONTHLY_JOB_LIMIT", "30"))

# fallback em memória para dev sem Supabase
_memory_jobs: dict[str, dict[str, int]] = {}


async def check_access(phone: str) -> bool:
    if os.getenv("WHATSAPP_OPEN_ACCESS", "").lower() in ("1", "true", "yes"):
        return True

    allowed = os.getenv("WHATSAPP_ALLOWED_PHONES", "")
    if allowed.strip():
        return phone in {p.strip() for p in allowed.split(",") if p.strip()}

    client = get_supabase()
    if not client:
        return True  # dev sem Supabase: libera

    try:
        res = (
            client.table("assinaturas")
            .select("status")
            .eq("phone", phone)
            .eq("status", "ativa")
            .maybe_single()
            .execute()
        )
        return bool(res.data)
    except Exception:
        return False


async def check_job_limit(phone: str) -> bool:
    mes = datetime.utcnow().strftime("%Y-%m")

    client = get_supabase()
    if not client:
        counts = _memory_jobs.setdefault(phone, {})
        return counts.get(mes, 0) < MONTHLY_LIMIT

    try:
        res = (
            client.table("uso_mensal")
            .select("total")
            .eq("phone", phone)
            .eq("mes", mes)
            .maybe_single()
            .execute()
        )
        total = (res.data or {}).get("total", 0)
        return total < MONTHLY_LIMIT
    except Exception:
        return True  # em caso de erro, não bloqueia


def record_job(phone: str) -> None:
    mes = datetime.utcnow().strftime("%Y-%m")

    client = get_supabase()
    if not client:
        counts = _memory_jobs.setdefault(phone, {})
        counts[mes] = counts.get(mes, 0) + 1
        return

    try:
        client.rpc("incrementar_uso", {"p_phone": phone, "p_mes": mes}).execute()
    except Exception:
        pass
