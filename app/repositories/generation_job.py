"""Repositório de jobs de geração (SQLAlchemy)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.document_types import confirmation_message
from app.models.generation_job import GenerationJob


def job_to_record(job: GenerationJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "company_name": job.company_name,
        "document_type": job.document_type,
        "client_id": job.owner_phone,
        "phone": job.owner_phone,
        "status": job.status,
        "confirmation_message": confirmation_message(job.document_type, job.company_name),
        "ppt_path": job.ppt_path,
        "ppt_filename": job.ppt_filename,
        "qa_passed": job.qa_passed,
        "qa_issues": job.qa_issues or [],
        "error": job.error,
        "whatsapp_phone": job.owner_phone,
        "deal_id": str(job.deal_id) if job.deal_id else None,
        "conversation_id": str(job.conversation_id) if job.conversation_id else None,
    }


def _parse_uuid(value: Any) -> Optional[UUID]:
    if value is None or value == "":
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def create_generation_job(
    session: Session,
    *,
    company_name: str,
    document_type: str,
    owner_phone: str,
    deal_id: Optional[str | UUID] = None,
    conversation_id: Optional[str | UUID] = None,
    job_id: Optional[str | UUID] = None,
) -> GenerationJob:
    kwargs: dict[str, Any] = {
        "company_name": company_name,
        "document_type": document_type,
        "owner_phone": owner_phone or "default",
        "status": "pending",
        "deal_id": _parse_uuid(deal_id),
        "conversation_id": _parse_uuid(conversation_id),
    }
    if job_id:
        kwargs["id"] = _parse_uuid(job_id)
    job = GenerationJob(**kwargs)
    session.add(job)
    session.flush()
    session.refresh(job)
    return job


def get_generation_job(
    session: Session,
    job_id: str | UUID,
    *,
    owner_phone: Optional[str] = None,
) -> Optional[GenerationJob]:
    query = session.query(GenerationJob).filter(GenerationJob.id == _parse_uuid(job_id))
    if owner_phone:
        query = query.filter(GenerationJob.owner_phone == owner_phone)
    return query.one_or_none()


def update_generation_job(
    session: Session,
    job_id: str | UUID,
    **fields: Any,
) -> Optional[GenerationJob]:
    job = get_generation_job(session, job_id)
    if job is None:
        return None

    if "deal_id" in fields:
        fields["deal_id"] = _parse_uuid(fields["deal_id"])
    if "conversation_id" in fields:
        fields["conversation_id"] = _parse_uuid(fields["conversation_id"])

    for key, value in fields.items():
        if key in ("error", "qa_issues") or value is not None:
            setattr(job, key, value)

    session.flush()
    session.refresh(job)
    return job


def list_generation_jobs(session: Session, owner_phone: str, limit: int = 50) -> list[GenerationJob]:
    return (
        session.query(GenerationJob)
        .filter(GenerationJob.owner_phone == owner_phone)
        .order_by(GenerationJob.created_at.desc())
        .limit(limit)
        .all()
    )


def phone_has_generation_jobs(session: Session, owner_phone: str) -> bool:
    return (
        session.query(GenerationJob.id)
        .filter(GenerationJob.owner_phone == owner_phone)
        .limit(1)
        .first()
        is not None
    )
