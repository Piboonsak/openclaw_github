"""Tests for the routine document workflow API (W4 SIT closure Pack B —
Upload -> Process -> Review Scan -> Review Mapping, `TASK-W4-SIT-E2E-CLAUDE-
IMPLEMENT-ROUTINE-OPS-05`)."""

from __future__ import annotations

import io
import unittest
import unittest.mock
import uuid
from datetime import date
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.settings import settings
from src.backend.api.documents import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.enums import DocumentStatus
from src.backend.db.models import Document, DocumentFlag, FieldCorrection, JournalLine, JournalVoucher
from src.backend.db.session import get_db
from src.backend.pipeline.orchestrator import PipelineContext


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _admin_user():
    return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")


class InMemoryRepository:
    def __init__(self, company_ids=None) -> None:
        self.company_ids = set(company_ids or [])
        self.documents: dict[uuid.UUID, Document] = {}
        self.extractions = []
        self.vouchers: dict[uuid.UUID, JournalVoucher] = {}
        self.lines: dict[uuid.UUID, JournalLine] = {}
        self.line_items: dict[uuid.UUID, object] = {}
        self.flags: list[DocumentFlag] = []
        self.field_corrections: list[FieldCorrection] = []

    async def company_exists(self, company_id):
        return company_id in self.company_ids

    async def get_company(self, company_id):
        return SimpleNamespace(id=company_id, tax_id="0125561025189")

    async def add_document(self, document):
        if document.id is None:
            document.id = uuid.uuid4()
        document.extractions = []
        document.journal_vouchers = []
        document.line_items = []
        self.documents[document.id] = document

    async def get_document(self, document_id):
        return self.documents.get(document_id)

    async def list_documents(self, company_id, status=None):
        items = [d for d in self.documents.values() if d.company_id == company_id]
        if status:
            items = [d for d in items if d.status == status]
        return items

    async def add_extraction(self, extraction):
        self.extractions.append(extraction)
        doc = self.documents.get(extraction.document_id)
        if doc is not None:
            doc.extractions.append(extraction)

    async def add_voucher(self, voucher):
        if voucher.id is None:
            voucher.id = uuid.uuid4()
        self.vouchers[voucher.id] = voucher
        doc = self.documents.get(voucher.document_id)
        if doc is not None:
            doc.journal_vouchers.append(voucher)

    async def add_line(self, line):
        if line.id is None:
            line.id = uuid.uuid4()
        self.lines[line.id] = line
        voucher = self.vouchers.get(line.voucher_id)
        if voucher is not None:
            voucher.lines.append(line)

    async def add_line_item(self, line_item):
        if getattr(line_item, "id", None) is None:
            line_item.id = uuid.uuid4()
        self.line_items[line_item.id] = line_item
        doc = self.documents.get(line_item.document_id)
        if doc is not None:
            doc.line_items.append(line_item)

    async def clear_line_items(self, document_id):
        for key in [k for k, li in self.line_items.items() if li.document_id == document_id]:
            self.line_items.pop(key, None)
        doc = self.documents.get(document_id)
        if doc is not None:
            doc.line_items = []

    async def get_voucher(self, voucher_id):
        return self.vouchers.get(voucher_id)

    async def get_line(self, line_id):
        return self.lines.get(line_id)

    async def add_flag(self, flag):
        self.flags.append(flag)

    async def add_field_correction(self, correction):
        self.field_corrections.append(correction)

    async def flush(self):
        return None


class DocumentsApiTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.repo = InMemoryRepository([self.company_id])

        from src.backend.api import documents as module

        self.module = module
        self.patch = unittest.mock.patch.object(
            module, "SqlAlchemyDocumentRepository", new=lambda db: self.repo
        )
        self.patch.start()

        async def fake_get_db():
            yield SimpleNamespace()

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

    def tearDown(self) -> None:
        self.patch.stop()


