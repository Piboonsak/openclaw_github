"""Pydantic request/response schemas for admin User CRUD (W4 SIT closure)."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_ALLOWED_ROLES = {"staff", "admin", "sys_admin"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    username: str = Field(..., min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=255)
    role: str = Field("staff", description="staff, admin, or sys_admin")
    company_ids: list[str] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("email must be a valid email address")
        return value

    def normalized_role(self) -> str:
        return self.role if self.role in _ALLOWED_ROLES else "staff"


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    company_ids: Optional[list[str]] = None


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool
    last_login: Optional[str] = None
    company_ids: list[str] = Field(default_factory=list)


class UserCreateResponse(UserResponse):
    temp_password: str


class PasswordResetResponse(BaseModel):
    id: str
    temp_password: str
