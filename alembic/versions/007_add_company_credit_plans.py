"""Add company credit plans table.

Revision ID: 007
Revises: 006
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_credit_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_name", sa.String(100), nullable=False),
        sa.Column(
            "billing_model",
            sa.String(30),
            server_default="page_credit",
            nullable=False,
        ),
        sa.Column(
            "included_page_credits",
            sa.Integer,
            server_default="0",
            nullable=False,
        ),
        sa.Column("price_original_thb", sa.Numeric(12, 2)),
        sa.Column("price_effective_thb", sa.Numeric(12, 2)),
        sa.Column("cycle_start", sa.Date),
        sa.Column("cycle_end", sa.Date),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_credit_plans_company_active",
        "company_credit_plans",
        ["company_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credit_plans_company_active",
        table_name="company_credit_plans",
    )
    op.drop_table("company_credit_plans")
