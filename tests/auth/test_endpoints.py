from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.auth import router as auth_router_module
from src.backend.auth.auth import create_refresh_token, hash_password
from src.backend.auth.dependencies import get_current_active_user
from src.backend.auth.router import router
from src.backend.db.session import get_db


class DummyAsyncSession:
    async def flush(self) -> None:
        return None


def _build_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="admin@example.com",
        username="admin",
        password_hash="",
        display_name="Admin User",
        role="admin",
        is_active=True,
        must_change_password=False,
        last_login=None,
    )


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def test_login_success(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    user = _build_user()
    user.password_hash = hash_password("Password123!")

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
        json={"username": "admin", "password": "Password123!"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_invalid_credentials(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_find_user_by_login(db, username):  # noqa: ANN001
        return None

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        auth_router_module, "_find_user_by_login", fake_find_user_by_login
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "ข้อมูลผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"


def test_me_requires_token() -> None:
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_returns_profile(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    user = _build_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_current_user():
        return user

    async def fake_get_user_company_ids(db, user_id):  # noqa: ANN001
        return ["company-1", "company-2"]

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_active_user] = fake_current_user
    monkeypatch.setattr(
        auth_router_module, "get_user_company_ids", fake_get_user_company_ids
    )

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["company_ids"] == ["company-1", "company-2"]


def test_refresh_returns_new_access_token(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    user = _build_user()

    async def fake_get_db():
        yield DummyAsyncSession()

    async def fake_find_user_by_id(db, user_id):  # noqa: ANN001
        return user if str(user.id) == user_id else None

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(auth_router_module, "_find_user_by_id", fake_find_user_by_id)

    refresh_token = create_refresh_token(str(user.id))
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
