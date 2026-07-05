"""Celery tasks for asynchronous document processing.

W4 SIT closure (`TASK-W4-SIT-E2E-CLAUDE-ROUTINE-OPS-CLOSURE-07`, Codex Review
03 finding #1): this task used to call an explicit stub
("Pipeline placeholder for W2 until PoC pipeline merge completes"), leaving
two divergent processing paths in the repo — the real synchronous
`POST /v1/documents/{id}/process` API and this queued-but-fake one. It now
runs the same real `run_pipeline` orchestrator and the same
`build_pipeline_persistence_plan` mapping the API path uses, via a sync
SQLAlchemy session (Celery tasks run outside the request's async context).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from config.settings import settings
from src.backend.db.base import get_sync_session_factory
from src.backend.db.enums import DocumentStatus
from src.backend.db.models import Company, Document, Extraction, JournalLine, JournalVoucher
from src.backend.pipeline.orchestrator import run_pipeline
from src.backend.services.document_workflow import build_pipeline_persistence_plan
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


def _resolve_local_path(document: Document) -> Path:
    ext = Path(document.filename or "").suffix.lower() or ".bin"
    return settings.UPLOAD_ROOT / f"{document.sha256}{ext}"


def _run_and_persist_pipeline(document_id: str) -> dict[str, Any]:
    """Run the real OCR/extraction/journal-routing pipeline for `document_id`
    and persist the result via a sync SQLAlchemy session, using the same
    `build_pipeline_persistence_plan` the async API path uses. Returns a
    small summary dict for the task result payload."""
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        document = session.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"Document not found: {document_id}")

        local_path = _resolve_local_path(document)
        if not local_path.exists():
            raise FileNotFoundError(f"Source file is no longer available: {local_path}")

        company = session.get(Company, document.company_id)
        ctx = asyncio.run(
            run_pipeline(
                str(local_path),
                company_id=str(document.company_id),
                company_tax_id=company.tax_id if company else None,
            )
        )

        plan = build_pipeline_persistence_plan(ctx)
        document.status = plan.status
        document.processing_error = plan.processing_error
        for field_name, value in plan.document_fields.items():
            setattr(document, field_name, value)
        session.add(document)

        if plan.extraction_kwargs is not None:
            session.add(Extraction(document_id=document.id, **plan.extraction_kwargs))

        if plan.voucher_kwargs is not None:
            voucher = JournalVoucher(document_id=document.id, **plan.voucher_kwargs)
            session.add(voucher)
            session.flush()
            for spec in plan.line_specs:
                session.add(JournalLine(voucher_id=voucher.id, **spec))

        session.commit()
        return {
            "document_id": str(document.id),
            "status": plan.status,
            "pipeline_error": plan.processing_error,
        }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, document_id: str) -> dict[str, Any]:
    """Run document processing asynchronously with persistent task state."""
    _set_document_status(document_id, DocumentStatus.PROCESSING.value)

    try:
        result = _run_and_persist_pipeline(document_id)
        return {
            "task_id": self.request.id,
            "document_id": document_id,
            "status": result["status"],
            "result": result,
        }
    except Exception as exc:
        _set_document_status(document_id, _error_status_value(), str(exc))
        if (not celery_app.conf.task_always_eager) and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise
