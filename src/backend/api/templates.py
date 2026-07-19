"""Template CRUD + preview endpoints (TASK-1002).

Routes:
  GET    /v1/templates                   — list (company_id filter + masters)
  POST   /v1/templates                   — create
  GET    /v1/templates/{id}              — get
  PUT    /v1/templates/{id}              — update columns / metadata
  DELETE /v1/templates/{id}              — soft delete
  POST   /v1/templates/{id}/clone        — deep-copy to company
  POST   /v1/templates/{id}/preview      — preview first N rows via template engine
"""

from __future__ import annotations

import copy
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.template_schemas import (
    CloneRequest,
    ColumnDefSchema,
    PreviewRequest,
    PreviewResponse,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)
from src.backend.auth.dependencies import ensure_company_access, get_current_active_user
from src.backend.db.models import ExportTemplate, User
from src.backend.db.session import get_db
from src.backend.services.template_engine import ColumnDef, TemplateEngine

router = APIRouter()

_PREVIEW_MAX_ROWS = 5


# ---------------------------------------------------------------------------
# Pure-Python helpers — testable without a DB session
# ---------------------------------------------------------------------------


def cols_from_jsonb(columns_jsonb: list | None) -> list[ColumnDef]:
    """Convert stored JSONB column list → ColumnDef objects for the engine."""
    if not columns_jsonb:
        return []
    return [ColumnDef.from_dict(c) for c in columns_jsonb if isinstance(c, dict)]


def render_preview(
    columns: list[ColumnDef],
    sample_data: list[dict],
    max_rows: int = _PREVIEW_MAX_ROWS,
) -> PreviewResponse:
    """Run template engine on sample_data and return headers + rows (no DB needed)."""
    engine = TemplateEngine(columns)
    headers, rows = engine.render(sample_data[:max_rows])
    return PreviewResponse(headers=headers, rows=rows)


def _template_to_response(t: ExportTemplate) -> TemplateResponse:
    raw_cols = t.columns if isinstance(t.columns, list) else []
    columns = [ColumnDefSchema(**c) for c in raw_cols if isinstance(c, dict)]
    return TemplateResponse(
        id=str(t.id),
        template_name=t.template_name,
        template_type=t.template_type,
        company_id=str(t.company_id) if t.company_id else None,
        columns=columns,
        file_format=t.file_format,
        encoding=t.encoding,
        delimiter=t.delimiter,
        is_master=t.is_master,
        is_active=t.is_active,
        cloned_from=str(t.cloned_from) if t.cloned_from else None,
        template_mode=getattr(t, "template_mode", None) or "flat_document",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/v1/templates", response_model=list[TemplateResponse])
async def list_templates(
    company_id: Optional[str] = Query(None, description="Filter by company UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[TemplateResponse]:
    """Return templates for a company (includes master templates with company_id=NULL)."""
    stmt = select(ExportTemplate).where(ExportTemplate.is_active == True)  # noqa: E712
    if company_id:
        cid = uuid.UUID(company_id)
        await ensure_company_access(db, current_user, cid)
        stmt = stmt.where(
            (ExportTemplate.company_id == cid) | (ExportTemplate.is_master == True)  # noqa: E712
        )
    else:
        stmt = stmt.where(ExportTemplate.is_master == True)  # noqa: E712
    result = await db.execute(stmt)
    return [_template_to_response(t) for t in result.scalars().all()]


@router.post("/v1/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    cols_jsonb = [c.model_dump() for c in body.columns]
    tmpl = ExportTemplate(
        company_id=uuid.UUID(body.company_id) if body.company_id else None,
        template_name=body.template_name,
        template_type=body.template_type,
        columns=cols_jsonb,
        file_format=body.file_format,
        encoding=body.encoding,
        delimiter=body.delimiter,
        is_master=body.is_master,
        template_mode=body.template_mode,
        created_by=current_user.id,
    )
    db.add(tmpl)
    await db.flush()
    await db.refresh(tmpl)
    return _template_to_response(tmpl)


@router.get("/v1/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl or not tmpl.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_response(tmpl)


@router.put("/v1/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl or not tmpl.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    if body.template_name is not None:
        tmpl.template_name = body.template_name
    if body.columns is not None:
        tmpl.columns = [c.model_dump() for c in body.columns]
    if body.file_format is not None:
        tmpl.file_format = body.file_format
    if body.encoding is not None:
        tmpl.encoding = body.encoding
    if body.delimiter is not None:
        tmpl.delimiter = body.delimiter
    if body.template_mode is not None:
        tmpl.template_mode = body.template_mode
    await db.flush()
    await db.refresh(tmpl)
    return _template_to_response(tmpl)


@router.delete("/v1/templates/{template_id}", status_code=204, response_class=Response)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> Response:
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl or not tmpl.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    tmpl.is_active = False
    await db.flush()
    return Response(status_code=204)


@router.post(
    "/v1/templates/{template_id}/clone",
    response_model=TemplateResponse,
    status_code=201,
)
async def clone_template(
    template_id: uuid.UUID,
    body: CloneRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TemplateResponse:
    source = await db.get(ExportTemplate, template_id)
    if not source or not source.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    if not source.is_master:
        raise HTTPException(
            status_code=400, detail="Only master templates can be cloned"
        )
    await ensure_company_access(db, current_user, body.company_id)

    cloned_cols = copy.deepcopy(source.columns)
    default_name = body.template_name or f"{source.template_name} (clone)"
    cloned = ExportTemplate(
        company_id=uuid.UUID(body.company_id),
        template_name=default_name,
        template_type=source.template_type,
        columns=cloned_cols,
        file_format=source.file_format,
        encoding=source.encoding,
        delimiter=source.delimiter,
        is_master=False,
        template_mode=getattr(source, "template_mode", None) or "flat_document",
        cloned_from=source.id,
        created_by=current_user.id,
    )
    db.add(cloned)
    await db.flush()
    await db.refresh(cloned)
    return _template_to_response(cloned)


@router.post("/v1/templates/{template_id}/preview", response_model=PreviewResponse)
async def preview_template(
    template_id: uuid.UUID,
    body: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> PreviewResponse:
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl or not tmpl.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    cols = cols_from_jsonb(tmpl.columns if isinstance(tmpl.columns, list) else [])
    return render_preview(cols, body.sample_data)
