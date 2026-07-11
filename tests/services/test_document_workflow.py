"""Tests for the routine document workflow service (W4 SIT closure Pack B —
Upload -> Process -> Review Scan -> Review Mapping persistence layer).
"""

from __future__ import annotations

import unittest
import uuid
from datetime import date, datetime, timezone

from src.backend.db.enums import DocumentStatus, LineItemStatus
from src.backend.db.models import Document, DocumentFlag, FieldCorrection, JournalLine, JournalVoucher
from src.backend.pipeline.orchestrator import PipelineContext
from src.backend.services.document_workflow import (
    apply_pipeline_result,
    approve_document,
    confirm_document_line_items,
    confirm_journal_voucher,
    create_document,
    flag_document,
    update_document_fields,
    update_document_line_items,
    update_journal_line,
)


class InMemoryDocumentRepository:
    def __init__(self, company_ids: list[uuid.UUID] | None = None) -> None:
        self.company_ids = set(company_ids or [])
        self.documents: dict[uuid.UUID, Document] = {}
        self.extractions: list = []
        self.vouchers: dict[uuid.UUID, JournalVoucher] = {}
        self.lines: dict[uuid.UUID, JournalLine] = {}
        self.line_items: dict[uuid.UUID, object] = {}
        self.flags: list[DocumentFlag] = []
        self.field_corrections: list[FieldCorrection] = []

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return company_id in self.company_ids

    async def get_company(self, company_id: uuid.UUID):
        return None

    async def add_document(self, document: Document) -> None:
        if document.id is None:
            document.id = uuid.uuid4()
        self.documents[document.id] = document

    async def get_document(self, document_id: uuid.UUID):
        return self.documents.get(document_id)

    async def list_documents(self, company_id: uuid.UUID, status: str | None = None):
        items = [d for d in self.documents.values() if d.company_id == company_id]
        if status:
            items = [d for d in items if d.status == status]
        return items

    async def add_extraction(self, extraction) -> None:
        self.extractions.append(extraction)

    async def add_voucher(self, voucher: JournalVoucher) -> None:
        if voucher.id is None:
            voucher.id = uuid.uuid4()
        self.vouchers[voucher.id] = voucher
        document = self.documents.get(voucher.document_id)
        if document is not None:
            document.journal_vouchers.append(voucher)

    async def clear_vouchers(self, document_id: uuid.UUID) -> None:
        vids = [vid for vid, v in self.vouchers.items() if v.document_id == document_id]
        for vid in vids:
            self.vouchers.pop(vid, None)
        for lid in [lid for lid, ln in self.lines.items() if ln.voucher_id in vids]:
            self.lines.pop(lid, None)
        document = self.documents.get(document_id)
        if document is not None:
            document.journal_vouchers = [
                v for v in document.journal_vouchers if v.document_id != document_id
            ]

    async def add_line(self, line: JournalLine) -> None:
        if line.id is None:
            line.id = uuid.uuid4()
        self.lines[line.id] = line
        voucher = self.vouchers.get(line.voucher_id)
        if voucher is not None:
            voucher.lines.append(line)

    async def get_voucher(self, voucher_id: uuid.UUID):
        return self.vouchers.get(voucher_id)

    async def get_line(self, line_id: uuid.UUID):
        return self.lines.get(line_id)

    async def add_line_item(self, line_item) -> None:
        if getattr(line_item, "id", None) is None:
            line_item.id = uuid.uuid4()
        self.line_items[line_item.id] = line_item
        document = self.documents.get(line_item.document_id)
        if document is not None:
            document.line_items.append(line_item)

    async def clear_line_items(self, document_id: uuid.UUID) -> None:
        for key in [k for k, li in self.line_items.items() if li.document_id == document_id]:
            self.line_items.pop(key, None)
        document = self.documents.get(document_id)
        if document is not None:
            document.line_items.clear()

    async def add_flag(self, flag: DocumentFlag) -> None:
        self.flags.append(flag)

    async def add_field_correction(self, correction: FieldCorrection) -> None:
        self.field_corrections.append(correction)

    async def flush(self) -> None:
        pass


def _make_document(company_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        company_id=company_id,
        filename="INV-001.pdf",
        status=DocumentStatus.UPLOADED.value,
    )


