"""Epic 5 pipeline orchestrator skeleton (TASK-501/502/503)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from config.settings import settings
from src.backend.ml.amount_reconciler import apply_amount_confidence, reconcile_amounts
from src.backend.ml.field_extractor import run_extraction
from src.backend.ml.llm_claude import STAGE_C_SYSTEM_PROMPT
from src.backend.ml.line_item_extractor import extract_line_items
from src.backend.ml.llm_router import cascade_repair
from src.backend.ml.ocr import run_ocr
from src.backend.services.rule_engine import run_journal_router

# Threshold below which LLM escalation is triggered (aligned with design D2)
CONFIDENCE_ESCALATION_THRESHOLD = 0.70
STAGE_C_CRITICAL_FIELDS = {
    "invoice_number",
    "invoice_date",
    "seller_tax_id",
    "buyer_tax_id",
    "net_amount",
    "vat_amount",
    "total_amount",
}

# Weighted critical-field model for overall confidence. Money + tax-id fields
# dominate; document identifiers and names contribute little. A wrong amount must
# drag overall confidence down far more than a misread invoice number.
_FIELD_WEIGHTS = {
    "seller_tax_id": 3.0,
    "buyer_tax_id": 3.0,
    "net_amount": 3.0,
    "vat_amount": 3.0,
    "total_amount": 3.0,
    "wht_amount": 1.5,
    "invoice_number": 1.0,
    "invoice_date": 1.0,
    "seller_name": 1.0,
}
# Fields that must be present for a document to earn high confidence.
_REQUIRED_CRITICAL = (
    "seller_tax_id",
    "buyer_tax_id",
    "net_amount",
    "vat_amount",
    "total_amount",
)
# Hard-gate ceilings.
_GATE_RECONCILE_FAIL = 0.69
_GATE_TAX_MISMATCH = 0.79
_GATE_CRITICAL_MISSING = 0.74


class StageResult(Enum):
    SUCCESS = auto()
    FAILED = auto()


@dataclass
class PipelineContext:
    source_file: str
    company_id: str | None = None
    ocr_output: dict[str, Any] = field(default_factory=dict)
    extraction_output: dict[str, Any] = field(default_factory=dict)
    stage_c_output: dict[str, Any] = field(default_factory=dict)
    journal_output: dict[str, Any] = field(default_factory=dict)
    line_item_output: dict[str, Any] = field(default_factory=dict)
    overall_confidence: float = 0.0
    stage_c_applied: bool = False
    escalated_to_sonnet: bool = False
    status: StageResult = StageResult.SUCCESS
    error: str | None = None
    # HR-07-02 per-stage evidence: one entry per completed stage
    # ({"stage": str, "elapsed_s": float}) plus the stage that was active when a
    # failure/timeout occurred, so the Processing UI and logs can say exactly
    # where a document spent its time or died.
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    failed_stage: str | None = None
    stage_c_timed_out: bool = False
    line_item_timed_out: bool = False


def _compute_overall_confidence(
    fields: dict[str, Any],
    confidence: dict[str, Any],
    ocr_output: dict[str, Any],
    reconciliation: dict[str, Any] | None = None,
    tax_id_match: bool | None = None,
) -> float:
    """Compute overall confidence from weighted critical fields plus hard gates.

    Money and tax-id fields dominate the weighted field score. Hard gates then
    cap the result when the document fails arithmetic reconciliation, the buyer
    tax id does not match the company, or a required critical field is missing —
    so a confident-but-wrong document cannot reach the green band.
    """
    ocr_conf = min(1.0, max(0.0, float(ocr_output.get("ocr_confidence", 0.75))))

    weighted_sum = 0.0
    weight_total = 0.0
    for key, weight in _FIELD_WEIGHTS.items():
        value = confidence.get(key)
        if isinstance(value, (int, float)):
            weighted_sum += float(value) * weight
            weight_total += weight
    field_conf = weighted_sum / weight_total if weight_total else 0.6

    present = sum(1 for k in _REQUIRED_CRITICAL if str(fields.get(k) or "").strip())
    completeness = present / len(_REQUIRED_CRITICAL)

    overall = ocr_conf * 0.20 + field_conf * 0.55 + completeness * 0.25

    # --- Hard gates ---
    if reconciliation is not None and not reconciliation.get("reconciled", True):
        overall = min(overall, _GATE_RECONCILE_FAIL)
    if tax_id_match is False:
        overall = min(overall, _GATE_TAX_MISMATCH)
    if present < len(_REQUIRED_CRITICAL):
        overall = min(overall, _GATE_CRITICAL_MISSING)

    has_low_critical = any(
        isinstance(confidence.get(key), (int, float))
        and float(confidence.get(key, 0.0)) < CONFIDENCE_ESCALATION_THRESHOLD
        for key in STAGE_C_CRITICAL_FIELDS
    )
    if has_low_critical:
        overall = min(overall, CONFIDENCE_ESCALATION_THRESHOLD - 0.01)

    return overall


def _to_amount_float(value: Any) -> float | None:
    text = str(value if value is not None else "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _amount_close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    tolerance = max(1.0, max(abs(a), abs(b)) * 0.005)
    return abs(a - b) <= tolerance


def _build_numeric_consistency_alerts(
    fields: dict[str, Any],
    reconciliation: dict[str, Any],
) -> list[dict[str, str]]:
    """Build mismatch notifications for 5 key numeric fields with recommendations."""
    checks = reconciliation.get("checks", {}) or {}
    corrected = reconciliation.get("corrected", {}) or {}

    net = _to_amount_float(fields.get("net_amount"))
    vat = _to_amount_float(fields.get("vat_amount"))
    total = _to_amount_float(fields.get("total_amount"))
    wht = _to_amount_float(fields.get("wht_amount"))
    wht_rate = _to_amount_float(fields.get("wht_rate"))
    paid = _to_amount_float(fields.get("amount_paid"))
    rate = _to_amount_float(fields.get("vat_rate")) or 7.0
    layout = str(reconciliation.get("layout") or "")

    alerts: list[dict[str, str]] = []

    def _add(
        field_name: str, current: float | None, recommended: float | None, reason: str
    ) -> None:
        if recommended is None:
            return
        alerts.append(
            {
                "field": field_name,
                "current": "" if current is None else f"{current:.2f}",
                "recommended": f"{recommended:.2f}",
                "reason": reason,
            }
        )

    if checks.get("total") == "fail":
        rec_total = _to_amount_float(corrected.get("total_amount"))
        if rec_total is None and net is not None and vat is not None:
            rec_total = net + vat
        _add("total_amount", total, rec_total, "net_plus_vat_mismatch")

    if checks.get("vat") == "fail":
        rec_vat: float | None = None
        if layout == "inclusive" and total is not None and rate > 0:
            rec_vat = total * rate / (100.0 + rate)
        elif net is not None and rate > 0:
            rec_vat = net * rate / 100.0
        elif total is not None and rate > 0:
            rec_vat = total * rate / (100.0 + rate)
        _add("vat_amount", vat, rec_vat, "vat_formula_mismatch")

    if checks.get("wht") == "fail":
        rec_wht: float | None = None
        if wht_rate and wht_rate > 0:
            if net is not None:
                rec_wht = net * wht_rate / 100.0
            elif total is not None:
                rec_wht = total * wht_rate / 100.0
        _add("wht_amount", wht, rec_wht, "wht_formula_mismatch")

    if checks.get("paid") == "fail" and total is not None:
        rec_paid = total - (wht or 0.0)
        _add("amount_paid", paid, rec_paid, "paid_not_equal_total_minus_wht")

    return alerts


def _backfill_amounts_from_reconciliation(
    fields: dict[str, Any],
    reconciliation: dict[str, Any],
) -> list[str]:
    """Backfill missing net/vat/total only when at least two values are present.

    This keeps display fields complete (for review/export) while avoiding
    speculative fill-ins from a single observed value.
    """
    amount_keys = ("net_amount", "vat_amount", "total_amount")
    observed_count = sum(1 for key in amount_keys if str(fields.get(key) or "").strip())
    if observed_count < 2:
        return []

    derived = reconciliation.get("derived") or {}
    key_map = {
        "net_amount": "net",
        "vat_amount": "vat",
        "total_amount": "gross",
    }

    backfilled: list[str] = []
    for field_key, derived_key in key_map.items():
        if str(fields.get(field_key) or "").strip():
            continue
        value = derived.get(derived_key)
        if isinstance(value, (int, float)):
            fields[field_key] = f"{float(value):.2f}"
            backfilled.append(field_key)
    return backfilled


def _realign_amount_slots(
    fields: dict[str, Any],
    reconciliation: dict[str, Any],
) -> list[str]:
    """Realign mis-slotted net/total when arithmetic strongly indicates swap.

    This fixes a common extraction issue where subtotal is written into
    ``total_amount``; for exclusive VAT docs that causes net to be derived from the
    wrong base unless we move values back to canonical slots.
    """
    derived = reconciliation.get("derived") or {}
    d_net = _to_amount_float(derived.get("net"))
    d_gross = _to_amount_float(derived.get("gross"))
    if d_net is None or d_gross is None:
        return []

    net = _to_amount_float(fields.get("net_amount"))
    total = _to_amount_float(fields.get("total_amount"))

    updated: list[str] = []

    if net is None and total is not None and _amount_close(total, d_net):
        fields["net_amount"] = f"{d_net:.2f}"
        updated.append("net_amount")
        if not _amount_close(total, d_gross):
            fields["total_amount"] = f"{d_gross:.2f}"
            updated.append("total_amount")
        return updated

    if net is not None and total is not None:
        # Both present but reversed: net holds gross and total holds net.
        if _amount_close(net, d_gross) and _amount_close(total, d_net):
            fields["net_amount"] = f"{d_net:.2f}"
            fields["total_amount"] = f"{d_gross:.2f}"
            updated.extend(["net_amount", "total_amount"])

    return updated


def _stabilize_amount_confidence(
    fields: dict[str, Any],
    confidence: dict[str, Any],
    reconciliation: dict[str, Any],
    ocr_confidence: float,
) -> None:
    """Avoid under-scoring amount fields when arithmetic checks are fully consistent.

    The extractor can assign conservative confidence to numeric fields even when
    Net/VAT/Total relationships reconcile perfectly. In that case, keep a minimum
    floor so overall confidence reflects both OCR quality and arithmetic validity.
    """
    checks = reconciliation.get("checks", {}) or {}
    if not reconciliation.get("reconciled"):
        return
    if checks.get("total") != "ok" or checks.get("vat") != "ok":
        return

    floor = min(0.90, max(0.72, float(ocr_confidence) * 0.90))
    for key in ("net_amount", "vat_amount", "total_amount"):
        if not str(fields.get(key) or "").strip():
            continue
        current = confidence.get(key)
        if isinstance(current, (int, float)):
            confidence[key] = max(float(current), floor)


async def run_pipeline(
    image_path: str,
    company_id: str | None = None,
    company_tax_id: str | None = None,
    force_refresh: bool = False,
    progress_callback: Callable[[str], None] | None = None,
    enable_stock: bool = False,
) -> PipelineContext:
    """Run OCR -> extraction -> Stage C cascade repair -> journal routing.

    `progress_callback`, when provided, is invoked with a short stage name at
    each key boundary ("ocr", "extract", "line_item", "mapping") so async callers
    (the Celery `process_document` task) can surface real progress instead of a
    single opaque "processing" state. It is a best-effort UI signal only and
    must never affect pipeline behavior if it raises.

    `enable_stock` (from `Company.settings.enable_stock`) gates a non-blocking
    line-item extraction sub-stage after header extraction. Its failure never
    fails the pipeline — header extraction stands on its own.
    """

    settings.reload()
    ctx = PipelineContext(source_file=image_path, company_id=company_id)

    # HR-07-02 stage-evidence tracker: remember the active stage + its start
    # time so we can record per-stage elapsed and, on failure, the exact stage
    # that was running.
    _stage_state: dict[str, Any] = {"name": None, "t0": time.monotonic()}

    def _record_stage_end() -> None:
        prev = _stage_state["name"]
        if prev is None:
            return
        ctx.stage_history.append(
            {
                "stage": prev,
                "elapsed_s": round(time.monotonic() - _stage_state["t0"], 2),
            }
        )
        _stage_state["name"] = None

    def _emit(stage: str) -> None:
        # Close the previous stage's timing window, open this one, then fire the
        # best-effort progress callback (a raising callback must never affect the
        # pipeline).
        _record_stage_end()
        _stage_state["name"] = stage
        _stage_state["t0"] = time.monotonic()
        if progress_callback is None:
            return
        try:
            progress_callback(stage)
        except Exception:
            pass

    async def _run_stage_with_timeout(func: Callable[[], Any], timeout_s: float) -> Any:
        """Run a blocking stage function in a worker thread bounded by a wall
        clock (HR-07-02). Raises ``asyncio.TimeoutError`` if it overruns. The
        orphaned worker thread is itself bounded by the provider HTTP timeout, so
        it drains shortly after rather than riding the task to soft_time_limit."""
        return await asyncio.wait_for(asyncio.to_thread(func), timeout_s)

    try:
        _emit("ocr")
        ctx.ocr_output = run_ocr(
            image_path, cache_root=settings.CACHE_ROOT, force_refresh=force_refresh
        )
        _emit("extract")
        ctx.extraction_output = run_extraction(
            ctx.ocr_output, cache_root=settings.CACHE_ROOT, force_refresh=force_refresh
        )
        ctx.extraction_output["company_id"] = company_id

        fields = ctx.extraction_output.get("fields", {})
        confidence = ctx.extraction_output.get("confidence_per_field", {})
        meta = ctx.extraction_output.get("meta", {})

        # Use OCR confidence from extraction meta (where the extractor stores it)
        ocr_info = {"ocr_confidence": meta.get("ocr_confidence", 0.75)}

        # --- Stage C: per-field cascade (regex -> free -> paid) ---
        overall = _compute_overall_confidence(fields, confidence, ocr_info)
        low_conf_keys = [
            k
            for k, v in confidence.items()
            if k in STAGE_C_CRITICAL_FIELDS
            and isinstance(v, (int, float))
            and float(v) < CONFIDENCE_ESCALATION_THRESHOLD
        ]

        if low_conf_keys:
            raw_text = fields.get("source_text", "")
            # HR-07-02: bound the whole Stage C cascade (which can attempt several
            # provider/model calls) with a wall clock. On overrun keep whatever
            # header we already have and continue — low-confidence fields simply
            # stay flagged for human review rather than killing the document.
            stage_c_started = time.monotonic()
            try:
                cascade = await _run_stage_with_timeout(
                    lambda: cascade_repair(
                        raw_text=raw_text,
                        current_fields=fields,
                        current_confidence=confidence,
                        system_prompt=STAGE_C_SYSTEM_PROMPT,
                        image_path=image_path,
                    ),
                    float(getattr(settings, "STAGE_C_STAGE_TIMEOUT_SECONDS", 240) or 240),
                )
            except asyncio.TimeoutError:
                ctx.stage_c_timed_out = True
                cascade = {
                    "fields": {},
                    "confidence": {},
                    "attempts": [],
                    "unresolved_fields": low_conf_keys,
                    "skipped": True,
                    "skip_reason": "stage_c_timeout",
                }
                ctx.extraction_output["stage_c_timed_out"] = True
            ctx.extraction_output["stage_c_elapsed_s"] = round(
                time.monotonic() - stage_c_started, 2
            )
            ctx.stage_c_output = cascade
            if cascade.get("fields"):
                fields.update(cascade["fields"])
                confidence.update(cascade["confidence"])
                ctx.extraction_output["stage_c_applied"] = True
                ctx.extraction_output["stage_c_reason"] = (
                    f"low_confidence_fields:{low_conf_keys}"
                )
                ctx.stage_c_applied = True
            attempts = cascade.get("attempts", [])
            ctx.extraction_output["stage_c_attempts"] = attempts
            if attempts:
                first_attempt = attempts[0]
                last_attempt = attempts[-1]
                ctx.extraction_output["stage_c_initial_provider"] = first_attempt.get(
                    "provider", ""
                )
                ctx.extraction_output["stage_c_initial_model"] = first_attempt.get(
                    "model", ""
                )
                ctx.extraction_output["stage_c_provider"] = last_attempt.get(
                    "provider", ""
                )
                ctx.extraction_output["stage_c_model"] = last_attempt.get("model", "")
            unresolved = cascade.get("unresolved_fields", [])
            if unresolved:
                ctx.extraction_output["stage_c_unresolved_fields"] = unresolved

        # --- Re-run reconciliation AFTER Stage C may have overwritten amounts ---
        # The rules pass reconciled the original extraction, but Stage C can change
        # net/vat/total. Re-anchor on the (possibly repaired) document VAT, reapply
        # per-field penalties, then auto-correct gross when the printed total is the
        # post-WHT paid amount.
        reconciliation = reconcile_amounts(fields)
        realigned_fields = _realign_amount_slots(fields, reconciliation)
        if realigned_fields:
            reconciliation = reconcile_amounts(fields)
            ctx.extraction_output["reconciliation_realigned_fields"] = realigned_fields
        backfilled_fields = _backfill_amounts_from_reconciliation(
            fields, reconciliation
        )
        if backfilled_fields:
            # Re-run after backfilling to keep derived/checks in sync with surfaced fields.
            reconciliation = reconcile_amounts(fields)
            ctx.extraction_output["reconciliation_backfilled_fields"] = (
                backfilled_fields
            )
        apply_amount_confidence(fields, confidence, reconciliation)
        _stabilize_amount_confidence(
            fields,
            confidence,
            reconciliation,
            float(ocr_info.get("ocr_confidence", 0.75) or 0.75),
        )
        if reconciliation.get("total_is_paid"):
            for key, value in reconciliation.get("corrected", {}).items():
                fields[key] = value
            # Re-reconcile after auto-correction so downstream sees consistent state.
            reconciliation = reconcile_amounts(fields)
            apply_amount_confidence(fields, confidence, reconciliation)
            _stabilize_amount_confidence(
                fields,
                confidence,
                reconciliation,
                float(ocr_info.get("ocr_confidence", 0.75) or 0.75),
            )

        numeric_alerts = _build_numeric_consistency_alerts(fields, reconciliation)
        fields["numeric_consistency_alerts"] = numeric_alerts
        fields["reconciliation"] = reconciliation
        ctx.extraction_output["reconciliation"] = reconciliation
        ctx.extraction_output["vat_layout"] = reconciliation.get("layout")
        ctx.extraction_output["numeric_consistency_alerts"] = numeric_alerts

        # Buyer tax-id vs company tax-id gate.
        tax_id_match: bool | None = None
        if company_tax_id:
            buyer_tax_id = "".join(
                ch for ch in str(fields.get("buyer_tax_id") or "") if ch.isdigit()
            )
            company_digits = "".join(ch for ch in str(company_tax_id) if ch.isdigit())
            if buyer_tax_id and company_digits:
                tax_id_match = buyer_tax_id == company_digits
                if not tax_id_match:
                    confidence["buyer_tax_id"] = min(
                        float(confidence.get("buyer_tax_id", 0.9) or 0.0), 0.45
                    )
        ctx.extraction_output["tax_id_match"] = tax_id_match

        # Critical flags surfaced to the frontend.
        ctx.extraction_output["critical_flags"] = {
            "reconciled": reconciliation.get("reconciled"),
            "vat_check": reconciliation.get("checks", {}).get("vat"),
            "total_check": reconciliation.get("checks", {}).get("total"),
            "wht_check": reconciliation.get("checks", {}).get("wht"),
            "total_is_paid": reconciliation.get("total_is_paid"),
            "tax_id_match": tax_id_match,
            "mismatches": reconciliation.get("mismatches", []),
            "numeric_consistency_alerts": numeric_alerts,
        }

        # Recompute after Stage C repair + reconciliation
        overall = _compute_overall_confidence(
            fields, confidence, ocr_info, reconciliation, tax_id_match
        )

        # Sonnet escalation now handled within cascade_repair() model plan.
        ctx.escalated_to_sonnet = bool(
            any(
                "sonnet" in str(item.get("model", "")).lower()
                and not item.get("skipped")
                for item in (ctx.extraction_output.get("stage_c_attempts") or [])
            )
        )
        ctx.extraction_output["escalated_to_sonnet"] = ctx.escalated_to_sonnet

        # Final overall confidence
        overall = _compute_overall_confidence(
            fields, confidence, ocr_info, reconciliation, tax_id_match
        )
        ctx.overall_confidence = overall
        ctx.extraction_output["overall_confidence"] = overall

        # --- Non-blocking line-item extraction (Epic 9), only when the owning
        # company has enable_stock. Wrapped in its own try/except so a failure
        # never touches ctx.status or blocks header persistence / journal
        # routing — header extraction stands on its own. ---
        if enable_stock:
            _emit("line_item")
            try:
                metadata = {
                    "doc_id": company_id or "",
                    "invoice_number": fields.get("invoice_number", ""),
                    "invoice_date": fields.get("invoice_date", ""),
                    "seller_name": fields.get("seller_name", ""),
                    "total_amount": fields.get("total_amount", ""),
                    "currency": fields.get("currency", "THB") or "THB",
                }
                ocr_text = fields.get("source_text", "") or ""
                # HR-07-02: the optional line-item stage is bounded by its own wall
                # clock AND catches every failure, so a hung/slow line-item LLM
                # call can never stop the document from reaching Review Scan.
                ctx.line_item_output = await _run_stage_with_timeout(
                    lambda: extract_line_items(
                        image_path=image_path,
                        ocr_text=ocr_text,
                        metadata=metadata,
                    ),
                    float(
                        getattr(settings, "LINE_ITEM_STAGE_TIMEOUT_SECONDS", 75) or 75
                    ),
                )
                ctx.extraction_output["line_items"] = ctx.line_item_output.get(
                    "line_items", []
                )
            except asyncio.TimeoutError:
                ctx.line_item_timed_out = True
                ctx.line_item_output = {
                    "error": "line_item_timeout",
                    "line_items": [],
                }
                ctx.extraction_output["line_items"] = []
                ctx.extraction_output["line_item_timed_out"] = True
            except Exception as exc:  # noqa: BLE001 - line items are best-effort
                ctx.line_item_output = {"error": str(exc), "line_items": []}
                ctx.extraction_output["line_items"] = []

        _emit("mapping")
        ctx.journal_output = run_journal_router(
            ctx.extraction_output,
            company_id=company_id,
            cache_root=settings.CACHE_ROOT,
            rules_root=settings.RULES_ROOT,
            force_refresh=force_refresh,
        )
        # Close the final ("mapping") stage timing window on the happy path.
        _record_stage_end()
    except Exception as exc:  # pragma: no cover - safety net for runtime failures
        ctx.status = StageResult.FAILED
        ctx.error = str(exc)
        # HR-07-02: remember which stage was active so the Processing UI / logs
        # can show where the document died instead of an opaque failure.
        ctx.failed_stage = _stage_state["name"]
        _record_stage_end()
    return ctx


def select_model(ctx: PipelineContext) -> str:
    """Expose selected extraction model for diagnostics."""
    model = ctx.extraction_output.get("model") if ctx.extraction_output else None
    return str(model or "claude-haiku-4-5-20250514")
