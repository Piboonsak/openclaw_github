"""FastAPI router — POST /v1/templates/analyze (TASK-1009 Schema Analyzer).

Mounts at /api/v1/templates/analyze when included via endpoints.py.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from src.backend.services.schema_analyzer import analyze_file

router = APIRouter()

_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/v1/templates/analyze")
async def analyze_template(
    file: UploadFile = File(..., description="CSV or Excel file to analyze"),
) -> JSONResponse:
    """Analyze a sample CSV/Excel file and return inferred template structure.

    Acceptance criteria: ac_1009_upload, ac_1009_encoding, ac_1009_thai_header,
    ac_1009_confidence, ac_1009_mode, ac_1009_profile
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: csv, xlsx, xls",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    try:
        result = analyze_file(content, file.filename or "upload")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"File analysis failed: {exc}")

    raw = dataclasses.asdict(result)
    response_body: dict[str, Any] = {
        "file_info": {
            "filename": raw["filename"],
            "rows_detected": raw["rows_detected"],
            "encoding_detected": raw["encoding_detected"],
            "file_size_kb": raw["file_size_kb"],
        },
        "suggested_template_mode": raw["suggested_template_mode"],
        "suggested_row_source": raw["suggested_row_source"],
        "suggested_encoding": raw["suggested_encoding"],
        "columns": raw["columns"],
        "warnings": raw["warnings"],
        "data_profile": raw["data_profile"],
    }
    return JSONResponse(content=response_body)
