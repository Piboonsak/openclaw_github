"""Tests for the live export dataset builder.

Uses a lightweight fake async session (the suite has no async DB engine) that
returns pre-built transient ORM objects, so we exercise the record-mapping logic
of `build_export_records` without a real database.

Covers the three granularity engines (document / journal / line_item —
W5-EXPORT-FORMAT-NORMALIZE) and the vendor/customer master name-join.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import date

from src.backend.db.enums import LineItemStatus
from src.backend.db.models import (
    Company,
    CustomerMaster,
    Document,
    DocumentLineItem,
    JournalLine,
    JournalVoucher,
    VendorMaster,
)
from src.backend.services.export_dataset import build_export_records


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """Routes execute() to docs / vendor master / customer master by inspecting
    the compiled statement's table name (the builder issues three selects)."""

    def __init__(self, company, docs, vendors=None, customers=None):
        self._company = company
        self._docs = docs
        self._vendors = vendors or []
        self._customers = customers or []

    async def get(self, model, pk):
        return self._company

    async def execute(self, stmt):
        text = str(stmt).lower()
        if "vendor_master" in text:
            return _FakeResult(self._vendors)
        if "customer_master" in text:
            return _FakeResult(self._customers)
        return _FakeResult(self._docs)


def _company(enable_stock: bool = False) -> Company:
    return Company(
        name="บริษัท ทดสอบ จำกัด",
        tax_id="0105560123456",
        settings={"enable_stock": enable_stock},
    )


def _doc_with_voucher(*, buyer_name: str | None = None) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        filename="INV-001.pdf",
        invoice_number="INV-001",
        invoice_date=date(2026, 7, 1),
        seller_name="Vendor Co",
        seller_tax_id="0107561234567",
        buyer_name=buyer_name,
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
            amount_field="net_amount", description="ค่าของ",
        ),
        JournalLine(
            id=uuid.uuid4(), voucher_id=voucher.id, line_order=2,
            account_code="1151", account_name="ภาษีซื้อ", is_debit=True, amount=70.0,
            amount_field="vat_amount", description="VAT",
        ),
        JournalLine(
            id=uuid.uuid4(), voucher_id=voucher.id, line_order=3,
            account_code="2195", account_name="เจ้าหนี้", is_debit=False, amount=1070.0,
            amount_field="total_amount", description="เจ้าหนี้การค้า",
        ),
    ]
    doc.journal_vouchers = [voucher]
    doc.line_items = [
        DocumentLineItem(
            id=uuid.uuid4(), document_id=doc.id, line_order=1,
            product_name="ท่อ PVC", qty=10, unit="เส้น", unit_price=80, line_amount=800,
            matched_product_code="5200-04", confidence=0.9,
            status=LineItemStatus.CONFIRMED.value,
        ),
        DocumentLineItem(
            id=uuid.uuid4(), document_id=doc.id, line_order=2,
            product_name="ยังไม่ยืนยัน", qty=1, unit="ชิ้น", unit_price=50, line_amount=50,
            confidence=0.4, status=LineItemStatus.PENDING.value,
        ),
    ]
    return doc


class TestDocumentGranularity(unittest.IsolatedAsyncioTestCase):
    async def test_document_mode_emits_one_row_per_document(self):
        """Default (document) mode: one row per document — NOT one per posting.
        Header amounts on that single row; account_code from the primary P&L
        (net_amount) posting, not the VAT or AP-control line."""
        doc = _doc_with_voucher()
        session = _FakeSession(_company(), [doc])
        rows = await build_export_records(session, doc.company_id)

        self.assertEqual(len(rows), 1)  # 3 postings collapse to 1 document row
        row = rows[0]
        self.assertEqual(row["invoice_number"], "INV-001")
        self.assertEqual(row["net_amount"], "1000.00")
        self.assertEqual(row["vat_amount"], "70.00")
        self.assertEqual(row["total_amount"], "1070.00")
        # Primary posting is the expense (net_amount) line — 5040 — not 1151/2195.
        self.assertEqual(row["account_code"], "5040")
        self.assertEqual(row["description"], "ค่าของ")
        self.assertEqual(row["document_type"], "PV")

    async def test_journal_mode_emits_one_row_per_posting(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(), [doc])
        rows = await build_export_records(
            session, doc.company_id, granularity="journal"
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["account_code"], "5040")
        self.assertEqual(rows[0]["debit"], "1000.00")
        self.assertEqual(rows[0]["credit"], "")
        self.assertEqual(rows[2]["account_code"], "2195")
        self.assertEqual(rows[2]["credit"], "1070.00")

    async def test_line_item_mode_emits_one_row_per_confirmed_item(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(enable_stock=True), [doc])
        rows = await build_export_records(
            session, doc.company_id, granularity="line_item"
        )
        line_rows = [r for r in rows if r.get("document_type") == "line_item"]
        self.assertEqual(len(line_rows), 1)  # pending item excluded
        self.assertEqual(line_rows[0]["product_name"], "ท่อ PVC")
        self.assertEqual(line_rows[0]["product_code"], "5200-04")
        self.assertEqual(line_rows[0]["qty"], "10.00")

    async def test_line_item_mode_falls_back_to_document_row_when_none_confirmed(self):
        doc = _doc_with_voucher()
        for item in doc.line_items:
            item.status = LineItemStatus.PENDING.value
        session = _FakeSession(_company(enable_stock=True), [doc])
        rows = await build_export_records(
            session, doc.company_id, granularity="line_item"
        )
        # Document is not silently dropped: it falls back to a single doc row.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account_code"], "5040")
        self.assertNotEqual(rows[0].get("document_type"), "line_item")

    async def test_include_line_items_flag_maps_to_line_item_mode(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(enable_stock=True), [doc])
        rows = await build_export_records(
            session, doc.company_id, include_line_items=True
        )
        self.assertTrue(any(r.get("document_type") == "line_item" for r in rows))

    async def test_empty_when_no_documents(self):
        session = _FakeSession(_company(), [])
        rows = await build_export_records(session, uuid.uuid4())
        self.assertEqual(rows, [])


