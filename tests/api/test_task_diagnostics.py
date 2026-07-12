"""Tests for the processing worker/queue diagnostics endpoint
(W5-CLAUDE-OCR-PENDING-STALL-FIX-08).

The endpoint makes an OCR pending-stall diagnosable: it must report a live
worker count when workers respond and clearly flag "no worker / broker
unreachable" (worker_count == 0, broker_reachable == False) so a permanent
`pending` can be told apart from a task that is merely queued.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.backend.app import endpoints


def _call() -> dict:
    return asyncio.run(endpoints.get_task_diagnostics(_current_user=SimpleNamespace()))


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
