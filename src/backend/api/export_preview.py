"""Export preview + balance validation endpoints (TASK-1104).

Routes:
  POST /v1/export/preview   — JSON table preview (headers + first 10 rows)
  POST /v1/export/validate  — balance check: Sum(Dr) == Sum(Cr) per voucher
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.template_schemas import PreviewResponse
from src.backend.api.templates import cols_from_jsonb, render_preview
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import ExportTemplate, User
from src.backend.db.session import get_db
from src.backend.services.export_service import validate_balance

router = APIRouter()

_PREVIEW_MAX_ROWS = 10


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ExportPreviewRequest(BaseModel):
    template_id: str
    sample_data: list[dict] = Field(default=[], max_length=50)


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


# ---------------------------------------------------------------------------
# ac_1104_preview — preview via template engine
# ---------------------------------------------------------------------------

@router.post("/v1/export/preview", response_model=PreviewResponse)
async def export_preview(
    body: ExportPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> PreviewResponse:
    """Return formatted JSON table preview (first 10 rows) using the named template."""
    tmpl = await db.get(ExportTemplate, uuid.UUID(body.template_id))
    if not tmpl or not tmpl.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    cols = cols_from_jsonb(tmpl.columns if isinstance(tmpl.columns, list) else [])
    return render_preview(cols, body.sample_data, max_rows=_PREVIEW_MAX_ROWS)


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
