from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from src.backend.db.enums import DocumentStatus
from src.backend.workers.celery_app import celery_app
from src.backend.workers.tasks import process_document


@dataclass
class DummyDocument:
    id: uuid.UUID
    status: str = DocumentStatus.UPLOADED.value
    processing_error: str | None = None


class DummySession:
    def __init__(self, documents: dict[uuid.UUID, DummyDocument]) -> None:
        self.documents = documents

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def get(self, model, document_id: uuid.UUID):  # noqa: ANN001
        return self.documents.get(document_id)

    def add(self, document: DummyDocument) -> None:
        self.documents[document.id] = document

    def commit(self) -> None:
        return None


@pytest.fixture
def eager_mode(monkeypatch):
    old_always = celery_app.conf.task_always_eager
    old_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = old_always
        celery_app.conf.task_eager_propagates = old_propagates


def _install_session_factory(monkeypatch, documents: dict[uuid.UUID, DummyDocument]) -> None:
    def _factory():
        return lambda: DummySession(documents)

    monkeypatch.setattr("src.backend.workers.tasks.get_sync_session_factory", _factory)


def test_status_processing_on_start(monkeypatch, eager_mode) -> None:
    doc_id = uuid.uuid4()
    documents = {doc_id: DummyDocument(id=doc_id)}
    _install_session_factory(monkeypatch, documents)

    def fake_pipeline(document: DummyDocument) -> dict[str, Any]:
        assert documents[doc_id].status == DocumentStatus.PROCESSING.value
        return {"ok": True}

    monkeypatch.setattr("src.backend.workers.tasks._run_pipeline_stub", fake_pipeline)

    result = process_document.delay(str(doc_id))

    assert result.successful()


def test_status_review_scan_on_complete(monkeypatch, eager_mode) -> None:
    doc_id = uuid.uuid4()
    documents = {doc_id: DummyDocument(id=doc_id)}
    _install_session_factory(monkeypatch, documents)

    monkeypatch.setattr(
        "src.backend.workers.tasks._run_pipeline_stub",
        lambda document: {"ok": True},
    )

    result = process_document.delay(str(doc_id))

    assert result.successful()
    assert documents[doc_id].status == DocumentStatus.REVIEW_SCAN.value
    assert documents[doc_id].processing_error is None


def test_task_failure_sets_error_status(monkeypatch) -> None:
    doc_id = uuid.uuid4()
    documents = {doc_id: DummyDocument(id=doc_id)}
    _install_session_factory(monkeypatch, documents)

    old_always = celery_app.conf.task_always_eager
    old_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False

    try:
        def fail_pipeline(document: DummyDocument) -> dict[str, Any]:
            raise RuntimeError("pipeline failed")

        monkeypatch.setattr("src.backend.workers.tasks._run_pipeline_stub", fail_pipeline)

        result = process_document.delay(str(doc_id))

        assert result.failed()
        assert documents[doc_id].status == "error"
        assert documents[doc_id].processing_error == "pipeline failed"
    finally:
        celery_app.conf.task_always_eager = old_always
        celery_app.conf.task_eager_propagates = old_propagates


def test_task_timeout_config() -> None:
    assert celery_app.conf.task_soft_time_limit == 120
    assert celery_app.conf.task_time_limit == 180
