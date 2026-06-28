"""Vendor and customer master import services for TASK-1207."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.models import Company, CustomerMaster, VendorMaster
from src.backend.services.schema_analyzer import detect_encoding

MasterEntity = Literal["vendor", "customer"]

_VENDOR_CODE_HEADERS = {"vendor_code", "vendor code", "code"}
_VENDOR_NAME_HEADERS = {"vendor_name", "vendor name", "name"}
_CUSTOMER_CODE_HEADERS = {"customer_code", "customer code", "code"}
_CUSTOMER_NAME_HEADERS = {"customer_name", "customer name", "name"}
_GL_CODE_HEADERS = {"gl_code", "gl code", "account_code", "account code"}
_AR_FLAG_HEADERS = {"ar_flag", "ar flag"}
_IS_ACTIVE_HEADERS = {"is_active", "is active", "active"}


@dataclass
class ImportErrorDetail:
    row_number: int
    message: str


@dataclass
class ImportSummary:
    imported: int
    updated: int
    errors: list[ImportErrorDetail] = field(default_factory=list)
    encoding_detected: str = "utf-8"


@dataclass
class MasterListItem:
    code: str
    name: str
    is_active: bool
    extra: dict[str, str | int | None] = field(default_factory=dict)


@dataclass
class MasterListPage:
    items: list[MasterListItem]
    total: int
    page: int
    page_size: int
    search: str | None


class MasterDataRepository(Protocol):
    async def company_exists(self, company_id: uuid.UUID) -> bool: ...

    async def get_vendor_by_code(
        self,
        company_id: uuid.UUID,
        vendor_code: str,
    ) -> VendorMaster | None: ...

    async def get_customer_by_code(
        self,
        company_id: uuid.UUID,
        customer_code: str,
    ) -> CustomerMaster | None: ...

    async def add_vendor(self, entry: VendorMaster) -> None: ...

    async def add_customer(self, entry: CustomerMaster) -> None: ...

    async def list_vendors(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[VendorMaster]: ...

    async def list_customers(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[CustomerMaster]: ...


class SqlAlchemyMasterRepository:
    """Production repository backed by AsyncSession."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return await self.db.get(Company, company_id) is not None

    async def get_vendor_by_code(
        self,
        company_id: uuid.UUID,
        vendor_code: str,
    ) -> VendorMaster | None:
        stmt = select(VendorMaster).where(
            VendorMaster.company_id == company_id,
            VendorMaster.vendor_code == vendor_code,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_customer_by_code(
        self,
        company_id: uuid.UUID,
        customer_code: str,
    ) -> CustomerMaster | None:
        stmt = select(CustomerMaster).where(
            CustomerMaster.company_id == company_id,
            CustomerMaster.customer_code == customer_code,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_vendor(self, entry: VendorMaster) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def add_customer(self, entry: CustomerMaster) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_vendors(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[VendorMaster]:
        stmt = select(VendorMaster).where(VendorMaster.company_id == company_id)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    VendorMaster.vendor_code.ilike(pattern),
                    VendorMaster.vendor_name.ilike(pattern),
                )
            )
        stmt = stmt.order_by(VendorMaster.vendor_code.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_customers(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[CustomerMaster]:
        stmt = select(CustomerMaster).where(CustomerMaster.company_id == company_id)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    CustomerMaster.customer_code.ilike(pattern),
                    CustomerMaster.customer_name.ilike(pattern),
                )
            )
        stmt = stmt.order_by(CustomerMaster.customer_code.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


def _normalize_header(header: str | None) -> str:
    return str(header or "").strip().lower().replace("_", " ").replace("-", " ")


def _resolve_header(row: dict[str, str], candidates: set[str]) -> str:
    normalized = {_normalize_header(key): key for key in row}
    for candidate in candidates:
        source_key = normalized.get(_normalize_header(candidate))
        if source_key is not None:
            return row.get(source_key, "")
    return ""


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return True
    normalized = str(value).strip().lower()
    if normalized == "":
        return True
    return normalized not in {"0", "false", "no", "n", "inactive"}


def _parse_int(value: str | None, default: int = 0) -> int:
    normalized = str(value or "").strip()
    if not normalized:
        return default
    return int(normalized)


def _decode_csv_bytes(content: bytes) -> tuple[str, str]:
    detected = detect_encoding(content)
    codec = "cp874" if detected == "tis-620" else "utf-8-sig"
    return content.decode(codec, errors="replace"), detected


def _parse_csv_rows(content: bytes) -> tuple[list[dict[str, str]], str]:
    decoded, detected = _decode_csv_bytes(content)
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required")

    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({str(key or ""): str(value or "").strip() for key, value in row.items()})
    return rows, detected


async def import_master_csv(
    repo: MasterDataRepository,
    company_id: uuid.UUID,
    entity: MasterEntity,
    content: bytes,
) -> ImportSummary:
    """Import vendor/customer master rows from CSV with upsert behavior."""
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    rows, detected = _parse_csv_rows(content)
    summary = ImportSummary(imported=0, updated=0, encoding_detected=detected)

    for index, row in enumerate(rows, start=2):
        try:
            if entity == "vendor":
                vendor_code = _resolve_header(row, _VENDOR_CODE_HEADERS).strip()
                vendor_name = _resolve_header(row, _VENDOR_NAME_HEADERS).strip()
                gl_code = _resolve_header(row, _GL_CODE_HEADERS).strip() or None
                is_active = _parse_bool(_resolve_header(row, _IS_ACTIVE_HEADERS))

                if not vendor_code or not vendor_name:
                    raise ValueError("vendor_code and vendor_name are required")

                existing_vendor = await repo.get_vendor_by_code(company_id, vendor_code)
                if existing_vendor is None:
                    await repo.add_vendor(
                        VendorMaster(
                            company_id=company_id,
                            vendor_code=vendor_code,
                            vendor_name=vendor_name,
                            gl_code=gl_code,
                            is_active=is_active,
                        )
                    )
                    summary.imported += 1
                else:
                    existing_vendor.vendor_name = vendor_name
                    existing_vendor.gl_code = gl_code
                    existing_vendor.is_active = is_active
                    summary.updated += 1
                continue

            customer_code = _resolve_header(row, _CUSTOMER_CODE_HEADERS).strip()
            customer_name = _resolve_header(row, _CUSTOMER_NAME_HEADERS).strip()
            ar_flag = _parse_int(_resolve_header(row, _AR_FLAG_HEADERS), default=0)
            is_active = _parse_bool(_resolve_header(row, _IS_ACTIVE_HEADERS))

            if not customer_code or not customer_name:
                raise ValueError("customer_code and customer_name are required")

            existing_customer = await repo.get_customer_by_code(company_id, customer_code)
            if existing_customer is None:
                await repo.add_customer(
                    CustomerMaster(
                        company_id=company_id,
                        customer_code=customer_code,
                        customer_name=customer_name,
                        ar_flag=ar_flag,
                        is_active=is_active,
                    )
                )
                summary.imported += 1
            else:
                existing_customer.customer_name = customer_name
                existing_customer.ar_flag = ar_flag
                existing_customer.is_active = is_active
                summary.updated += 1
        except ValueError as exc:
            summary.errors.append(ImportErrorDetail(row_number=index, message=str(exc)))

    return summary


async def list_master_entries(
    repo: MasterDataRepository,
    company_id: uuid.UUID,
    entity: MasterEntity,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> MasterListPage:
    """Return a paginated vendor/customer listing."""
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 200)

    if entity == "vendor":
        rows = await repo.list_vendors(company_id, search)
        items = [
            MasterListItem(
                code=row.vendor_code,
                name=row.vendor_name,
                is_active=row.is_active,
                extra={"gl_code": row.gl_code},
            )
            for row in rows
        ]
    else:
        rows = await repo.list_customers(company_id, search)
        items = [
            MasterListItem(
                code=row.customer_code,
                name=row.customer_name,
                is_active=row.is_active,
                extra={"ar_flag": row.ar_flag},
            )
            for row in rows
        ]

    total = len(items)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return MasterListPage(
        items=items[start:end],
        total=total,
        page=safe_page,
        page_size=safe_page_size,
        search=search,
    )
