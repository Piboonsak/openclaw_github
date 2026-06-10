"""Validation and journal routing helpers for TASK-503."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from src.backend.ml.amount_reconciler import classify_vat_layout
from src.backend.services.rule_loader import JournalRule, load_company_rules

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_ROOT = REPO_ROOT / "src" / "backend" / "services" / "cache"
DEFAULT_RULES_ROOT = REPO_ROOT / "rules"
JOURNAL_SCHEMA_VERSION = "v2"
SCORE_WEIGHTS = {
    "document_type": 20,
    "payment_method": 20,
    "source_document": 25,
    "has_vat": 10,
    "vat_type": 10,
    "has_wht": 10,
}
VARIABLE_ACCOUNT_KEYWORDS = {
    "ค่าไฟ": ("5040", "ค่าไฟฟ้า"),
    "ไฟฟ้า": ("5040", "ค่าไฟฟ้า"),
    "electric": ("5040", "Electricity Expense"),
    "ค่าเช่า": ("5045", "ค่าเช่า"),
    "rent": ("5045", "Rent Expense"),
    "fuel": ("5020", "Fuel Expense"),
    "น้ำมัน": ("5020", "Fuel Expense"),
    "office": ("5080", "Office Supplies Expense"),
    "เครื่องเขียน": ("5080", "Office Supplies Expense"),
    "ads": ("5100", "Advertising Expense"),
    "โฆษณา": ("5100", "Advertising Expense"),
}


def validate_required_fields(fields: dict, required_fields: list[str]) -> dict:
    """Validate required fields and return missing list."""
    missing = [
        name for name in required_fields if not str(fields.get(name, "")).strip()
    ]
    return {"missing_fields": missing, "is_valid": len(missing) == 0}


def _ensure_default_rules(rules_root: Path) -> None:
    global_dir = rules_root / "global"
    global_dir.mkdir(parents=True, exist_ok=True)

    base_patterns = global_dir / "base_patterns.yaml"
    vat_rules = global_dir / "vat_rules.yaml"
    wht_rates = global_dir / "wht_rates.yaml"

    if not base_patterns.exists():
        base_patterns.write_text(
            yaml.safe_dump(
                {
                    "purchase_invoice": {
                        "debit_account": "5040",
                        "credit_account": "2195",
                        "vat_input_account": "1154",
                        "journal_code": "PV",
                    }
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    if not vat_rules.exists():
        vat_rules.write_text(
            yaml.safe_dump(
                {"default_vat_rate": 0.07}, sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )

    if not wht_rates.exists():
        wht_rates.write_text(
            yaml.safe_dump(
                {"default_wht_rate": 0.03}, sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )


def _load_rule_defaults(rules_root: Path) -> dict[str, Any]:
    _ensure_default_rules(rules_root)
    global_dir = rules_root / "global"
    base_patterns = yaml.safe_load(
        (global_dir / "base_patterns.yaml").read_text(encoding="utf-8")
    )
    vat_rules = yaml.safe_load(
        (global_dir / "vat_rules.yaml").read_text(encoding="utf-8")
    )
    wht_rates = yaml.safe_load(
        (global_dir / "wht_rates.yaml").read_text(encoding="utf-8")
    )
    return {
        "pattern": base_patterns.get("purchase_invoice", {}),
        "vat_rate": float(vat_rules.get("default_vat_rate", 0.07)),
        "wht_rate": float(wht_rates.get("default_wht_rate", 0.03)),
    }


def _hash_for_payload(payload: dict[str, Any]) -> str:
    basis = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _coalesce_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _looks_like_corporate(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("บริษัท", "จำกัด", "company", "co.", "ltd"))


def _detect_document_type(source_text: str) -> str:
    lowered = source_text.lower()
    candidates = (
        ("รายงานรับ", "Receipts Report"),
        ("รายงานจ่าย", "Payments Report"),
        ("receipt report", "Receipts Report"),
        ("payment report", "Payments Report"),
        ("payment voucher", "Payment Voucher"),
        ("purchase order", "Purchase Order"),
        ("p/o", "Purchase Order"),
        ("tax invoice", "Tax Invoice"),
        ("invoice", "Invoice"),
        ("receipt", "Receipt"),
        ("bill", "Bill"),
        ("ใบกำกับภาษี", "Tax Invoice"),
        ("ใบแจ้งหนี้", "Invoice"),
        ("ใบเสร็จ", "Receipt"),
        ("บิล", "Bill"),
    )
    for needle, label in candidates:
        if needle in lowered:
            return label
    return "Invoice"


def _derive_routing_context(
    fields: dict[str, Any], rules: dict[str, Any]
) -> dict[str, Any]:
    source_text = _coalesce_text(fields.get("source_text"))
    lowered = source_text.lower()
    gross_amount = _to_float(fields.get("gross_amount") or fields.get("total_amount"))
    wht_amount = _to_float(fields.get("wht_amount"))
    no_vat_hint = any(
        token in lowered for token in ("without vat", "no vat", "ไม่มี vat", "ไม่มีภาษี")
    )
    has_vat_hint = (not no_vat_hint) and any(
        token in lowered for token in ("vat", "ภาษีซื้อ", "ภาษีขาย", "ใบกำกับภาษี")
    )
    vat_rate = rules.get("vat_rate", 0.07)
    has_vat = has_vat_hint and gross_amount > 0
    # Anchor on the VAT value seen on the document and classify the layout
    # (exclusive "บวก VAT" vs inclusive "ถอด VAT") instead of always assuming
    # inclusive. This prevents over-writing a trusted extracted VAT/net.
    doc_vat = _to_float(fields.get("vat_amount"))
    doc_net = _to_float(fields.get("net_amount"))
    rate_pct = vat_rate * 100.0
    if doc_vat or doc_net or gross_amount:
        _layout, _derived = classify_vat_layout(
            net=doc_net or None,
            vat=doc_vat or None,
            total=gross_amount or None,
            rate=rate_pct,
        )
        if has_vat or doc_vat:
            vat_amount = doc_vat or _derived.get("vat") or 0.0
        else:
            vat_amount = doc_vat or 0.0
        net_amount = (
            doc_net
            or _derived.get("net")
            or round(max(gross_amount - vat_amount, 0.0), 2)
        )
    else:
        vat_amount = doc_vat or 0.0
        net_amount = doc_net or round(max(gross_amount - vat_amount, 0.0), 2)

    amount_paid = _to_float(fields.get("amount_paid"))
    payment_amount = amount_paid or round(max(gross_amount - wht_amount, 0.0), 2)
    payable_amount = _to_float(fields.get("payable_amount")) or round(
        max(gross_amount - wht_amount, 0.0), 2
    )
    receivable_amount = _to_float(fields.get("receivable_amount")) or gross_amount
    net_received = _to_float(fields.get("net_received")) or payment_amount

    seller_name = _coalesce_text(fields.get("seller_name"), fields.get("vendor_name"))
    payment_method = (
        "cash"
        if any(token in lowered for token in ("cash", "เงินสด", "ชำระแล้ว", "paid"))
        else "credit"
    )
    payment_source = "director_loan" if "กรรมการ" in lowered else "cash"
    source_document = (
        "P/O"
        if any(token in lowered for token in ("purchase order", "p/o", "po #"))
        else ""
    )

    if any(token in lowered for token in ("รอเรียกเก็บ", "deferred")):
        vat_type = "deferred"
    elif any(token in lowered for token in ("รับรู้ภาษีขาย", "recognize")):
        vat_type = "recognize"
    else:
        vat_type = "normal" if has_vat else ""

    return {
        **fields,
        "document_type": _coalesce_text(
            fields.get("document_type"), _detect_document_type(source_text)
        ),
        "payment_method": _coalesce_text(fields.get("payment_method"), payment_method),
        "payment_source": _coalesce_text(fields.get("payment_source"), payment_source),
        "source_document": _coalesce_text(
            fields.get("source_document"), source_document
        ),
        "has_vat": bool(fields.get("has_vat", has_vat)),
        "vat_type": _coalesce_text(fields.get("vat_type"), vat_type),
        "has_wht": bool(wht_amount > 0),
        "gross_amount": gross_amount,
        "total_amount": gross_amount,
        "net_amount": net_amount,
        "vat_amount": vat_amount,
        "wht_amount": wht_amount,
        "payment_amount": payment_amount,
        "payable_amount": payable_amount,
        "receivable_amount": receivable_amount,
        "net_received": net_received,
        "seller_type": _coalesce_text(
            fields.get("seller_type"),
            "corporate" if _looks_like_corporate(seller_name) else "individual",
        ),
    }


def _evaluate_condition_expression(expression: str, context: dict[str, Any]) -> bool:
    if not expression.strip():
        return True
    safe_globals = {"__builtins__": {}}
    safe_locals = {
        key: value
        for key, value in context.items()
        if isinstance(value, (str, int, float, bool)) or value is None
    }
    try:
        return bool(eval(expression, safe_globals, safe_locals))
    except Exception:
        return False


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool):
        return bool(actual) is expected
    return str(actual).strip().lower() == str(expected).strip().lower()


def count_defined_conditions(rule: JournalRule) -> int:
    return len(
        [key for key, value in rule.conditions.items() if value not in (None, "")]
    )


def score_rule(
    rule: JournalRule, extraction: dict[str, Any]
) -> tuple[int, list[str], bool]:
    score = 0
    matched: list[str] = []
    document_type = _coalesce_text(extraction.get("document_type"))
    if rule.document_types:
        if document_type and any(
            doc.lower() == document_type.lower() for doc in rule.document_types
        ):
            score += SCORE_WEIGHTS["document_type"]
            matched.append("document_type")
        elif document_type:
            return (0, [], True)

    for key, expected in rule.conditions.items():
        actual = extraction.get(key)
        if actual in (None, ""):
            continue
        if not _values_match(expected, actual):
            return (0, [], True)
        score += SCORE_WEIGHTS.get(key, 10)
        matched.append(key)

    return (score, matched, False)


def pick_best_rule(
    extraction: dict[str, Any], compiled_rules: tuple[JournalRule, ...]
) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    for rule in compiled_rules:
        score, matched, rejected = score_rule(rule, extraction)
        if rejected:
            continue
        scored.append(
            {
                "rule": rule,
                "score": score,
                "specificity": count_defined_conditions(rule),
                "matched": matched,
            }
        )

    if not scored:
        return {"status": "UNRESOLVED_RULE", "needs_review": True}

    scored.sort(key=lambda item: (item["score"], item["specificity"]), reverse=True)
    winner = scored[0]
    ambiguous = (
        len(scored) > 1
        and scored[0]["score"] == scored[1]["score"]
        and scored[0]["specificity"] == scored[1]["specificity"]
    )
    return {
        "status": "OK",
        "rule": winner["rule"],
        "rule_id": winner["rule"].rule_id,
        "score": winner["score"],
        "specificity": winner["specificity"],
        "matched": winner["matched"],
        "needs_review": ambiguous,
    }


def _select_account_for_entry(
    entry: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any] | None:
    for alternative in entry.get("alternatives", []) or []:
        condition = str(alternative.get("condition", "")).strip()
        if condition and _evaluate_condition_expression(condition, context):
            return {
                "account_code": str(
                    alternative.get("account_code", entry.get("account_code", ""))
                ).strip(),
                "account_name": str(
                    alternative.get("account_name", entry.get("account_name", ""))
                ).strip(),
            }

    condition = str(entry.get("condition", "")).strip()
    if condition and not _evaluate_condition_expression(condition, context):
        return None

    return {
        "account_code": str(entry.get("account_code", "")).strip(),
        "account_name": str(entry.get("account_name", "")).strip(),
    }


def resolve_variable_account(
    selected: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """Resolve variable placeholders using seller/source text keyword mapping."""
    account_code = str(selected.get("account_code", "")).strip()
    account_name = str(selected.get("account_name", "")).strip()

    if account_code and "xxx" not in account_code.lower():
        return selected

    source_text = _coalesce_text(
        context.get("source_text"),
        context.get("seller_name"),
        context.get("vendor_name"),
    ).lower()

    for keyword, mapped in VARIABLE_ACCOUNT_KEYWORDS.items():
        if keyword in source_text:
            return {
                "account_code": mapped[0],
                "account_name": mapped[1],
            }

    return selected


def _resolve_amount(field_name: str, context: dict[str, Any]) -> float:
    return round(_to_float(context.get(field_name)), 2)


def _fallback_payload(
    fields: dict[str, Any], rules: dict[str, Any], sha: str
) -> dict[str, Any]:
    # Keep fallback aligned with reconciliation: trust printed VAT/Net first.
    # This avoids recomputing VAT as total*rate (wrong for inclusive totals and
    # harmful when a correct VAT is already present on the document).
    gross = _to_float(fields.get("total_amount") or fields.get("gross_amount"))
    doc_vat = _to_float(fields.get("vat_amount"), 0.0)
    doc_net = _to_float(fields.get("net_amount"), 0.0)
    vat_rate = float(rules.get("vat_rate", 0.07))
    layout, derived = classify_vat_layout(
        net=doc_net or None,
        vat=doc_vat or None,
        total=gross or None,
        rate=vat_rate * 100.0,
    )

    vat_amount = round(doc_vat if doc_vat > 0 else (derived.get("vat") or 0.0), 2)
    base_amount = round(
        doc_net
        if doc_net > 0
        else (derived.get("net") or max((gross or 0.0) - vat_amount, 0.0)),
        2,
    )
    amount = round(derived.get("gross") or gross or (base_amount + vat_amount), 2)

    postings = [
        {
            "account_code": rules["pattern"].get("debit_account", "5040"),
            "debit": round(base_amount, 2),
            "credit": 0.0,
            "line_type": "expense",
        },
        {
            "account_code": rules["pattern"].get("vat_input_account", "1154"),
            "debit": vat_amount,
            "credit": 0.0,
            "line_type": "vat",
        },
        {
            "account_code": rules["pattern"].get("credit_account", "2195"),
            "debit": 0.0,
            "credit": round(amount, 2),
            "line_type": "ap",
        },
    ]
    total_debit = round(sum(item["debit"] for item in postings), 2)
    total_credit = round(sum(item["credit"] for item in postings), 2)
    balanced = abs(total_debit - total_credit) < 0.01
    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "sha256": sha,
        "rule_id": "DEFAULT-PURCHASE",
        "journal_code": rules["pattern"].get("journal_code", "PV"),
        "postings": postings,
        "totals": {"debit": total_debit, "credit": total_credit},
        "is_balanced": balanced,
        "status": "READY" if balanced else "UNRESOLVED_RULE",
        "cache_hit": False,
        "flags": [f"vat_layout:{layout}"] if layout else [],
    }


def _build_payload_from_rule(
    chosen: dict[str, Any],
    context: dict[str, Any],
    sha: str,
) -> dict[str, Any]:
    postings: list[dict[str, Any]] = []
    flags: list[str] = []
    rule: JournalRule = chosen["rule"]

    for entry in rule.entries:
        selected = _select_account_for_entry(
            entry.raw
            if hasattr(entry, "raw")
            else {
                "account_code": entry.account_code,
                "account_name": entry.account_name,
                "amount_field": entry.amount_field,
                "condition": entry.condition,
                "alternatives": list(entry.alternatives),
                "is_variable": entry.is_variable,
            },
            context,
        )
        if selected is None:
            continue

        selected = resolve_variable_account(selected, context)

        amount = _resolve_amount(entry.amount_field, context)
        if amount <= 0:
            continue

        if entry.is_variable or "xxx" in selected["account_code"].lower():
            flags.append("needs_human_account_pick")

        postings.append(
            {
                "account_code": selected["account_code"],
                "account_name": selected["account_name"],
                "debit": amount if entry.side == "debit" else 0.0,
                "credit": amount if entry.side == "credit" else 0.0,
                "line_type": entry.side,
                "amount_field": entry.amount_field,
                "description": entry.description,
                "is_variable": entry.is_variable,
            }
        )

    total_debit = round(sum(item["debit"] for item in postings), 2)
    total_credit = round(sum(item["credit"] for item in postings), 2)
    balanced = abs(total_debit - total_credit) < 0.01
    status = "READY" if balanced else "UNRESOLVED_RULE"
    if chosen.get("needs_review"):
        flags.append("ambiguous_rule")
    if not balanced:
        flags.append("balance_check_failed")

    return {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "sha256": sha,
        "rule_id": rule.rule_id,
        "journal_code": rule.book_code,
        "postings": postings,
        "totals": {"debit": total_debit, "credit": total_credit},
        "is_balanced": balanced,
        "status": status,
        "cache_hit": False,
        "score": chosen.get("score", 0),
        "specificity": chosen.get("specificity", 0),
        "matched_conditions": chosen.get("matched", []),
        "flags": sorted(set(flags)),
        "needs_review": bool(chosen.get("needs_review", False) or flags),
    }


def _merge_stage_c_decision(
    extraction_output: dict[str, Any],
    journal_payload: dict[str, Any],
) -> dict[str, Any]:
    extraction_meta = extraction_output.get("meta", {})
    extraction_triggers = extraction_meta.get("triggers", {})

    flags = {str(flag) for flag in journal_payload.get("flags", [])}
    rule_conflict = bool(
        journal_payload.get("status") == "UNRESOLVED_RULE"
        or "ambiguous_rule" in flags
        or "balance_check_failed" in flags
        or "unresolved_rule" in flags
    )
    variable_account_needed = bool("needs_human_account_pick" in flags)

    trigger_map = {
        "template_unknown": bool(extraction_triggers.get("template_unknown", False)),
        "field_confidence_low": bool(
            extraction_triggers.get("field_confidence_low", False)
            or extraction_output.get("low_confidence_fields")
        ),
        "rule_conflict": rule_conflict,
        "variable_account_needed": variable_account_needed,
    }
    reasons = [key for key, triggered in trigger_map.items() if triggered]
    stage_c = {
        "triggered": bool(reasons),
        "reasons": reasons,
        "recommended_route": "rule_extractor" if reasons else "standard_pipeline",
    }

    journal_payload["stage_c"] = stage_c
    journal_payload.setdefault("meta", {})
    journal_payload["meta"]["triggers"] = trigger_map
    journal_payload["meta"]["decision"] = stage_c

    extraction_output["stage_c"] = stage_c
    extraction_output.setdefault("meta", {})
    extraction_output["meta"]["triggers"] = {
        **extraction_output["meta"].get("triggers", {}),
        **trigger_map,
    }
    extraction_output["meta"]["decision"] = stage_c
    return stage_c


def run_journal_router(
    extraction_output: dict[str, Any],
    *,
    company_id: str | None = None,
    cache_root: Path | None = None,
    rules_root: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Create journal output and persist `journal_output.json` under cache/{sha256}/."""
    sha = str(extraction_output.get("sha256") or _hash_for_payload(extraction_output))
    root = cache_root or DEFAULT_CACHE_ROOT
    resolved_company_id = company_id or extraction_output.get("company_id")
    artifact_key = sha if not resolved_company_id else f"{sha}_{resolved_company_id}"
    artifact_dir = root / artifact_key
    artifact_path = artifact_dir / "journal_output.json"
    if artifact_path.exists() and not force_refresh:
        cached = json.loads(artifact_path.read_text(encoding="utf-8"))
        if cached.get("schema_version") == JOURNAL_SCHEMA_VERSION:
            cached["cache_hit"] = True
            return cached

    fields = extraction_output.get("fields", {})
    rules = _load_rule_defaults(rules_root or DEFAULT_RULES_ROOT)
    payload: dict[str, Any]

    if resolved_company_id:
        loaded = load_company_rules(
            resolved_company_id, rules_root=rules_root or DEFAULT_RULES_ROOT
        )
        context = _derive_routing_context(fields, rules)
        chosen = pick_best_rule(context, loaded.journal_rules)
        if chosen.get("status") == "OK":
            payload = _build_payload_from_rule(chosen, context, sha)
            payload["company_id"] = resolved_company_id
        else:
            payload = _fallback_payload(fields, rules, sha)
            payload["status"] = "UNRESOLVED_RULE"
            payload["flags"] = ["unresolved_rule"]
            payload["needs_review"] = True
            payload["company_id"] = resolved_company_id
    else:
        payload = _fallback_payload(fields, rules, sha)

    _merge_stage_c_decision(extraction_output, payload)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload
