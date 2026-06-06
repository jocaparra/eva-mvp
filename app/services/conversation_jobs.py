"""Vínculo entre jobs web e conversas persistentes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.conversation import add_message, ensure_deal_for_conversation, get_conversation_for_owner, link_deal_to_conversation


def prepare_conversation_job(
    session: Session,
    *,
    conversation_id: UUID,
    owner_phone: str,
    company_name: str,
    user_message: str,
    job_id: str,
) -> str:
    """Persiste mensagens e garante deal_id antes de disparar o job."""
    deal_uuid = ensure_deal_for_conversation(
        session, conversation_id, owner_phone, company_name
    )
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    if conv.title == "Nova conversa":
        from app.repositories.conversation import _title_from_content
        conv.title = _title_from_content(user_message)
    add_message(
        session,
        conversation_id=conversation_id,
        owner_phone=owner_phone,
        role="user",
        content=user_message,
    )
    add_message(
        session,
        conversation_id=conversation_id,
        owner_phone=owner_phone,
        role="assistant",
        content=f"⏳ Gerando <strong>{company_name}</strong>... Aguarde 2–5 minutos.",
        job_id=job_id,
    )
    return str(deal_uuid)


def finalize_conversation_job(
    session: Session,
    *,
    conversation_id: UUID,
    owner_phone: str,
    company_name: str,
    job_id: str,
    success: bool,
    error: str = "",
    deal_id: str = "",
) -> None:
    """Mensagem final do assistant ao concluir ou falhar o job."""
    if deal_id:
        link_deal_to_conversation(session, conversation_id, owner_phone, UUID(deal_id))
    if success:
        content = f"✅ <strong>{company_name}</strong> está pronto! Documento disponível para download."
    else:
        content = f"❌ Erro ao gerar {company_name}: {error or 'tente novamente.'}"
    add_message(
        session,
        conversation_id=conversation_id,
        owner_phone=owner_phone,
        role="assistant",
        content=content,
        job_id=job_id,
    )
