"""Live export dataset builder (W5-EXPORT-LINEITEM-REALDATA-04).

Builds the flat ``list[dict]`` records the ``TemplateEngine`` consumes from REAL
reviewed/mapped documents for a company — replacing the old client-supplied
``sample_data`` fixture on the live Export path. One header/GL row per journal
line always; confirmed line-item rows appended when ``include_line_items`` is set
and the company enables stock. ``sample_data`` remains only for the Template
Configurator design-time preview, never for live export.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.backend.db.enums import DocumentStatus, LineItemStatus
from src.backend.db.models import Company, Document, JournalVoucher

# Documents that have been through review/mapping are eligible for live export.
_DEFAULT_EXPORT_STATUSES: tuple[str, ...] = (
    DocumentStatus.MAPPING_CONFIRMED.value,
    DocumentStatus.EXPORTED.value,
)


def _money(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _date_str(value: Any) -> str:
    if value is None:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def build_export_records(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    document_ids: list[uuid.UUID] | None = None,
    statuses: tuple[str, ...] | None = None,
    include_line_items: bool = False,
) -> list[dict[str, Any]]:
    """Return flat export records for a company's reviewed/mapped documents.

    Record keys match ``ColumnDef.source_field`` names used by the default Quick
    Export columns (invoice_number, invoice_date, seller_name, seller_tax_id,
    net_amount, vat_amount, total_amount, document_type, account_code,
    description) plus GL (voucher_no, debit, credit) and line-item product fields.
    """
    company = await db.get(Company, company_id)
    company_name = company.name if company else ""
    company_tax_id = company.tax_id if company else ""
    enable_stock = (
        bool((company.settings or {}).get("enable_stock")) if company else False
    )

    stmt = (
        select(Document)
        .where(Document.company_id == company_id)
        .options(
            selectinload(Document.journal_vouchers).selectinload(
                JournalVoucher.lines
            ),
            selectinload(Document.line_items),
        )
        .order_by(Document.created_at.asc())
    )
    status_filter = statuses if statuses is not None else _DEFAULT_EXPORT_STATUSES
    if status_filter:
        stmt = stmt.where(Document.status.in_(status_filter))
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))

    result = await db.execute(stmt)
    documents = list(result.scalars().all())

    records: list[dict[str, Any]] = []
    for doc in documents:
        header = {
            "invoice_number": doc.invoice_number or "",
            "invoice_date": _date_str(doc.invoice_date),
            "seller_name": doc.seller_name or "",
            "seller_tax_id": doc.seller_tax_id or "",
            "buyer_tax_id": doc.buyer_tax_id or "",
            "net_amount": _money(doc.net_amount),
            "vat_amount": _money(doc.vat_amount),
            "wht_amount": _money(doc.wht_amount),
            "total_amount": _money(doc.total_amount),
            "company_name": company_name,
            "company_tax_id": company_tax_id,
            "document_type": "",
            "description": "",
            "account_code": "",
        }

        voucher = doc.journal_vouchers[0] if doc.journal_vouchers else None
        if voucher and voucher.lines:
            for line in sorted(voucher.lines, key=lambda ln: ln.line_order):
                row = dict(header)
                row.update(
                    {
                        "voucher_no": voucher.voucher_no or "",
                        "voucher_date": _date_str(voucher.voucher_date),
                        "book_code": voucher.book_code or "",
                        "document_type": voucher.book_code or "",
                        "account_code": line.account_code or "",
                        "account_name": line.account_name or "",
                        "description": line.description or "",
                        "debit": _money(line.amount) if line.is_debit else "",
                        "credit": _money(line.amount) if not line.is_debit else "",
                    }
                )
                records.append(row)
        else:
            records.append(dict(header))

        if include_line_items and enable_stock:
            for item in sorted(doc.line_items, key=lambda x: x.line_order):
                if item.status != LineItemStatus.CONFIRMED.value:
                    continue
                row = dict(header)
                row.update(
                    {
                        "document_type": "line_item",
                        "product_name": item.product_name or "",
                        "product_unit": item.unit or "",
                        "product_unit_price": _money(item.unit_price),
                        "product_code": item.matched_product_code or "",
                        "qty": _money(item.qty),
                        "line_amount": _money(item.line_amount),
                        "description": item.product_name or "",
                    }
                )
                records.append(row)

    return records
