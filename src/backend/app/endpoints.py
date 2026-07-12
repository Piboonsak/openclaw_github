"""API endpoints for OCR, field extraction, journal routing, and exports."""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import os
import shutil
from pathlib import Path
from typing import Any

from celery.result import AsyncResult
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, Response

from config.settings import settings
from src.backend.api.coa import router as _coa_router
from src.backend.api.companies_admin import router as _companies_admin_router
from src.backend.api.documents import router as _documents_router
from src.backend.api.export_preview import router as _export_preview_router
from src.backend.api.mapping_rules import router as _mapping_rules_router
from src.backend.api.master_import import router as _master_import_router
from src.backend.api.product_master import router as _product_master_router
from src.backend.api.schema_analyze import router as _schema_analyze_router
from src.backend.api.templates import router as _templates_router
from src.backend.api.users_admin import router as _users_admin_router
from src.backend.app.health import collect_service_health, get_uptime_seconds
from src.backend.auth.dependencies import (
    get_current_active_user,
    require_password_finalized,
)
from src.backend.db.models import User
from src.backend.ml.llm_router import get_routing_diagnostics, read_cost_log_tail
from src.backend.pipeline.orchestrator import run_pipeline, select_model
from src.backend.services.export_service import (
    create_excel_ledger,
    create_purchase_tax_report,
)
from src.backend.services.rule_engine import validate_required_fields
from src.backend.services.rule_generation_jobs import RULE_GENERATION_JOBS
from src.backend.storage import materialize_local_cache, store_document_bytes
from src.backend.workers.celery_app import celery_app
from src.backend.workers.tasks import process_document

router = APIRouter()
REPO_ROOT = Path(__file__).resolve().parents[3]

# Default demo companies — mirrors DEFAULT_COMPANIES in ux-ui-prototype.html
_DEFAULT_COMPANIES: list[dict[str, Any]] = [
    {"id": "co-1", "name": "บริษัท ยะวัน เทค จำกัด", "taxId": "0105559123456"},
    {"id": "co-2", "name": "บริษัท ยะวัน เทรดดิ้ง จำกัด", "taxId": "0105559654321"},
]

_TASK_STATUS_MAP = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "RETRY": "started",
    "STARTED": "started",
    "PROGRESS": "started",
    "SUCCESS": "success",
    "FAILURE": "failure",
}


def _companies_store_path() -> Path:
    """Return path for the shared companies JSON store.

    Resolution order:
      1. COMPANIES_STORE env var (explicit override)
      2. Parent of RULES_ROOT env var (same data tree as rule files)
      3. REPO_ROOT/data/companies.json (local dev fallback)
    """
    explicit = os.getenv("COMPANIES_STORE", "").strip()
    if explicit:
        return Path(explicit)
    rules_root_env = os.getenv("RULES_ROOT", "").strip()
    if rules_root_env:
        return Path(rules_root_env).parent / "companies.json"
    return REPO_ROOT / "data" / "companies.json"


