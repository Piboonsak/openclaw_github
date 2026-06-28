"""Add BL-001 vendor/customer master and mapping cache tables.

Revision ID: 010
Revises: 009
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


match_type_enum = ENUM(
    "exact",
    "fuzzy",
    "llm",
    "manual",
    name="match_type",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE match_type AS ENUM ('exact', 'fuzzy', 'llm', 'manual');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "vendor_master",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor_code", sa.String(20), nullable=False),
        sa.Column("vendor_name", sa.Text, nullable=False),
        sa.Column("gl_code", sa.String(10)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "vendor_code", name="uq_vendor_company_code"),
    )

    op.create_table(
        "customer_master",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_code", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.Text, nullable=False),
        sa.Column("ar_flag", sa.SmallInteger, server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id",
            "customer_code",
            name="uq_customer_company_code",
        ),
    )

    op.create_table(
        "account_mapping_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ocr_name", sa.Text, nullable=False),
        sa.Column("matched_code", sa.String(20), nullable=False),
        sa.Column("match_type", match_type_enum, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("confirmed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_mapping_company_ocr_name",
        "account_mapping_cache",
        ["company_id", "ocr_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mapping_company_ocr_name",
        table_name="account_mapping_cache",
    )
    op.drop_table("account_mapping_cache")
    op.drop_table("customer_master")
    op.drop_table("vendor_master")
    match_type_enum.drop(op.get_bind(), checkfirst=True)
