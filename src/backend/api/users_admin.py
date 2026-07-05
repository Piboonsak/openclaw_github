"""Real-persistence User CRUD + admin password reset (W4 SIT closure — TASK-1204 minimal slice).

Replaces the visible-shell "Add/Edit User" / "Reset PW" prototype actions with
actual DB-backed create/read/update against `users` + `user_company_assignments`,
so a created or edited user survives refresh/re-login. There is no email/SMTP
integration yet, so a newly created user's temporary password is returned once
in the create/reset-password response body for the admin to hand over directly;
the user is forced through the existing `must_change_password` first-login flow.

Routes:
  GET  /v1/admin/users                     — list users with company assignments (admin only)
  POST /v1/admin/users                     — create a user (admin only)
  PUT  /v1/admin/users/{id}                — update role/active/company assignments (admin only)
  POST /v1/admin/users/{id}/reset-password — generate a new temp password (admin only)
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.user_schemas import (
    PasswordResetResponse,
    UserCreate,
    UserCreateResponse,
    UserResponse,
    UserUpdate,
)
from src.backend.auth.auth import hash_password
from src.backend.auth.dependencies import require_admin
from src.backend.db.models import Company, User, UserCompanyAssignment

_ASSIGNABLE_ROLES = {"staff", "admin", "sys_admin"}


def _reject_sys_admin_escalation(requested_role: str | None, requester: User) -> None:
    """Admin cannot assign sys_admin (EPIC-12 TASK-1204 role table) — only a
    sys_admin can grant sys_admin. Rejected explicitly (403), not silently
    downgraded, since a deliberate escalation attempt should not look like a
    quiet no-op success.
    """
    if requested_role == "sys_admin" and requester.role != "sys_admin":
        raise HTTPException(
            status_code=403,
            detail="Only a sys_admin can assign the sys_admin role",
        )
from src.backend.db.session import get_db

router = APIRouter(prefix="/v1/admin/users", tags=["users-admin"])


def _generate_temp_password() -> str:
    # Guarantees a letter + digit so it passes the same policy enforced on
    # self-serve change-password (see auth/router.py MIN_PASSWORD_LENGTH check).
    return "Lf" + secrets.token_hex(5)


async def _company_ids_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await db.scalars(
        select(UserCompanyAssignment.company_id).where(
            UserCompanyAssignment.user_id == user_id
        )
    )
    return [str(company_id) for company_id in rows]


def _user_to_response(user: User, company_ids: list[str]) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=bool(user.must_change_password),
        last_login=user.last_login.isoformat() if user.last_login else None,
        company_ids=company_ids,
    )


async def _validate_company_ids(db: AsyncSession, company_ids: list[str]) -> list[uuid.UUID]:
    parsed = [uuid.UUID(cid) for cid in company_ids]
    if not parsed:
        return []
    result = await db.execute(select(Company.id).where(Company.id.in_(parsed)))
    found = {row for row in result.scalars().all()}
    missing = [str(cid) for cid in parsed if cid not in found]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Company id(s) not found: {', '.join(missing)}",
        )
    return parsed


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[UserResponse]:
    result = await db.execute(select(User).order_by(User.username))
    users = result.scalars().all()
    responses = []
    for user in users:
        company_ids = await _company_ids_for_user(db, user.id)
        responses.append(_user_to_response(user, company_ids))
    return responses


@router.post("", response_model=UserCreateResponse, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserCreateResponse:
    normalized_role = body.normalized_role()
    _reject_sys_admin_escalation(normalized_role, current_user)
    company_uuids = await _validate_company_ids(db, body.company_ids)
    temp_password = _generate_temp_password()
    user = User(
        tenant_id=current_user.tenant_id,
        email=body.email,
        username=body.username,
        password_hash=hash_password(temp_password),
        display_name=body.display_name,
        role=normalized_role,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="อีเมลหรือชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว",
        ) from exc

    for company_id in company_uuids:
        db.add(UserCompanyAssignment(user_id=user.id, company_id=company_id))
    await db.flush()
    await db.refresh(user)

    response = _user_to_response(user, [str(cid) for cid in company_uuids])
    return UserCreateResponse(**response.model_dump(), temp_password=temp_password)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        _reject_sys_admin_escalation(body.role, current_user)
        user.role = body.role if body.role in _ASSIGNABLE_ROLES else user.role
    if body.is_active is not None:
        user.is_active = body.is_active

    if body.company_ids is not None:
        company_uuids = await _validate_company_ids(db, body.company_ids)
        await db.execute(
            delete(UserCompanyAssignment).where(UserCompanyAssignment.user_id == user.id)
        )
        for company_id in company_uuids:
            db.add(UserCompanyAssignment(user_id=user.id, company_id=company_id))

    await db.flush()
    await db.refresh(user)
    company_ids = await _company_ids_for_user(db, user.id)
    return _user_to_response(user, company_ids)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_user_password(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> PasswordResetResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp_password = _generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True
    await db.flush()
    return PasswordResetResponse(id=str(user.id), temp_password=temp_password)
