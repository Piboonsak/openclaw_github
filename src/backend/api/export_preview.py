"""Export preview + balance validation endpoints (TASK-1104).

Routes:
  POST /v1/export/preview   — JSON table preview (headers + first 10 rows)
  POST /v1/export/validate  — balance check: Sum(Dr) == Sum(Cr) per voucher
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.template_schemas import ColumnDefSchema, PreviewResponse
from src.backend.api.templates import cols_from_jsonb, render_preview
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import ExportTemplate, User
from src.backend.db.session import get_db
from src.backend.services.export_dataset import build_export_records
from src.backend.services.export_service import validate_balance
from src.backend.services.template_engine import TemplateEngine

router = APIRouter()


async def _resolve_export_rows(
    db: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    document_ids: list[uuid.UUID] | None,
    include_line_items: bool,
    sample_data: list[dict],
) -> list[dict]:
    """Live Export builds rows from real reviewed/mapped documents when a
    ``company_id`` is provided; ``sample_data`` is used only for the Template
    Configurator design-time preview (no company context)."""
    if company_id is not None:
        return await build_export_records(
            db,
            company_id,
            document_ids=document_ids or None,
            include_line_items=include_line_items,
        )
    return sample_data

_PREVIEW_MAX_ROWS = 10
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")
_UNSAFE_WHITESPACE_RE = re.compile(r"[\r\n\t]+")
_SPACE_RUN_RE = re.compile(r" {2,}")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ExportPreviewRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None
    sample_data: list[dict] = Field(default=[], max_length=50)
    column_overrides: list[ColumnDefSchema] = Field(default=[])
    # Live export: when company_id is set, rows come from real reviewed/mapped
    # documents (sample_data is ignored for live export, used only for the
    # Template Configurator design-time preview).
    company_id: Optional[uuid.UUID] = None
    document_ids: Optional[list[uuid.UUID]] = None
    include_line_items: bool = False


class VoucherLine(BaseModel):
    debit: float = 0.0
    credit: float = 0.0


class VoucherInput(BaseModel):
    voucher_no: str
    lines: list[VoucherLine] = []


class ValidateRequest(BaseModel):
    vouchers: list[VoucherInput]
    tolerance: float = Field(default=0.01, ge=0.0)


class UnbalancedVoucher(BaseModel):
    voucher_no: str
    total_debit: float
    total_credit: float
    difference: float


class ValidateResponse(BaseModel):
    valid: bool
    unbalanced_vouchers: list[UnbalancedVoucher]


class ExportFileRequest(BaseModel):
    template_id: Optional[uuid.UUID] = None
    sample_data: list[dict] = Field(default=[], max_length=200)
    format: Optional[str] = Field(default=None, pattern="^(csv|xlsx)$")
    filename: Optional[str] = None
    column_overrides: list[ColumnDefSchema] = Field(default=[])
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    # Live export from real documents (see ExportPreviewRequest).
    company_id: Optional[uuid.UUID] = None
    document_ids: Optional[list[uuid.UUID]] = None
    include_line_items: bool = False


def _sanitize_download_stem(name: str | None) -> str:
    """Return a header-safe filename stem with dangerous characters removed."""
    cleaned = _UNSAFE_WHITESPACE_RE.sub(" ", (name or "").strip())
    cleaned = _SAFE_FILENAME_RE.sub("_", cleaned)
    cleaned = _SPACE_RUN_RE.sub(" ", cleaned)
    cleaned = cleaned.strip(" .") or "ledgerflow-export"
    return cleaned[:120]


def _csv_media_type_for_encoding(encoding: str) -> str:
    normalized = (encoding or "utf-8").lower()
    if normalized in ("tis-620", "cp874"):
        return "text/csv; charset=windows-874"
    if normalized == "utf-8-bom":
        return "text/csv; charset=utf-8"
    return f"text/csv; charset={normalized}"


# ---------------------------------------------------------------------------
# ac_1104_preview — preview via template engine
# ---------------------------------------------------------------------------

@router.post("/v1/export/preview", response_model=PreviewResponse)
async def export_preview(
    body: ExportPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> PreviewResponse:
    """Return formatted JSON table preview (first 10 rows).

    Supports both export paths:
      - ``template_id`` set -> load saved template columns (Template Export)
      - ``template_id`` null + ``column_overrides`` provided -> Quick Export,
        rendered from the per-run column list with no saved template needed
    """
    runtime_columns = [col.model_dump() for col in body.column_overrides]
    template_columns: list[dict[str, Any]] = []

    if body.template_id:
        tmpl = await db.get(ExportTemplate, body.template_id)
        if not tmpl or not tmpl.is_active:
            raise HTTPException(status_code=404, detail="Template not found")
        template_columns = tmpl.columns if isinstance(tmpl.columns, list) else []

    columns_json = runtime_columns or template_columns
    if not columns_json:
        raise HTTPException(
            status_code=422,
            detail="Provide template_id or column_overrides for preview",
        )

    cols = cols_from_jsonb(columns_json)
    rows = await _resolve_export_rows(
        db,
        company_id=body.company_id,
        document_ids=body.document_ids,
        include_line_items=body.include_line_items,
        sample_data=body.sample_data,
    )
    return render_preview(cols, rows, max_rows=_PREVIEW_MAX_ROWS)


# ---------------------------------------------------------------------------
# ac_1104_balanced / ac_1104_unbalanced / ac_1104_tolerance / ac_1104_report
# ---------------------------------------------------------------------------

@router.post("/v1/export/validate", response_model=ValidateResponse)
async def export_validate(
    body: ValidateRequest,
    _current_user: User = Depends(get_current_active_user),
) -> ValidateResponse:
    """Check Sum(Dr) == Sum(Cr) per voucher (tolerance: 0.01 THB by default)."""
    raw = [
        {
            "voucher_no": v.voucher_no,
            "lines": [{"debit": ln.debit, "credit": ln.credit} for ln in v.lines],
        }
        for v in body.vouchers
    ]
    result = validate_balance(raw, tolerance=body.tolerance)
    return ValidateResponse(
        valid=result["valid"],
        unbalanced_vouchers=[UnbalancedVoucher(**u) for u in result["unbalanced_vouchers"]],
    )


@router.post("/v1/export")
async def export_file(
    body: ExportFileRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> Response:
    """Generate CSV/XLSX bytes from a saved template or per-run column overrides."""
    runtime_columns = [col.model_dump() for col in body.column_overrides]
    template_columns: list[dict[str, Any]] = []
    file_format = body.format or "csv"
    encoding = body.encoding or "utf-8"
    delimiter = body.delimiter or ","
    template_name = "ledgerflow-export"

    if body.template_id:
        tmpl = await db.get(ExportTemplate, body.template_id)
        if not tmpl or not tmpl.is_active:
            raise HTTPException(status_code=404, detail="Template not found")
        template_name = tmpl.template_name
        template_columns = tmpl.columns if isinstance(tmpl.columns, list) else []
        file_format = body.format or tmpl.file_format or "csv"
        encoding = body.encoding or tmpl.encoding or "utf-8"
        delimiter = body.delimiter or tmpl.delimiter or ","

    columns_json = runtime_columns or template_columns
    if not columns_json:
        raise HTTPException(
            status_code=422,
            detail="Provide template_id or column_overrides for export",
        )

    columns = cols_from_jsonb(columns_json)
    engine = TemplateEngine(
        columns=columns,
        encoding=encoding,
        delimiter=delimiter,
        file_format=file_format,
    )
    export_rows = await _resolve_export_rows(
        db,
        company_id=body.company_id,
        document_ids=body.document_ids,
        include_line_items=body.include_line_items,
        sample_data=body.sample_data,
    )
    headers, rows = engine.render(export_rows, column_overrides=columns)
    safe_stem = _sanitize_download_stem(body.filename or template_name)

    if file_format == "xlsx":
        payload = engine.write_excel(headers, rows, columns=columns)
        return Response(
            content=payload,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_stem}.xlsx"',
            },
        )

    payload = engine.write_csv(headers, rows, columns=columns)
    return Response(
        content=payload,
        media_type=_csv_media_type_for_encoding(encoding),
        headers={
            "Content-Disposition": f'attachment; filename="{safe_stem}.csv"',
        },
    )
