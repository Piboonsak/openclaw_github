"""Mapping Rules CRUD + DOCX import endpoints (TASK-1203 company settings
document-ingestion workflow).

Routes:
  GET    /v1/companies/{id}/mapping-rules             — list rules
  POST   /v1/companies/{id}/mapping-rules             — create one rule manually
  PUT    /v1/companies/{id}/mapping-rules/{rule_id}    — edit one rule
  DELETE /v1/companies/{id}/mapping-rules/{rule_id}    — delete one rule
  POST   /v1/companies/{id}/mapping-rules/import-docx — AI extraction preview (not saved yet)
  POST   /v1/companies/{id}/mapping-rules/confirm      — save a (possibly edited) preview/list
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.mapping_rule_schemas import (
    MappingRuleEntry,
    MappingRuleImportResult,
    MappingRuleResponse,
    MappingRulesConfirmRequest,
    MappingRulesDocxPreviewResponse,
)
from src.backend.auth.dependencies import ensure_company_access, get_current_active_user
from src.backend.db.models import Company, User
from src.backend.db.session import get_db
from src.backend.services.coa_import import SqlAlchemyCoaRepository
from src.backend.services.mapping_rules_import import (
    SqlAlchemyMappingRuleRepository,
    extract_mapping_rules_preview_from_docx,
    upsert_mapping_rules,
)
from src.backend.storage import materialize_local_cache, store_document_bytes

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _rule_to_response(rule) -> MappingRuleResponse:
    return MappingRuleResponse(
        id=str(rule.id),
        vendor_name=rule.vendor_name,
        document_type=rule.document_type,
        recommended_debit_code=rule.recommended_debit_code,
        recommended_account_name=rule.recommended_account_name,
        confirmed_count=rule.confirmed_count,
        last_confirmed_at=rule.last_confirmed_at.isoformat() if rule.last_confirmed_at else "",
    )


@router.get("/v1/companies/{company_id}/mapping-rules", response_model=list[MappingRuleResponse])
async def list_mapping_rules(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[MappingRuleResponse]:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyMappingRuleRepository(db)
    if not await repo.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    rules = await repo.list_rules(company_id)
    return [_rule_to_response(r) for r in rules]


@router.post(
    "/v1/companies/{company_id}/mapping-rules",
    response_model=MappingRuleResponse,
    status_code=201,
)
async def create_mapping_rule(
    company_id: uuid.UUID,
    body: MappingRuleEntry,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MappingRuleResponse:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyMappingRuleRepository(db)
    try:
        await upsert_mapping_rules(
            repo,
            company_id,
            [body.model_dump()],
            created_by=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    saved = await repo.get_by_vendor_doctype(company_id, body.vendor_name, body.document_type)
    if saved is None:  # pragma: no cover - defensive, upsert always creates/updates one row
        raise HTTPException(status_code=500, detail="Rule save failed unexpectedly")
    return _rule_to_response(saved)


@router.put(
    "/v1/companies/{company_id}/mapping-rules/{rule_id}",
    response_model=MappingRuleResponse,
)
async def update_mapping_rule(
    company_id: uuid.UUID,
    rule_id: uuid.UUID,
    body: MappingRuleEntry,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MappingRuleResponse:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyMappingRuleRepository(db)
    rule = await repo.get_rule(company_id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Mapping rule not found")
    rule.vendor_name = body.vendor_name
    rule.document_type = body.document_type
    rule.recommended_debit_code = body.recommended_debit_code
    rule.recommended_account_name = body.recommended_account_name
    await db.flush()
    return _rule_to_response(rule)


@router.delete(
    "/v1/companies/{company_id}/mapping-rules/{rule_id}",
    status_code=204,
    response_class=Response,
)
async def delete_mapping_rule(
    company_id: uuid.UUID,
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyMappingRuleRepository(db)
    rule = await repo.get_rule(company_id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Mapping rule not found")
    await repo.delete_rule(rule)
    return Response(status_code=204)


@router.post(
    "/v1/companies/{company_id}/mapping-rules/import-docx",
    response_model=MappingRulesDocxPreviewResponse,
)
async def import_mapping_rules_docx(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="Mapping Rules DOCX"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MappingRulesDocxPreviewResponse:
    """AI-extraction preview only — does not write to the database. The
    caller reviews/edits the returned rows and POSTs them to `/confirm`.
    """
    await ensure_company_access(db, current_user, company_id)
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    ext = Path(file.filename or "").suffix.lower()
    if ext != ".docx":
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Accepted: docx")
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

    coa_repo = SqlAlchemyCoaRepository(db)
    existing_accounts = await coa_repo.list_accounts(company_id)
    chart_of_accounts = [
        {"code": a.account_code, "name": a.account_name} for a in existing_accounts
    ]

    try:
        rules, text_preview = await extract_mapping_rules_preview_from_docx(
            local_path,
            company_name=company.name,
            business_type=company.business_type or "",
            chart_of_accounts=chart_of_accounts,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return MappingRulesDocxPreviewResponse(rules=rules, source_text_preview=text_preview)


@router.post(
    "/v1/companies/{company_id}/mapping-rules/confirm",
    response_model=MappingRuleImportResult,
)
async def confirm_mapping_rules(
    company_id: uuid.UUID,
    body: MappingRulesConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MappingRuleImportResult:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyMappingRuleRepository(db)
    try:
        summary = await upsert_mapping_rules(
            repo,
            company_id,
            [r.model_dump() for r in body.rules],
            created_by=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return MappingRuleImportResult(
        imported=summary.imported,
        updated=summary.updated,
        errors=[{"row_number": e.row_number, "message": e.message} for e in summary.errors],
    )
