"""JWT auth endpoints."""

from __future__ import annotations

import re
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
    hash_password,
    verify_password,
)
from src.backend.auth.dependencies import get_current_active_user, get_user_company_ids
from src.backend.db.models import User
from src.backend.db.session import get_db

router = APIRouter(prefix="/v1/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8
_PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
_PASSWORD_DIGIT_RE = re.compile(r"\d")


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


def _validate_new_password(new_password: str, *, old_password: str) -> None:
    """Enforce SIT/MVP password policy. Raises HTTPException(400) on failure."""
    if new_password == old_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม",
        )
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"รหัสผ่านใหม่ต้องมีอย่างน้อย {MIN_PASSWORD_LENGTH} ตัวอักษร",
        )
    if not _PASSWORD_LETTER_RE.search(new_password) or not _PASSWORD_DIGIT_RE.search(
        new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="รหัสผ่านใหม่ต้องประกอบด้วยตัวอักษรและตัวเลขอย่างน้อยอย่างละหนึ่งตัว",
        )


def _build_user_payload(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "display_name": user.display_name or user.username,
        "role": user.role,
        "must_change_password": bool(user.must_change_password),
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
        "must_change_password": bool(current_user.must_change_password),
        "company_ids": await get_user_company_ids(db, current_user.id),
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="รหัสผ่านปัจจุบันไม่ถูกต้อง",
        )
    _validate_new_password(payload.new_password, old_password=payload.old_password)

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    await db.flush()

    return {
        "status": "ok",
        "user": _build_user_payload(current_user),
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
