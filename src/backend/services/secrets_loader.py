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
# When the key file groups a credential under an INI-style section header
# (e.g. ``[ANTHROPIC_API_KEY]`` with named sub-entries), prefer the sub-entry
# whose name matches this project.
_ANTHROPIC_PREFERRED_SUBKEY = "AI-pre-accounting-copilot"


def _resolve_path(env_name: str, default_path: Path) -> Path:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return Path(configured)
    return default_path


def _read_key_value_file(
    path: Path, key_name: str, preferred_subkey: str | None = None
) -> str:
    """Read ``key_name`` from a simple ``KEY=value`` credential file.

    Supports two layouts:

    1. Flat ``KEY="value"`` lines (matched directly by ``key_name``).
    2. INI-style sections where the credential is grouped under a
       ``[KEY_NAME]`` header with one or more named sub-entries that use
       either ``=`` or ``:`` as the delimiter, e.g.::

           [ANTHROPIC_API_KEY]
           NongKung-API-Key="sk-ant-..."
           AI-pre-accounting-copilot:"sk-ant-..."

       A blank line ends the section. When matching a section, the entry whose
       name equals ``preferred_subkey`` is returned if present, otherwise the
       first entry in the section.
    """
    if not path.exists() or not path.is_file():
        return ""

    direct = ""
    section: str | None = None
    section_values: dict[str, str] = {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    section = None
                    continue
                if line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip()
                    continue

                if "=" in line:
                    name, value = line.split("=", 1)
                elif ":" in line:
                    name, value = line.split(":", 1)
                else:
                    continue

                name = name.strip()
                value = value.strip().strip('"').strip("'")

                if name == key_name and not direct:
                    direct = value
                if section == key_name:
                    section_values.setdefault(name, value)
    except OSError:
        return ""

    if direct:
        return direct
    if section_values:
        if preferred_subkey and preferred_subkey in section_values:
            return section_values[preferred_subkey]
        return next(iter(section_values.values()))
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
    anthropic_value = _read_key_value_file(
        keys_path, "ANTHROPIC_API_KEY", preferred_subkey=_ANTHROPIC_PREFERRED_SUBKEY
    )
    return _load_env_key("ANTHROPIC_API_KEY", anthropic_value)


def load_llm_keys() -> dict[str, bool]:
    """Load Anthropic, OpenAI, and OpenRouter keys from local files."""
    anthropic_path = _resolve_path("LLM_KEYS_FILE", DEFAULT_ANTHROPIC_KEYS_FILE)
    openai_path = _resolve_path("OPENAI_KEY_FILE", DEFAULT_OPENAI_KEY_FILE)

    anthropic_value = _read_key_value_file(
        anthropic_path,
        "ANTHROPIC_API_KEY",
        preferred_subkey=_ANTHROPIC_PREFERRED_SUBKEY,
    )
    openrouter_value = _read_key_value_file(anthropic_path, "OPENROUTER_API_KEY")
    openai_value = _read_openai_key_file(openai_path)

    return {
        "ANTHROPIC_API_KEY": _load_env_key("ANTHROPIC_API_KEY", anthropic_value),
        "OPENAI_API_KEY": _load_env_key("OPENAI_API_KEY", openai_value),
        "OPENROUTER_API_KEY": _load_env_key("OPENROUTER_API_KEY", openrouter_value),
    }
