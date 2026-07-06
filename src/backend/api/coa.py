"""Chart of Accounts CRUD + import endpoints (TASK-1203).

Routes:
  GET  /v1/companies/{id}/coa            — list accounts for a company
  POST /v1/companies/{id}/coa/import     — YAML/CSV upsert import
  POST /v1/companies/{id}/coa/import-pdf — AI extraction preview (not saved yet)
  POST /v1/companies/{id}/coa/confirm    — save a (possibly edited) preview/list
"""

from __future__ import annotations

import uuid
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.coa_schemas import (
    ChartOfAccountResponse,
    CoaConfirmRequest,
    CoaImportResult,
    CoaPdfAsyncStartResponse,
    CoaPdfAsyncStatusResponse,
    CoaPdfPreviewResponse,
)
from src.backend.auth.dependencies import ensure_company_access, get_current_active_user
from src.backend.db.models import Company, User
from src.backend.db.session import get_db
from src.backend.services.coa_import import (
    SqlAlchemyCoaRepository,
    extract_coa_preview_from_pdf,
    parse_coa_file,
    upsert_chart_of_accounts,
)
from src.backend.storage import materialize_local_cache, store_document_bytes
from src.backend.workers.celery_app import celery_app
from src.backend.workers.tasks import extract_coa_pdf

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_IMPORT_EXTENSIONS = {".yaml", ".yml", ".csv"}


def _account_to_response(account) -> ChartOfAccountResponse:
    return ChartOfAccountResponse(
        id=str(account.id),
        account_code=account.account_code,
        account_name=account.account_name,
        account_type=account.account_type,
        is_active=account.is_active,
    )


async def _get_company_or_404(db: AsyncSession, company_id: uuid.UUID) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/v1/companies/{company_id}/coa", response_model=list[ChartOfAccountResponse])
async def list_chart_of_accounts(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ChartOfAccountResponse]:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyCoaRepository(db)
    if not await repo.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    accounts = await repo.list_accounts(company_id)
    return [_account_to_response(a) for a in accounts]


