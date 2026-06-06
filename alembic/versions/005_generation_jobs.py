"""generation jobs table

Revision ID: 005_generation_jobs
Revises: 004_conversations
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_generation_jobs"
down_revision: Union[str, None] = "004_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_phone", sa.String(32), nullable=False),
        sa.Column("company_name", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("ppt_path", sa.String(1024), nullable=True),
        sa.Column("ppt_filename", sa.String(512), nullable=True),
        sa.Column("qa_passed", sa.Boolean(), nullable=True),
        sa.Column("qa_issues", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "deal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deal_workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_generation_jobs_owner_phone", "generation_jobs", ["owner_phone"])


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_owner_phone", table_name="generation_jobs")
    op.drop_table("generation_jobs")
