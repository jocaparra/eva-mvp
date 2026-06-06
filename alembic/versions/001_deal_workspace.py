"""deal workspace tables

Revision ID: 001_deal_workspace
Revises:
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_deal_workspace"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(512), nullable=False),
        sa.Column("owner_phone", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("retrieved_context", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deal_workspaces_owner_phone", "deal_workspaces", ["owner_phone"])

    op.create_table(
        "workspace_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deal_workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file", sa.String(512), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_documents_deal_id", "workspace_documents", ["deal_id"])

    op.create_table(
        "workspace_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deal_workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("qa_issues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_artifacts_deal_id", "workspace_artifacts", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_artifacts_deal_id", table_name="workspace_artifacts")
    op.drop_table("workspace_artifacts")
    op.drop_index("ix_workspace_documents_deal_id", table_name="workspace_documents")
    op.drop_table("workspace_documents")
    op.drop_index("ix_deal_workspaces_owner_phone", table_name="deal_workspaces")
    op.drop_table("deal_workspaces")
