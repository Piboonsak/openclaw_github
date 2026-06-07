"""Background COA rule generation service aligned to EPIC-5 D6."""

from __future__ import annotations

import json
import shutil
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Callable

import yaml
from jsonschema import Draft202012Validator

from config.settings import settings
from src.backend.ml.ocr import run_ocr
from src.backend.services.secrets_loader import load_llm_keys

ProgressCallback = Callable[..., None]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES_ROOT = REPO_ROOT / "rules"
DEFAULT_SCHEMA_PATH = DEFAULT_RULES_ROOT / "rule_schema.json"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _join_ocr_blocks(ocr_output: dict[str, Any]) -> str:
    return "\n".join(str(block.get("text", "")).strip() for block in ocr_output.get("blocks", []) if str(block.get("text", "")).strip())


def _extract_docx_text(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path, "r") as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise RuntimeError("Invalid .docx file: missing word/document.xml") from exc

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: list[str] = []
    for para in root.findall(".//w:p", ns):
        parts = [node.text for node in para.findall(".//w:t", ns) if node.text]
        text = "".join(parts).strip()
        if text:
            lines.append(text)
    combined = "\n".join(lines).strip()
    if not combined:
        raise RuntimeError("DOCX contains no readable text.")
    return combined


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")]
    return cleaned.strip()


def _call_anthropic(prompt: str, system: str, model: str) -> str:
    from anthropic import Anthropic  # type: ignore

    api_key = settings.ANTHROPIC_API_KEY or ""
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        temperature=0,
        max_tokens=7000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(getattr(item, "text", "") for item in response.content if getattr(item, "type", "") == "text").strip()


def _call_openai(prompt: str, system: str, model: str) -> str:
    from openai import OpenAI  # type: ignore

    api_key = settings.OPENAI_API_KEY or ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (completion.choices[0].message.content or "").strip()


def _call_llm(provider: str, prompt: str, system: str, model: str) -> str:
    if provider == "openai":
        return _call_openai(prompt, system, model)
    return _call_anthropic(prompt, system, model)


def _load_validator(schema_path: Path) -> Draft202012Validator:
    return Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))


def _validate_schema(payload: dict[str, Any], schema_path: Path) -> None:
    validator = _load_validator(schema_path)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "<root>"
    raise RuntimeError(f"Rule schema validation failed at {location}: {first.message}")


def _build_stage3_prompt(company_name: str, business_type: str, coa_text: str) -> str:
    return f"""
You are a senior Thai accounting system analyst.
Extract the chart of accounts from the source document.
Return YAML only with keys:
company:
  name: string
  business_type: string
chart_of_accounts:
  - code: string
    name: string
    type: asset|liability|equity|revenue|expense
account_confidence:
  - code: string
    confidence: 0-100

Company name: {company_name}
Business type: {business_type}

COA source text:
{coa_text[:24000]}
""".strip()


def _build_stage4_prompt(company_name: str, business_type: str, mapping_text: str, coa_payload: dict[str, Any]) -> str:
    coa_yaml = yaml.safe_dump(
        {
            "company": coa_payload.get("company", {}),
            "chart_of_accounts": coa_payload.get("chart_of_accounts", []),
        },
        sort_keys=False,
        allow_unicode=True,
    )
    return f"""
You are a senior Thai accounting system analyst.
Using the chart of accounts and Thai accounting mapping guide, generate double-entry journal rules.
Return YAML only with keys:
journal_entry_rules:
  - rule_id: string
    name: string
    description: string
    document_types: [string]
    transaction_type: string
    book_code: string
    conditions: object
    entries:
      - side: debit|credit
        account_code: string
        account_name: string
        amount_field: string
        description: string
        condition: string (optional)
        is_variable: boolean (optional)
        alternatives: [] (optional)
    validation:
      balance_check: string
      formula: string
      note: string (optional)
rule_confidence:
  - rule_id: string
    confidence: 0-100

Company name: {company_name}
Business type: {business_type}

Chart of accounts:
{coa_yaml[:18000]}

Accounting mapping guide:
{mapping_text[:24000]}
""".strip()


