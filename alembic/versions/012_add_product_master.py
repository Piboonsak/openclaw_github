"""Add product/price-list master (Pack C: company-level product master
foundation for line-item/product matching quality — separate from
`enable_stock`, which only toggles line-item OCR).

Revision ID: 012
Revises: 011
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_master",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_code", sa.String(50), nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("unit", sa.String(20)),
        sa.Column("unit_cost", sa.Float),
        sa.Column("category", sa.String(100)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id", "product_code", name="uq_product_company_code"
        ),
    )


def downgrade() -> None:
    op.drop_table("product_master")
