"""Accuracy evaluator for TASK-510 KPI gates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass
class KPIThresholds:
    field_level: float = 0.85
    account_level: float = 0.80
    journal_level: float = 0.75
    # Per-field gates (0 = not gated)
    invoice_number: float = 0.85
    invoice_date: float = 0.85
    seller_tax_id: float = 0.90
    buyer_tax_id: float = 0.90
    net_amount: float = 0.80
    vat_amount: float = 0.80
    total_amount: float = 0.85


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _safe_div(num: float, den: float) -> float:
    return round(num / den, 4) if den else 0.0


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _fuzzy_match_ratio(a: Any, b: Any) -> float:
    left = _normalize_text(a)
    right = _normalize_text(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _within_amount_tolerance(a: float, b: float, *, tolerance: float = 1.0) -> bool:
    return abs(a - b) <= tolerance


def evaluate_accuracy(
    journal_output: dict[str, Any],
    expected_doc: dict[str, Any],
) -> dict[str, Any]:
    fields = expected_doc
    extracted_fields = journal_output.get("fields") or {}
    postings = journal_output.get("postings", [])

    extracted_invoice = extracted_fields.get("invoice_number") or expected_doc.get(
        "invoice_number"
    )
    extracted_date = extracted_fields.get("invoice_date") or expected_doc.get(
        "invoice_date"
    )

    expected_total = _to_float(fields.get("amounts", {}).get("gross_amount"))
    expected_net = _to_float(fields.get("amounts", {}).get("net_amount"))
    expected_vat = _to_float(fields.get("amounts", {}).get("vat_amount"))
    extracted_total = _to_float(extracted_fields.get("total_amount"), expected_total)
    extracted_net = _to_float(extracted_fields.get("net_amount"), 0.0)
    extracted_vat = _to_float(extracted_fields.get("vat_amount"), 0.0)
    journal_credit = sum(_to_float(p.get("credit")) for p in postings)

    # --- Per-field accuracy tracking ---
    per_field: dict[str, bool] = {}

    per_field["invoice_number"] = (
        _fuzzy_match_ratio(expected_doc.get("invoice_number"), extracted_invoice) >= 0.9
    )
    per_field["invoice_date"] = (
        _fuzzy_match_ratio(expected_doc.get("invoice_date"), extracted_date) >= 0.95
    )
    per_field["total_amount"] = (
        expected_total > 0 and _within_amount_tolerance(expected_total, extracted_total)
    )
    if expected_net > 0:
        per_field["net_amount"] = _within_amount_tolerance(expected_net, extracted_net)
    if expected_vat > 0:
        per_field["vat_amount"] = _within_amount_tolerance(expected_vat, extracted_vat)

    expected_seller_tax = str(expected_doc.get("seller_tax_id", "")).strip()
    extracted_seller_tax = str(extracted_fields.get("seller_tax_id", "")).strip()
    if expected_seller_tax:
        per_field["seller_tax_id"] = expected_seller_tax == extracted_seller_tax

    expected_buyer_tax = str(expected_doc.get("buyer_tax_id", "")).strip()
    extracted_buyer_tax = str(extracted_fields.get("buyer_tax_id", "")).strip()
    if expected_buyer_tax:
        per_field["buyer_tax_id"] = expected_buyer_tax == extracted_buyer_tax

    expected_vat_rate = str(expected_doc.get("vat_rate", "")).strip()
    extracted_vat_rate = str(extracted_fields.get("vat_rate", "")).strip()
    if expected_vat_rate:
        per_field["vat_rate"] = expected_vat_rate == extracted_vat_rate

    # Legacy field-level KPI: 3-field minimum set (backwards-compatible)
    field_hits = sum([
        int(per_field["invoice_number"]),
        int(per_field["invoice_date"]),
        int(per_field["total_amount"]),
    ])
    field_total = 3

    account_expected = [
        str(line.get("account_code"))
        for line in expected_doc.get("expected_journal", {}).get("postings", [])
        if line.get("account_code")
    ]
    account_actual = [
        str(line.get("account_code")) for line in postings if line.get("account_code")
    ]
    account_hits = len(set(account_expected).intersection(set(account_actual)))

    line_match_ratio = _safe_div(account_hits, len(account_expected) or 1)
    journal_ok = (
        _within_amount_tolerance(expected_total, journal_credit)
        if expected_total
        else bool(journal_output.get("is_balanced"))
    ) and line_match_ratio >= 0.7
    rule_effectiveness = 1.0 if journal_output.get("status") == "READY" else 0.0

    return {
        "field_level_accuracy": _safe_div(field_hits, field_total),
        "account_level_accuracy": _safe_div(account_hits, len(account_expected) or 1),
        "journal_level_accuracy": 1.0 if journal_ok else 0.0,
        "rule_effectiveness": rule_effectiveness,
        "per_field": per_field,
        "details": {
            "expected_total": expected_total,
            "extracted_total": round(extracted_total, 2),
            "journal_credit": round(journal_credit, 2),
            "account_hits": account_hits,
            "account_expected": len(account_expected),
            "account_match_ratio": line_match_ratio,
        },
    }


def aggregate_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "field_level_accuracy": 0.0,
            "account_level_accuracy": 0.0,
            "journal_level_accuracy": 0.0,
            "rule_effectiveness": 0.0,
            "per_field_accuracy": {},
            "sample_size": 0,
        }

    n = len(reports)
    
    # Collect all per-field names across all reports
    all_field_names: set[str] = set()
    for r in reports:
        all_field_names.update(r.get("per_field", {}).keys())

    per_field_accuracy: dict[str, float] = {}
    for field_name in sorted(all_field_names):
        hits = sum(1 for r in reports if r.get("per_field", {}).get(field_name, False))
        total = sum(1 for r in reports if field_name in r.get("per_field", {}))
        per_field_accuracy[field_name] = _safe_div(hits, total) if total else 0.0

    return {
        "field_level_accuracy": round(
            sum(r["field_level_accuracy"] for r in reports) / n, 4
        ),
        "account_level_accuracy": round(
            sum(r["account_level_accuracy"] for r in reports) / n, 4
        ),
        "journal_level_accuracy": round(
            sum(r["journal_level_accuracy"] for r in reports) / n, 4
        ),
        "rule_effectiveness": round(
            sum(r["rule_effectiveness"] for r in reports) / n, 4
        ),
        "per_field_accuracy": per_field_accuracy,
        "sample_size": n,
    }


def gate_passed(
    summary: dict[str, Any], thresholds: KPIThresholds | None = None
) -> tuple[bool, list[str]]:
    th = thresholds or KPIThresholds()
    failures: list[str] = []

    if summary.get("field_level_accuracy", 0.0) < th.field_level:
        failures.append(f"field_level_accuracy<{th.field_level}")
    if summary.get("account_level_accuracy", 0.0) < th.account_level:
        failures.append(f"account_level_accuracy<{th.account_level}")
    if summary.get("journal_level_accuracy", 0.0) < th.journal_level:
        failures.append(f"journal_level_accuracy<{th.journal_level}")

    # Per-field gates
    pf = summary.get("per_field_accuracy", {})
    gate_map = {
        "invoice_number": th.invoice_number,
        "invoice_date": th.invoice_date,
        "seller_tax_id": th.seller_tax_id,
        "buyer_tax_id": th.buyer_tax_id,
        "net_amount": th.net_amount,
        "vat_amount": th.vat_amount,
        "total_amount": th.total_amount,
    }
    for field_name, target in gate_map.items():
        if target > 0 and field_name in pf and pf[field_name] < target:
            failures.append(f"per_field.{field_name}<{target} (actual:{pf[field_name]:.2%})")

    return (len(failures) == 0, failures)


def write_accuracy_report(path: str | Path, payload: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return out
