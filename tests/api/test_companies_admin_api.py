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
from src.backend.auth.dependencies import (
    get_current_active_user,
    get_user_company_ids,
    require_admin,
    require_sys_admin,
)
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
        self.settings = kwargs.get("settings") or {}
        self.is_active = kwargs.get("is_active", True)


class FakeAsyncSession:
    def __init__(self, *, companies=None, tenant=None, raise_on_flush=None, assigned_company_ids=None):
        self.companies_by_id = {c.id: c for c in (companies or [])}
        self.tenant = tenant or SimpleNamespace(id=uuid.uuid4())
        self.added = []
        self.raise_on_flush = raise_on_flush
        # None = no staff-scoping test in play (execute() returns everything).
        # A list = simulates the `.where(Company.id.in_(assigned))` filter that
        # list_companies applies once it has already called get_user_company_ids.
        self.assigned_company_ids = assigned_company_ids

    async def execute(self, _stmt):
        if self.assigned_company_ids is not None:
            allowed = set(self.assigned_company_ids)
            return FakeResult(
                [c for c in self.companies_by_id.values() if c.id in allowed]
            )
        return FakeResult(self.companies_by_id.values())

    async def scalar(self, _stmt):
        return self.tenant

    async def scalars(self, _stmt):
        return list(self.assigned_company_ids or [])

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


def _staff_user():
    return SimpleNamespace(id=uuid.uuid4(), username="staff1", role="staff")


def _sys_admin_user():
    return SimpleNamespace(id=uuid.uuid4(), username="sysadmin1", role="sys_admin")


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


class TestListCompaniesScoping(unittest.TestCase):
    """ac_1204_staff_scope / ac_1204_admin_scope (RWG-02 real-workflow finding):
    GET /v1/admin/companies previously ignored role entirely and returned every
    active company to any authenticated user, so a staff user assigned to one
    company could see every other tenant's companies too.
    """

    def test_admin_sees_every_company_regardless_of_assignment(self):
        app = _build_app()
        client = TestClient(app)
        company_a = FakeCompany(name="A Co", tax_id="0105560123456")
        company_b = FakeCompany(name="B Co", tax_id="0105560999999")
        session = FakeAsyncSession(companies=[company_a, company_b])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

        response = client.get("/v1/admin/companies")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_sys_admin_sees_every_company_regardless_of_assignment(self):
        app = _build_app()
        client = TestClient(app)
        company_a = FakeCompany(name="A Co", tax_id="0105560123456")
        company_b = FakeCompany(name="B Co", tax_id="0105560999999")
        session = FakeAsyncSession(companies=[company_a, company_b])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = lambda: _sys_admin_user()

        response = client.get("/v1/admin/companies")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_staff_sees_only_assigned_companies(self):
        app = _build_app()
        client = TestClient(app)
        assigned = FakeCompany(name="Assigned Co", tax_id="0105560123456")
        unassigned = FakeCompany(name="Other Co", tax_id="0105560999999")
        session = FakeAsyncSession(
            companies=[assigned, unassigned],
            assigned_company_ids=[assigned.id],
        )

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = lambda: _staff_user()

        response = client.get("/v1/admin/companies")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "Assigned Co")

    def test_staff_with_no_assignments_sees_empty_list_not_everything(self):
        app = _build_app()
        client = TestClient(app)
        session = FakeAsyncSession(
            companies=[FakeCompany(name="Other Co", tax_id="0105560999999")],
            assigned_company_ids=[],
        )

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = lambda: _staff_user()

        response = client.get("/v1/admin/companies")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class TestCreateCompany(unittest.TestCase):
    """Company create is sys_admin-only (EPIC-12 TASK-1204 role table: "Admin
    can edit, not create") — ac_1204_sysadmin / TC-RWG02-10.
    """

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
        app.dependency_overrides[require_sys_admin] = lambda: _sys_admin_user()

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

    def test_create_persists_enable_stock_setting(self):
        """HR-18 (FOLLOWUP-22): the company-level line-item/stock toggle must
        round-trip through Company.settings, not be a UI-only value."""
        app = FastAPI()
        from src.backend.api import companies_admin as module

        app.include_router(module.router)
        client = TestClient(app)
        session = FakeAsyncSession(companies=[])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_sys_admin] = lambda: _sys_admin_user()

        response = client.post(
            "/v1/admin/companies",
            json={
                "name": "Stock Co",
                "tax_id": "0107561234567",
                "settings": {"enable_stock": True},
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["settings"], {"enable_stock": True})
        self.assertEqual(session.added[0].settings, {"enable_stock": True})

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
        app.dependency_overrides[require_sys_admin] = lambda: _sys_admin_user()

        response = client.post(
            "/v1/admin/companies",
            json={"name": "Dup Co", "tax_id": "0105560123456"},
        )

        self.assertEqual(response.status_code, 409)

    def test_admin_is_denied_create_only_sys_admin_can(self):
        """Admin passes `require_admin` elsewhere in this router (list/update)
        but must NOT satisfy `require_sys_admin` here — confirms the two
        dependencies are genuinely distinct, not aliases of each other.
        """
        app = FastAPI()
        from src.backend.api import companies_admin as module

        app.include_router(module.router)
        client = TestClient(app)
        session = FakeAsyncSession(companies=[])

        async def fake_get_db():
            yield session

        async def fake_current_user():
            return _admin_user()

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = fake_current_user

        response = client.post(
            "/v1/admin/companies",
            json={"name": "New Co", "tax_id": "0107561234567"},
        )

        self.assertEqual(response.status_code, 403)


class TestDeleteCompany(unittest.TestCase):
    def test_sys_admin_can_soft_delete(self):
        app = _build_app()
        client = TestClient(app)
        existing = FakeCompany(name="To Delete", tax_id="0105560123456")
        session = FakeAsyncSession(companies=[existing])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_sys_admin] = lambda: _sys_admin_user()

        response = client.delete(f"/v1/admin/companies/{existing.id}")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(existing.is_active)

    def test_admin_is_denied_delete(self):
        app = _build_app()
        client = TestClient(app)
        existing = FakeCompany(name="To Delete", tax_id="0105560123456")
        session = FakeAsyncSession(companies=[existing])

        async def fake_get_db():
            yield session

        async def fake_current_user():
            return _admin_user()

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[get_current_active_user] = fake_current_user

        response = client.delete(f"/v1/admin/companies/{existing.id}")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(existing.is_active)

    def test_missing_company_returns_404(self):
        app = _build_app()
        client = TestClient(app)
        session = FakeAsyncSession(companies=[])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_sys_admin] = lambda: _sys_admin_user()

        response = client.delete(f"/v1/admin/companies/{uuid.uuid4()}")

        self.assertEqual(response.status_code, 404)


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

    def test_update_merges_settings_without_dropping_existing_keys(self):
        """HR-18 (FOLLOWUP-22): toggling enable_stock via PUT must not wipe
        other keys already stored in Company.settings."""
        app = _build_app()
        client = TestClient(app)
        existing = FakeCompany(
            name="Metro", tax_id="0105560123456", settings={"other_flag": True}
        )
        session = FakeAsyncSession(companies=[existing])

        async def fake_get_db():
            yield session

        app.dependency_overrides[get_db] = fake_get_db
        app.dependency_overrides[require_admin] = lambda: _admin_user()

        response = client.put(
            f"/v1/admin/companies/{existing.id}",
            json={"settings": {"enable_stock": True}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["settings"], {"other_flag": True, "enable_stock": True}
        )
        self.assertEqual(existing.settings, {"other_flag": True, "enable_stock": True})

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
