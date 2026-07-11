"""Tests for the live export dataset builder (W5-EXPORT-LINEITEM-REALDATA-04).

Uses a lightweight fake async session (the suite has no async DB engine) that
returns pre-built transient ORM objects, so we exercise the record-mapping logic
of `build_export_records` without a real database.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import date

from src.backend.db.enums import LineItemStatus
from src.backend.db.models import (
    Company,
    Document,
    DocumentLineItem,
    JournalLine,
    JournalVoucher,
)
from src.backend.services.export_dataset import build_export_records


class _FakeResult:
    def __init__(self, docs):
        self._docs = docs

    def scalars(self):
        return self

    def all(self):
        return self._docs


class _FakeSession:
    def __init__(self, company, docs):
        self._company = company
        self._docs = docs

    async def get(self, model, pk):
        return self._company

    async def execute(self, stmt):
        return _FakeResult(self._docs)


def _company(enable_stock: bool) -> Company:
    return Company(
        name="บริษัท ทดสอบ จำกัด",
        tax_id="0105560123456",
        settings={"enable_stock": enable_stock},
    )


def _doc_with_voucher() -> Document:
    doc = Document(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        filename="INV-001.pdf",
        invoice_number="INV-001",
        invoice_date=date(2026, 7, 1),
        seller_name="Vendor Co",
        seller_tax_id="0107561234567",
        net_amount=1000.0,
        vat_amount=70.0,
        total_amount=1070.0,
        status="mapping_confirmed",
    )
    voucher = JournalVoucher(
        id=uuid.uuid4(),
        document_id=doc.id,
        voucher_no="PV-001",
        voucher_date=date(2026, 7, 1),
        book_code="PV",
    )
    voucher.lines = [
        JournalLine(
            id=uuid.uuid4(), voucher_id=voucher.id, line_order=1,
            account_code="5040", account_name="ค่าใช้จ่าย", is_debit=True, amount=1000.0,
        ),
        JournalLine(
            id=uuid.uuid4(), voucher_id=voucher.id, line_order=2,
            account_code="2195", account_name="เจ้าหนี้", is_debit=False, amount=1070.0,
        ),
    ]
    doc.journal_vouchers = [voucher]
    doc.line_items = [
        DocumentLineItem(
            id=uuid.uuid4(), document_id=doc.id, line_order=1,
            product_name="ท่อ PVC", qty=10, unit="เส้น", unit_price=80, line_amount=800,
            confidence=0.9, status=LineItemStatus.CONFIRMED.value,
        ),
        DocumentLineItem(
            id=uuid.uuid4(), document_id=doc.id, line_order=2,
            product_name="ยังไม่ยืนยัน", qty=1, unit="ชิ้น", unit_price=50, line_amount=50,
            confidence=0.4, status=LineItemStatus.PENDING.value,
        ),
    ]
    return doc


class TestBuildExportRecords(unittest.IsolatedAsyncioTestCase):
    async def test_header_gl_rows_from_real_voucher(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(enable_stock=False), [doc])
        rows = await build_export_records(session, doc.company_id)
        # One row per journal line.
        gl_rows = [r for r in rows if r.get("account_code")]
        self.assertEqual(len(gl_rows), 2)
        self.assertEqual(gl_rows[0]["invoice_number"], "INV-001")
        self.assertEqual(gl_rows[0]["seller_tax_id"], "0107561234567")
        self.assertEqual(gl_rows[0]["account_code"], "5040")
        self.assertEqual(gl_rows[0]["debit"], "1000.00")
        self.assertEqual(gl_rows[0]["credit"], "")
        self.assertEqual(gl_rows[0]["company_name"], "บริษัท ทดสอบ จำกัด")

    async def test_confirmed_line_items_included_when_enabled(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(enable_stock=True), [doc])
        rows = await build_export_records(
            session, doc.company_id, include_line_items=True
        )
        line_rows = [r for r in rows if r.get("document_type") == "line_item"]
        # Only the CONFIRMED line item is exported (pending one excluded).
        self.assertEqual(len(line_rows), 1)
        self.assertEqual(line_rows[0]["product_name"], "ท่อ PVC")
        self.assertEqual(line_rows[0]["product_unit_price"], "80.00")
        self.assertEqual(line_rows[0]["qty"], "10.00")

    async def test_line_items_excluded_when_flag_off(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(enable_stock=True), [doc])
        rows = await build_export_records(
            session, doc.company_id, include_line_items=False
        )
        self.assertFalse(any(r.get("document_type") == "line_item" for r in rows))

    async def test_empty_when_no_documents(self):
        session = _FakeSession(_company(enable_stock=True), [])
        rows = await build_export_records(session, uuid.uuid4())
        self.assertEqual(rows, [])
