"""JWT auth endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.backend.auth.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.backend.auth.dependencies import get_current_active_user, get_user_company_ids
from src.backend.db.models import User
from src.backend.db.session import get_db

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _build_user_payload(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "display_name": user.display_name or user.username,
        "role": user.role,
    }


async def _find_user_by_login(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(
        select(User).where((User.username == username) | (User.email == username))
    )


async def _find_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, uuid.UUID(user_id))


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await _find_user_by_login(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ข้อมูลผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    access_token = create_access_token(str(user.id), role=user.role)
    refresh_token = create_refresh_token(str(user.id))
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _build_user_payload(user),
    }


@router.get("/me")
async def me(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name or current_user.username,
        "role": current_user.role,
        "company_ids": await get_user_company_ids(db, current_user.id),
    }


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc

    user = await _find_user_by_id(db, token_payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    return {
        "access_token": create_access_token(str(user.id), role=user.role),
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