class TestCreateDocument(unittest.IsolatedAsyncioTestCase):
    async def test_creates_document_for_existing_company(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = await create_document(
            repo,
            company_id,
            filename="INV-001.pdf",
            original_filename="INV-001.pdf",
            storage_key="tenant/company/2026/07/abc.pdf",
            sha256="abc123",
            file_size_bytes=1024,
            content_type="application/pdf",
            uploaded_by=uuid.uuid4(),
        )
        self.assertEqual(document.status, DocumentStatus.UPLOADED.value)
        self.assertIn(document.id, repo.documents)

    async def test_rejects_unknown_company(self) -> None:
        repo = InMemoryDocumentRepository([])
        with self.assertRaises(LookupError):
            await create_document(
                repo,
                uuid.uuid4(),
                filename="a.pdf",
                original_filename="a.pdf",
                storage_key=None,
                sha256="x",
                file_size_bytes=1,
                content_type="application/pdf",
                uploaded_by=None,
            )


def _fake_ctx(company_id: uuid.UUID) -> PipelineContext:
    ctx = PipelineContext(source_file="/tmp/inv.pdf", company_id=str(company_id))
    ctx.extraction_output = {
        "fields": {
            "buyer_tax_id": "0125561025189",
            "buyer_name": "บริษัท ฤทธิ์ล้ำเลิศ จำกัด",
            "seller_tax_id": "0105560123456",
            "seller_name": "Vendor Co Ltd",
            "invoice_number": "INV-001",
            "invoice_date": "2026-07-01",
            "net_amount": 1000.0,
            "vat_amount": 70.0,
            "wht_amount": 30.0,
            "total_amount": 1040.0,
        },
        "confidence_per_field": {"invoice_number": 0.95},
        "tax_id_match": True,
        "reconciliation": {"reconciled": True},
        "critical_flags": {"reconciled": True},
        "stage_c_provider": "anthropic",
        "stage_c_model": "claude",
    }
    ctx.journal_output = {
        "journal_code": "PV",
        "rule_id": "DEFAULT-PURCHASE",
        "is_balanced": True,
        "totals": {"debit": 1070.0, "credit": 1070.0},
        "flags": [],
        "postings": [
            {"account_code": "5040", "account_name": "ค่าใช้จ่าย", "debit": 1000.0, "credit": 0.0},
            {"account_code": "1154", "account_name": "ภาษีซื้อ", "debit": 70.0, "credit": 0.0},
            {"account_code": "2195", "account_name": "เจ้าหนี้การค้า", "debit": 0.0, "credit": 1070.0},
        ],
    }
    ctx.overall_confidence = 0.91
    ctx.stage_c_applied = True
    return ctx


class TestApplyPipelineResult(unittest.IsolatedAsyncioTestCase):
    async def test_success_persists_extraction_and_balanced_voucher(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _make_document(company_id)
        ctx = _fake_ctx(company_id)

        outcome = await apply_pipeline_result(repo, document, ctx)

        self.assertEqual(document.status, DocumentStatus.REVIEW_SCAN.value)
        self.assertEqual(document.invoice_number, "INV-001")
        self.assertEqual(document.invoice_date, date(2026, 7, 1))
        self.assertEqual(float(document.total_amount), 1040.0)
        self.assertTrue(document.taxid_match)
        self.assertIsNotNone(outcome.extraction)
        self.assertEqual(len(repo.extractions), 1)
        self.assertIsNotNone(outcome.voucher)
        self.assertEqual(outcome.voucher.book_code, "PV")
        self.assertTrue(outcome.voucher.is_balanced)
        self.assertEqual(len(repo.lines), 3)

    async def test_reprocess_replaces_voucher_no_stale_rows(self) -> None:
        # W5-12-F2: reprocessing must not leave a stale earlier voucher that
        # document detail / export (which read journal_vouchers[0]) could surface.
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _registered_doc(repo, company_id)

        await apply_pipeline_result(repo, document, _fake_ctx(company_id))
        first_voucher_id = document.journal_vouchers[0].id

        await apply_pipeline_result(repo, document, _fake_ctx(company_id))

        # Exactly one voucher + one balanced line-set remains, and it is the fresh one.
        self.assertEqual(len(repo.vouchers), 1)
        self.assertEqual(len(repo.lines), 3)
        self.assertEqual(len(document.journal_vouchers), 1)
        self.assertNotEqual(document.journal_vouchers[0].id, first_voucher_id)

    async def test_pipeline_error_marks_document_failed(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _make_document(company_id)
        ctx = PipelineContext(source_file="/tmp/bad.pdf", company_id=str(company_id))
        ctx.error = "OCR provider unavailable"

        outcome = await apply_pipeline_result(repo, document, ctx)

        self.assertEqual(document.status, DocumentStatus.FAILED.value)
        self.assertEqual(document.processing_error, "OCR provider unavailable")
        self.assertIsNone(outcome.extraction)
        self.assertIsNone(outcome.voucher)
        self.assertEqual(len(repo.extractions), 0)


def _fake_ctx_with_line_items(company_id: uuid.UUID) -> PipelineContext:
    ctx = _fake_ctx(company_id)
    ctx.line_item_output = {
        "document_total": "1000.00",
        "currency": "THB",
        "line_items": [
            {
                "product_name": "ท่อ PVC 4 นิ้ว",
                "qty": "10",
                "unit": "เส้น",
                "unit_price": "80",
                "line_amount": "800",
                "line_type": "part_or_material",
                "line_type_confidence": "0.86",
                "stock_candidate": True,
            },
            {
                "product_name": "ค่าขนส่ง",
                "qty": "1",
                "unit": "",
                "unit_price": "200",
                "line_amount": "200",
                "line_type": "service",
                "line_type_confidence": "0.4",
                "stock_candidate": False,
            },
        ],
    }
    return ctx


def _registered_doc(repo: InMemoryDocumentRepository, company_id: uuid.UUID) -> Document:
    """A document registered in the repo (as create_document would), so the
    in-memory repo can attach persisted line items back to it."""
    document = _make_document(company_id)
    repo.documents[document.id] = document
    return document


class TestLineItemPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_apply_persists_line_items_as_pending(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _registered_doc(repo, company_id)
        ctx = _fake_ctx_with_line_items(company_id)

        await apply_pipeline_result(repo, document, ctx)

        self.assertEqual(len(document.line_items), 2)
        first = sorted(document.line_items, key=lambda li: li.line_order)[0]
        self.assertEqual(first.product_name, "ท่อ PVC 4 นิ้ว")
        self.assertEqual(float(first.qty), 10.0)
        self.assertEqual(float(first.unit_price), 80.0)
        self.assertAlmostEqual(float(first.confidence), 0.86, places=4)
        self.assertEqual(first.status, LineItemStatus.PENDING.value)

    async def test_reprocess_replaces_line_items(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _registered_doc(repo, company_id)
        await apply_pipeline_result(repo, document, _fake_ctx_with_line_items(company_id))
        await apply_pipeline_result(repo, document, _fake_ctx_with_line_items(company_id))
        # Idempotent reprocess: still 2 rows, not 4.
        self.assertEqual(len(document.line_items), 2)
        self.assertEqual(len(repo.line_items), 2)

    async def test_header_only_document_has_no_line_items(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _registered_doc(repo, company_id)
        await apply_pipeline_result(repo, document, _fake_ctx(company_id))
        self.assertEqual(len(document.line_items), 0)

    async def test_confirm_and_edit_line_items(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryDocumentRepository([company_id])
        document = _registered_doc(repo, company_id)
        await apply_pipeline_result(repo, document, _fake_ctx_with_line_items(company_id))

        await confirm_document_line_items(repo, document)
        self.assertTrue(
            all(li.status == LineItemStatus.CONFIRMED.value for li in document.line_items)
        )

        target = sorted(document.line_items, key=lambda li: li.line_order)[0]
        await update_document_line_items(
            repo, document, [{"id": str(target.id), "product_name": "ท่อ PVC (แก้ไข)", "qty": 12}]
        )
        self.assertEqual(target.product_name, "ท่อ PVC (แก้ไข)")
        self.assertEqual(float(target.qty), 12.0)
        # Editing drops the row back to pending for re-confirmation.
        self.assertEqual(target.status, LineItemStatus.PENDING.value)


class TestApproveAndFlag(unittest.IsolatedAsyncioTestCase):
    async def test_approve_document_sets_scan_approved(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        document.status = DocumentStatus.REVIEW_SCAN.value
        user_id = uuid.uuid4()

        result = await approve_document(repo, document, user_id)

        self.assertEqual(result.status, DocumentStatus.SCAN_APPROVED.value)
        self.assertEqual(result.scan_status, "approved")
        self.assertEqual(result.scan_reviewed_by, user_id)
        self.assertIsNotNone(result.scan_reviewed_at)
        # scan_reviewed_at is a naive TIMESTAMP column; asyncpg (live SIT)
        # rejects tz-aware values with a DataError -> the approve 500s
        # (W4-SIT-E2E-APPROVE-FIX-11). Guard the invariant directly.
        self.assertIsNone(result.scan_reviewed_at.tzinfo)

    async def test_flag_document_creates_flag_and_sets_status(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        document.status = DocumentStatus.REVIEW_SCAN.value
        user_id = uuid.uuid4()

        result = await flag_document(
            repo, document, user_id, reason="tax_id_mismatch", comment="Buyer tax id doesn't match"
        )

        self.assertEqual(result.status, DocumentStatus.SCAN_FLAGGED.value)
        self.assertEqual(len(repo.flags), 1)
        self.assertEqual(repo.flags[0].reason, "tax_id_mismatch")
        self.assertEqual(repo.flags[0].flagged_by, user_id)


def _make_voucher_with_lines(document_id: uuid.UUID) -> JournalVoucher:
    voucher = JournalVoucher(
        id=uuid.uuid4(),
        document_id=document_id,
        voucher_date=date(2026, 7, 1),
        book_code="PV",
        status="draft",
        is_balanced=True,
        total_debit=1070.0,
        total_credit=1070.0,
        flags={"flags": []},
    )
    voucher.lines = [
        JournalLine(
            id=uuid.uuid4(),
            voucher_id=voucher.id,
            line_order=1,
            account_code="5040",
            account_name="ค่าใช้จ่าย",
            is_debit=True,
            amount=1000.0,
        ),
        JournalLine(
            id=uuid.uuid4(),
            voucher_id=voucher.id,
            line_order=2,
            account_code="2195",
            account_name="เจ้าหนี้การค้า",
            is_debit=False,
            amount=1000.0,
        ),
    ]
    return voucher


class TestUpdateJournalLineAndConfirm(unittest.IsolatedAsyncioTestCase):
    async def test_update_journal_line_records_correction_and_recomputes_balance(self) -> None:
        repo = InMemoryDocumentRepository()
        document_id = uuid.uuid4()
        voucher = _make_voucher_with_lines(document_id)
        line = voucher.lines[0]
        user_id = uuid.uuid4()

        updated = await update_journal_line(
            repo, voucher, line, user_id, account_code="5041", account_name=None, amount=None
        )

        self.assertEqual(line.account_code, "5041")
        self.assertEqual(len(repo.field_corrections), 1)
        self.assertEqual(repo.field_corrections[0].old_value, "5040")
        self.assertEqual(repo.field_corrections[0].new_value, "5041")
        self.assertTrue(updated.is_balanced)

    async def test_update_journal_line_amount_can_unbalance_voucher(self) -> None:
        repo = InMemoryDocumentRepository()
        voucher = _make_voucher_with_lines(uuid.uuid4())
        line = voucher.lines[0]

        updated = await update_journal_line(
            repo, voucher, line, uuid.uuid4(), account_code=line.account_code, account_name=None, amount=500.0
        )

        self.assertFalse(updated.is_balanced)
        self.assertEqual(float(updated.total_debit), 500.0)
        self.assertEqual(float(updated.total_credit), 1000.0)

    async def test_confirm_balanced_voucher_succeeds(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        document.status = DocumentStatus.REVIEW_MAPPING.value
        voucher = _make_voucher_with_lines(document.id)
        user_id = uuid.uuid4()

        result = await confirm_journal_voucher(repo, voucher, document, user_id)

        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.confirmed_by, user_id)
        self.assertEqual(document.status, DocumentStatus.MAPPING_CONFIRMED.value)
        # Same naive-TIMESTAMP constraint as approve (confirmed_at column).
        self.assertIsNone(result.confirmed_at.tzinfo)

    async def test_confirm_unbalanced_voucher_raises(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        voucher = _make_voucher_with_lines(document.id)
        voucher.is_balanced = False

        with self.assertRaises(ValueError):
            await confirm_journal_voucher(repo, voucher, document, uuid.uuid4())


class _AsyncpgNaiveTimestampRepository(InMemoryDocumentRepository):
    """Emulates the single asyncpg behavior the plain in-memory repo omits:
    binding a tz-aware datetime to a naive `TIMESTAMP WITHOUT TIME ZONE`
    column raises. On live SIT this is exactly where Review Scan approve /
    Review Mapping confirm returned 500 (W4-SIT-E2E-APPROVE-FIX-11); the plain
    happy-path repo (and the SQLite-backed tests) accept tz-aware datetimes,
    so nothing caught it before. flush() here fails at the same seam.
    """

    async def flush(self) -> None:
        for document in self.documents.values():
            self._reject_aware(document.scan_reviewed_at, "documents.scan_reviewed_at")
        for voucher in self.vouchers.values():
            self._reject_aware(voucher.confirmed_at, "journal_vouchers.confirmed_at")

    @staticmethod
    def _reject_aware(value, column: str) -> None:
        if value is not None and getattr(value, "tzinfo", None) is not None:
            raise ValueError(
                f"asyncpg DataError: can't bind tz-aware datetime to naive column {column}"
            )


class TestAsyncpgNaiveTimestampRegression(unittest.IsolatedAsyncioTestCase):
    """Would have caught the live SIT approve/confirm 500s in-repo."""

    async def test_approve_document_survives_asyncpg_naive_timestamp_flush(self) -> None:
        repo = _AsyncpgNaiveTimestampRepository()
        document = _make_document(uuid.uuid4())
        document.status = DocumentStatus.REVIEW_SCAN.value
        await repo.add_document(document)

        # Pre-fix (tz-aware write) this flush raised, mirroring the live 500.
        result = await approve_document(repo, document, uuid.uuid4())
        self.assertEqual(result.status, DocumentStatus.SCAN_APPROVED.value)

    async def test_confirm_voucher_survives_asyncpg_naive_timestamp_flush(self) -> None:
        repo = _AsyncpgNaiveTimestampRepository()
        document = _make_document(uuid.uuid4())
        document.status = DocumentStatus.REVIEW_MAPPING.value
        voucher = _make_voucher_with_lines(document.id)
        await repo.add_document(document)
        await repo.add_voucher(voucher)

        result = await confirm_journal_voucher(repo, voucher, document, uuid.uuid4())
        self.assertEqual(result.status, "confirmed")


class TestUpdateDocumentFields(unittest.IsolatedAsyncioTestCase):
    async def test_updates_changed_fields_and_records_corrections(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        document.invoice_number = "INV-OLD"
        document.seller_name = "Old Vendor"
        user_id = uuid.uuid4()

        updated = await update_document_fields(
            repo,
            document,
            user_id,
            {"invoice_number": "INV-NEW", "seller_name": "Old Vendor", "net_amount": "1234.50"},
        )

        self.assertEqual(updated.invoice_number, "INV-NEW")
        self.assertEqual(float(updated.net_amount), 1234.50)
        # seller_name unchanged -> no correction recorded for it
        corrected_fields = {c.field_name for c in repo.field_corrections}
        self.assertIn("invoice_number", corrected_fields)
        self.assertIn("net_amount", corrected_fields)
        self.assertNotIn("seller_name", corrected_fields)

    async def test_ignores_fields_not_in_the_editable_allowlist(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())
        document.status = "review_scan"

        await update_document_fields(repo, document, uuid.uuid4(), {"status": "mapping_confirmed"})

        self.assertEqual(document.status, "review_scan")

    async def test_parses_invoice_date_string(self) -> None:
        repo = InMemoryDocumentRepository()
        document = _make_document(uuid.uuid4())

        updated = await update_document_fields(
            repo, document, uuid.uuid4(), {"invoice_date": "2026-08-15"}
        )

        self.assertEqual(updated.invoice_date, date(2026, 8, 15))


if __name__ == "__main__":
    unittest.main()
