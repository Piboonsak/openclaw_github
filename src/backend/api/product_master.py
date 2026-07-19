"""Product/price-list master import + list endpoints (Pack C product-master
foundation, separate from `enable_stock`).

Routes:
  POST /v1/companies/{id}/product-master/import — CSV upsert import
  GET  /v1/companies/{id}/product-master         — paginated list + search
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.api.schemas.product_master_schemas import (
    ProductImportResult,
    ProductListPage,
)
from src.backend.auth.dependencies import ensure_company_access, get_current_active_user
from src.backend.db.models import User
from src.backend.db.session import get_db
from src.backend.services.product_master_import import (
    SqlAlchemyProductMasterRepository,
    deactivate_product_master_entry,
    import_product_master_csv,
    list_product_master_entries,
)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".csv"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post(
    "/v1/companies/{company_id}/product-master/import",
    response_model=ProductImportResult,
)
async def import_product_master(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="Product/price-list CSV"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProductImportResult:
    await ensure_company_access(db, current_user, company_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: csv",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    repo = SqlAlchemyProductMasterRepository(db)
    try:
        summary = await import_product_master_csv(repo, company_id, content)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return ProductImportResult(
        imported=summary.imported,
        updated=summary.updated,
        errors=[{"row_number": e.row_number, "message": e.message} for e in summary.errors],
    )


@router.get(
    "/v1/companies/{company_id}/product-master",
    response_model=ProductListPage,
)
async def get_product_master_entries(
    company_id: uuid.UUID,
    q: str | None = Query(None, description="Search by product code or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProductListPage:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyProductMasterRepository(db)
    try:
        result = await list_product_master_entries(repo, company_id, q, page, page_size)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ProductListPage(
        items=[
            {
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "unit_cost": item.unit_cost,
                "category": item.category,
                "is_active": item.is_active,
            }
            for item in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        search=result.search,
    )


@router.delete(
    "/v1/companies/{company_id}/product-master/{product_code}", status_code=204
)
async def deactivate_product_master(
    company_id: uuid.UUID,
    product_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """Soft-delete (deactivate) a product master row (HR-17-07)."""
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyProductMasterRepository(db)
    try:
        await deactivate_product_master_entry(repo, company_id, product_code)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(status_code=204)
