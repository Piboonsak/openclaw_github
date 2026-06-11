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
DEFAULT_MODELS = {
    "openrouter": "openai/gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o-mini",
}
LLM_REQUEST_TIMEOUT_SECONDS = 45


def _rules_root() -> Path:
    settings.reload()
    return settings.RULES_ROOT


def _schema_path_for(rules_root: Path) -> Path:
    scoped_schema = rules_root / "rule_schema.json"
    return scoped_schema if scoped_schema.exists() else DEFAULT_SCHEMA_PATH


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _join_ocr_blocks(ocr_output: dict[str, Any]) -> str:
    return "\n".join(
        str(block.get("text", "")).strip()
        for block in ocr_output.get("blocks", [])
        if str(block.get("text", "")).strip()
    )


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
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Anthropic SDK is not installed. Run: pip install anthropic"
        ) from exc

    api_key = settings.ANTHROPIC_API_KEY or ""
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    client = Anthropic(api_key=api_key, timeout=LLM_REQUEST_TIMEOUT_SECONDS)
    response = client.messages.create(
        model=model,
        temperature=0,
        max_tokens=7000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "\n".join(
        getattr(item, "text", "")
        for item in response.content
        if getattr(item, "type", "") == "text"
    ).strip()


def _call_openai(prompt: str, system: str, model: str) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OpenAI SDK is not installed. Run: pip install openai"
        ) from exc

    api_key = settings.OPENAI_API_KEY or ""
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (completion.choices[0].message.content or "").strip()


def _call_openrouter(prompt: str, system: str, model: str) -> str:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OpenAI SDK is not installed. Run: pip install openai"
        ) from exc

    api_key = settings.OPENROUTER_API_KEY or ""
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    client = OpenAI(
        api_key=api_key,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://ai-accounting-copilot.local",
            "X-Title": "ai-accounting-copilot",
        },
    )
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (completion.choices[0].message.content or "").strip()


def _is_auth_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "invalid x-api-key" in lowered
        or "authentication_error" in lowered
        or "incorrect api key" in lowered
        or "401" in lowered
    )


def _resolve_model(provider: str, model: str) -> str:
    chosen = (model or "").strip()
    if not chosen:
        return DEFAULT_MODELS[provider]
    # If caller sends a provider-specific model for the other backend, use safe default.
    if provider == "openai" and "claude" in chosen.lower():
        return DEFAULT_MODELS[provider]
    if provider == "openrouter" and chosen.lower().startswith("claude"):
        return "anthropic/claude-3.5-sonnet"
    if provider == "anthropic" and "gpt" in chosen.lower():
        return DEFAULT_MODELS[provider]
    return chosen


def _provider_order(provider: str) -> list[str]:
    normalized = (provider or "").strip().lower()
    if normalized in {"", "auto"}:
        return ["openrouter", "anthropic", "openai"]
    if normalized == "openrouter":
        return ["openrouter", "anthropic", "openai"]
    if normalized == "openai":
        return ["openai", "openrouter", "anthropic"]
    return ["anthropic", "openrouter", "openai"]


def _call_llm(provider: str, prompt: str, system: str, model: str) -> str:
    errors: list[str] = []
    for candidate in _provider_order(provider):
        candidate_model = _resolve_model(candidate, model)
        if candidate == "anthropic":
            has_key = bool(settings.ANTHROPIC_API_KEY)
        elif candidate == "openai":
            has_key = bool(settings.OPENAI_API_KEY)
        else:
            has_key = bool(settings.OPENROUTER_API_KEY)
        if not has_key:
            errors.append(f"{candidate}: missing API key")
            continue

        try:
            if candidate == "openrouter":
                return _call_openrouter(prompt, system, candidate_model)
            if candidate == "openai":
                return _call_openai(prompt, system, candidate_model)
            return _call_anthropic(prompt, system, candidate_model)
        except Exception as exc:
            message = str(exc)
            errors.append(f"{candidate}: {message}")
            # For non-auth hard failures, stop immediately when provider was explicit.
            if (provider or "").strip().lower() not in {
                "",
                "auto",
            } and not _is_auth_error(message):
                break
            continue

    raise RuntimeError("LLM call failed for all providers. " + " | ".join(errors))


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


