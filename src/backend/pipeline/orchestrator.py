"""Epic 5 pipeline orchestrator skeleton (TASK-501/502/503)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.backend.ml.field_extractor import run_extraction
from src.backend.ml.llm_claude import call_claude_repair, should_trigger_stage_c
from src.backend.ml.model_router import pick_model, should_escalate_to_sonnet
from src.backend.ml.ocr import run_ocr
from src.backend.services.rule_engine import run_journal_router

# Threshold below which LLM escalation is triggered (aligned with design D2)
CONFIDENCE_ESCALATION_THRESHOLD = 0.70


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
    overall_confidence: float = 0.0
    stage_c_applied: bool = False
    escalated_to_sonnet: bool = False
    status: StageResult = StageResult.SUCCESS
    error: str | None = None


def _compute_overall_confidence(
    fields: dict[str, Any], confidence: dict[str, Any], ocr_output: dict[str, Any]
) -> float:
    """Compute overall confidence matching the frontend formula logic.

    Uses: OCR confidence × 0.25 + field avg × 0.45 + completeness × 0.30
    Only averages confidence for required fields (not optional ones).
    Required fields: invoice_number, invoice_date, seller_name,
    seller_tax_id, buyer_tax_id, total_amount (6 fields).
    """
    ocr_conf = min(1.0, max(0.0, float(ocr_output.get("ocr_confidence", 0.75))))

    required_keys = [
        "invoice_number",
        "invoice_date",
        "seller_name",
        "seller_tax_id",
        "buyer_tax_id",
        "total_amount",
    ]

    # Average confidence only for required fields
    conf_values = [
        float(confidence[k])
        for k in required_keys
        if k in confidence and isinstance(confidence[k], (int, float))
    ]
    field_conf = sum(conf_values) / len(conf_values) if conf_values else 0.6

    present = sum(1 for k in required_keys if str(fields.get(k) or "").strip())
    completeness = present / len(required_keys)

    overall = ocr_conf * 0.25 + field_conf * 0.45 + completeness * 0.30

    has_low_critical = any(
        isinstance(confidence.get(key), (int, float))
        and float(confidence.get(key, 0.0)) < CONFIDENCE_ESCALATION_THRESHOLD
        for key in required_keys
    )
    if has_low_critical:
        overall = min(overall, CONFIDENCE_ESCALATION_THRESHOLD - 0.01)

    return overall


async def run_pipeline(
    image_path: str, company_id: str | None = None
) -> PipelineContext:
    """Run OCR -> extraction -> Stage C repair -> Sonnet escalation -> journal routing."""
    ctx = PipelineContext(source_file=image_path, company_id=company_id)
    try:
        ctx.ocr_output = run_ocr(image_path)
        ctx.extraction_output = run_extraction(ctx.ocr_output)
        ctx.extraction_output["company_id"] = company_id

        fields = ctx.extraction_output.get("fields", {})
        confidence = ctx.extraction_output.get("confidence_per_field", {})
        meta = ctx.extraction_output.get("meta", {})

        # Use OCR confidence from extraction meta (where the extractor stores it)
        ocr_info = {"ocr_confidence": meta.get("ocr_confidence", 0.75)}

        # --- Stage C: Claude-based repair ---
        # Trigger by existing rules (cross-field conflict, missing VAT, low per-field conf)
        trigger, reason = should_trigger_stage_c(fields, confidence)

        # Also trigger if overall confidence is below escalation threshold
        overall = _compute_overall_confidence(fields, confidence, ocr_info)
        if not trigger and overall < CONFIDENCE_ESCALATION_THRESHOLD:
            trigger = True
            reason = (
                f"overall_confidence={overall:.2f} < {CONFIDENCE_ESCALATION_THRESHOLD}"
            )

        if trigger:
            raw_text = fields.get("source_text", "")
            model = ctx.extraction_output.get("model")
            repair = call_claude_repair(raw_text, fields, confidence, model)
            ctx.stage_c_output = repair
            if not repair.get("skipped") and repair.get("fields"):
                fields.update(repair["fields"])
                confidence.update(repair["confidence"])
                ctx.extraction_output["stage_c_applied"] = True
                ctx.extraction_output["stage_c_reason"] = reason
                ctx.stage_c_applied = True

        # Recompute after Stage C repair
        overall = _compute_overall_confidence(fields, confidence, ocr_info)

        # --- Sonnet escalation: if still below threshold after Stage C ---
        if overall < CONFIDENCE_ESCALATION_THRESHOLD and not ctx.escalated_to_sonnet:
            ocr_conf = float(meta.get("ocr_confidence", 0.75))
            low_conf_fields = sum(
                1
                for k, v in confidence.items()
                if k not in ("source_text",)
                and isinstance(v, (int, float))
                and v < CONFIDENCE_ESCALATION_THRESHOLD
            )
            escalate = should_escalate_to_sonnet(
                page_count=int(meta.get("page_count", 1)),
                ocr_confidence=ocr_conf,
                low_confidence_fields=low_conf_fields,
                rule_conflict=bool(fields.get("cross_field_conflict")),
            )
            if escalate:
                # Re-run extraction with Sonnet model
                sonnet_model = pick_model(escalated_to_sonnet=True)
                raw_text = fields.get("source_text", "")
                sonnet_repair = call_claude_repair(
                    raw_text, fields, confidence, sonnet_model
                )
                if not sonnet_repair.get("skipped") and sonnet_repair.get("fields"):
                    fields.update(sonnet_repair["fields"])
                    confidence.update(sonnet_repair["confidence"])
                ctx.escalated_to_sonnet = True
                ctx.extraction_output["escalated_to_sonnet"] = True
                ctx.extraction_output["model"] = sonnet_model

        # Final overall confidence
        overall = _compute_overall_confidence(fields, confidence, ocr_info)
        ctx.overall_confidence = overall
        ctx.extraction_output["overall_confidence"] = overall

        ctx.journal_output = run_journal_router(
            ctx.extraction_output,
            company_id=company_id,
        )
    except Exception as exc:  # pragma: no cover - safety net for runtime failures
        ctx.status = StageResult.FAILED
        ctx.error = str(exc)
    return ctx


def select_model(ctx: PipelineContext) -> str:
    """Expose selected extraction model for diagnostics."""
    model = ctx.extraction_output.get("model") if ctx.extraction_output else None
    return str(model or "claude-haiku-4-5-20250514")
