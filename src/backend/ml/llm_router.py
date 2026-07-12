"""Stage C multi-provider routing and repair logic."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from config.settings import settings
from src.backend.ml.amount_reconciler import reconcile_amounts
from src.backend.ml.field_validators import validate_field
from src.backend.ml.providers import AnthropicProvider, LLMProvider, OpenRouterProvider
from src.backend.services.secrets_loader import load_llm_keys

_DAILY_BUDGET_FILE = Path(__file__).parent / "cache" / "stage_c_budget.json"
_COST_LOG_FILE = Path(__file__).resolve().parents[3] / "tmp" / "llm_cost_log.jsonl"
_DEFAULT_DAILY_USD_CAP = 2.0
_DEFAULT_FREE_DAILY_USD_CAP = 1.0
_DEFAULT_PAID_DAILY_USD_CAP = 2.0
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
# Vision-capable default for Stage C image cascade (Patch B).
# Previously "anthropic/claude-3.5-haiku" — text-only, incompatible with image input.
_OPENROUTER_DEFAULT_MODEL = "google/gemini-2.5-flash"
_DEFAULT_FREE_MODELS = ["google/gemini-2.5-flash-lite"]
_DEFAULT_BACKUP_MODELS = ["openai/gpt-4.1-nano", "google/gemini-3.1-flash-lite"]
_DEFAULT_FREE_CONF_THRESHOLD = 0.70
# Direct Anthropic API requires fully-dated model IDs. OpenRouter accepts the
# short aliases, but when we fall back to the native Anthropic provider we must
# resolve bare aliases to a concrete, currently-available snapshot ID, otherwise
# the call 404s ("model: <alias>"). Keep this in sync with `models.list()`.
_ANTHROPIC_MODEL_ALIASES = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-opus-4-1": "claude-opus-4-1-20250805",
    "claude-opus-4": "claude-opus-4-20250514",
}
# Emergency-only Claude model used when the primary OpenRouter gateway is
# unreachable and we fall back to the native Anthropic provider for a model that
# is not a Claude model (e.g. google/gemini-*). Vision-capable so image repair
# still works in an outage. Per D9/Patch B, Anthropic is a cost-controlled
# emergency fallback only — the primary vision path is gemini-2.5-flash-lite
# via OpenRouter.
_ANTHROPIC_EMERGENCY_FALLBACK_MODEL = "claude-sonnet-4-5-20250929"
_DEFAULT_CRITICAL_FIELDS = {
    "invoice_number",
    "invoice_date",
    "seller_tax_id",
    "buyer_tax_id",
    "net_amount",
    "vat_amount",
    "total_amount",
}


def _critical_fields() -> set[str]:
    raw = os.environ.get("STAGE_C_CRITICAL_FIELDS", "")
    if not raw.strip():
        return set(_DEFAULT_CRITICAL_FIELDS)
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or set(_DEFAULT_CRITICAL_FIELDS)


def _load_budget() -> dict[str, Any]:
    if _DAILY_BUDGET_FILE.exists():
        try:
            return json.loads(_DAILY_BUDGET_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "date": "",
        "spent_usd": 0.0,
        "spent_by_tier": {"free": 0.0, "paid": 0.0},
    }


def _save_budget(data: dict[str, Any]) -> None:
    _DAILY_BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DAILY_BUDGET_FILE.write_text(json.dumps(data), encoding="utf-8")


def _today_str() -> str:
    return time.strftime("%Y-%m-%d")


def _normalize_tier(tier: str | None) -> str:
    if (tier or "").strip().lower() == "free":
        return "free"
    return "paid"


def _tier_cap_usd(tier: str) -> float:
    normalized = _normalize_tier(tier)
    if normalized == "free":
        return float(
            os.environ.get(
                "STAGE_C_FREE_DAILY_USD_CAP", str(_DEFAULT_FREE_DAILY_USD_CAP)
            )
        )
    return float(
        os.environ.get("STAGE_C_PAID_DAILY_USD_CAP", str(_DEFAULT_PAID_DAILY_USD_CAP))
    )


def _budget_allows(estimated_cost_usd: float, tier: str = "paid") -> tuple[bool, str]:
    normalized_tier = _normalize_tier(tier)
    cap = _tier_cap_usd(normalized_tier)
    budget = _load_budget()
    today = _today_str()
    if budget.get("date") != today:
        budget = {
            "date": today,
            "spent_usd": 0.0,
            "spent_by_tier": {"free": 0.0, "paid": 0.0},
        }

    spent_by_tier = budget.get("spent_by_tier") or {"free": 0.0, "paid": 0.0}
    tier_spent = float(spent_by_tier.get(normalized_tier, 0.0) or 0.0)

    if tier_spent + estimated_cost_usd > cap:
        return (
            False,
            f"Stage C {normalized_tier} daily budget cap ${cap:.2f} reached (spent ${tier_spent:.2f})",
        )
    return True, ""


def _record_spend(cost_usd: float, tier: str = "paid") -> None:
    normalized_tier = _normalize_tier(tier)
    budget = _load_budget()
    today = _today_str()
    if budget.get("date") != today:
        budget = {
            "date": today,
            "spent_usd": 0.0,
            "spent_by_tier": {"free": 0.0, "paid": 0.0},
        }

    spent_by_tier = budget.get("spent_by_tier") or {"free": 0.0, "paid": 0.0}
    spent_by_tier[normalized_tier] = round(
        float(spent_by_tier.get(normalized_tier, 0.0) or 0.0) + cost_usd,
        6,
    )

    budget["spent_usd"] = round(budget["spent_usd"] + cost_usd, 6)
    budget["spent_by_tier"] = spent_by_tier
    _save_budget(budget)


def _append_cost_log(entry: dict[str, Any]) -> None:
    _COST_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _COST_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_cost_log_tail(limit: int = 20) -> list[dict[str, Any]]:
    """Read the latest N cost log records from append-only jsonl file."""
    if limit <= 0:
        return []
    if not _COST_LOG_FILE.exists():
        return []

    rows: list[dict[str, Any]] = []
    with _COST_LOG_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def get_routing_diagnostics() -> dict[str, Any]:
    """Expose current Stage C routing configuration for diagnostics endpoints."""
    settings.reload()
    budget = _load_budget()
    spent_by_tier = budget.get("spent_by_tier") or {"free": 0.0, "paid": 0.0}
    free_models = [
        item.strip()
        for item in os.environ.get(
            "STAGE_C_FREE_MODELS", ",".join(_DEFAULT_FREE_MODELS)
        ).split(",")
        if item.strip()
    ]
    backup_models = [
        item.strip()
        for item in os.environ.get(
            "STAGE_C_BACKUP_MODELS", ",".join(_DEFAULT_BACKUP_MODELS)
        ).split(",")
        if item.strip()
    ]
    return {
        "provider_preference": os.environ.get("STAGE_C_PROVIDER", "openrouter"),
        "default_model": os.environ.get(
            "STAGE_C_DEFAULT_MODEL", _OPENROUTER_DEFAULT_MODEL
        ),
        "escalation_model": os.environ.get(
            "STAGE_C_ESCALATION_MODEL", "anthropic/claude-sonnet-4"
        ),
        "openrouter_base_url": settings.OPENROUTER_BASE_URL,
        "free_models": free_models,
        "backup_models": backup_models,
        "free_conf_threshold": float(
            os.environ.get(
                "STAGE_C_FREE_CONF_THRESHOLD", str(_DEFAULT_FREE_CONF_THRESHOLD)
            )
        ),
        "daily_budget_caps_usd": {
            "free": _tier_cap_usd("free"),
            "paid": _tier_cap_usd("paid"),
            "legacy_total": float(
                os.environ.get("STAGE_C_DAILY_USD_CAP", str(_DEFAULT_DAILY_USD_CAP))
            ),
        },
        "daily_budget_state": {
            "date": budget.get("date", ""),
            "spent_usd": float(budget.get("spent_usd", 0.0) or 0.0),
            "spent_by_tier": {
                "free": float(spent_by_tier.get("free", 0.0) or 0.0),
                "paid": float(spent_by_tier.get("paid", 0.0) or 0.0),
            },
        },
        "cost_log_file": str(_COST_LOG_FILE),
    }


def _estimate_cost_usd(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    lowered = (model or "").lower()
    if "haiku" in lowered:
        input_price = 0.25 / 1_000_000
        output_price = 1.25 / 1_000_000
    elif "opus" in lowered:
        input_price = 15.0 / 1_000_000
        output_price = 75.0 / 1_000_000
    elif "gpt-4.1-nano" in lowered:
        input_price = 0.10 / 1_000_000
        output_price = 0.40 / 1_000_000
    elif "gemini-3.1-flash-lite" in lowered:
        input_price = 0.25 / 1_000_000
        output_price = 1.50 / 1_000_000
    elif "gemini" in lowered:
        input_price = 0.075 / 1_000_000
        output_price = 0.30 / 1_000_000
    elif "deepseek" in lowered:
        input_price = 0.27 / 1_000_000
        output_price = 1.10 / 1_000_000
    elif "qwen" in lowered:
        input_price = 1.5 / 1_000_000
        output_price = 2.0 / 1_000_000
    else:
        # sonnet / generic mid-tier
        input_price = 3.0 / 1_000_000
        output_price = 15.0 / 1_000_000
    return round(prompt_tokens * input_price + completion_tokens * output_price, 6)


def _normalize_model_for_provider(model: str | None, provider: str) -> str:
    selected = (model or os.environ.get("STAGE_C_DEFAULT_MODEL", "")).strip()
    if not selected:
        return _OPENROUTER_DEFAULT_MODEL if provider == "openrouter" else _DEFAULT_MODEL

    if provider == "openrouter":
        if "/" in selected:
            return selected
        if selected.lower().startswith("claude"):
            return f"anthropic/{selected}"
        return selected

    # anthropic provider
    if selected.startswith("anthropic/"):
        selected = selected.split("/", 1)[1]
    resolved = _ANTHROPIC_MODEL_ALIASES.get(selected, selected)
    # Emergency fallback: if the primary OpenRouter gateway is unreachable and we
    # fall back to the native Anthropic provider for a non-Claude model
    # (e.g. google/gemini-*), the bare model id would 404 on Anthropic. Map it to
    # a vision-capable Claude model so image repair still succeeds in an outage.
    if not resolved.lower().startswith("claude"):
        return os.environ.get(
            "STAGE_C_ANTHROPIC_FALLBACK_MODEL", _ANTHROPIC_EMERGENCY_FALLBACK_MODEL
        )
    return resolved


def _provider_order(preferred_provider: str | None = None) -> list[str]:
    preferred = (
        (preferred_provider or os.environ.get("STAGE_C_PROVIDER", "openrouter"))
        .strip()
        .lower()
    )
    if preferred == "anthropic":
        return ["anthropic", "openrouter"]
    return ["openrouter", "anthropic"]


def _models_from_env(env_name: str, defaults: list[str]) -> list[str]:
    raw = os.environ.get(env_name, ",".join(defaults))
    models = [item.strip() for item in raw.split(",") if item.strip()]
    return models or list(defaults)


def _dedupe_model_plan(plan: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for model, tier in plan:
        key = model.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append((model, tier))
    return deduped


def _http_timeout_seconds() -> float:
    """Per-request LLM HTTP timeout (HR-07-02). Falls back to a conservative 60s
    if the setting is missing or unparseable so a provider call can never inherit
    the SDK's ~600s default and outlive the Celery soft_time_limit."""
    try:
        value = float(getattr(settings, "LLM_HTTP_TIMEOUT_SECONDS", 60) or 60)
    except (TypeError, ValueError):
        return 60.0
    return value if value > 0 else 60.0


