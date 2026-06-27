from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app import endpoints as endpoints_module
from src.backend.app.endpoints import router
from src.backend.auth.dependencies import get_current_active_user


class DummyAsyncResult:
    def __init__(self, state: str, result):  # noqa: ANN001
        self.state = state
        self.result = result

    def successful(self) -> bool:
        return self.state == "SUCCESS"

    def failed(self) -> bool:
        return self.state == "FAILURE"


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def fake_current_user():
        return SimpleNamespace(id="u-1", is_active=True)

    app.dependency_overrides[get_current_active_user] = fake_current_user
    return app


def test_task_status_queryable_success(monkeypatch) -> None:
    app = _create_test_app()
    client = TestClient(app)

    monkeypatch.setattr(
        endpoints_module,
        "AsyncResult",
        lambda task_id, app: DummyAsyncResult("SUCCESS", {"ok": True}),
    )

    response = client.get("/api/v1/tasks/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "success",
        "result": {"ok": True},
    }


def test_task_status_queryable_failure(monkeypatch) -> None:
    app = _create_test_app()
    client = TestClient(app)

    monkeypatch.setattr(
        endpoints_module,
        "AsyncResult",
        lambda task_id, app: DummyAsyncResult("FAILURE", RuntimeError("boom")),
    )

    response = client.get("/api/v1/tasks/task-456")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-456",
        "status": "failure",
        "result": "boom",
    }


def test_enqueue_document_processing(monkeypatch) -> None:
    app = _create_test_app()
    client = TestClient(app)

    monkeypatch.setattr(
        endpoints_module.process_document,
        "delay",
        lambda document_id: SimpleNamespace(id="task-queued-1"),
    )

    response = client.post("/api/v1/tasks/process-document/doc-001")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-queued-1",
        "status": "pending",
        "document_id": "doc-001",
    }
