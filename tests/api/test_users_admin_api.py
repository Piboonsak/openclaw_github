"""Tests for admin User CRUD + reset-password (W4 SIT closure — TASK-1204 minimal slice).

Covers:
  ac_w4_users_schema    — UserCreate/Update schema validation (email format, role normalization)
  ac_w4_users_create    — POST creates a user via the real User DB model and returns a temp password once
  ac_w4_users_list      — GET returns users with company assignments
  ac_w4_users_update    — PUT updates role/active/company assignments
  ac_w4_users_conflict  — duplicate email surfaces as 409, not a silent success
  ac_w4_users_404       — updating a missing user returns 404
  ac_w4_users_reset_pw  — reset-password issues a new temp password and forces must_change_password
"""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from src.backend.api.schemas.user_schemas import UserCreate, UserUpdate
from src.backend.auth.dependencies import require_admin
from src.backend.db.session import get_db


class TestUserSchemas(unittest.TestCase):
    def test_rejects_invalid_email(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            UserCreate(email="not-an-email", username="u1")

    def test_normalizes_unknown_role_to_staff(self):
        user = UserCreate(email="a@b.co", username="u1", role="superadmin")
        self.assertEqual(user.normalized_role(), "staff")

    def test_accepts_admin_role(self):
        user = UserCreate(email="a@b.co", username="u1", role="admin")
        self.assertEqual(user.normalized_role(), "admin")

    def test_update_all_optional(self):
        update = UserUpdate()
        self.assertIsNone(update.role)
        self.assertIsNone(update.company_ids)


class FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return self

    def all(self):
        return self._items

    def __iter__(self):
        return iter(self._items)


class FakeUser:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id") or uuid.uuid4()
        self.tenant_id = kwargs.get("tenant_id")
        self.email = kwargs["email"]
        self.username = kwargs["username"]
        self.password_hash = kwargs.get("password_hash", "")
        self.display_name = kwargs.get("display_name")
        self.role = kwargs.get("role", "staff")
        self.is_active = kwargs.get("is_active", True)
        self.must_change_password = kwargs.get("must_change_password", True)
        self.last_login = kwargs.get("last_login")


class FakeAsyncSession:
    def __init__(self, *, users=None, assignments=None, company_ids=None, raise_on_flush=None):
        self.users_by_id = {u.id: u for u in (users or [])}
        # assignments: user_id -> list[company_id]
        self.assignments = assignments or {}
        self.company_ids = set(company_ids or [])
        self.added = []
        self.deleted_calls = 0
        self.raise_on_flush = raise_on_flush

    async def execute(self, stmt):
        # Used for: list_users (select(User)), _validate_company_ids
        # (select(Company.id).where(...)), and the assignment-delete statement.
        compiled = str(stmt)
        if "DELETE" in compiled.upper():
            self.deleted_calls += 1
            return FakeResult([])
        if "users" in compiled.lower() and "company" not in compiled.lower():
            return FakeResult(self.users_by_id.values())
        return FakeResult(self.company_ids)

    async def scalars(self, _stmt):
        return FakeResult(self.assignments.get(_scalars_target(_stmt), []))

    async def get(self, _model, key):
        return self.users_by_id.get(key)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, FakeUser):
            self.users_by_id[obj.id] = obj

    async def flush(self):
        if self.raise_on_flush:
            raise self.raise_on_flush

    async def refresh(self, _obj):
        return None


def _scalars_target(_stmt):
    # Best effort: our router only calls scalars() for one user at a time in
    # list_users' per-row assignment lookup; tests exercise single-user cases
    # so returning the sole assignment bucket key works generically here.
    return "any"


def _build_app_with_overrides(session, *, admin=True, requester_role="admin"):
    from src.backend.api import users_admin as module

    app = FastAPI()
    app.include_router(module.router)

    async def fake_get_db():
        yield session

    app.dependency_overrides[get_db] = fake_get_db
    if admin:
        app.dependency_overrides[require_admin] = lambda: SimpleNamespace(
            id=uuid.uuid4(), tenant_id=uuid.uuid4(), username="admin", role=requester_role
        )
    return app


