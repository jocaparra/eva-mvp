"""Repositório de artefatos gerados e aprovações humanas."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.citations.matching import CitationStatus
from app.models.deal_workspace import ArtifactApproval, WorkspaceArtifact
from app.repositories.deal_workspace import DealAccessDeniedError, DealNotFoundError, get_deal_for_owner

BLOCKING_STATUSES = {CitationStatus.UNCITED.value, CitationStatus.DIVERGENT.value}


class ArtifactNotFoundError(Exception):
    pass


class ApprovalBlockedError(Exception):
    """QA bloqueante sem override justificado."""

    def __init__(self, message: str, blocking_issues: list[str]):
        super().__init__(message)
        self.blocking_issues = blocking_issues


class AlreadyApprovedError(Exception):
    pass


def compute_file_hash(file_path: Optional[str]) -> str:
    """SHA-256 dos bytes do artefato entregue (PPT/DOCX) — prova de aprovação."""
    if not file_path:
        return ""
    path = Path(file_path)
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_version_fingerprint(file_path: Optional[str], field_audits: dict) -> str:
    """Fingerprint para invalidação de versão (arquivo + audits)."""
    hasher = hashlib.sha256()
    file_hash = compute_file_hash(file_path)
    if file_hash:
        hasher.update(file_hash.encode("utf-8"))
    hasher.update(json.dumps(field_audits, sort_keys=True, default=str).encode("utf-8"))
    return hasher.hexdigest()


# Alias legado — content_hash persistido = hash dos bytes do arquivo
compute_content_hash = compute_file_hash


def _blocking_issues(artifact: WorkspaceArtifact) -> list[str]:
    issues: list[str] = []
    if not artifact.qa_passed:
        issues.extend(str(i) for i in (artifact.qa_issues or []))
    for field, audit in (artifact.field_audits or {}).items():
        if audit.get("status") in BLOCKING_STATUSES:
            issues.append(
                f"Campo '{field}' = '{audit.get('value')}' ({audit.get('status')})"
            )
    return issues


def get_artifact_for_owner(
    session: Session,
    deal_id: UUID,
    artifact_id: UUID,
    owner_phone: str,
) -> WorkspaceArtifact:
    get_deal_for_owner(session, deal_id, owner_phone)
    artifact = (
        session.query(WorkspaceArtifact)
        .options(selectinload(WorkspaceArtifact.approvals))
        .filter(
            WorkspaceArtifact.id == artifact_id,
            WorkspaceArtifact.deal_id == deal_id,
        )
        .one_or_none()
    )
    if artifact is None:
        raise ArtifactNotFoundError(str(artifact_id))
    return artifact


def get_active_approval(session: Session, artifact: WorkspaceArtifact) -> Optional[ArtifactApproval]:
    """Aprovação válida para a versão atual do artefato."""
    if not artifact.approved:
        return None
    return (
        session.query(ArtifactApproval)
        .filter(
            ArtifactApproval.artifact_id == artifact.id,
            ArtifactApproval.artifact_version == artifact.version,
            ArtifactApproval.content_hash == (artifact.content_hash or ""),
        )
        .order_by(ArtifactApproval.approved_at.desc())
        .first()
    )


def upsert_artifact_from_pipeline(
    session: Session,
    *,
    deal_id: UUID,
    owner_phone: str,
    artifact_type: str,
    pipeline_result: dict[str, Any],
) -> WorkspaceArtifact:
    """Persiste ou atualiza artefato; regeneração invalida aprovação anterior."""
    get_deal_for_owner(session, deal_id, owner_phone)

    field_audits = pipeline_result.get("field_audits") or {}
    file_path = pipeline_result.get("file_path") or pipeline_result.get("ppt_path")
    file_hash = compute_file_hash(file_path)

    artifact_type = pipeline_result.get("artifact_type") or artifact_type

    artifact = (
        session.query(WorkspaceArtifact)
        .filter(
            WorkspaceArtifact.deal_id == deal_id,
            WorkspaceArtifact.artifact_type == artifact_type,
        )
        .one_or_none()
    )

    citations = pipeline_result.get("financial_citations") or []
    qa_issues = pipeline_result.get("qa_issues") or []
    qa_passed = bool(pipeline_result.get("qa_passed"))
    audit_mode = pipeline_result.get("audit_mode") or "full"
    status = "ready" if qa_passed else "needs_review"

    if artifact is None:
        artifact = WorkspaceArtifact(
            deal_id=deal_id,
            artifact_type=artifact_type,
            status=status,
            file_path=file_path,
            citations=citations,
            qa_issues=qa_issues,
            field_audits=field_audits,
            audit_mode=audit_mode,
            qa_passed=qa_passed,
            version=1,
            content_hash=file_hash,
            approved=False,
        )
        session.add(artifact)
    else:
        regen = (artifact.content_hash or "") != file_hash or (artifact.field_audits or {}) != field_audits
        if regen:
            artifact.version += 1
            artifact.approved = False
        artifact.status = status
        artifact.file_path = file_path
        artifact.citations = citations
        artifact.qa_issues = qa_issues
        artifact.field_audits = field_audits
        artifact.audit_mode = audit_mode
        artifact.qa_passed = qa_passed
        artifact.content_hash = file_hash
        artifact.artifact_type = artifact_type

    session.flush()
    session.refresh(artifact)
    return artifact


def approve_artifact(
    session: Session,
    *,
    deal_id: UUID,
    artifact_id: UUID,
    owner_phone: str,
    override_reason: Optional[str] = None,
) -> ArtifactApproval:
    """Registra aprovação humana imutável; permite override com justificativa."""
    artifact = get_artifact_for_owner(session, deal_id, artifact_id, owner_phone)

    active = get_active_approval(session, artifact)
    if active is not None:
        raise AlreadyApprovedError(str(artifact_id))

    blocking = _blocking_issues(artifact)
    had_blocking = bool(blocking)
    override = bool(had_blocking)

    if had_blocking and not (override_reason or "").strip():
        raise ApprovalBlockedError(
            "Artefato com issues bloqueantes — override exige justificativa.",
            blocking,
        )

    approval = ArtifactApproval(
        artifact_id=artifact.id,
        deal_id=deal_id,
        artifact_version=artifact.version,
        content_hash=artifact.content_hash or "",
        approver_phone=owner_phone,
        had_blocking_issues=had_blocking,
        override=override,
        override_reason=(override_reason or "").strip() or None,
        field_audits_snapshot=artifact.field_audits or {},
        qa_issues_snapshot=artifact.qa_issues or [],
    )
    session.add(approval)
    artifact.approved = True
    artifact.status = "approved"
    session.flush()
    session.refresh(approval)
    return approval
