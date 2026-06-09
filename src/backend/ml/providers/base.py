"""Base interfaces for pluggable LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderResponse:
    """Normalized provider response payload."""

    text: str
    input_tokens: int
    output_tokens: int
    raw: Any


class LLMProvider(ABC):
    """Contract for LLM provider clients used by Stage C router."""

    @abstractmethod
    def call(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[str] | None = None,
    ) -> ProviderResponse:
        """Execute one provider request and return normalized output.

        When ``image_paths`` is provided, the implementation must attach the
        images as inline multi-modal content alongside ``user_prompt``.
        """
