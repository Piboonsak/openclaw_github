from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app import endpoints as endpoints_module
from src.backend.app.health import ServiceHealth


def create_test_app() -> FastAPI:
    app = FastAPI(version="2.0.0")
    app.include_router(endpoints_module.router, prefix="/api")
    return app


def test_health_endpoint_returns_status(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(
        endpoints_module,
        "collect_service_health",
        lambda: ServiceHealth(db="ok", redis="ok", minio="ok"),
    )
    monkeypatch.setattr(endpoints_module, "get_uptime_seconds", lambda: 12.3)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["services"]["db"] == "ok"


def test_health_status_codes(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(
        endpoints_module,
        "collect_service_health",
        lambda: ServiceHealth(db="ok", redis="error", minio="ok"),
    )
    monkeypatch.setattr(endpoints_module, "get_uptime_seconds", lambda: 1.0)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_readiness_fails_without_db(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(
        endpoints_module,
        "collect_service_health",
        lambda: ServiceHealth(db="error", redis="ok", minio="ok"),
    )
    monkeypatch.setattr(endpoints_module, "get_uptime_seconds", lambda: 2.0)

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["services"]["db"] == "error"


def test_health_includes_metadata(monkeypatch) -> None:
    app = create_test_app()
    client = TestClient(app)
    monkeypatch.setattr(
        endpoints_module,
        "collect_service_health",
        lambda: ServiceHealth(db="ok", redis="ok", minio="ok"),
    )
    monkeypatch.setattr(endpoints_module, "get_uptime_seconds", lambda: 45.6)

    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0"
    assert response.json()["uptime_seconds"] == 45.6
