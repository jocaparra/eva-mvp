import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

MONTHLY_LIMIT = int(os.getenv("MONTHLY_JOB_LIMIT", "30"))
_monthly_jobs: dict[str, dict[str, int]] = {}


async def check_access(phone: str) -> bool:
    """Verifica se o número tem assinatura ativa."""
    if os.getenv("WHATSAPP_OPEN_ACCESS", "").lower() in ("1", "true", "yes"):
        return True

    allowed = os.getenv("WHATSAPP_ALLOWED_PHONES", "")
    if allowed.strip():
        return phone in {p.strip() for p in allowed.split(",") if p.strip()}

    # Sem Supabase configurado: libera acesso em desenvolvimento
    if not os.getenv("SUPABASE_URL"):
        return True

    # TODO: consultar assinatura no Supabase
    return False


async def check_job_limit(phone: str) -> bool:
    """Verifica limite mensal de documentos."""
    month = datetime.utcnow().strftime("%Y-%m")
    counts = _monthly_jobs.setdefault(phone, {})
    return counts.get(month, 0) < MONTHLY_LIMIT


def record_job(phone: str) -> None:
    month = datetime.utcnow().strftime("%Y-%m")
    counts = _monthly_jobs.setdefault(phone, {})
    counts[month] = counts.get(month, 0) + 1
