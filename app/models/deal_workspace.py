"""Modelos SQLAlchemy do deal workspace (fonte de verdade persistente)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class DealWorkspace(Base):
    """Deal agregando empresa, documentos do data room e artefatos gerados."""

    __tablename__ = "deal_workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_name: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    retrieved_context: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    documents: Mapped[list["WorkspaceDocument"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["WorkspaceArtifact"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )


class WorkspaceDocument(Base):
    """Metadados de um documento enviado ao data room do deal."""

    __tablename__ = "workspace_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_workspaces.id", ondelete="CASCADE"), index=True
    )
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    deal: Mapped["DealWorkspace"] = relationship(back_populates="documents")


class WorkspaceArtifact(Base):
    """Artefato gerado (CIM, memo, modelo) com citações e gate de aprovação."""

    __tablename__ = "workspace_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_workspaces.id", ondelete="CASCADE"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    citations: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list)
    qa_issues: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list)
    field_audits: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    audit_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    qa_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    deal: Mapped["DealWorkspace"] = relationship(back_populates="artifacts")
    approvals: Mapped[list["ArtifactApproval"]] = relationship(
        back_populates="artifact", cascade="all, delete-orphan"
    )


class ArtifactApproval(Base):
    """Registro imutável de aprovação humana sobre uma versão do artefato."""

    __tablename__ = "artifact_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace_artifacts.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_workspaces.id", ondelete="CASCADE"), index=True
    )
    artifact_version: Mapped[int] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approver_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    had_blocking_issues: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    field_audits_snapshot: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    qa_issues_snapshot: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )

    artifact: Mapped["WorkspaceArtifact"] = relationship(back_populates="approvals")
