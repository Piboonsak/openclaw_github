"""Live export dataset builder.

Builds the flat ``list[dict]`` records the ``TemplateEngine`` consumes from REAL
reviewed/mapped documents for a company — replacing the old client-supplied
``sample_data`` fixture on the live Export path.

Granularity (W5-EXPORT-FORMAT-NORMALIZE): the customer's Express import formats
come in three shapes, so the builder emits ONE consistent row type per export:

  * ``document`` (บรรทัดเดียว, the default) — **one row per document**. The
    document-level net/vat/total sit on that single row; the P&L account
    code/description come from the primary posting (the ``net_amount`` line, i.e.
    the expense line for a purchase / revenue line for a sale — never the VAT or
    AP/AR-control line). This is the fix for the old behaviour that exploded one
    document into one row per journal posting with the header amounts duplicated.
  * ``journal`` (Express GL / Journal-RV) — **one row per journal posting** with
    per-line debit/credit. Used when the template actually has debit/credit
    columns.
  * ``line_item`` (หลายบรรทัด) — **one row per CONFIRMED line item** with the
    product code/qty, carrying the document header identity.

AP/AR master join (W5-EXPORT-FORMAT-NORMALIZE): each row is enriched with the
counterparty code/name from ``vendor_master`` / ``customer_master`` — a purchase
document's seller is looked up as a vendor, a sale document's buyer as a
customer — matched by normalized name (the master has no tax id to join on).

``sample_data`` remains only for the Template Configurator design-time preview,
never for live export.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.backend.db.enums import DocumentStatus, LineItemStatus
from src.backend.db.models import (
    Company,
    CustomerMaster,
    Document,
    JournalVoucher,
    VendorMaster,
)

Granularity = Literal["document", "journal", "line_item"]

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


def _norm_name(value: Any) -> str:
    """Whitespace-insensitive, case-folded key for matching a document's
    seller/buyer name against the vendor/customer master (which carries no tax
    id to join on)."""
    return "".join(str(value or "").split()).casefold()


def _resolve_granularity(
    granularity: Granularity | None, include_line_items: bool
) -> Granularity:
    if granularity in ("document", "journal", "line_item"):
        return granularity  # type: ignore[return-value]
    # Back-compat: the old ``include_line_items`` flag maps to line-item rows.
    return "line_item" if include_line_items else "document"


def _primary_posting(lines: list[Any]) -> Any | None:
    """Return the primary P&L posting for a document row.

    The account the customer wants in ``รหัสลงบัญชี`` is the expense line (for a
    purchase) or revenue line (for a sale) — the posting whose amount is the
    document ``net_amount`` — NOT the input/output VAT line nor the AP/AR-control
    line (which carries the gross ``total_amount``). Postings are tagged with the
    document field their amount was resolved from, so prefer ``net_amount``; fall
    back to the first non-VAT/non-gross line, then the first line.
    """
    if not lines:
        return None
    for line in lines:
        if getattr(line, "amount_field", None) == "net_amount":
            return line
    for line in lines:
        if getattr(line, "amount_field", None) not in ("vat_amount", "total_amount"):
            return line
    return lines[0]


async def _load_party_index(
    db: AsyncSession,
    company_id: uuid.UUID,
    model: Any,
    name_attr: str,
) -> dict[str, Any]:
    """Load a company's vendor/customer master into a normalized-name -> row map.

    First name wins on collision (master codes are unique per company, names may
    repeat); unmatched documents simply get blank party fields.
    """
    result = await db.execute(select(model).where(model.company_id == company_id))
    index: dict[str, Any] = {}
    for row in result.scalars().all():
        key = _norm_name(getattr(row, name_attr, None))
        if key:
            index.setdefault(key, row)
    return index


async def build_export_records(
    db: AsyncSession,
    company_id: uuid.UUID,
    *,
    document_ids: list[uuid.UUID] | None = None,
    statuses: tuple[str, ...] | None = None,
    include_line_items: bool = False,
    granularity: Granularity | None = None,
) -> list[dict[str, Any]]:
    """Return flat export records for a company's reviewed/mapped documents.

    ``granularity`` selects the row shape (see module docstring). When omitted it
    defaults to ``document`` (one row per document), or ``line_item`` if the
    legacy ``include_line_items`` flag is set. Record keys match the
    ``ColumnDef.source_field`` names templates use — header identity, amounts,
    GL (voucher_no/debit/credit), line-item product fields, and the vendor/
    customer master fields (vendor_code, vendor_name, customer_code,
    customer_name, vendor_gl_code).
    """
    mode = _resolve_granularity(granularity, include_line_items)

    company = await db.get(Company, company_id)
    company_name = company.name if company else ""
    company_tax_id = company.tax_id if company else ""

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

    # AP/AR master join (name-matched — the master has no tax id).
    vendor_index = await _load_party_index(db, company_id, VendorMaster, "vendor_name")
    customer_index = await _load_party_index(
        db, company_id, CustomerMaster, "customer_name"
    )

    records: list[dict[str, Any]] = []
    for doc in documents:
        vendor = vendor_index.get(_norm_name(doc.seller_name))
        customer = customer_index.get(_norm_name(doc.buyer_name))

        header = {
            "invoice_number": doc.invoice_number or "",
            "invoice_date": _date_str(doc.invoice_date),
            "seller_name": doc.seller_name or "",
            "seller_tax_id": doc.seller_tax_id or "",
            "buyer_name": doc.buyer_name or "",
            "buyer_tax_id": doc.buyer_tax_id or "",
            "net_amount": _money(doc.net_amount),
            "vat_amount": _money(doc.vat_amount),
            "wht_amount": _money(doc.wht_amount),
            "total_amount": _money(doc.total_amount),
            "company_name": company_name,
            "company_tax_id": company_tax_id,
            # AP/AR master fields — templates map รหัสผู้จำหน่าย -> vendor_code and
            # รหัสลูกค้า -> customer_code; blank when the name did not match.
            "vendor_code": vendor.vendor_code if vendor else "",
            "vendor_name": vendor.vendor_name if vendor else "",
            "vendor_gl_code": (vendor.gl_code or "") if vendor else "",
            "customer_code": customer.customer_code if customer else "",
            "customer_name": customer.customer_name if customer else "",
            "document_type": "",
            "description": "",
            "account_code": "",
        }

        voucher = doc.journal_vouchers[0] if doc.journal_vouchers else None
        lines = (
            sorted(voucher.lines, key=lambda ln: ln.line_order)
            if voucher and voucher.lines
            else []
        )

        if mode == "journal":
            records.extend(_journal_rows(header, voucher, lines))
        elif mode == "line_item":
            records.extend(_line_item_rows(header, voucher, lines, doc))
        else:  # document (บรรทัดเดียว) — one row per document
            records.append(_document_row(header, voucher, lines))

    return records


def _document_row(
    header: dict[str, Any], voucher: Any, lines: list[Any]
) -> dict[str, Any]:
    """One row per document: header amounts + the primary P&L posting's account."""
    row = dict(header)
    if voucher is not None:
        row["voucher_no"] = voucher.voucher_no or ""
        row["voucher_date"] = _date_str(voucher.voucher_date)
        row["book_code"] = voucher.book_code or ""
        row["document_type"] = voucher.book_code or ""
    primary = _primary_posting(lines)
    if primary is not None:
        row["account_code"] = primary.account_code or ""
        row["account_name"] = primary.account_name or ""
        row["description"] = primary.description or ""
    return row


def _journal_rows(
    header: dict[str, Any], voucher: Any, lines: list[Any]
) -> list[dict[str, Any]]:
    """One row per journal posting (Express GL / Journal-RV)."""
    if voucher is None or not lines:
        return [dict(header)]
    rows: list[dict[str, Any]] = []
    for line in lines:
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
        rows.append(row)
    return rows


def _line_item_rows(
    header: dict[str, Any], voucher: Any, lines: list[Any], doc: Any
) -> list[dict[str, Any]]:
    """One row per CONFIRMED line item (หลายบรรทัด). Falls back to a single
    document row when the document has no confirmed line items, so the document
    is never silently dropped from the export."""
    confirmed = [
        item
        for item in sorted(doc.line_items, key=lambda x: x.line_order)
        if item.status == LineItemStatus.CONFIRMED.value
    ]
    if not confirmed:
        return [_document_row(header, voucher, lines)]

    voucher_no = voucher.voucher_no if voucher is not None else ""
    rows: list[dict[str, Any]] = []
    for item in confirmed:
        row = dict(header)
        row.update(
            {
                "voucher_no": voucher_no or "",
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
        rows.append(row)
    return rows