def _build_provider(name: str) -> tuple[LLMProvider, str] | tuple[None, str]:
    settings.reload()
    timeout = _http_timeout_seconds()
    if name == "openrouter":
        key = (
            os.environ.get("BWCACC_OPENROUTER_API_KEY", "")
            or settings.BWCACC_OPENROUTER_API_KEY
            or os.environ.get("OPENROUTER_API_KEY", "")
            or settings.OPENROUTER_API_KEY
        )
        if not key:
            return None, "BWCACC_OPENROUTER_API_KEY/OPENROUTER_API_KEY not set"
        return OpenRouterProvider(
            api_key=key, base_url=settings.OPENROUTER_BASE_URL, timeout=timeout
        ), ""

    key = os.environ.get("ANTHROPIC_API_KEY", "") or settings.ANTHROPIC_API_KEY
    if not key:
        return None, "ANTHROPIC_API_KEY not set"
    return AnthropicProvider(api_key=key, timeout=timeout), ""


def _strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


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


def _normalize_repaired_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("/", "-")
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", text)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return text


def _is_bad_repaired_invoice_no(value: str) -> bool:
    cand = re.sub(r"\s+", "", str(value or "")).upper()
    if not cand:
        return True
    if cand.startswith(("PO", "P/O", "SO", "REF", "RFQ")):
        return True
    if re.fullmatch(r"\d{1,4}/\d{1,4}", cand):
        return True
    return False


