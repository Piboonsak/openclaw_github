"""Tests for Chart of Accounts API endpoints (TASK-1203)."""

from __future__ import annotations

import io
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.backend.api.coa as coa_module
from src.backend.api.coa import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import ChartOfAccount, Company
from src.backend.db.session import get_db


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _admin_user():
    return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")


class FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class FakeAsyncSession:
    def __init__(self, *, company: Company | None = None, accounts=None):
        self.company = company
        self.accounts_by_key: dict[tuple[uuid.UUID, str], ChartOfAccount] = {
            (a.company_id, a.account_code): a for a in (accounts or [])
        }
        self.added = []

    async def get(self, model, key):
        if model is Company:
            return self.company if self.company and self.company.id == key else None
        return None

    async def execute(self, _stmt):
        return FakeResult(self.accounts_by_key.values())

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChartOfAccount):
            self.accounts_by_key[(obj.company_id, obj.account_code)] = obj

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    async def scalars(self, _stmt):
        return []


class TestCoaImportFile(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.company = Company(
            id=self.company_id, tenant_id=uuid.uuid4(), name="Test Co",
            tax_id="0100000000001", is_active=True,
        )
        self.session = FakeAsyncSession(company=self.company)

        async def fake_get_db():
            yield self.session

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

    def test_csv_import_creates_accounts(self) -> None:
        content = b"account_code,account_name,account_type\n1100,Cash,asset\n"
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/coa/import",
            files={"file": ("coa.csv", io.BytesIO(content), "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["updated"], 0)

    def test_rejects_unsupported_extension(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/coa/import",
            files={"file": ("coa.pdf", io.BytesIO(b"whatever"), "application/pdf")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_returns_existing_accounts(self) -> None:
        existing = ChartOfAccount(
            id=uuid.uuid4(), company_id=self.company_id, account_code="1100",
            account_name="Cash", account_type="asset", is_active=True,
        )
        self.session.accounts_by_key[(self.company_id, "1100")] = existing

        resp = self.client.get(f"/v1/companies/{self.company_id}/coa")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["account_code"], "1100")

    def test_confirm_saves_reviewed_accounts(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/coa/confirm",
            json={"accounts": [{"code": "1100", "name": "Cash (edited)", "type": "asset"}]},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["imported"], 1)


class TestCoaImportPdf(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.company = Company(
            id=self.company_id, tenant_id=uuid.uuid4(), name="Test Co",
            business_type="retail", tax_id="0100000000001", is_active=True,
        )
        self.session = FakeAsyncSession(company=self.company)

        async def fake_get_db():
            yield self.session

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

    def test_pdf_upload_returns_preview_without_saving(self) -> None:
        """No real OCR/LLM call — this proves the endpoint wires
        upload -> storage -> extraction -> preview response correctly, and
        that nothing is written to the DB before /confirm is called.
        """
        fake_preview = [{"code": "1100", "name": "Cash", "type": "asset", "confidence": 90}]
        with patch(
            "src.backend.api.coa.store_document_bytes",
            return_value={"storage_key": "k", "sha256": "abc", "provider": "local"},
        ), patch(
            "src.backend.api.coa.materialize_local_cache", return_value="/tmp/fake.pdf"
        ), patch(
            "src.backend.api.coa.extract_coa_preview_from_pdf", return_value=fake_preview
        ) as mock_extract:
            resp = self.client.post(
                f"/v1/companies/{self.company_id}/coa/import-pdf",
                files={"file": ("coa.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["accounts"], fake_preview)
        self.assertEqual(len(self.session.added), 0)  # nothing persisted yet
        mock_extract.assert_called_once()

    def test_unknown_company_returns_404(self) -> None:
        self.session.company = None
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/coa/import-pdf",
            files={"file": ("coa.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
        )
        self.assertEqual(resp.status_code, 404)


class FakeAsyncResult:
    def __init__(self, state: str, result=None, info=None):
        self.state = state
        self.result = result
        self.info = info


class TestCoaImportPdfAsync(unittest.TestCase):
    """Async COA PDF extraction start/poll endpoints (W4-SIT-E2E-COA-ASYNC-10)."""

    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.company = Company(
            id=self.company_id, tenant_id=uuid.uuid4(), name="Test Co",
            business_type="retail", tax_id="0100000000001", is_active=True,
        )
        self.session = FakeAsyncSession(company=self.company)

        async def fake_get_db():
            yield self.session

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

    def test_start_returns_task_id_without_running_extraction(self) -> None:
        with patch(
            "src.backend.api.coa.store_document_bytes",
            return_value={"storage_key": "t/c/2026/07/abc.pdf", "sha256": "abc", "provider": "minio"},
        ), patch(
            "src.backend.api.coa.materialize_local_cache", return_value="/tmp/fake.pdf"
        ), patch.object(
            coa_module.extract_coa_pdf, "delay", return_value=SimpleNamespace(id="task-abc")
        ) as mock_delay:
            resp = self.client.post(
                f"/v1/companies/{self.company_id}/coa/import-pdf-async",
                files={"file": ("coa.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
            )

        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        self.assertEqual(body["task_id"], "task-abc")
        self.assertEqual(body["status"], "queued")
        self.assertEqual(len(self.session.added), 0)  # nothing persisted
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs["company_id"], str(self.company_id))
        self.assertEqual(kwargs["storage_key"], "t/c/2026/07/abc.pdf")
        self.assertEqual(kwargs["sha256"], "abc")

    def test_start_rejects_non_pdf(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/coa/import-pdf-async",
            files={"file": ("coa.csv", io.BytesIO(b"a,b"), "text/csv")},
        )
        self.assertEqual(resp.status_code, 400)

    def _get_status(self, task_id: str = "task-abc"):
        return self.client.get(
            f"/v1/companies/{self.company_id}/coa/import-pdf-async/{task_id}"
        )

    def test_status_queued_for_pending_task(self) -> None:
        with patch("src.backend.api.coa.AsyncResult", return_value=FakeAsyncResult("PENDING")):
            resp = self._get_status()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "queued")

    def test_status_running_with_progress_stage(self) -> None:
        fake = FakeAsyncResult("PROGRESS", info={"stage": "llm"})
        with patch("src.backend.api.coa.AsyncResult", return_value=fake):
            resp = self._get_status()
        body = resp.json()
        self.assertEqual(body["status"], "running")
        self.assertEqual(body["stage"], "llm")

    def test_status_succeeded_returns_review_accounts(self) -> None:
        fake = FakeAsyncResult(
            "SUCCESS",
            result={
                "company_id": str(self.company_id),
                "company_name_detected": "Test Co",
                "accounts": [{"code": "1100", "name": "Cash", "type": "asset", "confidence": 88}],
            },
        )
        with patch("src.backend.api.coa.AsyncResult", return_value=fake):
            resp = self._get_status()
        body = resp.json()
        self.assertEqual(body["status"], "succeeded")
        self.assertEqual(body["accounts"][0]["code"], "1100")
        self.assertEqual(body["company_name_detected"], "Test Co")
        self.assertEqual(len(self.session.added), 0)  # review-before-save: still nothing persisted

    def test_status_succeeded_for_other_company_is_404(self) -> None:
        fake = FakeAsyncResult(
            "SUCCESS",
            result={"company_id": str(uuid.uuid4()), "accounts": []},
        )
        with patch("src.backend.api.coa.AsyncResult", return_value=fake):
            resp = self._get_status()
        self.assertEqual(resp.status_code, 404)

    def test_status_failed_reports_error(self) -> None:
        fake = FakeAsyncResult("FAILURE", result=RuntimeError("LLM extraction returned no chart_of_accounts rows."))
        with patch("src.backend.api.coa.AsyncResult", return_value=fake):
            resp = self._get_status()
        body = resp.json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("chart_of_accounts", body["error"])


if __name__ == "__main__":
    unittest.main()
