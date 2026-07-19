"""Product/price-list master import service (Pack C product-master
foundation). Mirrors `master_data_import.py`'s vendor/customer pattern.

The customer's real file (`private_data/poc/Comp_1/picelist/TMD.csv`) is,
like the AP/AR files, an Express Accounting raw report export — here an
"inventory balance by category" report, not a plain price-list CSV. Verified
directly against the real file: report banner rows, a two-row column header,
`หมวด : <name>` category-section-header rows, then product rows. A product
row is reliably identified by column index 3 (product code) being non-empty
and not the literal header label "รหัสสินค้า" — every other row shape
(banner/header/category/subtotal) leaves that column empty. Confirmed 1090
unique product codes with zero collisions across the real file using this
rule.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.models import Company, ProductMaster
from src.backend.services.schema_analyzer import detect_encoding

_HEADER_LABEL = "รหัสสินค้า"
_CATEGORY_MARKER = "หมวด :"


@dataclass
class ProductImportErrorDetail:
    row_number: int
    message: str


@dataclass
class ProductImportSummary:
    imported: int
    updated: int
    errors: list[ProductImportErrorDetail] = field(default_factory=list)
    encoding_detected: str = "utf-8"


@dataclass
class ProductListItem:
    code: str
    name: str
    unit: str | None
    unit_cost: float | None
    category: str | None
    is_active: bool


@dataclass
class ProductListPage:
    items: list[ProductListItem]
    total: int
    page: int
    page_size: int
    search: str | None


def _parse_float(value: str | None) -> float | None:
    normalized = str(value or "").strip().replace(",", "")
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _decode_csv_bytes(content: bytes) -> tuple[str, str]:
    detected = detect_encoding(content)
    codec = "cp874" if detected == "tis-620" else "utf-8-sig"
    return content.decode(codec, errors="replace"), detected


def _parse_express_inventory_rows(rows: list[list[str]]) -> list[dict[str, str | None]]:
    parsed: list[dict[str, str | None]] = []
    current_category: str | None = None
    for row in rows:
        if len(row) > 2 and row[1].strip() == _CATEGORY_MARKER:
            current_category = row[2].strip() or None
            continue
        if len(row) <= 4 or not row[3].strip() or row[3].strip() == _HEADER_LABEL:
            continue
        code = row[3].strip()
        name = row[4].strip() if len(row) > 4 else ""
        unit = row[13].strip() if len(row) > 13 and row[13].strip() else None
        unit_cost = _parse_float(row[14]) if len(row) > 14 else None
        parsed.append(
            {
                "product_code": code,
                "product_name": name,
                "unit": unit,
                "unit_cost": unit_cost,
                "category": current_category,
            }
        )
    return parsed


def _parse_clean_csv_rows(decoded: str) -> list[dict[str, str | None]]:
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required")
    rows: list[dict[str, str | None]] = []
    for row in reader:
        rows.append(
            {
                "product_code": str(row.get("product_code", "")).strip(),
                "product_name": str(row.get("product_name", "")).strip(),
                "unit": (str(row.get("unit", "")).strip() or None),
                "unit_cost": _parse_float(row.get("unit_cost")),
                "category": (str(row.get("category", "")).strip() or None),
            }
        )
    return rows


def parse_product_master_csv(content: bytes) -> tuple[list[dict[str, str | None]], str]:
    """Detect the Express inventory-report shape (real file) vs. a plain
    header CSV (product_code,product_name,unit,unit_cost,category) and parse
    accordingly.
    """
    decoded, detected = _decode_csv_bytes(content)
    raw_rows = list(csv.reader(io.StringIO(decoded)))
    if not raw_rows:
        raise ValueError("CSV file is empty")

    looks_like_express = any(
        len(r) > 2 and r[1].strip() == _CATEGORY_MARKER for r in raw_rows[:20]
    )
    if looks_like_express:
        return _parse_express_inventory_rows(raw_rows), detected
    return _parse_clean_csv_rows(decoded), detected


class ProductMasterRepository(Protocol):
    async def company_exists(self, company_id: uuid.UUID) -> bool: ...

    async def get_by_code(
        self, company_id: uuid.UUID, product_code: str
    ) -> ProductMaster | None: ...

    async def add_product(self, entry: ProductMaster) -> None: ...

    async def list_products(
        self, company_id: uuid.UUID, search: str | None
    ) -> list[ProductMaster]: ...

    async def deactivate_product(
        self, company_id: uuid.UUID, product_code: str
    ) -> bool: ...


class SqlAlchemyProductMasterRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return await self.db.get(Company, company_id) is not None

    async def get_by_code(
        self, company_id: uuid.UUID, product_code: str
    ) -> ProductMaster | None:
        stmt = select(ProductMaster).where(
            ProductMaster.company_id == company_id,
            ProductMaster.product_code == product_code,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_product(self, entry: ProductMaster) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_products(
        self, company_id: uuid.UUID, search: str | None
    ) -> list[ProductMaster]:
        stmt = select(ProductMaster).where(ProductMaster.company_id == company_id)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    ProductMaster.product_code.ilike(pattern),
                    ProductMaster.product_name.ilike(pattern),
                )
            )
        stmt = stmt.order_by(ProductMaster.product_code.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_product(
        self, company_id: uuid.UUID, product_code: str
    ) -> bool:
        entry = await self.get_by_code(company_id, product_code)
        if entry is None:
            return False
        entry.is_active = False
        await self.db.flush()
        return True


async def deactivate_product_master_entry(
    repo: ProductMasterRepository,
    company_id: uuid.UUID,
    product_code: str,
) -> None:
    """Soft-delete (deactivate) a product master row (HR-17-07). Raises
    ``LookupError`` on unknown company, ``ValueError`` if the code is unknown."""
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")
    if not await repo.deactivate_product(company_id, product_code):
        raise ValueError(f"product '{product_code}' not found")


async def import_product_master_csv(
    repo: ProductMasterRepository,
    company_id: uuid.UUID,
    content: bytes,
) -> ProductImportSummary:
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    rows, detected = parse_product_master_csv(content)
    summary = ProductImportSummary(imported=0, updated=0, encoding_detected=detected)

    for index, row in enumerate(rows, start=1):
        code = str(row.get("product_code") or "").strip()
        name = str(row.get("product_name") or "").strip()
        if not code or not name:
            summary.errors.append(
                ProductImportErrorDetail(
                    row_number=index,
                    message="product_code and product_name are required",
                )
            )
            continue

        existing = await repo.get_by_code(company_id, code)
        if existing is None:
            await repo.add_product(
                ProductMaster(
                    company_id=company_id,
                    product_code=code,
                    product_name=name,
                    unit=row.get("unit"),
                    unit_cost=row.get("unit_cost"),
                    category=row.get("category"),
                    is_active=True,
                )
            )
            summary.imported += 1
        else:
            existing.product_name = name
            existing.unit = row.get("unit")
            existing.unit_cost = row.get("unit_cost")
            existing.category = row.get("category")
            summary.updated += 1

    return summary


async def list_product_master_entries(
    repo: ProductMasterRepository,
    company_id: uuid.UUID,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ProductListPage:
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 200)
    rows = await repo.list_products(company_id, search)
    items = [
        ProductListItem(
            code=row.product_code,
            name=row.product_name,
            unit=row.unit,
            unit_cost=row.unit_cost,
            category=row.category,
            is_active=row.is_active,
        )
        for row in rows
    ]
    total = len(items)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return ProductListPage(
        items=items[start:end],
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        search=search,
    )
