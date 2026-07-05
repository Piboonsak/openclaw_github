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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.coa_schemas import (
    ChartOfAccountResponse,
    CoaConfirmRequest,
    CoaImportResult,
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

    ext = Path(file.filename or "").suffix.lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Accepted: pdf")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

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
