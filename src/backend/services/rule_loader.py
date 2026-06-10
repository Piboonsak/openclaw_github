"""Helpers for loading and validating company-specific rule_coa files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from config.settings import settings

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES_ROOT = REPO_ROOT / "rules"
DEFAULT_SCHEMA_PATH = DEFAULT_RULES_ROOT / "rule_schema.json"


def _rules_root() -> Path:
    settings.reload()
    return settings.RULES_ROOT


def _schema_path_for(rules_root: Path) -> Path:
    scoped_schema = rules_root / "rule_schema.json"
    return scoped_schema if scoped_schema.exists() else DEFAULT_SCHEMA_PATH


@dataclass(frozen=True)
class RuleEntry:
    side: str
    account_code: str
    amount_field: str
    account_name: str = ""
    description: str = ""
    condition: str = ""
    is_variable: bool = False
    alternatives: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class JournalRule:
    rule_id: str
    name: str
    description: str
    document_types: tuple[str, ...]
    transaction_type: str
    book_code: str
    conditions: dict[str, Any]
    entries: tuple[RuleEntry, ...]
    validation: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class CompiledRules:
    company_id: str
    rule_path: Path | None
    payload: dict[str, Any]
    chart_of_accounts: tuple[dict[str, Any], ...]
    journal_rules: tuple[JournalRule, ...]
    globals_payload: dict[str, Any]


@lru_cache(maxsize=8)
def _load_schema(schema_path: str) -> Draft202012Validator:
    payload = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return Draft202012Validator(payload)


@lru_cache(maxsize=32)
def _load_company_rules_cached(
    company_id: str,
    rule_path_str: str,
    rule_mtime_ns: int,
    schema_path_str: str,
    rules_root_str: str,
    globals_fingerprint: str,
) -> CompiledRules:
    rule_path = Path(rule_path_str) if rule_path_str else None
    payload: dict[str, Any] = {}
    chart_of_accounts: tuple[dict[str, Any], ...] = ()
    journal_rules: tuple[JournalRule, ...] = ()

    if rule_path is not None:
        payload = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
        validator = _load_schema(schema_path_str)
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
        if errors:
            first = errors[0]
            path = ".".join(str(part) for part in first.path) or "<root>"
            raise RuntimeError(
                f"Invalid rule_coa for {company_id} at {path}: {first.message}"
            )
        chart_of_accounts = tuple(payload.get("chart_of_accounts", []))
        journal_rules = tuple(
            _compile_rule(item) for item in payload.get("journal_entry_rules", [])
        )

    globals_payload = _load_global_defaults(Path(rules_root_str))
    return CompiledRules(
        company_id=company_id,
        rule_path=rule_path,
        payload=payload,
        chart_of_accounts=chart_of_accounts,
        journal_rules=journal_rules,
        globals_payload=globals_payload,
    )


def _compile_rule(raw_rule: dict[str, Any]) -> JournalRule:
    entries = tuple(
        RuleEntry(
            side=str(entry.get("side", "")).strip(),
            account_code=str(entry.get("account_code", "")).strip(),
            amount_field=str(entry.get("amount_field", "")).strip(),
            account_name=str(entry.get("account_name", "")).strip(),
            description=str(entry.get("description", "")).strip(),
            condition=str(entry.get("condition", "")).strip(),
            is_variable=bool(entry.get("is_variable", False)),
            alternatives=tuple(entry.get("alternatives", []) or []),
        )
        for entry in raw_rule.get("entries", [])
    )
    return JournalRule(
        rule_id=str(raw_rule.get("rule_id", "")).strip(),
        name=str(raw_rule.get("name", "")).strip(),
        description=str(raw_rule.get("description", "")).strip(),
        document_types=tuple(raw_rule.get("document_types", []) or []),
        transaction_type=str(raw_rule.get("transaction_type", "")).strip(),
        book_code=str(raw_rule.get("book_code", "")).strip(),
        conditions=dict(raw_rule.get("conditions", {}) or {}),
        entries=entries,
        validation=dict(raw_rule.get("validation", {}) or {}),
        raw=dict(raw_rule),
    )


def _load_yaml_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_global_defaults(rules_root: Path) -> dict[str, Any]:
    global_root = rules_root / "global"
    return {
        "base_patterns": _load_yaml_if_exists(global_root / "base_patterns.yaml"),
        "vat_rules": _load_yaml_if_exists(global_root / "vat_rules.yaml"),
        "wht_rates": _load_yaml_if_exists(global_root / "wht_rates.yaml"),
    }


def load_company_rules(
    company_id: str,
    *,
    rules_root: Path | None = None,
    schema_path: Path | None = None,
) -> CompiledRules:
    resolved_rules_root = rules_root or _rules_root()
    resolved_schema_path = schema_path or _schema_path_for(resolved_rules_root)
    rule_path = resolved_rules_root / company_id / "rule_coa.yaml"

    globals_root = resolved_rules_root / "global"
    globals_fingerprint = "|".join(
        str(path.stat().st_mtime_ns) if path.exists() else "0"
        for path in (
            globals_root / "base_patterns.yaml",
            globals_root / "vat_rules.yaml",
            globals_root / "wht_rates.yaml",
        )
    )

    if not resolved_schema_path.exists():
        raise RuntimeError(f"Rule schema not found: {resolved_schema_path}")

    if not rule_path.exists():
        return _load_company_rules_cached(
            company_id,
            "",
            0,
            str(resolved_schema_path),
            str(resolved_rules_root),
            globals_fingerprint,
        )

    return _load_company_rules_cached(
        company_id,
        str(rule_path),
        rule_path.stat().st_mtime_ns,
        str(resolved_schema_path),
        str(resolved_rules_root),
        globals_fingerprint,
    )
