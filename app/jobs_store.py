"""Persistência de jobs — SQLAlchemy (Postgres/SQLite)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import session_scope
from app.repositories.generation_job import (
    create_generation_job,
    get_generation_job,
    job_to_record,
    list_generation_jobs,
    phone_has_generation_jobs,
    update_generation_job,
)


def create_job(
    company_name: str,
    doc_type: str,
    *,
    phone: str = "",
    client_id: str = "default",
    deal_id: str = "",
    conversation_id: str = "",
    db: Optional[Session] = None,
) -> str:
    owner = phone or client_id or "default"

    def _create(session: Session) -> str:
        job = create_generation_job(
            session,
            company_name=company_name,
            document_type=doc_type,
            owner_phone=owner,
            deal_id=deal_id or None,
            conversation_id=conversation_id or None,
        )
        log_action(
            owner,
            "job_created",
            resource_type="job",
            resource_id=str(job.id),
            metadata={"document_type": doc_type},
        )
        return str(job.id)

    if db is not None:
        return _create(db)

    with session_scope() as session:
        return _create(session)


def get_job(job_id: str, phone: Optional[str] = None, db: Optional[Session] = None) -> Optional[dict[str, Any]]:
    def _get(session: Session) -> Optional[dict[str, Any]]:
        job = get_generation_job(session, job_id, owner_phone=phone)
        return job_to_record(job) if job else None

    if db is not None:
        return _get(db)

    with session_scope() as session:
        return _get(session)


def update_job(job_id: str, db: Optional[Session] = None, **fields: Any) -> Optional[dict[str, Any]]:
    def _update(session: Session) -> Optional[dict[str, Any]]:
        job = update_generation_job(session, job_id, **fields)
        return job_to_record(job) if job else None

    if db is not None:
        return _update(db)

    with session_scope() as session:
        return _update(session)


def phone_has_jobs(phone: str) -> bool:
    with session_scope() as session:
        return phone_has_generation_jobs(session, phone)


def list_jobs(phone: str, limit: int = 50) -> list[dict[str, Any]]:
    with session_scope() as session:
        jobs = list_generation_jobs(session, phone, limit=limit)
        return [job_to_record(job) for job in jobs]