def _rejoin_wrapped_coa_rows(text: str) -> str:
    """Join rows that pypdf wrapped across two lines in Thai accounting COA PDFs.

    Some account rows split mid-row when the name contains English text (e.g. bank
    account numbers).  In those cases pypdf emits the code+name on one line and
    the หมวด/ระดับ/ประเภท/บัญชีคุม metadata on the next.  This function detects
    that pattern and rejoins them so the LLM sees one coherent row per account.
    """
    import re

    category_start = re.compile(
        r"^(ส/ท|หนี้สิน|ทุน|รายได้|ค่าใช้จ่าย)\s+\d"
    )
    lines = text.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            # If the next line starts with Thai category metadata but the current
            # line does not already contain it, merge them.
            if nxt and category_start.match(nxt) and not category_start.match(current.strip()):
                result.append(current.rstrip() + "  " + nxt)
                i += 2
                continue
        result.append(current)
        i += 1
    return "\n".join(result)


def _build_stage3_prompt(company_name: str, business_type: str, coa_text: str) -> str:
    cleaned = _rejoin_wrapped_coa_rows(coa_text)
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
{cleaned[:40000]}
""".strip()


def _build_stage4_prompt(
    company_name: str,
    business_type: str,
    mapping_text: str,
    coa_payload: dict[str, Any],
) -> str:
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


def _multi_pass_scores(
    first_rules: list[dict[str, Any]], second_rules: list[dict[str, Any]]
) -> dict[str, int]:
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
    debit_count = sum(
        1 for entry in entries if str(entry.get("side", "")).lower() == "debit"
    )
    credit_count = sum(
        1 for entry in entries if str(entry.get("side", "")).lower() == "credit"
    )
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


def _overall_confidence(
    llm_self: int, agreement: int, cross_ref: int, balance: int, coverage: int
) -> float:
    return round(
        (llm_self * 0.30)
        + (agreement * 0.25)
        + (cross_ref * 0.20)
        + (balance * 0.15)
        + (coverage * 0.10),
        1,
    )


def _confidence_status(score: float) -> str:
    if score >= 90:
        return "auto"
    if score >= 75:
        return "review"
    return "edit"


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _build_validation_report(
    company_name: str,
    generated_path: Path,
    rule_count: int,
    account_count: int,
    flagged_rules: list[str],
) -> str:
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
    root = rules_root or _rules_root()
    company_root = root / company_id
    source_root = company_root / "source"
    audit_root = company_root / "audit"
    source_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)
    schema_path = _schema_path_for(root)
    draft_path = company_root / "rule_coa.generated.yaml"
    active_path = company_root / "rule_coa.yaml"
    confidence_path = company_root / "confidence.json"
    validation_report_path = audit_root / "validation_report.md"
    generation_log_path = audit_root / "generation_log.json"

    stage_started = _now_ms()
    shutil.copy2(coa_file, source_root / "coa_upload.pdf")
    shutil.copy2(mapping_file, source_root / "mapping_upload.docx")
    progress_callback(
        stage=1, status="done", progress_pct=10, duration_ms=_now_ms() - stage_started
    )

    stage_started = _now_ms()
    progress_callback(stage=2, status="running", progress_pct=15)
    coa_ocr = run_ocr(str(coa_file))
    coa_text = _join_ocr_blocks(coa_ocr)
    mapping_text = _extract_docx_text(mapping_file)
    if not coa_text.strip():
        raise RuntimeError("COA PDF yielded no readable text.")
    progress_callback(
        stage=2, status="done", progress_pct=30, duration_ms=_now_ms() - stage_started
    )

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
    progress_callback(
        stage=3, status="done", progress_pct=55, duration_ms=_now_ms() - stage_started
    )

    stage_started = _now_ms()
    progress_callback(stage=4, status="running", progress_pct=60)
    stage4_prompt = _build_stage4_prompt(
        company_name,
        business_type,
        mapping_text,
        {"company": company_payload, "chart_of_accounts": normalized_accounts},
    )
    stage4_raw_first = _call_llm(
        provider, stage4_prompt, "Return only valid YAML.", model
    )
    stage4_payload_first = yaml.safe_load(_strip_code_fence(stage4_raw_first)) or {}
    try:
        stage4_raw_second = _call_llm(
            provider, stage4_prompt, "Return only valid YAML.", model
        )
        stage4_payload_second = (
            yaml.safe_load(_strip_code_fence(stage4_raw_second)) or {}
        )
    except Exception:
        # Keep generation usable even when the optional second-pass confidence probe fails.
        stage4_raw_second = ""
        stage4_payload_second = {
            "journal_entry_rules": stage4_payload_first.get("journal_entry_rules", [])
        }
    journal_rules = stage4_payload_first.get("journal_entry_rules", []) or []
    if not isinstance(journal_rules, list) or not journal_rules:
        raise RuntimeError("Stage 4 returned no journal_entry_rules.")
    agreement_scores = _multi_pass_scores(
        journal_rules, stage4_payload_second.get("journal_entry_rules", []) or []
    )
    llm_confidence_map = {
        str(item.get("rule_id", "")).strip(): int(float(item.get("confidence", 80)))
        for item in (stage4_payload_first.get("rule_confidence", []) or [])
        if str(item.get("rule_id", "")).strip()
    }
    progress_callback(
        stage=4, status="done", progress_pct=85, duration_ms=_now_ms() - stage_started
    )

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
                "name": str(rule.get("name", "")).strip() or rule_id,
                "line_count": len(rule.get("entries", []) or []),
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
        "overall_confidence": round(
            sum(item["confidence"] for item in rules_confidence)
            / max(len(rules_confidence), 1),
            1,
        ),
        "accounts": account_confidence,
        "rules": rules_confidence,
        "flags": [f"{len(flags)} rules below 90% threshold"] if flags else [],
        "generated_at_ms": _now_ms(),
    }
    _write_yaml(draft_path, payload)
    confidence_path.write_text(
        json.dumps(confidence_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    validation_report_path.write_text(
        _build_validation_report(
            company_name,
            draft_path,
            len(journal_rules),
            len(normalized_accounts),
            flags,
        ),
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
    generation_log_path.write_text(
        json.dumps(generation_log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_callback(
        stage=5, status="done", progress_pct=100, duration_ms=_now_ms() - stage_started
    )

    return {
        "job_id": job_id,
        "status": "done",
        "output_path": _display_path(draft_path),
        "draft_path": str(draft_path),
        "active_path": str(active_path),
        "confidence_path": str(confidence_path),
        "coa_count": len(normalized_accounts),
        "rule_count": len(journal_rules),
        "overall_confidence": confidence_payload["overall_confidence"],
        "accounts_confidence": account_confidence,
        "rules_confidence": rules_confidence,
        "journal_rules": journal_rules,
        "mapping_reference_excerpt": mapping_text[:600].strip(),
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


def save_rule_text(
    path: str | Path, yaml_text: str, schema_path: Path | None = None
) -> dict[str, Any]:
    payload = yaml.safe_load(yaml_text)
    if not isinstance(payload, dict):
        raise RuntimeError("Edited YAML root must be a mapping.")
    _validate_schema(payload, schema_path or _schema_path_for(_rules_root()))
    target = Path(path)
    _write_yaml(target, payload)
    return payload


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def validate_edited_rules(
    chart_of_accounts: list[dict[str, Any]],
    edited_rules: list[dict[str, Any]],
) -> None:
    if not isinstance(edited_rules, list) or not edited_rules:
        raise RuntimeError("Edited rules must be a non-empty list.")

    valid_codes = {
        str(item.get("code", "")).strip()
        for item in (chart_of_accounts or [])
        if str(item.get("code", "")).strip()
    }
    seen_rule_ids: set[str] = set()

    for rule in edited_rules:
        rule_id = str(rule.get("rule_id", "")).strip()
        if not rule_id:
            raise RuntimeError("Each rule must include a non-empty rule_id.")
        if rule_id in seen_rule_ids:
            raise RuntimeError(f"Duplicate rule_id detected: {rule_id}")
        seen_rule_ids.add(rule_id)

        entries = rule.get("entries", []) or []
        if not isinstance(entries, list) or not entries:
            raise RuntimeError(f"Rule {rule_id} must include at least one entry.")

        debit_total = 0.0
        credit_total = 0.0
        has_debit = False
        has_credit = False

        for entry in entries:
            side = str(entry.get("side", "")).strip().lower()
            if side not in {"debit", "credit"}:
                raise RuntimeError(
                    f"Rule {rule_id} has invalid entry side: {entry.get('side')}"
                )

            account_code = str(entry.get("account_code", "")).strip()
            if not account_code:
                raise RuntimeError(
                    f"Rule {rule_id} has an entry with empty account_code"
                )

            is_variable = bool(entry.get("is_variable", False)) or (
                "xxx" in account_code.lower()
            )
            if not is_variable and account_code not in valid_codes:
                raise RuntimeError(
                    f"Rule {rule_id} account_code '{account_code}' is not in company COA"
                )

            amount_field = str(entry.get("amount_field", "")).strip()
            if not amount_field:
                raise RuntimeError(
                    f"Rule {rule_id} has an entry with empty amount_field"
                )

            amount = _to_float(entry.get("example_amount"), 0.0)
            if amount < 0:
                raise RuntimeError(
                    f"Rule {rule_id} has negative example_amount for {account_code}"
                )

            if side == "debit":
                has_debit = True
                debit_total += amount
            else:
                has_credit = True
                credit_total += amount

        if not has_debit or not has_credit:
            raise RuntimeError(
                f"Rule {rule_id} must contain both debit and credit entries"
            )

        if abs(debit_total - credit_total) >= 0.01:
            raise RuntimeError(
                f"Rule {rule_id} is unbalanced (debit={debit_total:.2f}, credit={credit_total:.2f})"
            )


def save_edited_rules(
    job_result: dict[str, Any], edited_rules: list[dict[str, Any]]
) -> dict[str, Any]:
    draft_path = Path(job_result["draft_path"])
    active_path = Path(job_result["active_path"])
    schema_path = _schema_path_for(draft_path.parents[1])

    if not draft_path.exists():
        raise FileNotFoundError(f"Draft rule file not found: {draft_path}")

    current_payload = yaml.safe_load(draft_path.read_text(encoding="utf-8")) or {}
    if not isinstance(current_payload, dict):
        raise RuntimeError("Draft rule file has invalid YAML root.")

    chart_of_accounts = list(current_payload.get("chart_of_accounts", []) or [])
    validate_edited_rules(chart_of_accounts, edited_rules)

    sanitized_rules: list[dict[str, Any]] = []
    for rule in edited_rules:
        sanitized = dict(rule)
        entries: list[dict[str, Any]] = []
        for entry in rule.get("entries", []) or []:
            cleaned = dict(entry)
            cleaned.pop("example_amount", None)
            entries.append(cleaned)
        sanitized["entries"] = entries
        sanitized_rules.append(sanitized)

    current_payload["journal_entry_rules"] = sanitized_rules
    _validate_schema(current_payload, schema_path)
    _write_yaml(draft_path, current_payload)

    # Keep active YAML in sync if this generation has already been approved.
    if bool(job_result.get("approved", False)):
        active_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")

    confidence_index = {
        str(item.get("rule_id", "")).strip(): item
        for item in (job_result.get("rules_confidence", []) or [])
        if str(item.get("rule_id", "")).strip()
    }
    updated_confidence: list[dict[str, Any]] = []
    for rule in sanitized_rules:
        rule_id = str(rule.get("rule_id", "")).strip()
        previous = dict(confidence_index.get(rule_id, {}))
        previous["rule_id"] = rule_id
        previous["name"] = str(rule.get("name", "")).strip() or rule_id
        previous["line_count"] = len(rule.get("entries", []) or [])
        if not previous.get("status"):
            previous["status"] = "review"
        if "confidence" not in previous:
            previous["confidence"] = 80.0
        updated_confidence.append(previous)

    updated_result = dict(job_result)
    updated_result["journal_rules"] = sanitized_rules
    updated_result["rules_confidence"] = updated_confidence
    updated_result["rule_count"] = len(sanitized_rules)
    updated_result["yaml_content"] = draft_path.read_text(encoding="utf-8")
    updated_result["flags"] = [
        f"{sum(1 for item in updated_confidence if _to_float(item.get('confidence')) < 85)} rules below 85% threshold"
    ]

    return updated_result
