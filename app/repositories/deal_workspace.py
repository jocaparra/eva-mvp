"""Repositório CRUD do deal workspace."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.models.deal_workspace import DealWorkspace
from app.schemas.deal_workspace import DealWorkspaceResponse


class DealNotFoundError(Exception):
    pass


class DealAccessDeniedError(Exception):
    pass


def create_deal(session: Session, *, company_name: str, owner_phone: str) -> DealWorkspace:
    """Cria um deal workspace em status draft."""
    deal = DealWorkspace(
        company_name=company_name.strip(),
        owner_phone=owner_phone,
        status="draft",
        retrieved_context=[],
    )
    session.add(deal)
    session.flush()
    session.refresh(deal)
    return deal


def get_deal_for_owner(session: Session, deal_id: UUID, owner_phone: str) -> DealWorkspace:
    """Busca deal garantindo isolamento por owner_phone."""
    deal = (
        session.query(DealWorkspace)
        .options(
            selectinload(DealWorkspace.documents),
            selectinload(DealWorkspace.artifacts),
        )
        .filter(DealWorkspace.id == deal_id)
        .one_or_none()
    )
    if deal is None:
        raise DealNotFoundError(str(deal_id))
    if deal.owner_phone != owner_phone:
        raise DealAccessDeniedError(str(deal_id))
    return deal


def to_deal_state(deal: DealWorkspace) -> DealWorkspaceResponse:
    """Converte ORM → schema de resposta (DealState persistido)."""
    return DealWorkspaceResponse(
        deal_id=deal.id,
        company_name=deal.company_name,
        owner_phone=deal.owner_phone,
        status=deal.status,
        documents=deal.documents,
        retrieved_context=deal.retrieved_context or [],
        artifacts=deal.artifacts,
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )
