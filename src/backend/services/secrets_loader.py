"""Helpers for loading local LLM API keys into environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)
DEFAULT_ANTHROPIC_KEYS_FILE = Path(r"D:\key\ALL-Openclaw-keys.txt")
DEFAULT_OPENAI_KEY_FILE = Path(
    r"D:\key\API Key for OpenClawAA01 access to OpenAI[ChatGPT].txt"
)


def _resolve_path(env_name: str, default_path: Path) -> Path:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    return default_path


def _read_key_value_file(path: Path, key_name: str) -> str:
    if not path.exists() or not path.is_file():
        return ""

    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() != key_name:
                    continue
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""

    return ""


def _read_openai_key_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""

    encodings = ("utf-8", "utf-8-sig", "cp874", "latin-1")
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding) as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line.lower().startswith("key:"):
                        continue
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
        except (OSError, UnicodeDecodeError):
            continue

    return ""


def _load_env_key(target_name: str, value: str) -> bool:
    if os.getenv(target_name, "").strip():
        LOGGER.info("%s already set in environment", target_name)
        return True
    if not value:
        LOGGER.warning("%s missing", target_name)
        return False
    os.environ[target_name] = value
    LOGGER.info("%s loaded from file", target_name)
    return True


def load_openrouter_key() -> bool:
    """Load OPENROUTER_API_KEY from local key file if env is empty."""
    keys_path = _resolve_path("LLM_KEYS_FILE", DEFAULT_ANTHROPIC_KEYS_FILE)
    openrouter_value = _read_key_value_file(keys_path, "OPENROUTER_API_KEY")
    return _load_env_key("OPENROUTER_API_KEY", openrouter_value)


def load_anthropic_key() -> bool:
    """Load ANTHROPIC_API_KEY from local key file if env is empty."""
    keys_path = _resolve_path("LLM_KEYS_FILE", DEFAULT_ANTHROPIC_KEYS_FILE)
    anthropic_value = _read_key_value_file(keys_path, "ANTHROPIC_API_KEY")
    return _load_env_key("ANTHROPIC_API_KEY", anthropic_value)


def load_llm_keys() -> dict[str, bool]:
    """Load Anthropic, OpenAI, and OpenRouter keys from local files."""
    anthropic_path = _resolve_path("LLM_KEYS_FILE", DEFAULT_ANTHROPIC_KEYS_FILE)
    openai_path = _resolve_path("OPENAI_KEY_FILE", DEFAULT_OPENAI_KEY_FILE)

    anthropic_value = _read_key_value_file(anthropic_path, "ANTHROPIC_API_KEY")
    openrouter_value = _read_key_value_file(anthropic_path, "OPENROUTER_API_KEY")
    openai_value = _read_openai_key_file(openai_path)

    return {
        "ANTHROPIC_API_KEY": _load_env_key("ANTHROPIC_API_KEY", anthropic_value),
        "OPENAI_API_KEY": _load_env_key("OPENAI_API_KEY", openai_value),
        "OPENROUTER_API_KEY": _load_env_key("OPENROUTER_API_KEY", openrouter_value),
    }