class TestMasterJoin(unittest.IsolatedAsyncioTestCase):
    async def test_vendor_master_join_by_name_populates_vendor_code(self):
        doc = _doc_with_voucher()
        vendor = VendorMaster(
            company_id=doc.company_id, vendor_code="5004",
            vendor_name="Vendor Co", gl_code="2120-01",
        )
        session = _FakeSession(_company(), [doc], vendors=[vendor])
        rows = await build_export_records(session, doc.company_id)
        self.assertEqual(rows[0]["vendor_code"], "5004")
        self.assertEqual(rows[0]["vendor_name"], "Vendor Co")
        self.assertEqual(rows[0]["vendor_gl_code"], "2120-01")

    async def test_customer_master_join_by_name_populates_customer_code(self):
        doc = _doc_with_voucher(buyer_name="ลูกค้า Shopee")
        customer = CustomerMaster(
            company_id=doc.company_id, customer_code="163",
            customer_name="ลูกค้า Shopee",
        )
        session = _FakeSession(_company(), [doc], customers=[customer])
        rows = await build_export_records(session, doc.company_id)
        self.assertEqual(rows[0]["customer_code"], "163")
        self.assertEqual(rows[0]["customer_name"], "ลูกค้า Shopee")

    async def test_unmatched_party_leaves_blank_code(self):
        doc = _doc_with_voucher()
        session = _FakeSession(_company(), [doc], vendors=[])
        rows = await build_export_records(session, doc.company_id)
        self.assertEqual(rows[0]["vendor_code"], "")
        self.assertEqual(rows[0]["customer_code"], "")


class _DocIdFilteringSession(_FakeSession):
    """Fake session that actually honors ``Document.id IN (...)`` by compiling the
    statement with literal bound params and filtering the doc list to the ids that
    appear in the WHERE clause. This lets us prove the ``document_ids`` scoping in
    ``build_export_records`` without a real DB engine — the guard the W6-C1-01
    Export-selection feature depends on."""

    async def execute(self, stmt):
        text = str(stmt).lower()
        if "vendor_master" in text or "customer_master" in text:
            return await super().execute(stmt)
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        if "documents.id in" in compiled.lower():
            # SQLAlchemy renders UUID literals without dashes, so match on .hex.
            scoped = [
                d for d in self._docs
                if str(d.id) in compiled or d.id.hex in compiled
            ]
            return _FakeResult(scoped)
        return _FakeResult(self._docs)


class TestDocumentIdSelection(unittest.IsolatedAsyncioTestCase):
    """HR-17-05 / W6-C1-01: Export must be scoped to the documents the user
    selected. Before the fix the frontend never sent ``document_ids`` and every
    export dumped all mapping_confirmed docs. These prove the backend contract
    the new per-document checkboxes rely on."""

    def _two_docs(self):
        company_id = uuid.uuid4()
        doc_a = _doc_with_voucher()
        doc_b = _doc_with_voucher()
        doc_a.company_id = company_id
        doc_b.company_id = company_id
        doc_a.invoice_number = "INV-A"
        doc_b.invoice_number = "INV-B"
        return company_id, doc_a, doc_b

    async def test_document_ids_scopes_export_to_selection(self):
        company_id, doc_a, doc_b = self._two_docs()
        session = _DocIdFilteringSession(_company(), [doc_a, doc_b])
        rows = await build_export_records(
            session, company_id, document_ids=[doc_a.id]
        )
        invoices = {r["invoice_number"] for r in rows}
        self.assertEqual(invoices, {"INV-A"})  # doc_b excluded, not exported

    async def test_no_document_ids_exports_all(self):
        company_id, doc_a, doc_b = self._two_docs()
        session = _DocIdFilteringSession(_company(), [doc_a, doc_b])
        rows = await build_export_records(session, company_id, document_ids=None)
        invoices = {r["invoice_number"] for r in rows}
        self.assertEqual(invoices, {"INV-A", "INV-B"})


if __name__ == "__main__":
    unittest.main()