class TestUploadDocuments(DocumentsApiTestBase):
    def test_upload_creates_real_documents(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/documents/upload",
            files=[("files", ("INV-001.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))],
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["documents"]), 1)
        self.assertEqual(body["documents"][0]["status"], DocumentStatus.UPLOADED.value)
        self.assertEqual(len(self.repo.documents), 1)

    def test_upload_rejects_unsupported_extension(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/documents/upload",
            files=[("files", ("data.exe", io.BytesIO(b"whatever"), "application/octet-stream"))],
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_unknown_company(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{uuid.uuid4()}/documents/upload",
            files=[("files", ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        )
        self.assertEqual(resp.status_code, 404)


class TestProcessDocument(DocumentsApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.document = Document(
            id=uuid.uuid4(),
            company_id=self.company_id,
            filename="INV-001.pdf",
            sha256="deadbeef",
            status=DocumentStatus.UPLOADED.value,
        )
        self.document.extractions = []
        self.document.journal_vouchers = []
        self.repo.documents[self.document.id] = self.document

        self.local_path = settings.UPLOAD_ROOT / f"{self.document.sha256}.pdf"
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.local_path.write_bytes(b"%PDF-1.4 fake")

    def tearDown(self) -> None:
        super().tearDown()
        if self.local_path.exists():
            self.local_path.unlink()

    def _fake_ctx(self) -> PipelineContext:
        ctx = PipelineContext(source_file=str(self.local_path), company_id=str(self.company_id))
        ctx.extraction_output = {
            "fields": {
                "invoice_number": "INV-001",
                "invoice_date": "2026-07-01",
                "total_amount": 1070.0,
                "net_amount": 1000.0,
                "vat_amount": 70.0,
            },
            "confidence_per_field": {},
            "tax_id_match": True,
        }
        ctx.journal_output = {
            "journal_code": "PV",
            "rule_id": "DEFAULT-PURCHASE",
            "is_balanced": True,
            "totals": {"debit": 1070.0, "credit": 1070.0},
            "flags": [],
            "postings": [
                {"account_code": "5040", "debit": 1000.0, "credit": 0.0},
                {"account_code": "1154", "debit": 70.0, "credit": 0.0},
                {"account_code": "2195", "debit": 0.0, "credit": 1070.0},
            ],
        }
        ctx.overall_confidence = 0.9
        return ctx

    def test_process_runs_pipeline_and_persists_result(self) -> None:
        async def fake_run_pipeline(*args, **kwargs):
            return self._fake_ctx()

        with unittest.mock.patch.object(self.module, "run_pipeline", fake_run_pipeline):
            resp = self.client.post(f"/v1/documents/{self.document.id}/process")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], DocumentStatus.REVIEW_SCAN.value)
        self.assertEqual(body["invoice_number"], "INV-001")
        self.assertIsNotNone(body["voucher"])
        self.assertEqual(len(body["voucher"]["lines"]), 3)
        self.assertTrue(body["voucher"]["is_balanced"])

    def test_process_missing_source_file_returns_409(self) -> None:
        self.local_path.unlink()

        async def fake_run_pipeline(*args, **kwargs):
            raise AssertionError("should not be called when source file is missing")

        with unittest.mock.patch.object(self.module, "run_pipeline", fake_run_pipeline):
            resp = self.client.post(f"/v1/documents/{self.document.id}/process")

        self.assertEqual(resp.status_code, 409)

    def test_process_pipeline_error_marks_document_failed(self) -> None:
        async def fake_run_pipeline(*args, **kwargs):
            ctx = PipelineContext(source_file=str(self.local_path), company_id=str(self.company_id))
            ctx.error = "OCR unavailable"
            return ctx

        with unittest.mock.patch.object(self.module, "run_pipeline", fake_run_pipeline):
            resp = self.client.post(f"/v1/documents/{self.document.id}/process")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], DocumentStatus.FAILED.value)
        self.assertEqual(body["processing_error"], "OCR unavailable")


class TestApproveFlow(DocumentsApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.doc_a = Document(
            id=uuid.uuid4(), company_id=self.company_id, filename="a.pdf",
            status=DocumentStatus.REVIEW_SCAN.value,
        )
        self.doc_a.extractions, self.doc_a.journal_vouchers = [], []
        self.doc_b = Document(
            id=uuid.uuid4(), company_id=self.company_id, filename="b.pdf",
            status=DocumentStatus.REVIEW_SCAN.value,
        )
        self.doc_b.extractions, self.doc_b.journal_vouchers = [], []
        self.repo.documents[self.doc_a.id] = self.doc_a
        self.repo.documents[self.doc_b.id] = self.doc_b

    def test_approve_single_document(self) -> None:
        resp = self.client.post(f"/v1/documents/{self.doc_a.id}/approve")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], DocumentStatus.SCAN_APPROVED.value)

    def test_approve_all_without_ids_approves_every_review_scan_document(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/documents/approve-all", json={}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["approved"], 2)
        self.assertEqual(self.doc_a.status, DocumentStatus.SCAN_APPROVED.value)
        self.assertEqual(self.doc_b.status, DocumentStatus.SCAN_APPROVED.value)

    def test_flag_document_records_reason(self) -> None:
        resp = self.client.post(
            f"/v1/documents/{self.doc_a.id}/flag",
            json={"reason": "tax_id_mismatch", "comment": "buyer tax id wrong"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], DocumentStatus.SCAN_FLAGGED.value)
        self.assertEqual(len(self.repo.flags), 1)


class TestReviewMapping(DocumentsApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.document = Document(
            id=uuid.uuid4(), company_id=self.company_id, filename="a.pdf",
            status=DocumentStatus.REVIEW_MAPPING.value,
        )
        self.document.extractions, self.document.journal_vouchers = [], []
        self.repo.documents[self.document.id] = self.document

        self.voucher = JournalVoucher(
            id=uuid.uuid4(), document_id=self.document.id, voucher_date=date(2026, 7, 1),
            book_code="PV", status="draft", is_balanced=True,
            total_debit=1000.0, total_credit=1000.0, flags={"flags": []},
        )
        self.voucher.lines = [
            JournalLine(
                id=uuid.uuid4(), voucher_id=self.voucher.id, line_order=1,
                account_code="5040", is_debit=True, amount=1000.0,
            ),
            JournalLine(
                id=uuid.uuid4(), voucher_id=self.voucher.id, line_order=2,
                account_code="2195", is_debit=False, amount=1000.0,
            ),
        ]
        self.repo.vouchers[self.voucher.id] = self.voucher

    def test_update_line_account_code(self) -> None:
        line_id = self.voucher.lines[0].id
        resp = self.client.put(
            f"/v1/journal-vouchers/{self.voucher.id}/lines/{line_id}",
            json={"account_code": "5099"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        updated_line = next(ln for ln in body["lines"] if ln["id"] == str(line_id))
        self.assertEqual(updated_line["account_code"], "5099")
        self.assertEqual(len(self.repo.field_corrections), 1)

    def test_confirm_balanced_voucher(self) -> None:
        resp = self.client.post(f"/v1/journal-vouchers/{self.voucher.id}/confirm")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "confirmed")
        self.assertEqual(self.document.status, DocumentStatus.MAPPING_CONFIRMED.value)

    def test_confirm_unbalanced_voucher_returns_400(self) -> None:
        self.voucher.is_balanced = False
        resp = self.client.post(f"/v1/journal-vouchers/{self.voucher.id}/confirm")
        self.assertEqual(resp.status_code, 400)


class TestUpdateDocumentFields(DocumentsApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.document = Document(
            id=uuid.uuid4(), company_id=self.company_id, filename="a.pdf",
            status=DocumentStatus.REVIEW_SCAN.value, invoice_number="INV-OLD",
        )
        self.document.extractions, self.document.journal_vouchers = [], []
        self.repo.documents[self.document.id] = self.document

    def test_update_header_fields(self) -> None:
        resp = self.client.put(
            f"/v1/documents/{self.document.id}/fields",
            json={"invoice_number": "INV-NEW", "seller_name": "Vendor Co"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["invoice_number"], "INV-NEW")
        self.assertEqual(body["seller_name"], "Vendor Co")
        self.assertEqual(len(self.repo.field_corrections), 2)


class TestGetDocumentFile(DocumentsApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.document = Document(
            id=uuid.uuid4(), company_id=self.company_id, filename="a.pdf",
            status=DocumentStatus.REVIEW_SCAN.value, storage_key="tenant/company/2026/07/abc.pdf",
            content_type="application/pdf",
        )
        self.document.extractions, self.document.journal_vouchers = [], []
        self.repo.documents[self.document.id] = self.document

    def test_returns_real_stored_bytes(self) -> None:
        from src.backend.api import documents as module

        fake_client = SimpleNamespace(download_bytes=lambda key: b"%PDF-1.4 real bytes")
        with unittest.mock.patch.object(module, "get_storage_client", lambda: fake_client):
            resp = self.client.get(f"/v1/documents/{self.document.id}/file")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"%PDF-1.4 real bytes")
        self.assertEqual(resp.headers["content-type"], "application/pdf")

    def test_missing_storage_key_returns_404(self) -> None:
        self.document.storage_key = None
        resp = self.client.get(f"/v1/documents/{self.document.id}/file")
        self.assertEqual(resp.status_code, 404)

    def test_storage_read_failure_returns_404(self) -> None:
        from src.backend.api import documents as module

        def _boom(key):
            raise FileNotFoundError(key)

        fake_client = SimpleNamespace(download_bytes=_boom)
        with unittest.mock.patch.object(module, "get_storage_client", lambda: fake_client):
            resp = self.client.get(f"/v1/documents/{self.document.id}/file")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
