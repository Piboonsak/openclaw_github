"""Epic 5 pipeline orchestrator skeleton (TASK-501/502/503)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.backend.ml.field_extractor import run_extraction
from src.backend.ml.llm_claude import STAGE_C_SYSTEM_PROMPT
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
    """Run OCR -> extraction -> Stage C cascade repair -> journal routing."""
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
            cascade = cascade_repair(
                raw_text=raw_text,
                current_fields=fields,
                current_confidence=confidence,
                system_prompt=STAGE_C_SYSTEM_PROMPT,
                image_path=image_path,
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

        # Recompute after Stage C repair
        overall = _compute_overall_confidence(fields, confidence, ocr_info)

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
