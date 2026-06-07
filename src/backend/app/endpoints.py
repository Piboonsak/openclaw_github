"""API endpoints for OCR, field extraction, journal routing, and exports."""

from __future__ import annotations

import asyncio
import importlib
import io
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from src.backend.pipeline.orchestrator import run_pipeline, select_model
from src.backend.services.export_service import create_excel_ledger
from src.backend.services.rule_generation_jobs import RULE_GENERATION_JOBS
from src.backend.services.rule_engine import validate_required_fields

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]


@router.get("/health")
def health() -> dict[str, str]:
    """Check health status of backend."""
    return {"status": "ok"}


@router.post("/process")
async def process(
    file_path: str | None = Query(None, description="Path to file on disk"),
    company_id: str | None = Form(
        None, description="Company rule context for journal routing"
    ),
    file: UploadFile | None = File(None, description="Uploaded document blob"),
) -> dict[str, Any]:
    """Process a document (OCR -> Field Extraction -> GL Alignment Routing)."""
    temp_dir = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "backend"
        / "ml"
        / "cache"
        / "uploads"
    )
    temp_dir.mkdir(parents=True, exist_ok=True)

    if file:
        target_path = temp_dir / file.filename
        content = await file.read()
        target_path.write_bytes(content)
        resolved_path = str(target_path)
    elif file_path:
        resolved_path = file_path
        if not Path(resolved_path).exists():
            raise HTTPException(status_code=404, detail="Disked file path not found")
    else:
        raise HTTPException(
            status_code=400, detail="Provide either a disk file path or upload files"
        )

    # Run actual async pipeline orchestrator
    ctx = await run_pipeline(resolved_path, company_id=company_id)

    if ctx.error:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {ctx.error}")

    fields = ctx.extraction_output.get("fields", {})
    validation = validate_required_fields(
        fields, ["invoice_number", "invoice_date", "total_amount"]
    )

    return {
        "source_file": resolved_path,
        "text": "\n".join(
            [b.get("text", "") for b in ctx.ocr_output.get("blocks", [])]
        ),
        "fields": fields,
        "validation": validation,
        "extraction": ctx.extraction_output,
        "journal": ctx.journal_output,
        "company_id": ctx.company_id,
        "pipeline_status": ctx.status.name,
        "model_used": select_model(ctx),
    }


@router.get("/preview-first-page")
async def preview_first_page(
    file_path: str = Query(..., description="Path to document file on disk"),
) -> Response:
    """Render first page of a document as PNG for stable in-browser preview."""
    source = Path(file_path)
    if not source.exists() or not source.is_file():
        raise HTTPException(status_code=404, detail="Preview source file not found")

    suffix = source.suffix.lower()
    if suffix not in {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".bmp",
        ".tif",
        ".tiff",
    }:
        raise HTTPException(status_code=400, detail="Unsupported preview file type")

    try:
        if suffix == ".pdf":
            pdfium = importlib.import_module("pypdfium2")
            pdf = pdfium.PdfDocument(str(source))
            if len(pdf) == 0:
                raise HTTPException(status_code=400, detail="PDF has no pages")
            page = pdf[0]
            bitmap = page.render(scale=1.5)
            image = bitmap.to_pil()
        else:
            image_module = importlib.import_module("PIL.Image")
            image = image_module.open(source)

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to render preview image: {exc}"
        )


@router.post("/export-excel")
async def export_excel(
    vouchers: list[dict[str, Any]],
) -> FileResponse:
    """Generate professional Double-Entry Accounting General Ledger in Excel."""
    try:
        temp_dir = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "backend"
            / "ml"
            / "cache"
            / "exports"
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        xlsx_path = temp_dir / "double_entry_ledgers.xlsx"

        create_excel_ledger(vouchers, xlsx_path)

        return FileResponse(
            path=str(xlsx_path),
            filename="double_entry_ledgers.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate Excel ledger: {exc}"
        )


@router.post("/v1/rules/generate")
async def generate_rules(
    company_id: str = Form(...),
    company_name: str = Form(...),
    business_type: str = Form("service"),
    provider: str = Form("anthropic"),
    model: str = Form("claude-sonnet-4-6-20250601"),
    coa_file: UploadFile = File(...),
    mapping_file: UploadFile = File(...),
) -> dict[str, Any]:
    uploads_dir = REPO_ROOT / "src" / "backend" / "ml" / "cache" / "rule_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    coa_path = uploads_dir / f"{company_id}_{coa_file.filename}"
    mapping_path = uploads_dir / f"{company_id}_{mapping_file.filename}"

    with coa_path.open("wb") as handle:
        shutil.copyfileobj(coa_file.file, handle)
    with mapping_path.open("wb") as handle:
        shutil.copyfileobj(mapping_file.file, handle)

    job = await RULE_GENERATION_JOBS.create_job(
        {
            "company_id": company_id,
            "company_name": company_name,
            "business_type": business_type,
            "provider": provider,
            "model": model,
            "coa_file_path": str(coa_path),
            "mapping_file_path": str(mapping_path),
        }
    )
    asyncio.create_task(RULE_GENERATION_JOBS.run_job(job["job_id"]))

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "estimated_seconds": job["estimated_seconds"],
    }


@router.get("/v1/rules/generate/{job_id}/progress")
async def get_rule_job_progress(job_id: str) -> dict[str, Any]:
    job = await RULE_GENERATION_JOBS.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress_pct": job["progress_pct"],
        "current_stage": job["current_stage"],
        "stage_label": job["stage_label"],
        "stages": job["stages"],
        "error": job.get("error"),
    }


@router.get("/v1/rules/generate/{job_id}/result")
async def get_rule_job_result(job_id: str) -> dict[str, Any]:
    job = await RULE_GENERATION_JOBS.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "approved": bool(job.get("approved", False)),
        }
    result = dict(job.get("result") or {})
    result.update(
        {
            "job_id": job["job_id"],
            "status": job["status"],
            "approved": bool(job.get("approved", False)),
        }
    )
    return result


@router.post("/v1/rules/generate/{job_id}/approve")
async def approve_rule_job(job_id: str) -> dict[str, Any]:
    job = await RULE_GENERATION_JOBS.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Job is not done")
    await RULE_GENERATION_JOBS.mark_approved(job_id)
    return {"job_id": job_id, "status": "approved"}
