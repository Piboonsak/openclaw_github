"""TASK-503 validation API gate for journal routing and posting checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.backend.services.rule_engine import (
    _build_payload_from_rule,
    _derive_routing_context,
    _fallback_payload,
    _hash_for_payload,
    _load_rule_defaults,
    _merge_stage_c_decision,
    pick_best_rule,
)
from src.backend.services.rule_loader import CompiledRules, load_company_rules


class AccountingError(Exception):
    """Base accounting validation error for journal routing interfaces."""


class UnbalancedEntryError(AccountingError):
    """Raised when debit and credit totals are out of allowed tolerance."""


class InvalidChartOfAccountsError(AccountingError):
    """Raised when journal lines contain unresolved or unknown account codes."""


def validate_required_fields(fields: dict, required_fields: list[str]) -> dict:
    """Validate required fields and return missing list."""
    missing = [
        name for name in required_fields if not str(fields.get(name, "")).strip()
    ]
    return {"missing_fields": missing, "is_valid": len(missing) == 0}


def _rules_root_for(compiled_rules: CompiledRules) -> Path:
    if compiled_rules.rule_path is None:
        raise AccountingError(
            f"No rule_coa path found for company '{compiled_rules.company_id}'."
        )
    return compiled_rules.rule_path.parent.parent


def _confidence_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    score = int(payload.get("score", 0) or 0)
    if score >= 70:
        label = "high"
    elif score >= 40:
        label = "medium"
    else:
        label = "low"
    return {"score": score, "label": label}


def _to_express_gl(
    payload: dict[str, Any], extraction: dict[str, Any]
) -> dict[str, Any]:
    fields = extraction.get("fields", extraction)
    postings = payload.get("postings", [])
    return {
        "doc_id": str(extraction.get("sha256") or ""),
        "doc_type": str(fields.get("document_type") or ""),
        "voucher_date": str(fields.get("invoice_date") or fields.get("date") or ""),
        "reference": str(fields.get("invoice_number") or fields.get("reference") or ""),
        "book_code": str(payload.get("journal_code") or ""),
        "lines": [
            {
                "account": str(line.get("account_code") or ""),
                "description": str(
                    line.get("description") or line.get("line_type") or ""
                ),
                "debit": round(float(line.get("debit", 0.0) or 0.0), 2),
                "credit": round(float(line.get("credit", 0.0) or 0.0), 2),
            }
            for line in postings
        ],
        "total_debit": round(
            float(payload.get("totals", {}).get("debit", 0.0) or 0.0), 2
        ),
        "total_credit": round(
            float(payload.get("totals", {}).get("credit", 0.0) or 0.0), 2
        ),
        "balanced": bool(payload.get("is_balanced", False)),
        "status": str(payload.get("status") or ""),
    }


def _validate_posted_accounts(
    payload: dict[str, Any], compiled_rules: CompiledRules
) -> None:
    valid_codes = {
        str(item.get("code", "")).strip()
        for item in compiled_rules.chart_of_accounts
        if str(item.get("code", "")).strip()
    }
    for line in payload.get("postings", []):
        account_code = str(line.get("account_code", "")).strip()
        if not account_code or "xxx" in account_code.lower():
            raise InvalidChartOfAccountsError(
                f"Unresolved account code detected: '{account_code or '<empty>'}'"
            )
        if account_code not in valid_codes:
            raise InvalidChartOfAccountsError(
                f"Account code '{account_code}' does not exist in company COA."
            )


def _validate_balance(payload: dict[str, Any], tolerance: float = 0.01) -> None:
    totals = payload.get("totals", {})
    debit = round(float(totals.get("debit", 0.0) or 0.0), 2)
    credit = round(float(totals.get("credit", 0.0) or 0.0), 2)
    delta = round(abs(debit - credit), 2)
    if delta > tolerance:
        raise UnbalancedEntryError(
            f"Unbalanced journal entry: debit={debit:.2f}, credit={credit:.2f}, delta={delta:.2f}"
        )


def compile_rules(yaml_path: str | Path) -> CompiledRules:
    """Load and compile company journal rules from a specific rule_coa.yaml path."""
    resolved_path = Path(yaml_path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"rule_coa file not found: {resolved_path}")
    if resolved_path.name != "rule_coa.yaml":
        raise AccountingError(
            f"Expected rule_coa.yaml file, got '{resolved_path.name}'."
        )

    company_id = resolved_path.parent.name
    rules_root = resolved_path.parent.parent
    compiled = load_company_rules(company_id=company_id, rules_root=rules_root)
    if compiled.rule_path is None or compiled.rule_path.resolve() != resolved_path:
        raise AccountingError(
            "Loaded company rules do not match requested yaml path: "
            f"requested='{resolved_path}', loaded='{compiled.rule_path}'"
        )
    return compiled


def route_journal(extraction: dict, compiled_rules: Any) -> dict:
    """Route extraction payload to a journal result based on compiled company rules."""
    if not isinstance(compiled_rules, CompiledRules):
        raise TypeError("compiled_rules must be an instance of CompiledRules")

    normalized = dict(extraction)
    if "fields" not in normalized:
        normalized = {"fields": extraction}

    sha = str(normalized.get("sha256") or _hash_for_payload(normalized))
    fields = normalized.get("fields", {})
    rules_root = _rules_root_for(compiled_rules)
    defaults = _load_rule_defaults(rules_root)
    context = _derive_routing_context(fields, defaults)
    chosen = pick_best_rule(context, compiled_rules.journal_rules)

    if chosen.get("status") == "OK":
        payload = _build_payload_from_rule(chosen, context, sha)
    else:
        payload = _fallback_payload(fields, defaults, sha)
        payload["status"] = "UNRESOLVED_RULE"
        payload["flags"] = ["unresolved_rule"]
        payload["needs_review"] = True

    payload["company_id"] = compiled_rules.company_id
    payload["confidence"] = _confidence_from_payload(payload)
    payload["express_gl"] = _to_express_gl(payload, normalized)
    _merge_stage_c_decision(normalized, payload)
    return payload


def post_journal_entry(extraction: dict, compiled_rules: Any) -> dict:
    """Route and validate journal lines before posting to accounting output."""
    payload = route_journal(extraction, compiled_rules)
    _validate_posted_accounts(payload, compiled_rules)
    _validate_balance(payload, tolerance=0.01)
    return payload
