---
summary: "Use OpenRouter's unified API to access many models in OpenClaw"
read_when:
  - You want a single API key for many LLMs
  - You want to run models via OpenRouter in OpenClaw
title: "OpenRouter"
---

# OpenRouter

OpenRouter provides a **unified API** that routes requests to many models behind a single
endpoint and API key. It is OpenAI-compatible, so most OpenAI SDKs work by switching the base URL.

In OpenClaw, the source of truth for model selection is `agents.defaults.model.primary`
(or `agents.list[].model.primary` for per-agent overrides).

## CLI setup

```bash
openclaw onboard --auth-choice apiKey --token-provider openrouter --token "$OPENROUTER_API_KEY"
```

## Config snippet

```json5
{
  env: { OPENROUTER_API_KEY: "sk-or-..." },
  agents: {
    defaults: {
      model: { primary: "openrouter/anthropic/claude-sonnet-4-6" },
    },
  },
}
```

## Notes

- Model refs are `openrouter/<provider>/<model>`.
- OpenClaw onboarding defaults OpenRouter to `openrouter/anthropic/claude-sonnet-4-6` to avoid implicit router drift.
- `openrouter/auto` is supported as an explicit opt-in when you intentionally want OpenRouter to pick the runtime provider/model.
- For more model/provider options, see [/concepts/model-providers](/concepts/model-providers).
- OpenRouter uses a Bearer token with your API key under the hood.
