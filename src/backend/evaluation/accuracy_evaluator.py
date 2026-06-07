"""Accuracy evaluator for TASK-510 KPI gates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any


@dataclass
class KPIThresholds:
    field_level: float = 0.85
    account_level: float = 0.80
    journal_level: float = 0.75


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
    extracted_total = _to_float(extracted_fields.get("total_amount"), expected_total)
    journal_credit = sum(_to_float(p.get("credit")) for p in postings)

    field_hits = 0
    field_total = 3
    # invoice_number/date/total are the minimum KPI set for PoC gate.
    if _fuzzy_match_ratio(expected_doc.get("invoice_number"), extracted_invoice) >= 0.9:
        field_hits += 1
    if _fuzzy_match_ratio(expected_doc.get("invoice_date"), extracted_date) >= 0.95:
        field_hits += 1
    if expected_total > 0 and _within_amount_tolerance(expected_total, extracted_total):
        field_hits += 1

    account_expected = [
        str(line.get("account_code"))
        for line in expected_doc.get("expected_journal", {}).get("postings", [])
        if line.get("account_code")
    ]
    account_actual = [str(line.get("account_code")) for line in postings if line.get("account_code")]
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
            "sample_size": 0,
        }

    n = len(reports)
    return {
        "field_level_accuracy": round(sum(r["field_level_accuracy"] for r in reports) / n, 4),
        "account_level_accuracy": round(sum(r["account_level_accuracy"] for r in reports) / n, 4),
        "journal_level_accuracy": round(sum(r["journal_level_accuracy"] for r in reports) / n, 4),
        "rule_effectiveness": round(sum(r["rule_effectiveness"] for r in reports) / n, 4),
        "sample_size": n,
    }


def gate_passed(summary: dict[str, Any], thresholds: KPIThresholds | None = None) -> tuple[bool, list[str]]:
    th = thresholds or KPIThresholds()
    failures: list[str] = []

    if summary.get("field_level_accuracy", 0.0) < th.field_level:
        failures.append(f"field_level_accuracy<{th.field_level}")
    if summary.get("account_level_accuracy", 0.0) < th.account_level:
        failures.append(f"account_level_accuracy<{th.account_level}")
    if summary.get("journal_level_accuracy", 0.0) < th.journal_level:
        failures.append(f"journal_level_accuracy<{th.journal_level}")

    return (len(failures) == 0, failures)


def write_accuracy_report(path: str | Path, payload: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
