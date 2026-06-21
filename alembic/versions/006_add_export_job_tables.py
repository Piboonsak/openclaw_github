"""Add export job tables.

Revision ID: 006
Revises: 005
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("export_templates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("total_documents", sa.Integer, server_default="0", nullable=False),
        sa.Column("file_format", sa.String(10), server_default="csv", nullable=False),
        sa.Column("encoding", sa.String(20), server_default="utf-8", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_export_jobs_company", "export_jobs", ["company_id"])

    op.create_table(
        "export_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "export_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("export_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("download_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "export_job_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "export_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("export_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "export_job_id",
            "document_id",
            name="uq_export_job_document",
        ),
    )


def downgrade() -> None:
    op.drop_table("export_job_documents")
    op.drop_table("export_files")
    op.drop_index("ix_export_jobs_company", table_name="export_jobs")
    op.drop_table("export_jobs")
