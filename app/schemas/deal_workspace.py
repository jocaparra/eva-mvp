"""Schemas Pydantic para o deal workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CitationSchema(BaseModel):
    source_file: str
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    quote: Optional[str] = None


class CreateDealRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=512)


class WorkspaceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_file: str
    storage_path: Optional[str] = None
    mime_type: Optional[str] = None
    status: str
    created_at: datetime


class WorkspaceArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_type: str
    status: str
    file_path: Optional[str] = None
    citations: list[Any] = Field(default_factory=list)
    qa_issues: list[Any] = Field(default_factory=list)
    field_audits: dict[str, Any] = Field(default_factory=dict)
    audit_mode: str = "full"
    qa_passed: bool = False
    version: int = 1
    content_hash: Optional[str] = None
    approved: bool = False
    created_at: datetime
    updated_at: datetime


class ArtifactApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    deal_id: UUID
    artifact_version: int
    content_hash: str
    approver_phone: str
    approved_at: datetime
    had_blocking_issues: bool
    override: bool
    override_reason: Optional[str] = None
    field_audits_snapshot: dict[str, Any] = Field(default_factory=dict)
    qa_issues_snapshot: list[Any] = Field(default_factory=list)


class ArtifactReviewResponse(BaseModel):
    """Payload de revisão humana — audit por campo, não só pass/fail."""

    artifact: WorkspaceArtifactResponse
    field_audits: dict[str, Any] = Field(default_factory=dict)
    qa_issues: list[Any] = Field(default_factory=list)
    qa_passed: bool = False
    audit_mode: str = "full"
    active_approval: Optional[ArtifactApprovalResponse] = None
    approval_history: list[ArtifactApprovalResponse] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)


class ApproveArtifactRequest(BaseModel):
    override_reason: Optional[str] = Field(
        default=None,
        description="Obrigatório quando há issues bloqueantes (UNCITED/DIVERGENT ou qa_passed=false).",
    )


class ApproveArtifactResponse(BaseModel):
    approval: ArtifactApprovalResponse
    artifact: WorkspaceArtifactResponse


class DealWorkspaceResponse(BaseModel):
    """Resposta alinhada ao DealState persistido."""

    deal_id: UUID
    company_name: str
    owner_phone: str
    status: str
    documents: list[WorkspaceDocumentResponse] = Field(default_factory=list)
    retrieved_context: list[CitationSchema] = Field(default_factory=list)
    artifacts: list[WorkspaceArtifactResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
