"""Pydantic response schemas for company Product/Price-List Master (Pack C)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProductImportError(BaseModel):
    row_number: int
    message: str


class ProductImportResult(BaseModel):
    imported: int
    updated: int
    errors: list[ProductImportError] = Field(default_factory=list)


class ProductListItem(BaseModel):
    code: str
    name: str
    unit: Optional[str] = None
    unit_cost: Optional[float] = None
    category: Optional[str] = None
    is_active: bool


class ProductListPage(BaseModel):
    items: list[ProductListItem]
    total: int
    page: int
    page_size: int
    search: Optional[str] = None
