"""HR-07-02: explicit provider HTTP timeout wiring.

The primary cause of the Processing SoftTimeLimitExceeded regression was that the
provider SDK calls had no explicit timeout (SDK default ~600s > the task soft
limit), so a single stalled call was fatal. These tests pin the timeout down the
whole path: settings -> llm_router._build_provider -> OpenRouterProvider ->
openai client (constructor + per request).
"""

from __future__ import annotations

import sys
import types

from config.settings import settings
from src.backend.ml import llm_router


def _install_fake_openai(monkeypatch, captured: dict) -> None:
    class _FakeMessage:
        content = "{}"

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeUsage:
        prompt_tokens = 1
        completion_tokens = 1

    class _FakeResponse:
        choices = [_FakeChoice()]
        usage = _FakeUsage()

    class _FakeCompletions:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return _FakeResponse()

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.chat = _FakeChat()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_openrouter_provider_passes_timeout_to_client_and_request(monkeypatch):
    captured: dict = {}
    _install_fake_openai(monkeypatch, captured)

    from src.backend.ml.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider(api_key="k", timeout=42.0, max_retries=1)
    assert captured["init"]["timeout"] == 42.0
    assert captured["init"]["max_retries"] == 1

    provider.call(model="m", system_prompt="s", user_prompt="u")
    assert captured["create"]["timeout"] == 42.0


def test_build_provider_uses_configured_http_timeout(monkeypatch):
    monkeypatch.setenv("LLM_HTTP_TIMEOUT_SECONDS", "33")
    monkeypatch.setenv("BWCACC_OPENROUTER_API_KEY", "test-key")

    captured: dict = {}

    def _fake_provider_ctor(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(llm_router, "OpenRouterProvider", _fake_provider_ctor)

    provider, error = llm_router._build_provider("openrouter")

    assert provider is not None
    assert error == ""
    assert captured["timeout"] == 33.0


def test_http_timeout_falls_back_to_60_when_unset_or_bad(monkeypatch):
    monkeypatch.setattr(settings, "LLM_HTTP_TIMEOUT_SECONDS", 0, raising=False)
    assert llm_router._http_timeout_seconds() == 60.0
    monkeypatch.setattr(settings, "LLM_HTTP_TIMEOUT_SECONDS", "not-a-number", raising=False)
    assert llm_router._http_timeout_seconds() == 60.0
    monkeypatch.setattr(settings, "LLM_HTTP_TIMEOUT_SECONDS", 90, raising=False)
    assert llm_router._http_timeout_seconds() == 90.0
