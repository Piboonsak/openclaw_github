"""Celery tasks for asynchronous document processing."""

from __future__ import annotations

import uuid
from typing import Any

from src.backend.db.base import get_sync_session_factory
from src.backend.db.enums import DocumentStatus
from src.backend.db.models import Document
from src.backend.workers.celery_app import celery_app


def _error_status_value() -> str:
    """Return failure status while remaining compatible with current enum set."""
    error_status = getattr(DocumentStatus, "ERROR", None)
    if error_status is not None:
        return str(error_status.value)
    return "error"


def _load_document(document_id: str) -> Document:
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        document = session.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        return document


def _set_document_status(
    document_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        document = session.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        document.status = status
        document.processing_error = error_message
        session.add(document)
        session.commit()


def _run_pipeline_stub(document: Document) -> dict[str, Any]:
    """Pipeline placeholder for W2 until PoC pipeline merge completes."""
    return {
        "document_id": str(document.id),
        "pipeline": "stub",
        "message": "PoC pipeline integration pending merge",
    }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, document_id: str) -> dict[str, Any]:
    """Run document processing asynchronously with persistent task state."""
    _set_document_status(document_id, DocumentStatus.PROCESSING.value)

    try:
        document = _load_document(document_id)
        result = _run_pipeline_stub(document)
        _set_document_status(document_id, DocumentStatus.REVIEW_SCAN.value)
        return {
            "task_id": self.request.id,
            "document_id": document_id,
            "status": DocumentStatus.REVIEW_SCAN.value,
            "result": result,
        }
    except Exception as exc:
        _set_document_status(document_id, _error_status_value(), str(exc))
        if (not celery_app.conf.task_always_eager) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
