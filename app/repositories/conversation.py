"""Repositório CRUD de conversas — isolamento por owner_phone."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.conversation import Conversation, Message
from app.models.deal_workspace import DealWorkspace  # noqa: F401 — FK target
from app.repositories.deal_workspace import create_deal


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class ConversationNotFoundError(Exception):
    pass


class ConversationAccessDeniedError(Exception):
    pass


def _title_from_content(content: str, max_len: int = 50) -> str:
    cleaned = " ".join(content.split())
    if len(cleaned) <= max_len:
        return cleaned or "Nova conversa"
    return cleaned[: max_len - 1].rstrip() + "…"


def create_conversation(session: Session, *, owner_phone: str, title: str = "Nova conversa") -> Conversation:
    conv = Conversation(owner_phone=owner_phone, title=title.strip() or "Nova conversa")
    session.add(conv)
    session.flush()
    session.refresh(conv)
    return conv


def list_conversations(session: Session, owner_phone: str, limit: int = 50) -> list[Conversation]:
    return (
        session.query(Conversation)
        .filter(Conversation.owner_phone == owner_phone)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def get_conversation_for_owner(
    session: Session, conversation_id: UUID, owner_phone: str
) -> Conversation:
    conv = (
        session.query(Conversation)
        .options(selectinload(Conversation.messages))
        .filter(Conversation.id == conversation_id)
        .one_or_none()
    )
    if conv is None:
        raise ConversationNotFoundError(str(conversation_id))
    if conv.owner_phone != owner_phone:
        raise ConversationAccessDeniedError(str(conversation_id))
    return conv


def add_message(
    session: Session,
    *,
    conversation_id: UUID,
    owner_phone: str,
    role: str,
    content: str,
    job_id: Optional[str] = None,
) -> Message:
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    msg = Message(
        conversation_id=conv.id,
        role=role,
        content=content,
        job_id=job_id,
    )
    session.add(msg)
    if role == "user" and conv.title == "Nova conversa":
        conv.title = _title_from_content(content)
    conv.updated_at = _utcnow()
    session.flush()
    session.refresh(msg)
    return msg


def update_conversation_title(
    session: Session, conversation_id: UUID, owner_phone: str, title: str
) -> Conversation:
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    conv.title = title.strip()
    session.flush()
    session.refresh(conv)
    return conv


def delete_conversation(session: Session, conversation_id: UUID, owner_phone: str) -> None:
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    session.delete(conv)
    session.flush()


def ensure_deal_for_conversation(
    session: Session,
    conversation_id: UUID,
    owner_phone: str,
    company_name: str,
) -> UUID:
    """Garante deal_id na conversa; cria deal workspace se necessário."""
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    if conv.deal_id:
        return conv.deal_id
    deal = create_deal(session, company_name=company_name, owner_phone=owner_phone)
    conv.deal_id = deal.id
    session.flush()
    return deal.id


def link_deal_to_conversation(
    session: Session,
    conversation_id: UUID,
    owner_phone: str,
    deal_id: UUID,
) -> Conversation:
    conv = get_conversation_for_owner(session, conversation_id, owner_phone)
    conv.deal_id = deal_id
    session.flush()
    session.refresh(conv)
    return conv
