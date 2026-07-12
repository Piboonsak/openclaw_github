"""Regression tests for HR-07-02: Processing timeouts / circuit breakers.

These would FAIL on the pre-fix code (a slow provider/line-item call rode the
document task straight to Celery's ``soft_time_limit`` and killed the whole
batch). They prove:

  * an over-running OPTIONAL line-item stage is bounded and non-blocking — the
    document still reaches Review Scan;
  * one document's slow optional stage does NOT fail an unrelated sibling
    document processed at the same time (batch isolation);
  * an over-running Stage C cascade is bounded and the header survives;
  * per-stage evidence (elapsed timings + the failing stage) is captured.
"""

from __future__ import annotations

import asyncio
import time

from src.backend.db.enums import DocumentStatus
from src.backend.pipeline import orchestrator
from src.backend.services.document_workflow import build_pipeline_persistence_plan


def _extraction(invoice: str = "INV-1", *, low_conf: bool = False) -> dict:
    """A well-formed, arithmetically-reconciling header extraction result.

    ``low_conf`` drops one critical field below the Stage C escalation threshold
    so the cascade is actually invoked (needed to exercise the Stage C breaker).
    """
    seller_conf = 0.2 if low_conf else 0.95
    return {
        "fields": {
            "invoice_number": invoice,
            "invoice_date": "2026-07-01",
            "seller_name": "ผู้ขาย",
            "seller_tax_id": "0107544000043",
            "buyer_tax_id": "0125561025189",
            "net_amount": "1000.00",
            "vat_amount": "70.00",
            "total_amount": "1070.00",
            "currency": "THB",
            "source_text": f"เอกสาร {invoice}",
        },
        "confidence_per_field": {
            "seller_tax_id": seller_conf,
            "buyer_tax_id": 0.95,
            "net_amount": 0.95,
            "vat_amount": 0.95,
            "total_amount": 0.95,
            "invoice_number": 0.95,
            "invoice_date": 0.95,
        },
        "meta": {"ocr_confidence": 0.95},
    }


def _patch_header(monkeypatch, extraction) -> None:
    monkeypatch.setattr(orchestrator, "run_ocr", lambda image_path, **k: {"ocr_confidence": 0.95, "_path": image_path})
    if callable(extraction):
        monkeypatch.setattr(orchestrator, "run_extraction", extraction)
    else:
        monkeypatch.setattr(orchestrator, "run_extraction", lambda *a, **k: extraction)
    monkeypatch.setattr(
        orchestrator, "run_journal_router", lambda *a, **k: {"is_balanced": True, "postings": []}
    )


def test_line_item_stage_timeout_is_nonblocking(monkeypatch):
    """A hung optional line-item stage must be cut off and the document must
    still complete with empty/pending line items (never FAILED)."""
    monkeypatch.setenv("LINE_ITEM_STAGE_TIMEOUT_SECONDS", "0.05")
    _patch_header(monkeypatch, _extraction("INV-1"))

    def _slow_line_items(**kwargs):
        time.sleep(0.6)  # far beyond the 0.05s stage budget
        return {"line_items": [{"product_name": "X"}], "notes": []}

    monkeypatch.setattr(orchestrator, "extract_line_items", _slow_line_items)

    ctx = asyncio.run(orchestrator.run_pipeline("/tmp/x.pdf", enable_stock=True))

    assert ctx.status == orchestrator.StageResult.SUCCESS
    assert ctx.line_item_timed_out is True
    assert ctx.extraction_output.get("line_items") == []
    # Header + journal routing completed regardless of the stalled optional stage.
    assert ctx.extraction_output["fields"]["invoice_number"] == "INV-1"
    assert ctx.journal_output.get("is_balanced") is True