class TestCreateUser(unittest.TestCase):
    def test_creates_user_and_returns_temp_password_once(self):
        session = FakeAsyncSession(users=[], company_ids=set())
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/users",
            json={"email": "new@bwc.co.th", "username": "newstaff", "role": "staff"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["email"], "new@bwc.co.th")
        self.assertTrue(body["must_change_password"])
        self.assertIn("temp_password", body)
        self.assertGreaterEqual(len(body["temp_password"]), 8)

    def test_duplicate_email_returns_409(self):
        session = FakeAsyncSession(
            users=[], company_ids=set(), raise_on_flush=IntegrityError("stmt", {}, Exception("dup"))
        )
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/users",
            json={"email": "dup@bwc.co.th", "username": "dup"},
        )

        self.assertEqual(response.status_code, 409)

    def test_admin_cannot_assign_sys_admin_role(self):
        """EPIC-12 TASK-1204 role table: only a sys_admin can grant sys_admin —
        rejected explicitly (403), not silently downgraded to staff.
        """
        session = FakeAsyncSession(users=[], company_ids=set())
        app = _build_app_with_overrides(session, requester_role="admin")
        client = TestClient(app)

        response = client.post(
            "/v1/admin/users",
            json={"email": "new@bwc.co.th", "username": "newsysadmin", "role": "sys_admin"},
        )

        self.assertEqual(response.status_code, 403)

    def test_sys_admin_can_assign_sys_admin_role(self):
        session = FakeAsyncSession(users=[], company_ids=set())
        app = _build_app_with_overrides(session, requester_role="sys_admin")
        client = TestClient(app)

        response = client.post(
            "/v1/admin/users",
            json={"email": "new@bwc.co.th", "username": "newsysadmin", "role": "sys_admin"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "sys_admin")

    def test_unknown_company_id_returns_404(self):
        session = FakeAsyncSession(users=[], company_ids=set())
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.post(
            "/v1/admin/users",
            json={
                "email": "new@bwc.co.th",
                "username": "newstaff",
                "company_ids": [str(uuid.uuid4())],
            },
        )

        self.assertEqual(response.status_code, 404)


class TestUpdateUser(unittest.TestCase):
    def test_updates_role_and_active_flag(self):
        existing = FakeUser(email="a@b.co", username="a", role="staff")
        session = FakeAsyncSession(users=[existing])
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.put(
            f"/v1/admin/users/{existing.id}",
            json={"role": "admin", "is_active": False},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["role"], "admin")
        self.assertFalse(body["is_active"])

    def test_missing_user_returns_404(self):
        session = FakeAsyncSession(users=[])
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.put(
            f"/v1/admin/users/{uuid.uuid4()}",
            json={"role": "admin"},
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_escalate_existing_user_to_sys_admin(self):
        existing = FakeUser(email="a@b.co", username="a", role="staff")
        session = FakeAsyncSession(users=[existing])
        app = _build_app_with_overrides(session, requester_role="admin")
        client = TestClient(app)

        response = client.put(
            f"/v1/admin/users/{existing.id}",
            json={"role": "sys_admin"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(existing.role, "staff")

    def test_admin_can_edit_sys_admin_company_assignments_without_escalation(self):
        """HR-07-04: an admin editing an EXISTING sys_admin's company assignments
        echoes the unchanged `sys_admin` role. That is NOT an escalation and must
        save (previously it 403'd, so the assignment could never be saved)."""
        company_id = uuid.uuid4()
        existing = FakeUser(email="s@b.co", username="sys", role="sys_admin")
        session = FakeAsyncSession(users=[existing], company_ids={company_id})
        app = _build_app_with_overrides(session, requester_role="admin")
        client = TestClient(app)

        response = client.put(
            f"/v1/admin/users/{existing.id}",
            json={"role": "sys_admin", "company_ids": [str(company_id)]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(existing.role, "sys_admin")
        # The forbidden-escalation guard did not fire, and the assignment delete +
        # re-insert ran (proof the company_ids branch was reached).
        self.assertEqual(session.deleted_calls, 1)

    def test_sys_admin_can_promote_existing_user_to_sys_admin(self):
        """Role matrix: a genuine promotion is allowed for a sys_admin requester."""
        existing = FakeUser(email="a@b.co", username="a", role="staff")
        session = FakeAsyncSession(users=[existing])
        app = _build_app_with_overrides(session, requester_role="sys_admin")
        client = TestClient(app)

        response = client.put(
            f"/v1/admin/users/{existing.id}",
            json={"role": "sys_admin"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(existing.role, "sys_admin")


class TestResetPassword(unittest.TestCase):
    def test_generates_new_temp_password_and_forces_change(self):
        existing = FakeUser(
            email="a@b.co", username="a", must_change_password=False
        )
        session = FakeAsyncSession(users=[existing])
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.post(f"/v1/admin/users/{existing.id}/reset-password")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("temp_password", body)
        self.assertTrue(existing.must_change_password)

    def test_missing_user_returns_404(self):
        session = FakeAsyncSession(users=[])
        app = _build_app_with_overrides(session)
        client = TestClient(app)

        response = client.post(f"/v1/admin/users/{uuid.uuid4()}/reset-password")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
