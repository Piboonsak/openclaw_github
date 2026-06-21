"""Add page credit usage ledger table.

Revision ID: 008
Revises: 007
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_credit_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_batches.id", ondelete="SET NULL"),
        ),
        sa.Column("document_type", sa.String(50)),
        sa.Column("page_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("credits_used", sa.Integer, server_default="1", nullable=False),
        sa.Column("usage_reason", sa.String(30), server_default="scan", nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_page_credit_company_created",
        "page_credit_usage",
        ["company_id", "created_at"],
    )
    op.create_index(
        "ix_page_credit_document",
        "page_credit_usage",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_page_credit_document", table_name="page_credit_usage")
    op.drop_index(
        "ix_page_credit_company_created",
        table_name="page_credit_usage",
    )
    op.drop_table("page_credit_usage")
