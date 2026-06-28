"""Vendor and customer master import endpoints for TASK-1207."""

from __future__ import annotations

import dataclasses
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import User
from src.backend.db.session import get_db
from src.backend.services.master_data_import import (
    SqlAlchemyMasterRepository,
    import_master_csv,
    list_master_entries,
)

router = APIRouter()

_ALLOWED_EXTENSIONS = {".csv"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def _read_upload_bytes(file: UploadFile) -> bytes:
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
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    return content


@router.post("/v1/companies/{company_id}/vendor-master/import")
async def import_vendor_master(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="Vendor master CSV"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    content = await _read_upload_bytes(file)
    repo = SqlAlchemyMasterRepository(db)
    try:
        result = await import_master_csv(repo, company_id, "vendor", content)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=dataclasses.asdict(result))


@router.post("/v1/companies/{company_id}/customer-master/import")
async def import_customer_master(
    company_id: uuid.UUID,
    file: UploadFile = File(..., description="Customer master CSV"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    content = await _read_upload_bytes(file)
    repo = SqlAlchemyMasterRepository(db)
    try:
        result = await import_master_csv(repo, company_id, "customer", content)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return JSONResponse(content=dataclasses.asdict(result))


@router.get("/v1/companies/{company_id}/vendor-master")
async def get_vendor_master_entries(
    company_id: uuid.UUID,
    q: str | None = Query(None, description="Search by vendor code or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    repo = SqlAlchemyMasterRepository(db)
    try:
        result = await list_master_entries(repo, company_id, "vendor", q, page, page_size)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return JSONResponse(content=dataclasses.asdict(result))


@router.get("/v1/companies/{company_id}/customer-master")
async def get_customer_master_entries(
    company_id: uuid.UUID,
    q: str | None = Query(None, description="Search by customer code or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_active_user),
) -> JSONResponse:
    repo = SqlAlchemyMasterRepository(db)
    try:
        result = await list_master_entries(
            repo,
            company_id,
            "customer",
            q,
            page,
            page_size,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return JSONResponse(content=dataclasses.asdict(result))
