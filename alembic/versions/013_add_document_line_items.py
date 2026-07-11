"""Add document_line_items table (Epic 9 line-item scan /
W5-EXPORT-LINEITEM-REALDATA-04). Stores per-document extracted invoice line
items (product/qty/unit/price) produced only when the company has
`settings.enable_stock` true; human-confirmed before export. Separate from
`journal_lines` (GL Dr/Cr postings).

Revision ID: 013
Revises: 012
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_order", sa.Integer, nullable=False),
        sa.Column("product_name", sa.Text),
        sa.Column("qty", sa.Numeric(15, 2)),
        sa.Column("unit", sa.String(20)),
        sa.Column("unit_price", sa.Numeric(15, 2)),
        sa.Column("line_amount", sa.Numeric(15, 2)),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("line_type", sa.String(30)),
        sa.Column("matched_product_code", sa.String(50)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_line_items_document", "document_line_items", ["document_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_line_items_document", table_name="document_line_items")
    op.drop_table("document_line_items")
