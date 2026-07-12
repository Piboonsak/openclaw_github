"""OpenRouter provider adapter for Stage C repair."""

from __future__ import annotations

from src.backend.ml.image_loader import encode_image_data_uri, load_images_for_vision

from .base import LLMProvider, ProviderResponse


class OpenRouterProvider(LLMProvider):
    """OpenRouter client via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float | None = None,
        max_retries: int = 1,
    ) -> None:
        try:
            openai_module = __import__("openai")
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package not installed") from exc

        client_cls = getattr(openai_module, "OpenAI", None)
        if client_cls is None:  # pragma: no cover
            raise RuntimeError(
                "openai.OpenAI client is unavailable in installed package"
            )

        # HR-07-02: an explicit per-request timeout is the primary guard against a
        # stalled OpenRouter call hanging the document task until Celery's
        # soft_time_limit fires (the SDK default is ~600s, longer than the task
        # limit). `max_retries` is kept low so a timeout is not silently retried
        # into a multiple of the budget — the Stage C cascade already provides
        # cross-model/provider fallback.
        self._timeout = timeout
        client_kwargs: dict = {
            "api_key": api_key,
            "base_url": base_url,
            "max_retries": max_retries,
            "default_headers": {
                "HTTP-Referer": "https://github.com/Piboonsak/ai-accounting-copilot",
                "X-Title": "AI Pre-Accounting Copilot",
            },
        }
        if timeout is not None:
            client_kwargs["timeout"] = timeout
        self._client = client_cls(**client_kwargs)

    def call(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
    ) -> ProviderResponse:
        if image_paths:
            content: list[dict] = [{"type": "text", "text": user_prompt}]
            for src in image_paths:
                for img_bytes, mime in load_images_for_vision(src):
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": encode_image_data_uri(img_bytes, mime)
                            },
                        }
                    )
            user_message: object = content
        else:
            user_message = user_prompt

        create_kwargs: dict = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        if self._timeout is not None:
            create_kwargs["timeout"] = self._timeout
        response = self._client.chat.completions.create(**create_kwargs)
        content = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        return ProviderResponse(
            text=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=response,
        )
