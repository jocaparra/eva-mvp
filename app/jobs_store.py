"""Persistência de jobs — Supabase com fallback em memória."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from app.audit import log_action
from app.db import get_supabase
from app.document_types import confirmation_message

_memory_jobs: dict[str, dict[str, Any]] = {}


def _row_to_job(row: dict[str, Any]) -> dict[str, Any]:
    doc_type = row.get("document_type", "CIM")
    company = row.get("company_name", "")
    return {
        "id": str(row["id"]),
        "company_name": company,
        "document_type": doc_type,
        "client_id": row.get("phone", "default"),
        "phone": row.get("phone", "default"),
        "status": row.get("status", "pending"),
        "confirmation_message": confirmation_message(doc_type, company),
        "ppt_path": row.get("ppt_path"),
        "ppt_filename": row.get("ppt_filename"),
        "qa_passed": row.get("qa_passed"),
        "qa_issues": row.get("qa_issues") or [],
        "error": row.get("error"),
        "whatsapp_phone": row.get("phone"),
    }


def create_job(
    company_name: str,
    doc_type: str,
    *,
    phone: str = "",
    client_id: str = "default",
) -> str:
    job_id = str(uuid.uuid4())
    phone_value = phone or client_id or "default"
    payload = {
        "id": job_id,
        "phone": phone_value,
        "company_name": company_name,
        "document_type": doc_type,
        "status": "pending",
    }

    client = get_supabase()
    if client:
        client.table("jobs").insert(payload).execute()
        log_action(
            phone_value,
            "job_created",
            resource_type="job",
            resource_id=job_id,
            metadata={"document_type": doc_type},
        )
    else:
        _memory_jobs[job_id] = _row_to_job({**payload, "qa_passed": None, "qa_issues": None})

    return job_id


def get_job(job_id: str, phone: Optional[str] = None) -> Optional[dict[str, Any]]:
    client = get_supabase()
    if client:
        query = client.table("jobs").select("*").eq("id", job_id)
        if phone:
            query = query.eq("phone", phone)
        result = query.maybe_single().execute()
        row = result.data
        if not row:
            return None
        return _row_to_job(row)

    job = _memory_jobs.get(job_id)
    if not job:
        return None
    if phone and job.get("phone") != phone:
        return None
    return job


def update_job(job_id: str, **fields: Any) -> Optional[dict[str, Any]]:
    fields = {k: v for k, v in fields.items() if v is not None or k in ("error", "qa_issues")}
    client = get_supabase()
    if client:
        if fields:
            client.table("jobs").update(fields).eq("id", job_id).execute()
        return get_job(job_id)

    if job_id not in _memory_jobs:
        return None
    _memory_jobs[job_id].update(fields)
    return _memory_jobs[job_id]


def phone_has_jobs(phone: str) -> bool:
    client = get_supabase()
    if client:
        try:
            result = (
                client.table("jobs")
                .select("id")
                .eq("phone", phone)
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception:
            return False

    return any(job.get("phone") == phone for job in _memory_jobs.values())


def list_jobs(phone: str, limit: int = 50) -> list[dict[str, Any]]:
    client = get_supabase()
    if client:
        try:
            result = (
                client.table("jobs")
                .select("*")
                .eq("phone", phone)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return [_row_to_job(row) for row in (result.data or [])]
        except Exception:
            return []

    jobs = [job for job in _memory_jobs.values() if job.get("phone") == phone]
    return jobs[:limit]
