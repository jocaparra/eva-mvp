"""Montagem de respostas de revisão e aprovação de artefatos."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.deal_workspace import WorkspaceArtifact
from app.repositories.workspace_artifact import _blocking_issues, get_active_approval
from app.schemas.deal_workspace import (
    ArtifactApprovalResponse,
    ArtifactReviewResponse,
    WorkspaceArtifactResponse,
)


def build_artifact_review(session: Session, artifact: WorkspaceArtifact) -> ArtifactReviewResponse:
    """Expõe audit por campo para o revisor humano."""
    active = get_active_approval(session, artifact)
    history = sorted(artifact.approvals or [], key=lambda a: a.approved_at, reverse=True)

    return ArtifactReviewResponse(
        artifact=WorkspaceArtifactResponse.model_validate(artifact),
        field_audits=artifact.field_audits or {},
        qa_issues=artifact.qa_issues or [],
        qa_passed=artifact.qa_passed,
        audit_mode=artifact.audit_mode,
        active_approval=ArtifactApprovalResponse.model_validate(active) if active else None,
        approval_history=[ArtifactApprovalResponse.model_validate(a) for a in history],
        blocking_issues=_blocking_issues(artifact),
    )
