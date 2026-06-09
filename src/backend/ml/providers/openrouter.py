"""OpenRouter provider adapter for Stage C repair."""

from __future__ import annotations

from src.backend.ml.image_loader import encode_image_data_uri, load_images_for_vision

from .base import LLMProvider, ProviderResponse


class OpenRouterProvider(LLMProvider):
    """OpenRouter client via OpenAI-compatible API."""

    def __init__(
        self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"
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

        self._client = client_cls(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/Piboonsak/ai-accounting-copilot",
                "X-Title": "AI Pre-Accounting Copilot",
            },
        )

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

        response = self._client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
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
