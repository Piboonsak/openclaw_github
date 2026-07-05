"""Tests for Mapping Rules API endpoints (TASK-1203 company settings
document-ingestion workflow)."""

from __future__ import annotations

import io
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.api.mapping_rules import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import AccountMappingRule, Company
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
    def __init__(self, *, company: Company | None = None, rules=None):
        self.company = company
        self.rules_by_key: dict[tuple, AccountMappingRule] = {
            (r.company_id, r.vendor_name, r.document_type): r for r in (rules or [])
        }
        self.deleted: list = []

    async def get(self, model, key):
        if model is Company:
            return self.company if self.company and self.company.id == key else None
        if model is AccountMappingRule:
            for r in self.rules_by_key.values():
                if r.id == key:
                    return r
        return None

    async def execute(self, _stmt):
        return FakeResult(self.rules_by_key.values())

    def add(self, obj):
        if isinstance(obj, AccountMappingRule):
            self.rules_by_key[(obj.company_id, obj.vendor_name, obj.document_type)] = obj

    async def delete(self, obj):
        self.deleted.append(obj)
        key = next(k for k, v in self.rules_by_key.items() if v is obj)
        del self.rules_by_key[key]

    async def flush(self):
        return None

    async def refresh(self, _obj):
        return None

    async def scalars(self, _stmt):
        return []


class TestMappingRulesCrud(unittest.TestCase):
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

    def test_create_rule_manually(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/mapping-rules",
            json={
                "vendor_name": "OfficeMate",
                "document_type": "Invoice",
                "recommended_debit_code": "5100",
                "recommended_account_name": "Office Supplies",
            },
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["vendor_name"], "OfficeMate")
        self.assertEqual(body["confirmed_count"], 1)

    def test_list_rules(self) -> None:
        rule = AccountMappingRule(
            id=uuid.uuid4(), company_id=self.company_id, vendor_name="OfficeMate",
            document_type="Invoice", recommended_debit_code="5100",
            recommended_account_name="Office Supplies", confirmed_count=3,
        )
        self.session.rules_by_key[(self.company_id, "OfficeMate", "Invoice")] = rule

        resp = self.client.get(f"/v1/companies/{self.company_id}/mapping-rules")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["confirmed_count"], 3)

    def test_update_rule(self) -> None:
        rule = AccountMappingRule(
            id=uuid.uuid4(), company_id=self.company_id, vendor_name="OfficeMate",
            document_type="Invoice", recommended_debit_code="5100",
            recommended_account_name="Office Supplies", confirmed_count=1,
        )
        self.session.rules_by_key[(self.company_id, "OfficeMate", "Invoice")] = rule

        resp = self.client.put(
            f"/v1/companies/{self.company_id}/mapping-rules/{rule.id}",
            json={
                "vendor_name": "OfficeMate",
                "document_type": "Invoice",
                "recommended_debit_code": "5200",
                "recommended_account_name": "Selling Expense",
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["recommended_debit_code"], "5200")

    def test_delete_rule(self) -> None:
        rule = AccountMappingRule(
            id=uuid.uuid4(), company_id=self.company_id, vendor_name="OfficeMate",
            document_type="Invoice", confirmed_count=1,
        )
        self.session.rules_by_key[(self.company_id, "OfficeMate", "Invoice")] = rule

        resp = self.client.delete(f"/v1/companies/{self.company_id}/mapping-rules/{rule.id}")

        self.assertEqual(resp.status_code, 204)
        self.assertEqual(len(self.session.rules_by_key), 0)

    def test_delete_missing_rule_404(self) -> None:
        resp = self.client.delete(f"/v1/companies/{self.company_id}/mapping-rules/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)


class TestMappingRulesDocxImport(unittest.TestCase):
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

    def test_docx_upload_returns_preview_without_saving(self) -> None:
        fake_rules = [
            {
                "vendor_name": "OfficeMate",
                "document_type": "Invoice",
                "recommended_debit_code": "5100",
                "recommended_account_name": "Office Supplies",
            }
        ]
        with patch(
            "src.backend.api.mapping_rules.store_document_bytes",
            return_value={"storage_key": "k", "sha256": "abc", "provider": "local"},
        ), patch(
            "src.backend.api.mapping_rules.materialize_local_cache", return_value="/tmp/fake.docx"
        ), patch(
            "src.backend.api.mapping_rules.extract_mapping_rules_preview_from_docx",
            return_value=(fake_rules, "extracted text preview"),
        ) as mock_extract:
            resp = self.client.post(
                f"/v1/companies/{self.company_id}/mapping-rules/import-docx",
                files={"file": ("mapping.docx", io.BytesIO(b"PK\x03\x04fake"), "application/vnd.openxmlformats")},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["rules"], fake_rules)
        self.assertEqual(len(self.session.rules_by_key), 0)  # nothing persisted yet
        mock_extract.assert_called_once()

    def test_confirm_saves_reviewed_rules(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/mapping-rules/confirm",
            json={
                "rules": [
                    {
                        "vendor_name": "OfficeMate",
                        "document_type": "Invoice",
                        "recommended_debit_code": "5100",
                        "recommended_account_name": "Office Supplies",
                    }
                ]
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(len(self.session.rules_by_key), 1)

    def test_rejects_non_docx_extension(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/mapping-rules/import-docx",
            files={"file": ("mapping.pdf", io.BytesIO(b"whatever"), "application/pdf")},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
