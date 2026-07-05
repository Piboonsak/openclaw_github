"""Pydantic request/response schemas for admin Company CRUD (W4 SIT closure)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _normalize_tax_id(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    tax_id: str = Field(..., min_length=1, max_length=32)
    branch_code: str = Field("00000", max_length=32)
    address: Optional[str] = None
    business_type: Optional[str] = Field(None, max_length=50)

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, value: str) -> str:
        normalized = _normalize_tax_id(value)
        if len(normalized) != 13:
            raise ValueError("tax_id must contain exactly 13 digits")
        return normalized

    @field_validator("branch_code")
    @classmethod
    def validate_branch_code(cls, value: str) -> str:
        normalized = _normalize_tax_id(value) or "00000"
        return normalized.zfill(5)[:5]


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, min_length=1, max_length=32)
    branch_code: Optional[str] = Field(None, max_length=32)
    address: Optional[str] = None
    business_type: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = _normalize_tax_id(value)
        if len(normalized) != 13:
            raise ValueError("tax_id must contain exactly 13 digits")
        return normalized

    @field_validator("branch_code")
    @classmethod
    def validate_branch_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = _normalize_tax_id(value) or "00000"
        return normalized.zfill(5)[:5]


class CompanyResponse(BaseModel):
    id: str
    name: str
    tax_id: str
    branch_code: str
    address: Optional[str] = None
    business_type: Optional[str] = None
    is_active: bool
