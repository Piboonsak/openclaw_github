"""Stage C: Claude-based field repair for low-confidence or conflicted extractions.

Invoked by the pipeline orchestrator when:
  - cross_field_conflict is True
  - ≥2 fields have confidence < 0.6
  - VAT context is present but vat_amount == "" (extraction failed)

The function calls Claude with a structured prompt that includes the raw OCR text
and current best-guess fields, then returns only the fields that Claude improved
by > 0.15 confidence.  Budget guard limits to 1 call/doc and enforces a daily
spend cap read from STAGE_C_DAILY_USD_CAP env var (default: $2.00).

Security: API key is read from ANTHROPIC_API_KEY env var only — never hardcoded.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_DAILY_BUDGET_FILE = Path(__file__).parent / "cache" / "stage_c_budget.json"
_DEFAULT_DAILY_USD_CAP = 2.0

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
- invoice_date: ISO date YYYY-MM-DD or DD/MM/YYYY as found in the document
- seller_name: legal seller company name string
- buyer_name: legal buyer company name string
- seller_tax_id: 13-digit Thai tax ID
- buyer_tax_id: 13-digit Thai tax ID
- net_amount: numeric string without commas or currency symbol
- vat_amount: numeric string (7% VAT amount)
- vat_rate: numeric string (percentage only, e.g. "7")
- total_amount: numeric string (net + vat)
- wht_amount: withholding tax amount string (or "" if none)
"""


def _load_budget() -> dict[str, Any]:
    if _DAILY_BUDGET_FILE.exists():
        try:
            return json.loads(_DAILY_BUDGET_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": "", "spent_usd": 0.0}


def _save_budget(data: dict[str, Any]) -> None:
    _DAILY_BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DAILY_BUDGET_FILE.write_text(json.dumps(data), encoding="utf-8")


def _today_str() -> str:
    return time.strftime("%Y-%m-%d")


def _budget_allows(estimated_cost_usd: float) -> tuple[bool, str]:
    cap = float(os.environ.get("STAGE_C_DAILY_USD_CAP", str(_DEFAULT_DAILY_USD_CAP)))
    budget = _load_budget()
    today = _today_str()

    if budget.get("date") != today:
        budget = {"date": today, "spent_usd": 0.0}

    if budget["spent_usd"] + estimated_cost_usd > cap:
        return (
            False,
            f"Stage C daily budget cap ${cap:.2f} reached (spent ${budget['spent_usd']:.2f})",
        )
    return True, ""


def _record_spend(cost_usd: float) -> None:
    today = _today_str()
    budget = _load_budget()
    if budget.get("date") != today:
        budget = {"date": today, "spent_usd": 0.0}
    budget["spent_usd"] = round(budget["spent_usd"] + cost_usd, 6)
    _save_budget(budget)


def _estimate_cost_usd(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Approximate cost in USD based on known Claude pricing tiers."""
    if "haiku" in model:
        input_price = 0.25 / 1_000_000  # $0.25/MTok
        output_price = 1.25 / 1_000_000  # $1.25/MTok
    else:
        # sonnet-4.x tier
        input_price = 3.0 / 1_000_000  # $3/MTok
        output_price = 15.0 / 1_000_000  # $15/MTok
    return round(prompt_tokens * input_price + completion_tokens * output_price, 6)


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
    low_conf_keys = [
        k
        for k, v in confidence.items()
        if k not in ("source_text",) and isinstance(v, float) and v < 0.6
    ]
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


def _normalize_match_text(value: str) -> str:
    normalized = str(value or "").lower()
    normalized = "".join(normalized.split())
    return normalized


def _value_in_ocr(value: str, raw_text: str) -> bool:
    left = _normalize_match_text(value)
    right = _normalize_match_text(raw_text)
    if not left or not right:
        return False
    return left in right


def call_claude_repair(
    raw_text: str,
    current_fields: dict[str, Any],
    current_confidence: dict[str, Any],
    model: str | None = None,
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
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "fields": {},
            "confidence": {},
            "skipped": True,
            "skip_reason": "ANTHROPIC_API_KEY not set",
        }

    # Estimate cost before calling (rough: ~800 prompt tokens, ~150 completion tokens).
    selected_model = model or "claude-haiku-4-5-20250514"
    estimated = _estimate_cost_usd(800, 150, selected_model)
    allowed, reason = _budget_allows(estimated)
    if not allowed:
        return {"fields": {}, "confidence": {}, "skipped": True, "skip_reason": reason}

    try:
        anthropic_module = __import__("anthropic")
    except ImportError:
        return {
            "fields": {},
            "confidence": {},
            "skipped": True,
            "skip_reason": "anthropic package not installed",
        }

    # Build user prompt: redact source_text from current_fields to avoid prompt bloat
    display_fields = {
        k: v
        for k, v in current_fields.items()
        if k not in ("source_text", "cross_field_error")
    }

    user_prompt = (
        "=== RAW OCR TEXT ===\n"
        + raw_text[:4000]  # cap to prevent token overflow
        + "\n\n=== CURRENT EXTRACTED FIELDS ===\n"
        + json.dumps(display_fields, ensure_ascii=False, indent=2)
        + "\n\nPlease return corrected/completed fields as JSON."
    )

    try:
        client = anthropic_module.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=selected_model,
            max_tokens=512,
            system=STAGE_C_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text.strip()
        usage = response.usage
        actual_cost = _estimate_cost_usd(
            usage.input_tokens, usage.output_tokens, selected_model
        )
        _record_spend(actual_cost)
    except Exception as exc:
        return {
            "fields": {},
            "confidence": {},
            "skipped": True,
            "skip_reason": f"Claude API error: {exc}",
        }

    # Parse response
    try:
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        repaired = json.loads(content)
    except (json.JSONDecodeError, IndexError):
        return {
            "fields": {},
            "confidence": {},
            "skipped": True,
            "skip_reason": f"JSON parse failed: {content[:200]}",
        }

    # Merge logic: allow Claude to replace values that are low-confidence or suspect.
    improved_fields: dict[str, Any] = {}
    improved_confidence: dict[str, Any] = {}

    # Claude result gets 0.85 confidence for non-empty accepted fields.
    claude_base_conf = 0.85

    warnings = current_fields.get("field_validation_warnings") or []
    warning_fields: set[str] = set()
    if isinstance(warnings, list):
        for item in warnings:
            text = str(item)
            if ":" in text:
                warning_fields.add(text.split(":", 1)[0])

    for field_name, new_value in repaired.items():
        if field_name not in current_fields:
            continue  # Don't inject unknown fields
        if not new_value:
            continue  # Skip empty results from Claude

        current_conf = current_confidence.get(field_name, 0.0)
        current_value = str(current_fields.get(field_name) or "")
        current_in_ocr = _value_in_ocr(current_value, raw_text)
        has_warning = field_name in warning_fields

        accept = False
        if has_warning:
            accept = True
        elif isinstance(current_conf, float) and current_conf < 0.85:
            accept = True
        elif not current_in_ocr:
            accept = True

        if accept:
            improved_fields[field_name] = str(new_value)
            improved_confidence[field_name] = claude_base_conf

    return {
        "fields": improved_fields,
        "confidence": improved_confidence,
        "skipped": False,
        "skip_reason": "",
    }
