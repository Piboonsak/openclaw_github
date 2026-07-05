"""First-login flow: must_change_password + /auth/change-password + require_password_finalized.

Covers the SIT-default admin/admin case where the first successful login
signals the client to force a password change before any protected endpoint
becomes usable.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.backend.auth import router as auth_router_module
from src.backend.auth.auth import hash_password, verify_password
from src.backend.auth.dependencies import (
    get_current_active_user,
    require_password_finalized,
)
from src.backend.auth.router import router
from src.backend.db.session import get_db


class DummyAsyncSession:
    async def flush(self) -> None:
        return None


def _build_first_login_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="admin@ledgerflow.local",
        username="admin",
        password_hash=hash_password("admin"),
        display_name="System Admin",
        role="admin",
        is_active=True,
        must_change_password=True,
        last_login=None,
    )


def _create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")

    @app.get("/api/protected", tags=["_test"])
    async def protected_route(
        _user=Depends(require_password_finalized),  # noqa: ANN001
    ) -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_login_returns_must_change_password_flag_true(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_find_user_by_login(db, username):  # noqa: ANN001
        return user if username == "admin" else None

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        auth_router_module, "_find_user_by_login", fake_find_user_by_login
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["must_change_password"] is True
    assert body["access_token"]


def test_protected_endpoint_blocked_when_must_change_password(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user

    response = client.get("/api/protected")

    assert response.status_code == 428
    detail = response.json()["detail"]
    assert detail["code"] == "MUST_CHANGE_PASSWORD"


def test_change_password_success_clears_flag(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user

    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin", "new_password": "NewPass1234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["user"]["must_change_password"] is False
    assert user.must_change_password is False
    assert verify_password("NewPass1234", user.password_hash)


def test_change_password_rejects_wrong_old_password(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user

    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrong", "new_password": "NewPass1234"},
    )

    assert response.status_code == 401
    assert user.must_change_password is True


def test_change_password_rejects_weak_new_password(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user

    # Too short
    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin", "new_password": "abc12"},
    )
    assert response.status_code == 400

    # No digit
    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin", "new_password": "onlyletters"},
    )
    assert response.status_code == 400

    # Same as old
    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin", "new_password": "admin"},
    )
    assert response.status_code == 400

    assert user.must_change_password is True


def test_real_admin_router_enforces_password_finalized() -> None:
    """Confirms the wiring in `src/backend/app/endpoints.py` — not just the
    dependency function in isolation. Previously `require_password_finalized`
    was written but never attached to any real route, so a first-login user
    with a temp password had full, permanent app access.
    """
    from src.backend.app import endpoints as endpoints_module
    from src.backend.db.session import get_db as real_get_db

    app = FastAPI()
    app.include_router(endpoints_module.router, prefix="/api")

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        async def execute(self, _stmt):
            return FakeResult()

    async def fake_get_db():
        yield FakeSession()

    user = _build_first_login_user()

    async def fake_current_user():
        return user

    app.dependency_overrides[real_get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user
    client = TestClient(app)

    blocked = client.get("/api/v1/admin/companies")
    assert blocked.status_code == 428
    assert blocked.json()["detail"]["code"] == "MUST_CHANGE_PASSWORD"

    user.must_change_password = False
    allowed = client.get("/api/v1/admin/companies")
    assert allowed.status_code == 200


def test_protected_endpoint_allowed_after_change_password(monkeypatch) -> None:
    app = _create_app()
    client = TestClient(app)
    user = _build_first_login_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user

    change = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin", "new_password": "NewPass1234"},
    )
    assert change.status_code == 200

    response = client.get("/api/protected")
    assert response.status_code == 200
    assert response.json() == {"ok": "yes"}
