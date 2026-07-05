"""Tests for company-scoping dependency helpers (TASK-1204 ac_1204_staff_scope).

Covers:
  ac_1204_staff_scope — ensure_company_access blocks staff from company_ids
                        they are not assigned to, and admin bypasses the check
  ac_1204_admin_scope — admin is never restricted regardless of assignments
"""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

from src.backend.auth.dependencies import ensure_company_access


class FakeScalarsResult:
    def __init__(self, items):
        self._items = list(items)

    def __await__(self):
        async def _coro():
            return self._items

        return _coro().__await__()


class FakeAssignmentSession:
    """Minimal async session stub for get_user_company_ids's `db.scalars(...)` call."""

    def __init__(self, assigned_company_ids: list[uuid.UUID]):
        self._assigned = assigned_company_ids

    async def scalars(self, _stmt):
        return self._assigned


def _user(role: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), role=role)


class TestEnsureCompanyAccess(unittest.IsolatedAsyncioTestCase):
    async def test_admin_bypasses_assignment_check(self):
        db = FakeAssignmentSession([])  # admin has zero assignments, still allowed
        await ensure_company_access(db, _user("admin"), uuid.uuid4())  # must not raise

    async def test_staff_with_assignment_is_allowed(self):
        company_id = uuid.uuid4()
        db = FakeAssignmentSession([company_id])
        await ensure_company_access(db, _user("staff"), company_id)  # must not raise

    async def test_staff_without_assignment_is_blocked(self):
        company_id = uuid.uuid4()
        other_company_id = uuid.uuid4()
        db = FakeAssignmentSession([other_company_id])
        with self.assertRaises(HTTPException) as ctx:
            await ensure_company_access(db, _user("staff"), company_id)
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_staff_with_no_assignments_at_all_is_blocked(self):
        db = FakeAssignmentSession([])
        with self.assertRaises(HTTPException) as ctx:
            await ensure_company_access(db, _user("staff"), uuid.uuid4())
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
