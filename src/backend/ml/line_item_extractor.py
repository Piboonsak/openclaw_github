"""Line-item extraction stage (Epic 9 / W5-EXPORT-LINEITEM-REALDATA-04).

Runs one vision-LLM call to extract invoice line items, reusing the Stage-C
provider selection, per-provider model resolution and cost logging from
`llm_router`. Best-effort / non-blocking by contract: on any failure the caller
must treat the result as "no line items" and must NOT fail the pipeline — header
extraction stands on its own.
"""

from __future__ import annotations

import time
from typing import Any

from src.backend.ml import llm_router
from src.backend.ml.line_item_prompts import (
    DEFAULT_MODEL_SET,
    build_system_prompt,
    build_user_prompt,
    parse_line_item_response,
)

_DEFAULT_LINE_ITEM_MODEL = (
    DEFAULT_MODEL_SET[0] if DEFAULT_MODEL_SET else "google/gemini-2.5-flash-lite"
)


def extract_line_items(
    *,
    image_path: str,
    ocr_text: str,
    metadata: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    """Extract invoice line items via a vision LLM with provider fallback.

    Returns the parsed ``{document_total, currency, line_items[], notes[]}`` dict
    (plus ``_provider``/``_model``). Raises ``RuntimeError`` only if every
    provider fails — callers wrap this and swallow the exception.
    """
    llm_router.load_llm_keys()
    chosen_model = model or _DEFAULT_LINE_ITEM_MODEL
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(metadata, ocr_text or "")
    use_image = bool(image_path) and llm_router._image_input_enabled()
    image_paths = [image_path] if (use_image and image_path) else None

    errors: list[str] = []
    for provider_name in llm_router._provider_order():
        provider_client, provider_error = llm_router._build_provider(provider_name)
        if provider_client is None:
            errors.append(f"{provider_name}: {provider_error}")
            continue
        selected_model = llm_router._normalize_model_for_provider(
            chosen_model, provider_name
        )
        try:
            response = provider_client.call(
                model=selected_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_paths=image_paths,
            )
            parsed = parse_line_item_response(response.text)
            _log_cost(provider_name, selected_model, response)
            parsed["_provider"] = provider_name
            parsed["_model"] = selected_model
            return parsed
        except Exception as exc:  # pragma: no cover - provider fallback safety
            errors.append(f"{provider_name}: {exc}")

    raise RuntimeError(
        "line-item extraction failed: " + (" | ".join(errors) or "no provider available")
    )


def _log_cost(provider_name: str, model: str, response: Any) -> None:
    try:
        cost = llm_router._estimate_cost_usd(
            response.input_tokens, response.output_tokens, model
        )
        llm_router._append_cost_log(
            {
                "ts": time.time(),
                "date": llm_router._today_str(),
                "tier": "line_item",
                "provider": provider_name,
                "model": model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "triggered_by_fields": ["line_items"],
                "estimated_cost_usd": cost,
                "actual_cost_usd": cost,
                "skipped": False,
                "skip_reason": "",
            }
        )
    except Exception:
        pass
