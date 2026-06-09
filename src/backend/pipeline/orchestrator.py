"""Epic 5 pipeline orchestrator skeleton (TASK-501/502/503)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.backend.ml.amount_reconciler import apply_amount_confidence, reconcile_amounts
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
    overall_confidence: float = 0.0
    stage_c_applied: bool = False
    escalated_to_sonnet: bool = False
    status: StageResult = StageResult.SUCCESS
    error: str | None = None


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


async def run_pipeline(
    image_path: str,
    company_id: str | None = None,
    company_tax_id: str | None = None,
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

        # --- Re-run reconciliation AFTER Stage C may have overwritten amounts ---
        # The rules pass reconciled the original extraction, but Stage C can change
        # net/vat/total. Re-anchor on the (possibly repaired) document VAT, reapply
        # per-field penalties, then auto-correct gross when the printed total is the
        # post-WHT paid amount.
        reconciliation = reconcile_amounts(fields)
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
        if reconciliation.get("total_is_paid"):
            for key, value in reconciliation.get("corrected", {}).items():
                fields[key] = value
            # Re-reconcile after auto-correction so downstream sees consistent state.
            reconciliation = reconcile_amounts(fields)
        fields["reconciliation"] = reconciliation
        ctx.extraction_output["reconciliation"] = reconciliation
        ctx.extraction_output["vat_layout"] = reconciliation.get("layout")

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