def _normalize_rule(rule: dict[str, Any]) -> str:
    return json.dumps(rule, ensure_ascii=False, sort_keys=True)


def _multi_pass_scores(first_rules: list[dict[str, Any]], second_rules: list[dict[str, Any]]) -> dict[str, int]:
    second_index = {str(rule.get("rule_id", "")): rule for rule in second_rules}
    scores: dict[str, int] = {}
    for rule in first_rules:
        rule_id = str(rule.get("rule_id", ""))
        if not rule_id:
            continue
        match = second_index.get(rule_id)
        if not match:
            scores[rule_id] = 60
            continue
        scores[rule_id] = 100 if _normalize_rule(rule) == _normalize_rule(match) else 80
    return scores


def _cross_reference_score(rule: dict[str, Any], account_codes: set[str]) -> int:
    entries = rule.get("entries", []) or []
    if not entries:
        return 0
    hits = 0
    for entry in entries:
        code = str(entry.get("account_code", "")).strip()
        if not code or "xxx" in code.lower() or code in account_codes:
            hits += 1
    return int(round((hits / len(entries)) * 100))


def _balance_structure_score(rule: dict[str, Any]) -> int:
    entries = rule.get("entries", []) or []
    if not entries:
        return 0
    debit_count = sum(1 for entry in entries if str(entry.get("side", "")).lower() == "debit")
    credit_count = sum(1 for entry in entries if str(entry.get("side", "")).lower() == "credit")
    has_formula = bool(rule.get("validation", {}).get("balance_check"))
    return 100 if debit_count > 0 and credit_count > 0 and has_formula else 0


def _source_coverage_score(rule: dict[str, Any], source_text: str) -> int:
    candidates = [str(rule.get("name", "")), str(rule.get("description", ""))]
    hits = 0
    total = 0
    lowered = source_text.lower()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        total += 1
        if candidate.lower() in lowered:
            hits += 1
    entries = rule.get("entries", []) or []
    for entry in entries:
        name = str(entry.get("account_name", "")).strip()
        if not name:
            continue
        total += 1
        if name.lower() in lowered:
            hits += 1
    if total == 0:
        return 0
    return int(round((hits / total) * 100))


def _overall_confidence(llm_self: int, agreement: int, cross_ref: int, balance: int, coverage: int) -> float:
    return round((llm_self * 0.30) + (agreement * 0.25) + (cross_ref * 0.20) + (balance * 0.15) + (coverage * 0.10), 1)


def _confidence_status(score: float) -> str:
    if score >= 90:
        return "auto"
    if score >= 75:
        return "review"
    return "edit"


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _build_validation_report(company_name: str, generated_path: Path, rule_count: int, account_count: int, flagged_rules: list[str]) -> str:
    lines = [
        f"# Validation Report — {company_name}",
        "",
        f"- Draft file: `{generated_path.name}`",
        f"- Accounts extracted: {account_count}",
        f"- Rules generated: {rule_count}",
        f"- Flagged rules: {len(flagged_rules)}",
    ]
    if flagged_rules:
        lines.append("")
        lines.append("## Rules Requiring Review")
        lines.extend(f"- {rule_id}" for rule_id in flagged_rules)
    return "\n".join(lines) + "\n"