def _merge_improvements(
    *,
    repaired: dict[str, Any],
    current_fields: dict[str, Any],
    current_confidence: dict[str, Any],
    raw_text: str,
    image_used: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    improved_fields: dict[str, Any] = {}
    improved_confidence: dict[str, Any] = {}
    base_confidence = 0.85

    warnings = current_fields.get("field_validation_warnings") or []
    warning_fields: set[str] = set()
    if isinstance(warnings, list):
        for item in warnings:
            text = str(item)
            if ":" in text:
                warning_fields.add(text.split(":", 1)[0])

    for field_name, new_value in repaired.items():
        if field_name not in current_fields:
            continue
        if not new_value:
            continue

        candidate_value = str(new_value)
        if field_name == "invoice_date":
            candidate_value = _normalize_repaired_date(candidate_value)
            if not candidate_value:
                continue
        if field_name == "invoice_number" and _is_bad_repaired_invoice_no(
            candidate_value
        ):
            continue

        is_valid, _ = validate_field(field_name, candidate_value, raw_text)
        if not is_valid:
            continue

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

        if accept and field_name in {
            "net_amount",
            "vat_amount",
            "total_amount",
            "wht_amount",
            "amount_paid",
        }:
            # When the repair came from a vision (image) call, the image is
            # authoritative — the whole purpose is to correct amounts that OCR
            # mangled, so do not require the value to appear in the OCR text.
            # Hallucination risk is bounded by the arithmetic reconciliation
            # confidence-capping applied below.
            if not image_used and not _value_in_ocr(candidate_value, raw_text):
                accept = False

        if accept:
            improved_fields[field_name] = candidate_value
            improved_confidence[field_name] = base_confidence

    # Money fields earn high confidence only when the repaired amounts reconcile
    # arithmetically. Otherwise cap them so a confident-but-wrong repair cannot
    # produce a green band.
    money_fields = {
        "net_amount",
        "vat_amount",
        "total_amount",
        "wht_amount",
        "amount_paid",
    }
    if improved_fields.keys() & money_fields:
        merged = {**current_fields, **improved_fields}
        recon = reconcile_amounts(merged)
        checks = recon.get("checks", {})
        for field_name in improved_fields.keys() & money_fields:
            if (
                field_name in ("net_amount", "total_amount")
                and checks.get("total") == "fail"
            ):
                improved_confidence[field_name] = min(
                    improved_confidence[field_name], 0.45
                )
            elif field_name == "vat_amount" and checks.get("vat") == "fail":
                improved_confidence[field_name] = min(
                    improved_confidence[field_name], 0.40
                )
            elif field_name == "wht_amount" and checks.get("wht") == "fail":
                improved_confidence[field_name] = min(
                    improved_confidence[field_name], 0.40
                )
            elif not recon.get("reconciled"):
                improved_confidence[field_name] = min(
                    improved_confidence[field_name], 0.50
                )

    return improved_fields, improved_confidence


def _build_stage_c_user_prompt(
    *,
    raw_text: str,
    current_fields: dict[str, Any],
    weak_fields: list[str] | None,
    has_image: bool = False,
) -> str:
    display_fields = {
        k: v
        for k, v in current_fields.items()
        if k not in ("source_text", "cross_field_error")
    }
    weak = [item for item in (weak_fields or []) if item in display_fields]
    target_section = (
        "\n\n=== TARGET FIELDS (ONLY FIX THESE) ===\n" + ", ".join(weak) if weak else ""
    )
    if has_image:
        # Vision input: the model reads the document image directly.
        # OCR text is provided as fallback reference only — the image is authoritative.
        return (
            "An image of the source accounting document is attached. "
            "Read the image and correct the extracted fields below. "
            "Trust the image when it disagrees with the OCR text.\n\n"
            "=== CURRENT EXTRACTED FIELDS ===\n"
            + json.dumps(display_fields, ensure_ascii=False, indent=2)
            + target_section
            + "\n\n=== OCR REFERENCE TEXT (may contain errors) ===\n"
            + raw_text[:2000]
            + "\n\nReturn corrected fields as JSON only."
        )
    return (
        "=== RAW OCR TEXT ===\n"
        + raw_text[:4000]
        + "\n\n=== CURRENT EXTRACTED FIELDS ===\n"
        + json.dumps(display_fields, ensure_ascii=False, indent=2)
        + target_section
        + "\n\nPlease return corrected/completed fields as JSON."
    )


def _free_models() -> list[str]:
    raw = os.environ.get("STAGE_C_FREE_MODELS", ",".join(_DEFAULT_FREE_MODELS))
    models = [item.strip() for item in raw.split(",") if item.strip()]
    return models or list(_DEFAULT_FREE_MODELS)


def _image_input_enabled() -> bool:
    """Whether Stage C should send the source document image to the LLM (Patch B)."""
    return os.environ.get("STAGE_C_USE_IMAGE_INPUT", "true").strip().lower() == "true"


def _weak_fields_by_threshold(
    confidence: dict[str, Any],
    threshold: float,
) -> list[str]:
    weak: list[str] = []
    critical = _critical_fields()
    for key, value in confidence.items():
        if key in {"source_text"}:
            continue
        if key not in critical:
            continue
        if not isinstance(value, (int, float)):
            continue
        if float(value) < threshold:
            weak.append(key)
    return weak


def call_llm_repair(
    *,
    raw_text: str,
    current_fields: dict[str, Any],
    current_confidence: dict[str, Any],
    system_prompt: str,
    model: str | None = None,
    provider: str | None = None,
    weak_fields: list[str] | None = None,
    tier: str = "paid",
    image_path: str | None = None,
) -> dict[str, Any]:
    """Route Stage C repair through configured providers with fallback."""
    load_llm_keys()

    use_image = bool(image_path) and _image_input_enabled()
    image_paths = [image_path] if (use_image and image_path) else None

    user_prompt = _build_stage_c_user_prompt(
        raw_text=raw_text,
        current_fields=current_fields,
        weak_fields=weak_fields,
        has_image=use_image,
    )

    normalized_tier = _normalize_tier(tier)
    estimated = _estimate_cost_usd(800, 150, model or _DEFAULT_MODEL)
    allowed, reason = _budget_allows(estimated, tier=normalized_tier)
    if not allowed:
        _append_cost_log(
            {
                "ts": time.time(),
                "date": _today_str(),
                "tier": normalized_tier,
                "provider": "",
                "model": model or _DEFAULT_MODEL,
                "input_tokens": 0,
                "output_tokens": 0,
                "triggered_by_fields": weak_fields or [],
                "estimated_cost_usd": estimated,
                "actual_cost_usd": 0.0,
                "skipped": True,
                "skip_reason": reason,
            }
        )
        return {"fields": {}, "confidence": {}, "skipped": True, "skip_reason": reason}

    errors: list[str] = []
    attempted: list[tuple[str, str]] = []
    for provider_name in _provider_order(provider):
        provider_client, provider_error = _build_provider(provider_name)
        if provider_client is None:
            errors.append(f"{provider_name}: {provider_error}")
            continue

        selected_model = _normalize_model_for_provider(model, provider_name)
        attempted.append((provider_name, selected_model))
        try:
            response = provider_client.call(
                model=selected_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_paths=image_paths,
            )
            content = _strip_code_fence(response.text)
            repaired = json.loads(content)

            actual_cost = _estimate_cost_usd(
                response.input_tokens,
                response.output_tokens,
                selected_model,
            )
            _record_spend(actual_cost, tier=normalized_tier)
            _append_cost_log(
                {
                    "ts": time.time(),
                    "date": _today_str(),
                    "tier": normalized_tier,
                    "provider": provider_name,
                    "model": selected_model,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "triggered_by_fields": weak_fields or [],
                    "estimated_cost_usd": estimated,
                    "actual_cost_usd": actual_cost,
                    "skipped": False,
                    "skip_reason": "",
                }
            )

            improved_fields, improved_confidence = _merge_improvements(
                repaired=repaired,
                current_fields=current_fields,
                current_confidence=current_confidence,
                raw_text=raw_text,
                image_used=use_image,
            )
            return {
                "fields": improved_fields,
                "confidence": improved_confidence,
                "skipped": False,
                "skip_reason": "",
                "provider": provider_name,
                "model": selected_model,
            }
        except Exception as exc:  # pragma: no cover - provider fallback safety
            errors.append(f"{provider_name}: {exc}")

    fallback_model = (
        attempted[0][1]
        if attempted
        else _normalize_model_for_provider(model, "openrouter")
    )
    _append_cost_log(
        {
            "ts": time.time(),
            "date": _today_str(),
            "tier": normalized_tier,
            "provider": attempted[0][0] if attempted else "",
            "model": fallback_model,
            "input_tokens": 0,
            "output_tokens": 0,
            "triggered_by_fields": weak_fields or [],
            "estimated_cost_usd": estimated,
            "actual_cost_usd": 0.0,
            "skipped": True,
            "skip_reason": "LLM provider failed: " + " | ".join(errors),
        }
    )
    return {
        "fields": {},
        "confidence": {},
        "skipped": True,
        "skip_reason": "LLM provider failed: " + " | ".join(errors),
        "provider": attempted[0][0] if attempted else "",
        "model": fallback_model,
    }


def cascade_repair(
    *,
    raw_text: str,
    current_fields: dict[str, Any],
    current_confidence: dict[str, Any],
    system_prompt: str,
    provider: str | None = None,
    image_path: str | None = None,
) -> dict[str, Any]:
    """Run per-field cascade: free models first, then paid (haiku -> sonnet)."""
    threshold = float(
        os.environ.get("STAGE_C_FREE_CONF_THRESHOLD", str(_DEFAULT_FREE_CONF_THRESHOLD))
    )
    working_fields = dict(current_fields)
    working_conf = dict(current_confidence)
    merged_fields: dict[str, Any] = {}
    merged_confidence: dict[str, Any] = {}
    attempts: list[dict[str, Any]] = []

    weak_fields = _weak_fields_by_threshold(working_conf, threshold)
    if not weak_fields:
        return {
            "fields": {},
            "confidence": {},
            "attempts": [],
            "skipped": False,
            "skip_reason": "",
            "unresolved_fields": [],
        }

    preferred_provider = provider or os.environ.get("STAGE_C_PROVIDER", "openrouter")
    default_paid = os.environ.get("STAGE_C_DEFAULT_MODEL", _OPENROUTER_DEFAULT_MODEL)
    escalation_paid = os.environ.get(
        "STAGE_C_ESCALATION_MODEL", "anthropic/claude-sonnet-4"
    )

    # D9 / Patch B: the vision and text cascades share the same model plan —
    # free gemini-2.5-flash-lite first, then the paid default, then escalation.
    # When an image is available it is attached to every attempt (handled inside
    # call_llm_repair). The provider stays OpenRouter as primary; the native
    # Anthropic provider is an emergency fallback only (see _provider_order and
    # _normalize_model_for_provider), keeping cost ~$0.0006/doc.
    model_plan = [(model, "free") for model in _free_models()]
    model_plan.append((default_paid, "paid"))
    model_plan.extend(
        (model, "paid") for model in _models_from_env("STAGE_C_BACKUP_MODELS", _DEFAULT_BACKUP_MODELS)
    )
    if escalation_paid != default_paid:
        model_plan.append((escalation_paid, "paid"))
    model_plan = _dedupe_model_plan(model_plan)

    for model_name, tier in model_plan:
        if not weak_fields:
            break

        repair = call_llm_repair(
            raw_text=raw_text,
            current_fields=working_fields,
            current_confidence=working_conf,
            system_prompt=system_prompt,
            model=model_name,
            provider=preferred_provider,
            weak_fields=weak_fields,
            tier=tier,
            image_path=image_path,
        )
        attempts.append(
            {
                "tier": tier,
                "provider": repair.get("provider", preferred_provider),
                "model": repair.get("model", model_name),
                "skipped": bool(repair.get("skipped", False)),
                "skip_reason": repair.get("skip_reason", ""),
            }
        )

        if repair.get("skipped"):
            continue

        updated_fields = repair.get("fields") or {}
        updated_conf = repair.get("confidence") or {}
        if not updated_fields:
            continue

        working_fields.update(updated_fields)
        working_conf.update(updated_conf)
        merged_fields.update(updated_fields)
        merged_confidence.update(updated_conf)

        weak_fields = _weak_fields_by_threshold(working_conf, threshold)

    return {
        "fields": merged_fields,
        "confidence": merged_confidence,
        "attempts": attempts,
        "skipped": False,
        "skip_reason": "",
        "unresolved_fields": weak_fields,
    }
