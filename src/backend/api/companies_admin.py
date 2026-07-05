"""Real-persistence Company CRUD endpoints (W4 SIT closure — TASK-1203 minimal slice).

Replaces the visible-shell "Add/Edit Company" prototype actions with actual
DB-backed create/read/update against the `companies` table, so a created or
edited company survives refresh/re-login. This is intentionally scoped to the
single-tenant PoC/MVP deployment model used by `scripts/seed_data.py` — the
first `Tenant` row is used as the owner for any company created here.

Routes:
  GET    /v1/admin/companies       — list companies (admin/sys_admin: all; staff: assigned only)
  POST   /v1/admin/companies       — create a company (sys_admin only — TASK-1204 ac_1204_sysadmin)
  PUT    /v1/admin/companies/{id}  — update a company (admin or sys_admin)
  DELETE /v1/admin/companies/{id}  — soft-delete a company (sys_admin only)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.company_schemas import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
)
from src.backend.auth.dependencies import (
    ADMIN_ROLES,
    get_current_active_user,
    get_user_company_ids,
    require_admin,
    require_sys_admin,
)
from src.backend.db.models import Company, Tenant, User
from src.backend.db.session import get_db

router = APIRouter(prefix="/v1/admin/companies", tags=["companies-admin"])


def _company_to_response(company: Company) -> CompanyResponse:
    return CompanyResponse(
        id=str(company.id),
        name=company.name,
        tax_id=company.tax_id,
        branch_code=company.branch_code,
        address=company.address,
        business_type=company.business_type,
        is_active=company.is_active,
    )


async def _get_default_tenant(db: AsyncSession) -> Tenant:
    tenant = await db.scalar(select(Tenant).limit(1))
    if tenant is None:
        raise HTTPException(
            status_code=500,
            detail="No tenant configured — run scripts/seed_data.py before using admin Company APIs",
        )
    return tenant


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[CompanyResponse]:
    """Company scoping (ac_1204_staff_scope / ac_1204_admin_scope): admin sees
    every active company; staff only sees companies they are assigned to via
    `user_company_assignments`.
    """
    stmt = select(Company).where(Company.is_active == True).order_by(Company.name)  # noqa: E712
    if current_user.role not in ADMIN_ROLES:
        allowed_ids = await get_user_company_ids(db, current_user.id)
        if not allowed_ids:
            return []
        stmt = stmt.where(Company.id.in_([uuid.UUID(cid) for cid in allowed_ids]))
    result = await db.execute(stmt)
    return [_company_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    body: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    _sys_admin: User = Depends(require_sys_admin),
) -> CompanyResponse:
    tenant = await _get_default_tenant(db)
    company = Company(
        tenant_id=tenant.id,
        name=body.name,
        tax_id=body.tax_id,
        branch_code=body.branch_code,
        address=body.address,
        business_type=body.business_type,
        is_active=True,
    )
    db.add(company)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="เลขประจำตัวผู้เสียภาษีนี้มีอยู่ในระบบแล้ว",
        ) from exc
    await db.refresh(company)
    return _company_to_response(company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    body: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> CompanyResponse:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if body.name is not None:
        company.name = body.name
    if body.tax_id is not None:
        company.tax_id = body.tax_id
    if body.branch_code is not None:
        company.branch_code = body.branch_code
    if body.address is not None:
        company.address = body.address
    if body.business_type is not None:
        company.business_type = body.business_type
    if body.is_active is not None:
        company.is_active = body.is_active
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="เลขประจำตัวผู้เสียภาษีนี้มีอยู่ในระบบแล้ว",
        ) from exc
    await db.refresh(company)
    return _company_to_response(company)


@router.delete("/{company_id}", status_code=204, response_class=Response)
async def delete_company(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _sys_admin: User = Depends(require_sys_admin),
) -> Response:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.is_active = False
    await db.flush()
    return Response(status_code=204)
