"""Stage C trigger + legacy Claude wrapper for low-confidence extractions.

Invoked by the pipeline orchestrator when:
  - cross_field_conflict is True
  - ≥2 fields have confidence < 0.6
  - VAT context is present but vat_amount == "" (extraction failed)

The call function now delegates to src.backend.ml.llm_router.call_llm_repair,
which handles provider selection (OpenRouter primary, Anthropic fallback),
budget guard, and normalized response merging.
"""

from __future__ import annotations

import os
from typing import Any

from src.backend.ml.llm_router import call_llm_repair

STAGE_C_SYSTEM_PROMPT = """\
You are an AI assistant specialized in extracting fields from Thai accounting documents
(invoices, receipts, billing notes). Given OCR raw text and partially extracted fields,
correct any missing or incorrect values and return a JSON object with ONLY the fields you
are confident about. Use empty string "" for fields you cannot determine.

When extracting VAT and tax values, pay special attention to Thai keywords and OCR variants:
- ภาษีมูลค่าเพิ่ม
- จำนวนภาษีมูลค่าเพิ่ม
- จำนวนภาษี
- ยอดภาษี
- แยกภาษี
- VAT

When extracting names, prioritize legal company names for seller_name and buyer_name,
especially when tax IDs are present.

Return ONLY valid JSON, no markdown, no explanation.
Fields to extract:
- invoice_number: string
- invoice_date: ISO date YYYY-MM-DD only
- seller_name: legal seller company name string
- buyer_name: legal buyer company name string
- seller_tax_id: 13-digit Thai tax ID
- buyer_tax_id: 13-digit Thai tax ID
- net_amount: numeric string without commas or currency symbol
- vat_amount: numeric string (7% VAT amount)
- vat_rate: numeric string (percentage only, e.g. "7")
- total_amount: numeric string (net + vat)
- wht_amount: withholding tax amount string (or "" if none)

IMPORTANT - Numeric fields (net_amount, vat_amount, total_amount, wht_amount, amount_paid):
- Return ONLY values that are literally printed on the document.
- NEVER compute, derive, or recalculate a value from other fields.
- If a value is not printed, return "" (empty string).
- If printed VAT does not equal net*7%, the document may be inclusive (VAT = total*7/107).
- Keep the printed VAT and do not recompute.
"""


def should_trigger_stage_c(
    fields: dict[str, Any], confidence: dict[str, Any]
) -> tuple[bool, str]:
    """Determine whether Stage C Claude repair should be invoked.

    Returns (should_trigger, reason).
    """
    if fields.get("cross_field_conflict"):
        return True, f"cross_field_conflict: {fields.get('cross_field_error', '')}"

    # VAT context present but amount not extracted
    has_vat_context = any(
        [
            "ภาษีมูลค่าเพิ่ม" in (fields.get("source_text") or ""),
            "VAT" in (fields.get("source_text") or ""),
        ]
    )
    if has_vat_context and not fields.get("vat_amount"):
        return True, "vat_context_present_but_no_vat_amount"

    # Count fields with low confidence
    low_threshold = 0.70
    critical_fields = {
        "invoice_number",
        "invoice_date",
        "seller_name",
        "buyer_name",
        "seller_tax_id",
        "buyer_tax_id",
        "net_amount",
        "vat_amount",
        "total_amount",
    }
    low_conf_keys = [
        k
        for k, v in confidence.items()
        if k not in ("source_text",) and isinstance(v, float) and v < low_threshold
    ]
    if any(k in critical_fields for k in low_conf_keys):
        return True, f"critical_field_below_{low_threshold:.2f}: {low_conf_keys}"

    if len(low_conf_keys) >= 2:
        return True, f"low_confidence_fields: {low_conf_keys}"

    aggressive = os.environ.get("STAGE_C_AGGRESSIVE", "false").strip().lower() == "true"
    if aggressive:
        seller_name = str(fields.get("seller_name") or "").strip()
        buyer_name = str(fields.get("buyer_name") or "").strip()
        buyer_tax_id = str(fields.get("buyer_tax_id") or "").strip()

        if seller_name and len(seller_name) < 10:
            return True, "aggressive_short_seller_name"
        if buyer_name and buyer_tax_id and len(buyer_name) < 10:
            return True, "aggressive_short_buyer_name_with_tax_id"
        if bool(fields.get("vat_math_mismatch")):
            return True, "aggressive_vat_math_mismatch"

        warnings = fields.get("field_validation_warnings") or []
        if isinstance(warnings, list) and warnings:
            return True, "aggressive_field_validation_warnings"

    return False, ""


def call_claude_repair(
    raw_text: str,
    current_fields: dict[str, Any],
    current_confidence: dict[str, Any],
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Call Claude to repair/fill low-confidence extraction fields.

    Returns a dict:
      {
        "fields": {field_name: new_value, ...},      # merged improvements only
        "confidence": {field_name: new_conf, ...},   # merged improvements only
        "skipped": bool,                             # True if budget or API unavailable
        "skip_reason": str,
      }
    """
    # Keep legacy API stable while delegating provider logic to llm_router.
    return call_llm_repair(
        raw_text=raw_text,
        current_fields=current_fields,
        current_confidence=current_confidence,
        system_prompt=STAGE_C_SYSTEM_PROMPT,
        model=model,
        provider=provider,
    )
