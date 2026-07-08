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
from src.backend.services.coa_import import ocr_pdf_to_text
from src.backend.services.document_workflow import build_pipeline_persistence_plan
from src.backend.services.rule_generator import extract_chart_of_accounts
from src.backend.storage import get_storage_client
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
    """Return a local path to the uploaded document inside *this* container.

    The backend and celery-worker containers do not share an upload volume
    (docker/docker-compose.sit.yml mounts none), so the local cache written
    by the API process during upload is normally absent here — fall back to
    downloading the bytes from object storage (MinIO on SIT) by storage key,
    same pattern already used by `_materialize_coa_source` for the COA async
    job. Without this fallback every `process_document` task retries 3 times
    (60s apart) and then fails with FileNotFoundError, even though the file
    genuinely exists in object storage.
    """
    ext = Path(document.filename or "").suffix.lower() or ".bin"
    local_path = settings.UPLOAD_ROOT / f"{document.sha256}{ext}"
    if local_path.exists():
        return local_path
    if not document.storage_key:
        return local_path
    content = get_storage_client().download_bytes(document.storage_key)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    return local_path


def _run_and_persist_pipeline(
    document_id: str, progress_callback: Any | None = None
) -> dict[str, Any]:
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
                progress_callback=progress_callback,
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


def _report_progress(task, stage: str) -> None:
    """Best-effort progress reporting: a broken/unreachable result backend
    must never kill the actual extraction work (also keeps eager-mode test
    runs, which have no live Redis, from failing on state updates)."""
    try:
        task.update_state(state="PROGRESS", meta={"stage": stage})
    except Exception:
        pass


def _materialize_coa_source(storage_key: str, sha256: str, filename: str | None) -> Path:
    """Return a local path to the uploaded COA PDF inside *this* container.

    The backend and celery-worker containers do not share an upload volume
    (docker/docker-compose.sit.yml mounts none), so the local cache written
    by the API process is usually absent here — fall back to downloading the
    bytes from object storage (MinIO on SIT) by storage key.
    """
    ext = Path(filename or "").suffix.lower() or ".pdf"
    local_path = settings.UPLOAD_ROOT / f"{sha256}{ext}"
    if local_path.exists():
        return local_path
    content = get_storage_client().download_bytes(storage_key)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    return local_path


@celery_app.task(bind=True, time_limit=600, soft_time_limit=540)
def extract_coa_pdf(
    self,
    *,
    company_id: str,
    storage_key: str,
    sha256: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """Run the COA PDF OCR+LLM extraction as a background job
    (W4-SIT-E2E-COA-ASYNC-10). The synchronous route dies at the nginx 120s
    proxy wall on SIT (runtime diagnosis 07: live run took ~173s), so this
    task carries per-task time limits above the app-wide 120/180 defaults.

    Returns the same review-before-save preview payload the sync route
    produces — nothing is written to the database; the client must still
    POST the reviewed rows to `/coa/confirm`.
    """
    _report_progress(self, "fetching_file")
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        company = session.get(Company, uuid.UUID(company_id))
        if company is None:
            raise ValueError(f"Company not found: {company_id}")
        company_name = company.name
        business_type = company.business_type or ""

    local_path = _materialize_coa_source(storage_key, sha256, filename)

    _report_progress(self, "ocr")
    coa_text = ocr_pdf_to_text(local_path)
    if not coa_text.strip():
        raise RuntimeError("COA PDF yielded no readable text.")

    _report_progress(self, "llm")
    accounts = extract_chart_of_accounts(
        company_name=company_name,
        business_type=business_type,
        coa_text=coa_text,
    )
    return {
        "company_id": company_id,
        "company_name_detected": company_name,
        "accounts": accounts,
    }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, document_id: str) -> dict[str, Any]:
    """Run document processing asynchronously with persistent task state.

    Reports "ocr" / "extract" / "mapping" progress stages (W4 Processing UX
    fix) so the frontend can poll `GET /api/v1/tasks/{task_id}` and show real
    pipeline progress instead of an opaque spinner.
    """
    _set_document_status(document_id, DocumentStatus.PROCESSING.value)
    _report_progress(self, "queued")

    try:
        result = _run_and_persist_pipeline(
            document_id,
            progress_callback=lambda stage: _report_progress(self, stage),
        )
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
