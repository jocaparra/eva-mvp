"""artifact approval and field audits

Revision ID: 003_artifact_approval
Revises: 002_document_chunks
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_artifact_approval"
down_revision: Union[str, None] = "002_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspace_artifacts",
        sa.Column("field_audits", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "workspace_artifacts",
        sa.Column("audit_mode", sa.String(16), nullable=False, server_default="full"),
    )
    op.add_column(
        "workspace_artifacts",
        sa.Column("qa_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "workspace_artifacts",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "workspace_artifacts",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )

    op.create_table(
        "artifact_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deal_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("approver_phone", sa.String(32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("had_blocking_issues", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("field_audits_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("qa_issues_snapshot", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_artifact_approvals_artifact_id", "artifact_approvals", ["artifact_id"])
    op.create_index("ix_artifact_approvals_deal_id", "artifact_approvals", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_artifact_approvals_deal_id", table_name="artifact_approvals")
    op.drop_index("ix_artifact_approvals_artifact_id", table_name="artifact_approvals")
    op.drop_table("artifact_approvals")
    op.drop_column("workspace_artifacts", "content_hash")
    op.drop_column("workspace_artifacts", "version")
    op.drop_column("workspace_artifacts", "qa_passed")
    op.drop_column("workspace_artifacts", "audit_mode")
    op.drop_column("workspace_artifacts", "field_audits")
