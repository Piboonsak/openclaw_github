"""Legacy per-stage settings loader (config/environments/{stage}.env).

Reviewed 2026-07-08 by Sonnet (AI review, W4 SIT upload/OCR config audit):
nothing under `src/backend/**` imports this module or `get_settings()` —
only `src/config/__init__.py` re-exports it, to no consumer. The live
backend imports `config.settings` (repo-root config/settings.py) instead,
which is populated at deploy time via `docker/.env.{stage}` through the
`env_file:` directive in `docker/docker-compose.{stage}.yml`.

Conclusion: this module currently appears unused/dead. Not deleted yet —
pending a decision from the team on whether to remove it or revive it. See
docs/requirement/phaseII/W4-SIT-E2E-COPILOT-CONFIG-SECRETS-AUDIT-HANDOFF-17.prompt.json
for the full investigation this finding is part of.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    STAGE: str = "SIT"
    DEBUG: bool = True
    DATABASE_URL: str = (
        "postgresql://postgres:postgres@localhost:5432/ai_accounting_sit"
    )

    # Storage Configuration
    STORAGE_PROVIDER: str = "minio"
    STORAGE_ENDPOINT: Optional[str] = "http://localhost:9000"
    STORAGE_BUCKET: str = "ai-accounting-sit"
    STORAGE_ACCESS_KEY: Optional[str] = "minioadmin"
    STORAGE_SECRET_KEY: Optional[str] = "minioadmin"

    # OCR Settings
    OCR_SERVICE: str = "tesseract"
    TESSERACT_CMD: Optional[str] = "tesseract"

    # LLM Settings
    LLM_PROVIDER: str = "anthropic"
    LLM_MODEL: str = "claude-3-5-haiku-20241022"
    STAGE_C_FREE_MODELS: str = "google/gemini-2.5-flash-lite,openai/gpt-4.1-nano"
    STAGE_C_FREE_CONF_THRESHOLD: float = 0.70
    STAGE_C_FREE_DAILY_USD_CAP: float = 1.0
    STAGE_C_PAID_DAILY_USD_CAP: float = 2.0
    MAX_TOKENS_PER_INVOICE: int = 1500

    # Thresholds
    CONFIDENCE_THRESHOLD: float = 0.85
    ALLOWED_SCOPES: str = "all"

    # Select environment config based on STAGE environment variable
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"../../config/environments/{os.getenv('STAGE', 'SIT').lower()}.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Load settings for the selected STAGE."""
    # Ensure STAGE is set normalized as uppercase (SIT, UAT, PROD)
    stage = os.getenv("STAGE", "SIT").upper()
    os.environ["STAGE"] = stage
    return Settings()


p = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"../../config/environments/{os.getenv('STAGE', 'SIT').lower()}.env",
)
