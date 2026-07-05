from __future__ import annotations

import uuid
from typing import Any

import pytest

from config.settings import settings
from src.backend.db.enums import DocumentStatus
from src.backend.db.models import Company, Document
from src.backend.pipeline.orchestrator import PipelineContext
from src.backend.workers.celery_app import celery_app
from src.backend.workers.tasks import process_document


class DummySession:
    def __init__(self, documents: dict[uuid.UUID, Document], companies: dict[uuid.UUID, Company] | None = None) -> None:
        self.documents = documents
        self.companies = companies or {}
        self.added: list[Any] = []

    def __enter__(self) -> "DummySession":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def get(self, model, key):  # noqa: ANN001
        if model is Document:
            return self.documents.get(key)
        if model is Company:
            return self.companies.get(key)
        return None

    def add(self, obj) -> None:  # noqa: ANN001
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, Document):
            self.documents[obj.id] = obj
        self.added.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None


def _install_session_factory(monkeypatch, documents: dict[uuid.UUID, Document], companies: dict[uuid.UUID, Company] | None = None) -> None:
    def _factory():
        return lambda: DummySession(documents, companies)

    monkeypatch.setattr("src.backend.workers.tasks.get_sync_session_factory", _factory)


def _make_document_with_file(monkeypatch, tmp_path) -> Document:
    document = Document(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        filename="INV-001.pdf",
        sha256="deadbeef",
        status=DocumentStatus.UPLOADED.value,
    )
    monkeypatch.setattr(settings, "UPLOAD_ROOT", tmp_path)
    (tmp_path / f"{document.sha256}.pdf").write_bytes(b"%PDF-1.4 fake")
    return document


def _fake_ctx() -> PipelineContext:
    ctx = PipelineContext(source_file="ignored")
    ctx.extraction_output = {
        "fields": {"invoice_number": "INV-001", "invoice_date": "2026-07-01", "total_amount": 1070.0},
        "confidence_per_field": {},
    }
    ctx.journal_output = {"journal_code": "PV", "is_balanced": True, "totals": {"debit": 1070.0, "credit": 1070.0}, "flags": [], "postings": []}
    ctx.overall_confidence = 0.9
    return ctx


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


def test_status_processing_on_start(monkeypatch, eager_mode, tmp_path) -> None:
    document = _make_document_with_file(monkeypatch, tmp_path)
    documents = {document.id: document}
    _install_session_factory(monkeypatch, documents)

    seen_status = {}

    async def fake_run_pipeline(*args, **kwargs):
        seen_status["status"] = documents[document.id].status
        return _fake_ctx()

    monkeypatch.setattr("src.backend.workers.tasks.run_pipeline", fake_run_pipeline)

    result = process_document.delay(str(document.id))

    assert result.successful()
    assert seen_status["status"] == DocumentStatus.PROCESSING.value


def test_status_review_scan_on_complete(monkeypatch, eager_mode, tmp_path) -> None:
    document = _make_document_with_file(monkeypatch, tmp_path)
    documents = {document.id: document}
    _install_session_factory(monkeypatch, documents)

    async def fake_run_pipeline(*args, **kwargs):
        return _fake_ctx()

    monkeypatch.setattr("src.backend.workers.tasks.run_pipeline", fake_run_pipeline)

    result = process_document.delay(str(document.id))

    assert result.successful()
    assert documents[document.id].status == DocumentStatus.REVIEW_SCAN.value
    assert documents[document.id].processing_error is None
    assert documents[document.id].invoice_number == "INV-001"


def test_task_failure_sets_error_status(monkeypatch, tmp_path) -> None:
    document = _make_document_with_file(monkeypatch, tmp_path)
    documents = {document.id: document}
    _install_session_factory(monkeypatch, documents)

    old_always = celery_app.conf.task_always_eager
    old_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False

    try:
        async def fail_pipeline(*args, **kwargs):
            raise RuntimeError("pipeline failed")

        monkeypatch.setattr("src.backend.workers.tasks.run_pipeline", fail_pipeline)

        result = process_document.delay(str(document.id))

        assert result.failed()
        assert documents[document.id].status == "error"
        assert documents[document.id].processing_error == "pipeline failed"
    finally:
        celery_app.conf.task_always_eager = old_always
        celery_app.conf.task_eager_propagates = old_propagates


def test_task_missing_source_file_sets_error_status(monkeypatch, eager_mode, tmp_path) -> None:
    document = Document(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        filename="INV-001.pdf",
        sha256="deadbeef",
        status=DocumentStatus.UPLOADED.value,
    )
    monkeypatch.setattr(settings, "UPLOAD_ROOT", tmp_path)  # file deliberately not written
    documents = {document.id: document}
    _install_session_factory(monkeypatch, documents)

    old_always = celery_app.conf.task_always_eager
    old_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    try:
        result = process_document.delay(str(document.id))
        assert result.failed()
        assert documents[document.id].status == "error"
        assert "no longer available" in (documents[document.id].processing_error or "")
    finally:
        celery_app.conf.task_always_eager = old_always
        celery_app.conf.task_eager_propagates = old_propagates


def test_task_timeout_config() -> None:
    assert celery_app.conf.task_soft_time_limit == 120
    assert celery_app.conf.task_time_limit == 180
