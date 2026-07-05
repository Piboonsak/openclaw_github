"""FastAPI auth dependencies."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.auth import JWTError, decode_token
from src.backend.db.models import User, UserCompanyAssignment
from src.backend.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            raise credentials_error
        user_uuid = uuid.UUID(user_id)
    except (JWTError, ValueError) as exc:
        raise credentials_error from exc

    user = await db.scalar(select(User).where(User.id == user_uuid))
    if user is None:
        raise credentials_error
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def require_password_finalized(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Guard: block protected endpoints until the user has changed the default password.

    Attach this to any router (or as a global dependency) that must be inaccessible
    while the user is still on a seeded/default password. `/auth/me`, `/auth/change-password`,
    `/auth/logout`, and `/auth/refresh` should NOT use this guard so the first-login
    flow can complete.
    """
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={
                "code": "MUST_CHANGE_PASSWORD",
                "message": "กรุณาเปลี่ยนรหัสผ่านก่อนใช้งานระบบ",
            },
        )
    return current_user


ADMIN_ROLES = {"admin", "sys_admin"}


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Admin or sys_admin (sys_admin is a superset of admin — TASK-1204 3-role model)."""
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_sys_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Internal/system-only surfaces (Internal Console, company create/delete —
    ac_1204_sysadmin / ac_1204_admin_deny): admin does NOT satisfy this guard.
    """
    if current_user.role != "sys_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin access required",
        )
    return current_user


async def get_user_company_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    company_ids = await db.scalars(
        select(UserCompanyAssignment.company_id).where(
            UserCompanyAssignment.user_id == user_id
        )
    )
    return [str(company_id) for company_id in company_ids]


async def ensure_company_access(
    db: AsyncSession,
    current_user: User,
    company_id: uuid.UUID | str,
) -> None:
    """Company scoping (TASK-1204 ac_1204_staff_scope): admin/sys_admin see every
    company; staff may only touch companies they are assigned to via
    `user_company_assignments`.
    """
    if current_user.role in ADMIN_ROLES:
        return
    allowed = await get_user_company_ids(db, current_user.id)
    if str(company_id) not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not assigned to this company",
        )