def _read_companies() -> list[dict[str, Any]]:
    path = _companies_store_path()
    if not path.exists():
        return list(_DEFAULT_COMPANIES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return list(_DEFAULT_COMPANIES)


def _write_companies(companies: list[dict[str, Any]]) -> None:
    path = _companies_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _safe_upload_name(filename: str | None, fallback: str) -> str:
    cleaned = Path(filename or fallback).name.strip()
    return cleaned or fallback


def _normalize_tax_id(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """Check health status of backend dependencies."""
    services = collect_service_health()
    payload = {
        "status": services.overall_status,
        "version": request.app.version,
        "uptime_seconds": get_uptime_seconds(),
        "services": vars(services),
    }
    # Keep liveness endpoint stable for PoC smoke checks; use /health/ready for strict gating.
    return JSONResponse(status_code=200, content=payload)


@router.get("/health/live")
def health_live(request: Request) -> dict[str, Any]:
    return {
        "status": "alive",
        "version": request.app.version,
        "uptime_seconds": get_uptime_seconds(),
    }


@router.get("/health/ready")
def health_ready(request: Request) -> JSONResponse:
    services = collect_service_health()
    ready = all(value == "ok" for value in vars(services).values())
    payload = {
        "status": "ready" if ready else "not_ready",
        "version": request.app.version,
        "uptime_seconds": get_uptime_seconds(),
        "services": vars(services),
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@router.get("/v1/llm/routing")
def llm_routing_diagnostics(
    log_limit: int = Query(20, ge=1, le=200, description="Tail rows from cost log"),
) -> dict[str, Any]:
    """Return current Stage C provider/model routing and recent cost events."""
    settings.reload()
    return {
        "routing": get_routing_diagnostics(),
        "recent_cost_events": read_cost_log_tail(limit=log_limit),
    }


@router.get("/v1/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    _current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Return Celery task execution status, pipeline stage, and latest result
    payload. `stage` (e.g. "queued" / "ocr" / "extract" / "mapping") lets the
    Processing screen show real pipeline progress instead of an opaque
    spinner (W4 Processing UX fix) - it is only meaningful while status is
    "started".
    """
    async_result = AsyncResult(task_id, app=celery_app)
    normalized_status = _TASK_STATUS_MAP.get(async_result.state, "pending")

    stage: str | None = None
    result_payload: Any = None
    if async_result.successful():
        result_payload = async_result.result
    elif async_result.failed():
        result_payload = str(async_result.result)
    elif async_result.state == "PROGRESS":
        meta = async_result.info if isinstance(async_result.info, dict) else {}
        stage = str(meta.get("stage") or "") or None

    return {
        "task_id": task_id,
        "status": normalized_status,
        "stage": stage,
        "result": result_payload,
    }


@router.post("/v1/tasks/process-document/{document_id}")
async def enqueue_document_processing(
    document_id: str,
    _current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """Queue a document processing task to Celery workers."""
    task = process_document.delay(document_id)
    return {
        "task_id": task.id,
        "status": "pending",
        "document_id": document_id,
    }


@router.get("/v1/tasks/diagnostics")
async def get_task_diagnostics(
    _current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Processing worker/queue liveness (W5-CLAUDE-OCR-PENDING-STALL-FIX-08).

    Makes a stalled batch diagnosable instead of leaving the Processing screen on
    permanent `pending`: `worker_count == 0` / `broker_reachable == False` means
    no Celery worker is consuming the queue (so enqueued tasks will never run),
    which is a fundamentally different condition from a task that is merely
    queued. Use this on the Processing screen or in SIT proof to tell "no worker"
    apart from "just queued".
    """

    def _probe() -> dict[str, Any]:
        eager = bool(celery_app.conf.task_always_eager)
        result: dict[str, Any] = {
            "eager": eager,
            "process_document_registered": (
                "src.backend.workers.tasks.process_document" in celery_app.tasks
            ),
            "broker_reachable": False,
            "worker_count": 0,
            "workers": [],
        }
        if eager:
            # Eager mode runs tasks inline in the API process — no separate worker
            # is expected, and there is no pending-stall to diagnose.
            result["broker_reachable"] = True
            return result
        try:
            replies = celery_app.control.ping(timeout=1.0) or []
            workers = [name for reply in replies for name in reply.keys()]
            result["workers"] = workers
            result["worker_count"] = len(workers)
            result["broker_reachable"] = True
        except Exception as exc:  # broker unreachable / control channel down
            result["error"] = str(exc)[:200]
        return result

    try:
        return await asyncio.wait_for(asyncio.to_thread(_probe), timeout=8.0)
    except asyncio.TimeoutError:
        return {
            "eager": bool(celery_app.conf.task_always_eager),
            "process_document_registered": True,
            "broker_reachable": False,
            "worker_count": 0,
            "workers": [],
            "error": "diagnostics probe timed out (broker likely unreachable)",
        }


@router.post("/process")
async def process(
    file_path: str | None = Query(None, description="Path to file on disk"),
    company_id: str | None = Form(
        None, description="Company rule context for journal routing"
    ),
    company_tax_id: str | None = Form(
        None, description="Company tax id for buyer tax-id verification"
    ),
    force_refresh: bool = Form(
        False,
        description="Bypass OCR/extraction/journal caches and recompute pipeline",
    ),
    file: UploadFile | None = File(None, description="Uploaded document blob"),
) -> dict[str, Any]:
    """Process a document (OCR -> Field Extraction -> GL Alignment Routing)."""
    settings.reload()
    temp_dir = settings.UPLOAD_ROOT
    temp_dir.mkdir(parents=True, exist_ok=True)

    if file:
        content = await file.read()
        company_scope = company_id or "unassigned-company"
        stored_file = store_document_bytes(
            content=content,
            filename=file.filename,
            company_id=company_scope,
            content_type=file.content_type,
        )
        # The pipeline still consumes a local path today, so we keep a cache copy
        # after object-storage upload until TASK-801B/TASK-805 move processing off disk.
        target_path = materialize_local_cache(
            content=content,
            filename=file.filename,
            sha256=stored_file["sha256"],
        )
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
    ctx = await run_pipeline(
        resolved_path,
        company_id=company_id,
        company_tax_id=company_tax_id,
        force_refresh=force_refresh,
    )

    if ctx.error:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {ctx.error}")

    fields = ctx.extraction_output.get("fields", {})
    buyer_tax_id = _normalize_tax_id(fields.get("buyer_tax_id"))
    company_tax_norm = _normalize_tax_id(company_tax_id)
    tax_id_check = {
        "buyer_tax_id": buyer_tax_id,
        "company_tax_id": company_tax_norm,
        "is_match": bool(
            buyer_tax_id and company_tax_norm and buyer_tax_id == company_tax_norm
        ),
        "has_buyer_tax_id": bool(buyer_tax_id),
    }
    validation = validate_required_fields(
        fields, ["invoice_number", "invoice_date", "total_amount"]
    )

    response_payload = {
        "source_file": resolved_path,
        "text": "\n".join(
            [b.get("text", "") for b in ctx.ocr_output.get("blocks", [])]
        ),
        "ocr_warnings": ctx.ocr_output.get("warnings", []),
        "ocr_degraded": bool(ctx.ocr_output.get("warnings")),
        "fields": fields,
        "validation": validation,
        "tax_id_check": tax_id_check,
        "overall_confidence": ctx.overall_confidence,
        "stage_c_applied": ctx.stage_c_applied,
        "escalated_to_sonnet": ctx.escalated_to_sonnet,
        "stage_c": ctx.journal_output.get("stage_c")
        or ctx.extraction_output.get("stage_c")
        or {},
        "extraction": ctx.extraction_output,
        "journal": ctx.journal_output,
        "company_id": ctx.company_id,
        "pipeline_status": ctx.status.name,
        "model_used": select_model(ctx),
    }
    if file:
        response_payload["storage_key"] = stored_file["storage_key"]
        response_payload["storage_provider"] = stored_file["provider"]
    return response_payload


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
        settings.reload()
        temp_dir = settings.EXPORT_ROOT
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


@router.post("/export-purchase-tax-report", status_code=307)
async def export_purchase_tax_report_legacy(request: Request) -> Response:
    """307 redirect — use POST /v1/export-purchase-tax-report instead."""
    return Response(
        status_code=307,
        headers={
            "Location": str(request.url).replace(
                "/export-purchase-tax-report", "/v1/export-purchase-tax-report", 1
            )
        },
    )


@router.post("/v1/export-purchase-tax-report")
async def export_purchase_tax_report(
    payload: dict[str, Any] = Body(...),
) -> FileResponse:
    """Generate Purchase Tax Report (รายงานภาษีซื้อ) via template engine (TASK-1101)."""
    try:
        settings.reload()
        temp_dir = settings.EXPORT_ROOT
        temp_dir.mkdir(parents=True, exist_ok=True)
        xlsx_path = temp_dir / "purchase_tax_report.xlsx"

        documents = payload.get("documents", [])
        company_info = payload.get("companyInfo", {})
        period = payload.get("reportPeriod", ["", ""])

        create_purchase_tax_report(
            documents=documents,
            output_path=xlsx_path,
            company_info=company_info,
            report_period=tuple(period),
        )

        return FileResponse(
            path=str(xlsx_path),
            filename="purchase_tax_report.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate purchase tax report: {exc}",
        )


@router.post("/v1/rules/generate")
async def generate_rules(
    company_id: str = Form(...),
    company_name: str = Form(...),
    business_type: str = Form("service"),
    provider: str = Form("auto"),
    model: str = Form(""),
    coa_file: UploadFile = File(...),
    mapping_file: UploadFile = File(...),
) -> dict[str, Any]:
    settings.reload()
    uploads_dir = settings.UPLOAD_ROOT / "rule_uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    coa_path = (
        uploads_dir / f"{company_id}_{_safe_upload_name(coa_file.filename, 'coa.pdf')}"
    )
    mapping_path = (
        uploads_dir
        / f"{company_id}_{_safe_upload_name(mapping_file.filename, 'mapping.docx')}"
    )

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


@router.post("/v1/rules/generate/{job_id}/save-edits")
async def save_rule_edits(
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job = await RULE_GENERATION_JOBS.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Job is not done")

    edited_rules = payload.get("journal_rules")
    if not isinstance(edited_rules, list):
        raise HTTPException(
            status_code=422,
            detail="payload.journal_rules must be a non-empty array",
        )

    try:
        updated_result = await RULE_GENERATION_JOBS.save_rule_edits(
            job_id, edited_rules
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        **updated_result,
        "job_id": job_id,
        "status": "done",
        "approved": bool(
            (await RULE_GENERATION_JOBS.get_job(job_id) or {}).get("approved", False)
        ),
    }


# ── Company store ─────────────────────────────────────────────────────────────


@router.get("/v1/companies")
async def get_companies() -> dict[str, Any]:
    """Return the shared company list from server-side storage."""
    return {"companies": _read_companies()}


@router.post("/v1/companies/sync")
async def sync_companies(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Persist the full company list from the frontend to server-side storage.

    The frontend calls this on every company create/edit/delete so data is
    shared across all browsers and machines.
    """
    companies = payload.get("companies")
    if not isinstance(companies, list):
        raise HTTPException(status_code=422, detail="'companies' must be a list")
    # Basic structural validation — each item needs id, name, taxId
    for item in companies:
        if not isinstance(item, dict) or not all(
            k in item for k in ("id", "name", "taxId")
        ):
            raise HTTPException(
                status_code=422,
                detail="Each company must have 'id', 'name', and 'taxId' fields",
            )
    _write_companies(companies)
    return {"ok": True, "count": len(companies)}


# First-login / reset-password enforcement (TASK-1204 ac_1204 first-login
# intent — TC-RWG02-03): `must_change_password` was already set correctly on
# create/reset, but nothing enforced it, so a user could keep using a one-time
# temp password indefinitely. `require_password_finalized` already existed in
# auth/dependencies.py but was never attached to a real route. Wiring it here
# (rather than per-endpoint) covers every admin/company/master-data/template/
# export surface in one place; `/v1/auth/*` intentionally stays exempt so the
# forced first-login change-password flow itself remains reachable.
_PASSWORD_FINALIZED = [Depends(require_password_finalized)]

# ── TASK-1009: Schema Analyzer ─────────────────────────────────────────────
router.include_router(_schema_analyze_router, dependencies=_PASSWORD_FINALIZED)

# ── TASK-1207: Vendor & Customer Master Import ──────────────────────────────
router.include_router(_master_import_router, dependencies=_PASSWORD_FINALIZED)

# ── TASK-1002: Template CRUD + Preview ─────────────────────────────────────
router.include_router(_templates_router, dependencies=_PASSWORD_FINALIZED)

# ── TASK-1104: Export Preview + Balance Validation ──────────────────────────
router.include_router(_export_preview_router, dependencies=_PASSWORD_FINALIZED)

# ── W4 SIT closure: real Company/User CRUD (TASK-1203/TASK-1204 minimal slice) ─
router.include_router(_companies_admin_router, dependencies=_PASSWORD_FINALIZED)
router.include_router(_users_admin_router, dependencies=_PASSWORD_FINALIZED)

# ── TASK-1203: Chart of Accounts import (YAML/CSV/PDF) ─────────────────────
router.include_router(_coa_router, dependencies=_PASSWORD_FINALIZED)

# ── TASK-1203: Mapping Rules document-ingestion workflow ───────────────────
router.include_router(_mapping_rules_router, dependencies=_PASSWORD_FINALIZED)

# ── Pack C: Product/price-list master (separate from enable_stock) ────────
router.include_router(_product_master_router, dependencies=_PASSWORD_FINALIZED)

# ── Pack B: real Upload -> Process -> Review Scan -> Review Mapping workflow ─
router.include_router(_documents_router, dependencies=_PASSWORD_FINALIZED)
