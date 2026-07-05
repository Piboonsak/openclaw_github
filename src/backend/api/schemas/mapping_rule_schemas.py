"""Pydantic request/response schemas for company Mapping Rules (TASK-1203
company settings document-ingestion workflow)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MappingRuleEntry(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    document_type: Optional[str] = Field(None, max_length=50)
    recommended_debit_code: Optional[str] = Field(None, max_length=50)
    recommended_account_name: Optional[str] = Field(None, max_length=150)


class MappingRuleResponse(BaseModel):
    id: str
    vendor_name: str
    document_type: Optional[str] = None
    recommended_debit_code: Optional[str] = None
    recommended_account_name: Optional[str] = None
    confirmed_count: int
    last_confirmed_at: str


class MappingRuleImportError(BaseModel):
    row_number: int
    message: str


class MappingRuleImportResult(BaseModel):
    imported: int
    updated: int
    errors: list[MappingRuleImportError] = Field(default_factory=list)


class MappingRulesDocxPreviewResponse(BaseModel):
    rules: list[MappingRuleEntry]
    source_text_preview: str


class MappingRulesConfirmRequest(BaseModel):
    rules: list[MappingRuleEntry]
