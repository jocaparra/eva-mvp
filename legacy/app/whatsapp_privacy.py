"""Mensagens de privacidade e detecção de primeiro contato."""

from __future__ import annotations

import os
from typing import Set

from app.db import get_supabase
from app.jobs_store import phone_has_jobs
from app.whatsapp import send_message

_welcomed_phones: Set[str] = set()


def privacy_policy_url() -> str:
    return os.getenv(
        "PRIVACY_POLICY_URL", "https://oxai.online/privacidade"
    ).strip()


def privacy_welcome_message() -> str:
    url = privacy_policy_url()
    return (
        "🔒 *Política de privacidade EVA*\n\n"
        "Seus documentos e dados são protegidos:\n"
        "- Arquivos enviados são processados e descartados imediatamente\n"
        "- Nenhum documento original é armazenado\n"
        "- Apenas metadados de uso são registrados\n"
        "- Seus dados nunca são usados para treinar modelos de IA\n\n"
        f"_Ao usar a EVA você confirma que leu nossa política completa em {url}_"
    )


def document_received_message() -> str:
    return (
        "📄 Documento recebido. Processado em memória e descartado.\n"
        "Contexto disponível por 30 minutos."
    )


def _phone_in_subscriptions(phone: str) -> bool:
    client = get_supabase()
    if not client:
        return False
    try:
        result = (
            client.table("subscriptions")
            .select("phone")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False


def is_first_contact(phone: str) -> bool:
    if phone in _welcomed_phones:
        return False
    if _phone_in_subscriptions(phone) or phone_has_jobs(phone):
        _welcomed_phones.add(phone)
        return False
    return True


def send_privacy_welcome(phone: str) -> None:
    send_message(phone, privacy_welcome_message())
    _welcomed_phones.add(phone)
