"""Pydantic request/response schemas for company Chart of Accounts (TASK-1203)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChartOfAccountEntry(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    type: str = Field("expense", max_length=50)
    confidence: Optional[int] = None


class ChartOfAccountResponse(BaseModel):
    id: str
    account_code: str
    account_name: str
    account_type: Optional[str] = None
    is_active: bool


class CoaImportError(BaseModel):
    row_number: int
    message: str


class CoaImportResult(BaseModel):
    imported: int
    updated: int
    errors: list[CoaImportError] = Field(default_factory=list)


class CoaPdfPreviewResponse(BaseModel):
    accounts: list[ChartOfAccountEntry]
    company_name_detected: Optional[str] = None
    source_pages_extracted: bool = True


class CoaConfirmRequest(BaseModel):
    accounts: list[ChartOfAccountEntry]
