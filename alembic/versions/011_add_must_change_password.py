"""Add must_change_password flag to users.

Revision ID: 011
Revises: 010
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    # Existing users (upgraded environments) already know their password —
    # do not force them through the first-login flow.
    op.execute("UPDATE users SET must_change_password = false")


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
