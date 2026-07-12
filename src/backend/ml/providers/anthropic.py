"""Anthropic provider adapter for Stage C repair."""

from __future__ import annotations

from src.backend.ml.image_loader import encode_image_base64, load_images_for_vision

from .base import LLMProvider, ProviderResponse


class AnthropicProvider(LLMProvider):
    """Anthropic SDK-backed provider."""

    def __init__(self, api_key: str, timeout: float | None = None) -> None:
        self._api_key = api_key
        # HR-07-02: bound the emergency Anthropic fallback call the same way as
        # the primary OpenRouter path so a stalled request cannot ride the task
        # to Celery's soft_time_limit.
        self._timeout = timeout

    def call(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
    ) -> ProviderResponse:
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("anthropic package not installed") from exc

        if image_paths:
            content: list[dict] = []
            for src in image_paths:
                for img_bytes, mime in load_images_for_vision(src):
                    content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": encode_image_base64(img_bytes),
                            },
                        }
                    )
            content.append({"type": "text", "text": user_prompt})
            user_content: object = content
        else:
            user_content = user_prompt

        client_kwargs: dict = {"api_key": self._api_key, "max_retries": 1}
        if self._timeout is not None:
            client_kwargs["timeout"] = self._timeout
        client = Anthropic(**client_kwargs)
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        content = ""
        if getattr(response, "content", None):
            first = response.content[0]
            content = getattr(first, "text", "") or ""

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return ProviderResponse(
            text=content.strip(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=response,
        )