def test_slow_optional_stage_does_not_fail_sibling_document(monkeypatch):
    """Batch isolation: two documents processed concurrently — one with a hung
    line-item stage — must both succeed, and the fast one must still get its
    line items. Pre-fix, the hung call would starve the shared worker budget."""
    monkeypatch.setenv("LINE_ITEM_STAGE_TIMEOUT_SECONDS", "0.05")

    def _extract(ocr_output, **k):
        invoice = "HANG" if "hang" in str(ocr_output.get("_path", "")) else "FAST"
        return _extraction(invoice)

    _patch_header(monkeypatch, _extract)

    def _line_items(*, image_path, ocr_text, metadata, **k):
        if metadata.get("invoice_number") == "HANG":
            time.sleep(0.6)
        return {"line_items": [{"product_name": "P"}], "notes": []}

    monkeypatch.setattr(orchestrator, "extract_line_items", _line_items)

    async def _run_batch():
        return await asyncio.gather(
            orchestrator.run_pipeline("hang.pdf", enable_stock=True),
            orchestrator.run_pipeline("fast.pdf", enable_stock=True),
        )

    hang_ctx, fast_ctx = asyncio.run(_run_batch())

    assert hang_ctx.status == orchestrator.StageResult.SUCCESS
    assert fast_ctx.status == orchestrator.StageResult.SUCCESS
    # The slow document timed out on line items but still completed...
    assert hang_ctx.line_item_timed_out is True
    assert hang_ctx.extraction_output.get("line_items") == []
    # ...and did NOT prevent the sibling from producing its line items.
    assert fast_ctx.line_item_timed_out is False
    assert fast_ctx.extraction_output.get("line_items") == [{"product_name": "P"}]


def test_stage_c_timeout_keeps_header(monkeypatch):
    """A hung Stage C cascade must be cut off; the document keeps the header it
    already had and reaches Review Scan (low-confidence fields stay flagged)."""
    monkeypatch.setenv("STAGE_C_STAGE_TIMEOUT_SECONDS", "0.05")
    _patch_header(monkeypatch, _extraction("INV-9", low_conf=True))

    def _slow_cascade(**kwargs):
        time.sleep(0.6)
        return {
            "fields": {"seller_tax_id": "9999999999999"},
            "confidence": {"seller_tax_id": 0.99},
            "attempts": [],
            "unresolved_fields": [],
        }

    monkeypatch.setattr(orchestrator, "cascade_repair", _slow_cascade)

    ctx = asyncio.run(orchestrator.run_pipeline("/tmp/x.pdf"))

    assert ctx.status == orchestrator.StageResult.SUCCESS
    assert ctx.stage_c_timed_out is True
    assert ctx.extraction_output.get("stage_c_timed_out") is True
    # The slow repair was never applied — original header stands.
    assert ctx.extraction_output["fields"]["invoice_number"] == "INV-9"
    assert ctx.extraction_output["fields"]["seller_tax_id"] == "0107544000043"


def test_stage_history_records_each_stage(monkeypatch):
    _patch_header(monkeypatch, _extraction("INV-1"))

    ctx = asyncio.run(orchestrator.run_pipeline("/tmp/x.pdf"))

    stages = [entry["stage"] for entry in ctx.stage_history]
    assert stages == ["ocr", "extract", "mapping"]
    assert all(isinstance(entry.get("elapsed_s"), (int, float)) for entry in ctx.stage_history)
    assert ctx.failed_stage is None


def test_failed_stage_is_recorded_and_surfaced(monkeypatch):
    """On failure the active stage is captured and the persistence plan prefixes
    processing_error with it, so the Processing UI shows where the doc died."""
    _patch_header(monkeypatch, _extraction("INV-1"))

    def _boom(*a, **k):
        raise RuntimeError("router exploded")

    monkeypatch.setattr(orchestrator, "run_journal_router", _boom)

    ctx = asyncio.run(orchestrator.run_pipeline("/tmp/x.pdf"))

    assert ctx.status == orchestrator.StageResult.FAILED
    assert ctx.failed_stage == "mapping"

    plan = build_pipeline_persistence_plan(ctx)
    assert plan.status == DocumentStatus.FAILED.value
    assert plan.processing_error.startswith("[mapping]")
    assert "router exploded" in plan.processing_error
