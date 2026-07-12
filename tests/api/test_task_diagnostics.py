"""Tests for the processing worker/queue diagnostics endpoint
(W5-CLAUDE-OCR-PENDING-STALL-FIX-08).

The endpoint makes an OCR pending-stall diagnosable: it must report a live
worker count when workers respond and clearly flag "no worker / broker
unreachable" (worker_count == 0, broker_reachable == False) so a permanent
`pending` can be told apart from a task that is merely queued.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app import endpoints
from src.backend.auth.dependencies import get_current_active_user


def _call() -> dict:
    return asyncio.run(endpoints.get_task_diagnostics(_current_user=SimpleNamespace()))


class _FakeAsyncResult:
    """Stand-in so the task-status route needs no live result backend."""

    def __init__(self, task_id, app=None):  # noqa: ANN001
        self.id = task_id
        self.state = "PENDING"

    def successful(self):
        return False

    def failed(self):
        return False

    @property
    def info(self):
        return {}

    @property
    def result(self):
        return None


def _routed_client(monkeypatch, ping) -> TestClient:
    """A TestClient over the real endpoints router — so routing/order is
    exercised, which is what the shadow bug was about."""
    monkeypatch.setattr(endpoints.celery_app.control, "ping", ping)
    monkeypatch.setattr(endpoints, "AsyncResult", _FakeAsyncResult)
    app = FastAPI()
    app.include_router(endpoints.router)
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=uuid.uuid4(), username="admin", role="admin"
    )
    return TestClient(app)


def test_diagnostics_route_is_not_shadowed_by_task_id(monkeypatch) -> None:
    """HR-07-02C: GET /v1/tasks/diagnostics must hit the diagnostics endpoint,
    NOT be captured by /v1/tasks/{task_id} as task_id='diagnostics'. Fails on the
    pre-fix route order (returns the task-status payload instead)."""
    client = _routed_client(monkeypatch, lambda timeout=1.0: [{"celery@w1": {"ok": "pong"}}])
    resp = client.get("/v1/tasks/diagnostics")
    assert resp.status_code == 200
    body = resp.json()
    # Diagnostics shape present...
    assert "worker_count" in body and "broker_reachable" in body and "workers" in body
    assert body["worker_count"] == 1
    # ...and it is NOT the generic task-status payload for task_id="diagnostics".
    assert not (body.get("task_id") == "diagnostics" and "stage" in body)


def test_real_task_id_still_resolves_to_task_status(monkeypatch) -> None:
    """The dynamic route must still serve real task ids (no regression)."""
    client = _routed_client(monkeypatch, lambda timeout=1.0: [])
    task_id = "b274dfc0-2530-4fb5-9b7a-96b06a14b783"
    resp = client.get(f"/v1/tasks/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == task_id
    assert set(body) == {"task_id", "status", "stage", "result"}
    assert "worker_count" not in body


def test_diagnostics_reports_live_workers(monkeypatch) -> None:
    monkeypatch.setattr(
        endpoints.celery_app.control,
        "ping",
        lambda timeout=1.0: [{"celery@w1": {"ok": "pong"}}, {"celery@w2": {"ok": "pong"}}],
    )
    res = _call()
    assert res["broker_reachable"] is True
    assert res["worker_count"] == 2
    assert set(res["workers"]) == {"celery@w1", "celery@w2"}
    # The API side always has the task imported/registered.
    assert res["process_document_registered"] is True


def test_diagnostics_flags_no_worker_when_control_channel_down(monkeypatch) -> None:
    def _boom(timeout=1.0):
        raise OSError("Error 111 connecting to redis: Connection refused")

    monkeypatch.setattr(endpoints.celery_app.control, "ping", _boom)
    res = _call()
    assert res["broker_reachable"] is False
    assert res["worker_count"] == 0
    assert res["workers"] == []
    assert "error" in res


def test_diagnostics_reports_zero_workers_when_none_reply(monkeypatch) -> None:
    """Broker reachable but no worker consuming — the exact pending-stall shape."""
    monkeypatch.setattr(endpoints.celery_app.control, "ping", lambda timeout=1.0: [])
    res = _call()
    assert res["broker_reachable"] is True
    assert res["worker_count"] == 0


def test_diagnostics_eager_mode_short_circuits() -> None:
    original = endpoints.celery_app.conf.task_always_eager
    endpoints.celery_app.conf.task_always_eager = True
    try:
        res = _call()
        assert res["eager"] is True
        assert res["broker_reachable"] is True
    finally:
        endpoints.celery_app.conf.task_always_eager = original