@router.post("/v1/companies/{company_id}/coa/import", response_model=CoaImportResult)
async def import_chart_of_accounts_file(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="COA YAML or CSV"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CoaImportResult:
    await ensure_company_access(db, current_user, company_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_IMPORT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: yaml, yml, csv",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        rows = parse_coa_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    repo = SqlAlchemyCoaRepository(db)
    try:
        summary = await upsert_chart_of_accounts(repo, company_id, rows)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return CoaImportResult(
        imported=summary.imported,
        updated=summary.updated,
        errors=[{"row_number": e.row_number, "message": e.message} for e in summary.errors],
    )


@router.post("/v1/companies/{company_id}/coa/import-pdf", response_model=CoaPdfPreviewResponse)
async def import_chart_of_accounts_pdf(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="COA PDF"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CoaPdfPreviewResponse:
    """AI-extraction preview only (ac_1203_coa_pdf / ac_1203_coa_review) — does
    not write to the database. The caller reviews/edits the returned rows and
    POSTs them to `/coa/confirm` to save.
    """
    await ensure_company_access(db, current_user, company_id)
    company = await _get_company_or_404(db, company_id)

    content = await _read_validated_pdf(file)
    stored = store_document_bytes(
        content=content,
        filename=file.filename,
        company_id=str(company_id),
        content_type=file.content_type,
    )
    local_path = materialize_local_cache(
        content=content, filename=file.filename, sha256=stored["sha256"]
    )

    try:
        accounts = await extract_coa_preview_from_pdf(
            local_path,
            company_name=company.name,
            business_type=company.business_type or "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return CoaPdfPreviewResponse(
        accounts=accounts,
        company_name_detected=company.name,
    )


async def _read_validated_pdf(file: UploadFile) -> bytes:
    ext = Path(file.filename or "").suffix.lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Accepted: pdf")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")
    return content


@router.post(
    "/v1/companies/{company_id}/coa/import-pdf-async",
    response_model=CoaPdfAsyncStartResponse,
    status_code=202,
)
async def start_coa_pdf_extraction(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="COA PDF"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CoaPdfAsyncStartResponse:
    """Start COA PDF AI extraction as a background job and return a task id
    immediately (W4-SIT-E2E-COA-ASYNC-10). The synchronous `/coa/import-pdf`
    route exceeds the SIT nginx 120s proxy timeout on real files, so the
    production UI polls `GET .../import-pdf-async/{task_id}` instead of
    holding one long request open.
    """
    await ensure_company_access(db, current_user, company_id)
    await _get_company_or_404(db, company_id)

    content = await _read_validated_pdf(file)
    stored = store_document_bytes(
        content=content,
        filename=file.filename,
        company_id=str(company_id),
        content_type=file.content_type,
    )
    # Local cache is a fast path for single-host runs; the worker re-downloads
    # from object storage when (as on SIT) it does not share this volume.
    materialize_local_cache(content=content, filename=file.filename, sha256=stored["sha256"])

    task = extract_coa_pdf.delay(
        company_id=str(company_id),
        storage_key=stored["storage_key"],
        sha256=stored["sha256"],
        filename=file.filename,
    )
    return CoaPdfAsyncStartResponse(task_id=task.id, status="queued")


@router.get(
    "/v1/companies/{company_id}/coa/import-pdf-async/{task_id}",
    response_model=CoaPdfAsyncStatusResponse,
)
async def get_coa_pdf_extraction_status(
    company_id: uuid.UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CoaPdfAsyncStatusResponse:
    """Poll a background COA PDF extraction job. On success the payload holds
    the review-before-save account rows — nothing is persisted until the
    client confirms them via `/coa/confirm`.
    """
    await ensure_company_access(db, current_user, company_id)
    async_result = AsyncResult(task_id, app=celery_app)
    state = async_result.state

    if state == "SUCCESS":
        result = async_result.result if isinstance(async_result.result, dict) else {}
        # A task id is only readable through the company it was started for.
        if str(result.get("company_id", "")) != str(company_id):
            raise HTTPException(status_code=404, detail="Task not found for this company")
        return CoaPdfAsyncStatusResponse(
            task_id=task_id,
            status="succeeded",
            accounts=result.get("accounts", []),
            company_name_detected=result.get("company_name_detected"),
        )
    if state in ("FAILURE", "REVOKED"):
        return CoaPdfAsyncStatusResponse(
            task_id=task_id,
            status="failed",
            error=str(async_result.result or "extraction failed"),
        )
    if state == "PROGRESS":
        meta = async_result.info if isinstance(async_result.info, dict) else {}
        return CoaPdfAsyncStatusResponse(
            task_id=task_id, status="running", stage=str(meta.get("stage") or "")
        )
    if state in ("STARTED", "RETRY"):
        return CoaPdfAsyncStatusResponse(task_id=task_id, status="running", stage="starting")
    # PENDING/RECEIVED — Celery reports unknown ids as PENDING too; the client
    # enforces its own overall deadline, so "queued" is the honest answer here.
    return CoaPdfAsyncStatusResponse(task_id=task_id, status="queued")


@router.post("/v1/companies/{company_id}/coa/confirm", response_model=CoaImportResult)
async def confirm_chart_of_accounts(
    company_id: uuid.UUID,
    body: CoaConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CoaImportResult:
    """Save a reviewed (and possibly human-edited) COA preview list — the
    'confirm & save' step required after PDF/YAML/CSV extraction so nothing
    is written to the database before a human has seen it.
    """
    await ensure_company_access(db, current_user, company_id)
    rows = [
        {"account_code": a.code, "account_name": a.name, "account_type": a.type}
        for a in body.accounts
    ]
    repo = SqlAlchemyCoaRepository(db)
    try:
        summary = await upsert_chart_of_accounts(repo, company_id, rows)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return CoaImportResult(
        imported=summary.imported,
        updated=summary.updated,
        errors=[{"row_number": e.row_number, "message": e.message} for e in summary.errors],
    )
