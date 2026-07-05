"""Tests for admin Company CRUD (W4 SIT closure — TASK-1203 minimal slice).

Covers:
  ac_w4_companies_schema  — CompanyCreate/Update schema validation (tax_id digits, branch_code padding)
  ac_w4_companies_create  — POST creates a company via the real Company DB model
  ac_w4_companies_list    — GET returns active companies
  ac_w4_companies_update  — PUT updates an existing company
  ac_w4_companies_conflict — duplicate tax_id surfaces as 409, not a silent success
  ac_w4_companies_404     — updating a missing company returns 404
"""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from src.backend.api.companies_admin import router
from src.backend.api.schemas.company_schemas import CompanyCreate, CompanyUpdate
from src.backend.auth.dependencies import get_current_active_user, require_admin
from src.backend.db.session import get_db


class TestCompanySchemas(unittest.TestCase):
    def test_tax_id_must_be_13_digits(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CompanyCreate(name="Acme", tax_id="123")

    def test_tax_id_strips_non_digits(self):
        company = CompanyCreate(name="Acme", tax_id="0-105-560-123-456")
        self.assertEqual(company.tax_id, "0105560123456")

    def test_branch_code_defaults_and_pads(self):
        company = CompanyCreate(name="Acme", tax_id="0105560123456", branch_code="1")
        self.assertEqual(company.branch_code, "00001")

    def test_update_all_optional(self):
        update = CompanyUpdate()
        self.assertIsNone(update.name)
        self.assertIsNone(update.tax_id)
        self.assertIsNone(update.is_active)


class FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeCompany:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or uuid.uuid4()
        self.tenant_id = kwargs.get("tenant_id")
        self.name = kwargs["name"]
        self.tax_id = kwargs["tax_id"]
        self.branch_code = kwargs.get("branch_code", "00000")
        self.address = kwargs.get("address")
        self.business_type = kwargs.get("business_type")
        self.is_active = kwargs.get("is_active", True)


class FakeAsyncSession:
    def __init__(self, *, companies=None, tenant=None, raise_on_flush=None):
        self.companies_by_id = {c.id: c for c in (companies or [])}
        self.tenant = tenant or SimpleNamespace(id=uuid.uuid4())
        self.added = []
        self.raise_on_flush = raise_on_flush

    async def execute(self, _stmt):
        return FakeResult(self.companies_by_id.values())

    async def scalar(self, _stmt):
        return self.tenant

    async def get(self, _model, key):
        return self.companies_by_id.get(key)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, FakeCompany):
            self.companies_by_id[obj.id] = obj

    async def flush(self):
        if self.raise_on_flush:
            raise self.raise_on_flush

    async def refresh(self, _obj):
        return None


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _admin_user():
    return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")


class TestListCompanies(unittest.TestCase):
    def test_returns_active_companies(self):
        app = _build_app()
        client = TestClient(app)
        existing = FakeCompany(name="Metro", tax_id="0105560123456")
        session = FakeAsyncSession(companies=[existing])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

        response = client.get("/v1/admin/companies")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["tax_id"], "0105560123456")


class TestCreateCompany(unittest.TestCase):
    def test_creates_company_with_default_tenant(self):
        app = FastAPI()
        # companies_admin's own real create_company constructs a real Company()
        # ORM instance directly, so exercise it through the actual model class.
        from src.backend.api import companies_admin as module

        app.include_router(module.router)
        client = TestClient(app)
        session = FakeAsyncSession(companies=[])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_admin] = lambda: _admin_user()

        response = client.post(
            "/v1/admin/companies",
            json={"name": "New Co", "tax_id": "0107561234567", "branch_code": "00000"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "New Co")
        self.assertEqual(body["tax_id"], "0107561234567")
        self.assertTrue(body["is_active"])
        self.assertEqual(len(session.added), 1)

    def test_duplicate_tax_id_returns_409_not_fake_success(self):
        app = FastAPI()
        from src.backend.api import companies_admin as module

        app.include_router(module.router)
        client = TestClient(app)
        session = FakeAsyncSession(
            companies=[], raise_on_flush=IntegrityError("stmt", {}, Exception("dup"))
        )

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_admin] = lambda: _admin_user()

        response = client.post(
            "/v1/admin/companies",
            json={"name": "Dup Co", "tax_id": "0105560123456"},
        )

        self.assertEqual(response.status_code, 409)


class TestUpdateCompany(unittest.TestCase):
    def test_updates_existing_company(self):
        app = _build_app()
        client = TestClient(app)
        existing = FakeCompany(name="Old Name", tax_id="0105560123456")
        session = FakeAsyncSession(companies=[existing])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_admin] = lambda: _admin_user()

        response = client.put(
            f"/v1/admin/companies/{existing.id}",
            json={"name": "Renamed Co"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Renamed Co")
        self.assertEqual(existing.name, "Renamed Co")

    def test_missing_company_returns_404(self):
        app = _build_app()
        client = TestClient(app)
        session = FakeAsyncSession(companies=[])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_admin] = lambda: _admin_user()

        response = client.put(
            f"/v1/admin/companies/{uuid.uuid4()}",
            json={"name": "Nope"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
