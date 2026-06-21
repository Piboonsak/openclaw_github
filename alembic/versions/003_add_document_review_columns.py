"""Add document review columns and batch foreign key.

Revision ID: 003
Revises: 002
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("scan_status", sa.String(20), server_default="pending", nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column(
            "scan_reviewed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("scan_reviewed_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("processing_progress", JSONB, nullable=True),
    )

    op.execute(
        """
        UPDATE documents
        SET batch_id = NULL
        WHERE batch_id IS NOT NULL
          AND batch_id NOT IN (SELECT id FROM document_batches)
        """
    )
    op.create_foreign_key(
        "fk_documents_batch_id_document_batches",
        "documents",
        "document_batches",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_documents_batch_id_document_batches",
        "documents",
        type_="foreignkey",
    )
    op.drop_column("documents", "processing_progress")
    op.drop_column("documents", "scan_reviewed_at")
    op.drop_column("documents", "scan_reviewed_by")
    op.drop_column("documents", "scan_status")
