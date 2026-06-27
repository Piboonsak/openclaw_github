"""Seed initial tenant, companies, templates, and admin user.

Revision ID: 009
Revises: 008
Create Date: 2026-06-20
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from scripts.seed_data import (
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_COMPANIES_PATH,
    DEFAULT_TENANT_SLUG,
    build_master_templates,
    get_required_env,
    load_company_seeds,
    seed_database,
)
from src.backend.db.models import (
    Company,
    CompanyCreditPlan,
    ExportTemplate,
    Tenant,
    User,
    UserCompanyAssignment,
)

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        seed_database(
            session,
            companies_path=Path(
                os.getenv("COMPANIES_STORE", str(DEFAULT_COMPANIES_PATH))
            ).expanduser(),
            admin_email=os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip()
            or DEFAULT_ADMIN_EMAIL,
            admin_username=get_required_env("ADMIN_USERNAME"),
            admin_password=get_required_env("ADMIN_PASSWORD"),
        )
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        companies_path = Path(
            os.getenv("COMPANIES_STORE", str(DEFAULT_COMPANIES_PATH))
        ).expanduser()
        tax_ids = [item["tax_id"] for item in load_company_seeds(companies_path)]
        template_names = [item["template_name"] for item in build_master_templates()]
        admin_email = os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip() or DEFAULT_ADMIN_EMAIL

        tenant = session.execute(
            select(Tenant).where(Tenant.slug == DEFAULT_TENANT_SLUG)
        ).scalar_one_or_none()
        company_ids = [
            company_id
            for company_id in session.execute(
                select(Company.id).where(Company.tax_id.in_(tax_ids))
            ).scalars()
        ]
        admin_user = session.execute(
            select(User).where(User.email == admin_email)
        ).scalar_one_or_none()

        if admin_user is not None:
            session.execute(
                delete(UserCompanyAssignment).where(
                    UserCompanyAssignment.user_id == admin_user.id
                )
            )
            session.delete(admin_user)

        if company_ids:
            session.execute(
                delete(CompanyCreditPlan).where(
                    CompanyCreditPlan.company_id.in_(company_ids)
                )
            )
        session.execute(
            delete(ExportTemplate).where(
                ExportTemplate.template_name.in_(template_names),
                ExportTemplate.is_master.is_(True),
            )
        )
        session.execute(delete(Company).where(Company.tax_id.in_(tax_ids)))

        if tenant is not None:
            session.delete(tenant)

        session.commit()
    finally:
        session.close()
