"""Add template_mode to export_templates (HR-17-08 / W6-C1-04). Selects the
export row shape: flat_document (1 row per document), flatten_row (1 row per
confirmed line item), grouped_summary (1 row per GL posting). Existing rows
default to flat_document to preserve current behavior.

Revision ID: 014
Revises: 013
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "export_templates",
        sa.Column(
            "template_mode",
            sa.String(20),
            nullable=False,
            server_default="flat_document",
        ),
    )


def downgrade() -> None:
    op.drop_column("export_templates", "template_mode")