def run_rule_generation_job(
    *,
    job_id: str,
    company_id: str,
    company_name: str,
    tax_id: str,
    business_type: str,
    coa_file: Path,
    mapping_file: Path,
    provider: str,
    model: str,
    progress_callback: ProgressCallback,
    rules_root: Path | None = None,
) -> dict[str, Any]:
    load_llm_keys()
    settings.reload()
    root = rules_root or DEFAULT_RULES_ROOT
    company_root = root / company_id
    source_root = company_root / "source"
    audit_root = company_root / "audit"
    source_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)
    schema_path = root / "rule_schema.json"
    draft_path = company_root / "rule_coa.generated.yaml"
    active_path = company_root / "rule_coa.yaml"
    confidence_path = company_root / "confidence.json"
    validation_report_path = audit_root / "validation_report.md"
    generation_log_path = audit_root / "generation_log.json"

    stage_started = _now_ms()
    shutil.copy2(coa_file, source_root / "coa_upload.pdf")
    shutil.copy2(mapping_file, source_root / "mapping_upload.docx")
    progress_callback(stage=1, status="done", progress_pct=10, duration_ms=_now_ms() - stage_started)

    stage_started = _now_ms()
    progress_callback(stage=2, status="running", progress_pct=15)
    coa_ocr = run_ocr(str(coa_file))
    coa_text = _join_ocr_blocks(coa_ocr)
    mapping_text = _extract_docx_text(mapping_file)
    if not coa_text.strip():
        raise RuntimeError("COA PDF yielded no readable text.")
    progress_callback(stage=2, status="done", progress_pct=30, duration_ms=_now_ms() - stage_started)

    stage_started = _now_ms()
    progress_callback(stage=3, status="running", progress_pct=35)
    stage3_prompt = _build_stage3_prompt(company_name, business_type, coa_text)
    stage3_raw = _call_llm(provider, stage3_prompt, "Return only valid YAML.", model)
    stage3_payload = yaml.safe_load(_strip_code_fence(stage3_raw)) or {}
    accounts = stage3_payload.get("chart_of_accounts", []) or []
    if not isinstance(accounts, list) or not accounts:
        raise RuntimeError("Stage 3 returned no chart_of_accounts.")
    seen_codes: set[str] = set()
    normalized_accounts: list[dict[str, Any]] = []
    for account in accounts:
        code = str(account.get("code", "")).strip()
        name = str(account.get("name", "")).strip()
        account_type = str(account.get("type", "expense")).strip().lower()
        if not code or not name or code in seen_codes:
            continue
        seen_codes.add(code)
        normalized_accounts.append({"code": code, "name": name, "type": account_type})
    if not normalized_accounts:
        raise RuntimeError("Stage 3 could not normalize any account rows.")
    account_confidence_map = {
        str(item.get("code", "")).strip(): int(float(item.get("confidence", 85)))
        for item in (stage3_payload.get("account_confidence", []) or [])
        if str(item.get("code", "")).strip()
    }
    company_payload = stage3_payload.get("company") or {}
    company_payload = {
        "name": company_payload.get("name") or company_name,
        "short_name": company_payload.get("short_name") or company_name,
        "tax_id": company_payload.get("tax_id") or tax_id,
        "business_type": company_payload.get("business_type") or business_type,
        "notes": company_payload.get("notes", ""),
    }
    progress_callback(stage=3, status="done", progress_pct=55, duration_ms=_now_ms() - stage_started)

    stage_started = _now_ms()
    progress_callback(stage=4, status="running", progress_pct=60)
    stage4_prompt = _build_stage4_prompt(company_name, business_type, mapping_text, {"company": company_payload, "chart_of_accounts": normalized_accounts})
    stage4_raw_first = _call_llm(provider, stage4_prompt, "Return only valid YAML.", model)
    stage4_payload_first = yaml.safe_load(_strip_code_fence(stage4_raw_first)) or {}
    stage4_raw_second = _call_llm(provider, stage4_prompt, "Return only valid YAML.", model)
    stage4_payload_second = yaml.safe_load(_strip_code_fence(stage4_raw_second)) or {}
    journal_rules = stage4_payload_first.get("journal_entry_rules", []) or []
    if not isinstance(journal_rules, list) or not journal_rules:
        raise RuntimeError("Stage 4 returned no journal_entry_rules.")
    agreement_scores = _multi_pass_scores(journal_rules, stage4_payload_second.get("journal_entry_rules", []) or [])
    llm_confidence_map = {
        str(item.get("rule_id", "")).strip(): int(float(item.get("confidence", 80)))
        for item in (stage4_payload_first.get("rule_confidence", []) or [])
        if str(item.get("rule_id", "")).strip()
    }
    progress_callback(stage=4, status="done", progress_pct=85, duration_ms=_now_ms() - stage_started)

    stage_started = _now_ms()
    progress_callback(stage=5, status="running", progress_pct=90)
    payload = {
        "company": company_payload,
        "chart_of_accounts": normalized_accounts,
        "journal_entry_rules": journal_rules,
    }
    _validate_schema(payload, schema_path)

    account_codes = {account["code"] for account in normalized_accounts}
    flags: list[str] = []
    rules_confidence: list[dict[str, Any]] = []
    for rule in journal_rules:
        rule_id = str(rule.get("rule_id", "")).strip()
        llm_self = llm_confidence_map.get(rule_id, 80)
        agreement = agreement_scores.get(rule_id, 60)
        cross_ref = _cross_reference_score(rule, account_codes)
        balance = _balance_structure_score(rule)
        coverage = _source_coverage_score(rule, mapping_text)
        overall = _overall_confidence(llm_self, agreement, cross_ref, balance, coverage)
        status = _confidence_status(overall)
        if status != "auto":
            flags.append(rule_id)
        rules_confidence.append(
            {
                "rule_id": rule_id,
                "confidence": overall,
                "status": status,
                "signals": {
                    "llm_self": llm_self,
                    "multi_pass_agreement": agreement,
                    "coa_cross_reference": cross_ref,
                    "balance_check": balance,
                    "source_coverage": coverage,
                },
            }
        )

    account_confidence = [
        {
            "code": account["code"],
            "name": account["name"],
            "type": account["type"],
            "confidence": account_confidence_map.get(account["code"], 85),
        }
        for account in normalized_accounts
    ]
    confidence_payload = {
        "job_id": job_id,
        "company_id": company_id,
        "company_name": company_name,
        "overall_confidence": round(sum(item["confidence"] for item in rules_confidence) / max(len(rules_confidence), 1), 1),
        "accounts": account_confidence,
        "rules": rules_confidence,
        "flags": [f"{len(flags)} rules below 90% threshold"] if flags else [],
        "generated_at_ms": _now_ms(),
    }
    _write_yaml(draft_path, payload)
    confidence_path.write_text(json.dumps(confidence_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_report_path.write_text(
        _build_validation_report(company_name, draft_path, len(journal_rules), len(normalized_accounts), flags),
        encoding="utf-8",
    )
    generation_log = {
        "job_id": job_id,
        "company_id": company_id,
        "provider": provider,
        "model": model,
        "stage3_prompt_preview": stage3_prompt[:2000],
        "stage4_prompt_preview": stage4_prompt[:2000],
        "stage3_response_preview": stage3_raw[:2000],
        "stage4_response_preview": stage4_raw_first[:2000],
        "stage4_response_second_preview": stage4_raw_second[:2000],
        "draft_path": str(draft_path),
        "active_path": str(active_path),
    }
    generation_log_path.write_text(json.dumps(generation_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    progress_callback(stage=5, status="done", progress_pct=100, duration_ms=_now_ms() - stage_started)

    return {
        "job_id": job_id,
        "status": "done",
        "output_path": str(draft_path.relative_to(REPO_ROOT)),
        "draft_path": str(draft_path),
        "active_path": str(active_path),
        "confidence_path": str(confidence_path),
        "coa_count": len(normalized_accounts),
        "rule_count": len(journal_rules),
        "overall_confidence": confidence_payload["overall_confidence"],
        "accounts_confidence": account_confidence,
        "rules_confidence": rules_confidence,
        "flags": confidence_payload["flags"],
        "yaml_content": draft_path.read_text(encoding="utf-8"),
    }


def approve_generated_rules(job_result: dict[str, Any]) -> Path:
    draft_path = Path(job_result["draft_path"])
    active_path = Path(job_result["active_path"])
    if not draft_path.exists():
        raise FileNotFoundError(f"Draft rule file not found: {draft_path}")
    active_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
    return active_path


def load_rule_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def save_rule_text(path: str | Path, yaml_text: str, schema_path: Path | None = None) -> dict[str, Any]:
    payload = yaml.safe_load(yaml_text)
    if not isinstance(payload, dict):
        raise RuntimeError("Edited YAML root must be a mapping.")
    _validate_schema(payload, schema_path or DEFAULT_SCHEMA_PATH)
    target = Path(path)
    _write_yaml(target, payload)
    return payload
