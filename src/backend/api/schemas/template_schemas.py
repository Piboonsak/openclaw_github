"""Pydantic request/response schemas for Template CRUD (TASK-1002)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ColumnDefSchema(BaseModel):
    source_field: str
    header_label: str
    data_type: str = "string"
    format_pattern: Optional[str] = None
    default_value: Optional[str] = None
    transform: Optional[str] = None


class TemplateCreate(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=255)
    template_type: str = Field(..., min_length=1, max_length=50)
    company_id: Optional[str] = None
    columns: list[ColumnDefSchema] = []
    file_format: str = "csv"
    encoding: str = "utf-8"
    delimiter: str = ","
    is_master: bool = False


class TemplateUpdate(BaseModel):
    template_name: Optional[str] = Field(None, min_length=1, max_length=255)
    columns: Optional[list[ColumnDefSchema]] = None
    file_format: Optional[str] = None
    encoding: Optional[str] = None
    delimiter: Optional[str] = None


class CloneRequest(BaseModel):
    company_id: str
    template_name: Optional[str] = None


class PreviewRequest(BaseModel):
    sample_data: list[dict] = Field(default=[], max_length=50)


class PreviewResponse(BaseModel):
    headers: list[str]
    rows: list[list[str]]


class TemplateResponse(BaseModel):
    id: str
    template_name: str
    template_type: str
    company_id: Optional[str]
    columns: list[ColumnDefSchema]
    file_format: str
    encoding: str
    delimiter: str
    is_master: bool
    is_active: bool
    cloned_from: Optional[str]
