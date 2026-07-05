"""Pydantic request/response schemas for the routine document workflow
(W4 SIT closure Pack B — Upload -> Process -> Review Scan -> Review Mapping,
`TASK-W4-SIT-E2E-CLAUDE-IMPLEMENT-ROUTINE-OPS-05`)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: Optional[str] = None
    status: str
    scan_status: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None
    taxid_match: Optional[bool] = None
    net_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    wht_amount: Optional[float] = None
    total_amount: Optional[float] = None
    overall_confidence: Optional[float] = None
    processing_error: Optional[str] = None
    created_at: str


class DocumentUploadResult(BaseModel):
    documents: list[DocumentResponse]


class JournalLineResponse(BaseModel):
    id: str
    line_order: int
    account_code: str
    account_name: Optional[str] = None
    is_debit: bool
    amount: float
    description: Optional[str] = None


class JournalVoucherResponse(BaseModel):
    id: str
    voucher_no: Optional[str] = None
    voucher_date: str
    book_code: Optional[str] = None
    rule_id: Optional[str] = None
    status: str
    is_balanced: Optional[bool] = None
    total_debit: Optional[float] = None
    total_credit: Optional[float] = None
    flags: list[str] = Field(default_factory=list)
    lines: list[JournalLineResponse] = Field(default_factory=list)


class DocumentDetailResponse(DocumentResponse):
    extraction_fields: dict = Field(default_factory=dict)
    confidence_per_field: dict = Field(default_factory=dict)
    critical_flags: dict = Field(default_factory=dict)
    voucher: Optional[JournalVoucherResponse] = None


class ApproveAllRequest(BaseModel):
    document_ids: Optional[list[str]] = None


class ApproveAllResult(BaseModel):
    approved: int


class FlagRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=50)
    comment: Optional[str] = None


class JournalLineUpdateRequest(BaseModel):
    account_code: str = Field(..., min_length=1, max_length=50)
    account_name: Optional[str] = Field(None, max_length=150)
    amount: Optional[float] = None


class DocumentFieldsUpdateRequest(BaseModel):
    invoice_number: Optional[str] = Field(None, max_length=100)
    invoice_date: Optional[str] = None
    seller_name: Optional[str] = Field(None, max_length=255)
    buyer_tax_id: Optional[str] = Field(None, max_length=13)
    net_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    wht_amount: Optional[float] = None
    total_amount: Optional[float] = None
