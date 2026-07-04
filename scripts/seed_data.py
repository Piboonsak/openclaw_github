"""Seed core Phase II data into PostgreSQL.

Seeds:
- default tenant
- companies from data/companies.json
- customer-facing page-credit plans
- master export templates
- first admin user + company assignments
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.db.base import get_sync_session_factory
from src.backend.db.models import (
    Company,
    CompanyCreditPlan,
    ExportTemplate,
    Tenant,
    User,
    UserCompanyAssignment,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPANIES_PATH = REPO_ROOT / "data" / "companies.json"
DEFAULT_TENANT_NAME = "Default Tenant"
DEFAULT_TENANT_SLUG = "default-tenant"
DEFAULT_ADMIN_EMAIL = "admin@ledgerflow.local"
DEFAULT_ADMIN_DISPLAY_NAME = "System Admin"
DEFAULT_PLAN_NAME = "Pro Premium"
DEFAULT_INCLUDED_PAGE_CREDITS = 20_000
DEFAULT_PRICE_ORIGINAL_THB = 45_000.00
DEFAULT_PRICE_EFFECTIVE_THB = 25_500.00

def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_tax_id(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def load_company_seeds(path: Path = DEFAULT_COMPANIES_PATH) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    companies: list[dict[str, Any]] = []
    for item in raw:
        tax_id = normalize_tax_id(item.get("taxId"))
        if not tax_id:
            continue
        companies.append(
            {
                "name": item.get("name", "").strip() or f"Company {tax_id}",
                "tax_id": tax_id,
                "branch_code": str(item.get("branch") or "00000").strip() or "00000",
                "address": str(item.get("address") or "").strip() or None,
                "short_name": None,
            }
        )
    return companies


def build_master_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_name": "Express GL",
            "template_type": "express_gl",
            "file_format": "csv",
            "encoding": "utf-8",
            "delimiter": ",",
            "columns": [
                {
                    "source_field": "voucher_no",
                    "header_label": "Voucher_No",
                    "data_type": "string",
                },
                {
                    "source_field": "voucher_date",
                    "header_label": "Date",
                    "data_type": "date",
                    "format_pattern": "yyyy-mm-dd",
                },
                {
                    "source_field": "book_code",
                    "header_label": "Book_Code",
                    "data_type": "string",
                },
                {
                    "source_field": "account_code",
                    "header_label": "Account_Code",
                    "data_type": "string",
                    "transform": "pad_left:5:0",
                },
                {
                    "source_field": "debit",
                    "header_label": "Debit_Amount",
                    "data_type": "number",
                    "format_pattern": "#,##0.00",
                },
                {
                    "source_field": "credit",
                    "header_label": "Credit_Amount",
                    "data_type": "number",
                    "format_pattern": "#,##0.00",
                },
                {
                    "source_field": "description",
                    "header_label": "Line_Description",
                    "data_type": "string",
                },
                {
                    "source_field": "buyer_tax_id",
                    "header_label": "Target_Company_TaxID",
                    "data_type": "string",
                    "transform": "strip_dash",
                },
            ],
        },
        {
            "template_name": "Purchase Tax",
            "template_type": "purchase_tax",
            "file_format": "xlsx",
            "encoding": "utf-8",
            "delimiter": ",",
            "columns": [
                {
                    "source_field": "row_number",
                    "header_label": "ลำดับ",
                    "data_type": "number",
                },
                {
                    "source_field": "invoice_number",
                    "header_label": "เลขที่ใบกำกับภาษี",
                    "data_type": "string",
                },
                {
                    "source_field": "invoice_date",
                    "header_label": "วันที่",
                    "data_type": "date",
                    "transform": "thai_date",
                },
                {
                    "source_field": "seller_name",
                    "header_label": "ชื่อผู้ขาย",
                    "data_type": "string",
                },
                {
                    "source_field": "seller_tax_id",
                    "header_label": "เลขประจำตัวผู้เสียภาษี",
                    "data_type": "string",
                },
                {
                    "source_field": "seller_branch_code",
                    "header_label": "สถานประกอบการ",
                    "data_type": "string",
                    "transform": "pad_left:5:0",
                },
                {
                    "source_field": "net_amount",
                    "header_label": "มูลค่าสินค้า/บริการ",
                    "data_type": "number",
                    "format_pattern": "#,##0.00",
                },
                {
                    "source_field": "vat_amount",
                    "header_label": "ภาษีมูลค่าเพิ่ม",
                    "data_type": "number",
                    "format_pattern": "#,##0.00",
                },
                {
                    "source_field": "total_amount",
                    "header_label": "มูลค่ารวมภาษี",
                    "data_type": "number",
                    "format_pattern": "#,##0.00",
                },
                {
                    "source_field": "vat_rate",
                    "header_label": "VAT Rate",
                    "data_type": "number",
                },
                {
                    "source_field": "document_type",
                    "header_label": "ประเภทเอกสาร",
                    "data_type": "string",
                },
                {
                    "source_field": "description",
                    "header_label": "หมายเหตุ",
                    "data_type": "string",
                },
            ],
        },
    ]


def build_credit_plan_seed(plan_name: str = DEFAULT_PLAN_NAME) -> dict[str, Any]:
    return {
        "plan_name": plan_name,
        "billing_model": "page_credit",
        "included_page_credits": DEFAULT_INCLUDED_PAGE_CREDITS,
        "price_original_thb": DEFAULT_PRICE_ORIGINAL_THB,
        "price_effective_thb": DEFAULT_PRICE_EFFECTIVE_THB,
        "is_active": True,
    }


def _get_or_create_tenant(session: Session, name: str, slug: str) -> tuple[Tenant, bool]:
    tenant = session.execute(
        select(Tenant).where(Tenant.slug == slug)
    ).scalar_one_or_none()
    created = tenant is None
    if tenant is None:
        tenant = Tenant(name=name, slug=slug, settings={})
        session.add(tenant)
        session.flush()
    else:
        tenant.name = name
    return tenant, created


def _get_or_create_company(
    session: Session,
    tenant: Tenant,
    payload: dict[str, Any],
) -> tuple[Company, bool]:
    company = session.execute(
        select(Company).where(Company.tax_id == payload["tax_id"])
    ).scalar_one_or_none()
    created = company is None
    if company is None:
        company = Company(
            tenant_id=tenant.id,
            name=payload["name"],
            short_name=payload.get("short_name"),
            tax_id=payload["tax_id"],
            branch_code=payload.get("branch_code") or "00000",
            address=payload.get("address"),
            settings={},
        )
        session.add(company)
        session.flush()
    else:
        company.tenant_id = tenant.id
        company.name = payload["name"]
        company.short_name = payload.get("short_name")
        company.branch_code = payload.get("branch_code") or "00000"
        company.address = payload.get("address")
    return company, created


def _get_or_create_credit_plan(
    session: Session,
    company: Company,
    payload: dict[str, Any],
) -> tuple[CompanyCreditPlan, bool]:
    plan = session.execute(
        select(CompanyCreditPlan).where(
            CompanyCreditPlan.company_id == company.id,
            CompanyCreditPlan.plan_name == payload["plan_name"],
        )
    ).scalar_one_or_none()
    created = plan is None
    if plan is None:
        plan = CompanyCreditPlan(company_id=company.id, **payload)
        session.add(plan)
    else:
        for key, value in payload.items():
            setattr(plan, key, value)
    return plan, created


def _get_or_create_template(
    session: Session,
    payload: dict[str, Any],
) -> tuple[ExportTemplate, bool]:
    template = session.execute(
        select(ExportTemplate).where(
            ExportTemplate.template_name == payload["template_name"],
            ExportTemplate.is_master.is_(True),
        )
    ).scalar_one_or_none()
    created = template is None
    if template is None:
        template = ExportTemplate(
            company_id=None,
            template_name=payload["template_name"],
            template_type=payload["template_type"],
            columns=payload["columns"],
            static_values={},
            header_mappings={},
            file_format=payload["file_format"],
            delimiter=payload["delimiter"],
            encoding=payload["encoding"],
            is_master=True,
            is_active=True,
        )
        session.add(template)
    else:
        template.template_type = payload["template_type"]
        template.columns = payload["columns"]
        template.file_format = payload["file_format"]
        template.delimiter = payload["delimiter"]
        template.encoding = payload["encoding"]
        template.is_master = True
        template.is_active = True
    return template, created


def _get_or_create_admin_user(
    session: Session,
    tenant: Tenant,
    *,
    email: str,
    username: str,
    display_name: str,
    password: str,
) -> tuple[User, bool]:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    created = user is None
    if user is None:
        user = User(
            tenant_id=tenant.id,
            email=email,
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role="admin",
            is_active=True,
            must_change_password=True,
        )
        session.add(user)
        session.flush()
    else:
        user.tenant_id = tenant.id
        user.username = username
        user.display_name = display_name
        user.role = "admin"
        user.is_active = True
        password_matches_default = verify_password(password, user.password_hash)
        if user.must_change_password and not password_matches_default:
            # Still on first-login and hash drifted from env default: re-seed.
            user.password_hash = hash_password(password)
        elif password_matches_default and not user.must_change_password:
            # Admin is still on the seeded default password (e.g. after
            # migration backfill or fresh env): force the first-login flow.
            user.must_change_password = True
    return user, created


def _ensure_company_assignment(
    session: Session,
    user: User,
    company: Company,
) -> bool:
    assignment = session.execute(
        select(UserCompanyAssignment).where(
            UserCompanyAssignment.user_id == user.id,
            UserCompanyAssignment.company_id == company.id,
        )
    ).scalar_one_or_none()
    if assignment is not None:
        assignment.role_override = "admin"
        return False

    session.add(
        UserCompanyAssignment(
            user_id=user.id,
            company_id=company.id,
            role_override="admin",
        )
    )
    return True


def seed_database(
    session: Session,
    *,
    companies_path: Path = DEFAULT_COMPANIES_PATH,
    tenant_name: str = DEFAULT_TENANT_NAME,
    tenant_slug: str = DEFAULT_TENANT_SLUG,
    admin_email: str = DEFAULT_ADMIN_EMAIL,
    admin_username: str,
    admin_display_name: str = DEFAULT_ADMIN_DISPLAY_NAME,
    admin_password: str,
) -> dict[str, int]:
    stats = {
        "tenants_created": 0,
        "companies_created": 0,
        "credit_plans_created": 0,
        "templates_created": 0,
        "users_created": 0,
        "assignments_created": 0,
    }

    tenant, tenant_created = _get_or_create_tenant(session, tenant_name, tenant_slug)
    stats["tenants_created"] += int(tenant_created)

    credit_plan_payload = build_credit_plan_seed()
    companies: list[Company] = []
    for company_seed in load_company_seeds(companies_path):
        company, company_created = _get_or_create_company(session, tenant, company_seed)
        stats["companies_created"] += int(company_created)
        _, plan_created = _get_or_create_credit_plan(
            session, company, credit_plan_payload
        )
        stats["credit_plans_created"] += int(plan_created)
        companies.append(company)

    for template_seed in build_master_templates():
        _, template_created = _get_or_create_template(session, template_seed)
        stats["templates_created"] += int(template_created)

    admin_user, user_created = _get_or_create_admin_user(
        session,
        tenant,
        email=admin_email,
        username=admin_username,
        display_name=admin_display_name,
        password=admin_password,
    )
    stats["users_created"] += int(user_created)

    for company in companies:
        stats["assignments_created"] += int(
            _ensure_company_assignment(session, admin_user, company)
        )

    return stats


def run_seed() -> dict[str, int]:
    session_factory = get_sync_session_factory()
    admin_password = get_required_env("ADMIN_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL).strip() or DEFAULT_ADMIN_EMAIL
    admin_username = get_required_env("ADMIN_USERNAME")
    companies_path = Path(
        os.getenv("COMPANIES_STORE", str(DEFAULT_COMPANIES_PATH))
    ).expanduser()

    with session_factory() as session:
        stats = seed_database(
            session,
            companies_path=companies_path,
            admin_email=admin_email,
            admin_username=admin_username,
            admin_password=admin_password,
        )
        session.commit()
        return stats


if __name__ == "__main__":
    result = run_seed()
    print(json.dumps(result, indent=2))
