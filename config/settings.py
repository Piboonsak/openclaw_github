"""Configuration settings."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser() if value else default


def _csv_from_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.APP_ENV = os.getenv("APP_ENV", "development")
        self.PUBLIC_ENV = os.getenv("PUBLIC_ENV", self.APP_ENV)

        # Database (Phase II)
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql://copilot:dev_password@localhost:5432/ai_accounting_sit",
        )
        self.DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
        self.DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.RULES_ROOT = _path_from_env("RULES_ROOT", REPO_ROOT / "rules")
        self.CACHE_ROOT = _path_from_env(
            "CACHE_ROOT", REPO_ROOT / "src" / "backend" / "ml" / "cache"
        )
        self.UPLOAD_ROOT = _path_from_env("UPLOAD_ROOT", self.CACHE_ROOT / "uploads")
        self.EXPORT_ROOT = _path_from_env("EXPORT_ROOT", self.CACHE_ROOT / "exports")
        self.STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "minio")
        self.MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
        self.MINIO_BUCKET = os.getenv("MINIO_BUCKET", "ai-accounting-sit")
        self.MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.MINIO_TIMEOUT_SECONDS = int(os.getenv("MINIO_TIMEOUT_SECONDS", "5"))
        self.STORAGE_LOCAL_ROOT = _path_from_env(
            "STORAGE_LOCAL_ROOT", self.CACHE_ROOT / "object_store"
        )
        self.STORAGE_DEFAULT_TENANT_ID = os.getenv(
            "STORAGE_DEFAULT_TENANT_ID", "default-tenant"
        )
        self.STORAGE_PRESIGN_EXPIRE_SECONDS = int(
            os.getenv("STORAGE_PRESIGN_EXPIRE_SECONDS", "3600")
        )
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.REDIS_TIMEOUT_SECONDS = int(os.getenv("REDIS_TIMEOUT_SECONDS", "5"))
        self.CORS_ORIGINS = _csv_from_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
        )
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(
            os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.BWCACC_OPENROUTER_API_KEY = os.getenv("BWCACC_OPENROUTER_API_KEY", "")
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        self.OPENROUTER_BASE_URL = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.STAGE_C_PROVIDER = os.getenv("STAGE_C_PROVIDER", "openrouter")
        # Patch B: default to vision-capable model so Stage C cascade can send
        # the source image alongside OCR text. Override via STAGE_C_DEFAULT_MODEL.
        self.STAGE_C_DEFAULT_MODEL = os.getenv(
            "STAGE_C_DEFAULT_MODEL", "google/gemini-2.5-flash"
        )
        self.STAGE_C_BACKUP_MODELS = os.getenv(
            "STAGE_C_BACKUP_MODELS",
            "openai/gpt-4.1-nano,google/gemini-3.1-flash-lite",
        )
        self.STAGE_C_ESCALATION_MODEL = os.getenv(
            "STAGE_C_ESCALATION_MODEL", "anthropic/claude-sonnet-4"
        )
        # Patch B: only vision-capable models in the free/cheap tier.
        # gpt-4.1-nano removed (not verified for vision on the empirical 10-doc probe).
        self.STAGE_C_FREE_MODELS = os.getenv(
            "STAGE_C_FREE_MODELS",
            "google/gemini-2.5-flash-lite",
        )
        self.STAGE_C_FREE_CONF_THRESHOLD = float(
            os.getenv("STAGE_C_FREE_CONF_THRESHOLD", "0.70")
        )
        self.STAGE_C_FREE_DAILY_USD_CAP = float(
            os.getenv("STAGE_C_FREE_DAILY_USD_CAP", "1.0")
        )
        self.STAGE_C_PAID_DAILY_USD_CAP = float(
            os.getenv("STAGE_C_PAID_DAILY_USD_CAP", "2.0")
        )
        self.OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")
        self.DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "th_TH")
        # Patch B: Stage C cascade sends source image to the LLM by default.
        self.STAGE_C_USE_IMAGE_INPUT = (
            os.getenv("STAGE_C_USE_IMAGE_INPUT", "true").strip().lower() == "true"
        )
        # HR-07-02: bound provider/stage latency so one hung LLM call cannot ride
        # the document task all the way to Celery's soft_time_limit and kill the
        # whole (potentially multi-document) batch with SoftTimeLimitExceeded.
        #   * LLM_HTTP_TIMEOUT_SECONDS — per HTTP request to any LLM provider.
        #     The openai/anthropic SDKs default to ~600s, longer than the task
        #     soft limit, so without this a single stalled call is fatal.
        #   * STAGE_C_STAGE_TIMEOUT_SECONDS — wall-clock cap for the whole Stage C
        #     cascade (multiple provider attempts). Header keeps whatever it has.
        #   * LINE_ITEM_STAGE_TIMEOUT_SECONDS — wall-clock cap for the OPTIONAL
        #     line-item stage; on timeout the document still reaches Review Scan
        #     with empty/pending line items (non-blocking by contract).
        self.LLM_HTTP_TIMEOUT_SECONDS = float(
            os.getenv("LLM_HTTP_TIMEOUT_SECONDS", "60")
        )
        self.STAGE_C_STAGE_TIMEOUT_SECONDS = float(
            os.getenv("STAGE_C_STAGE_TIMEOUT_SECONDS", "240")
        )
        self.LINE_ITEM_STAGE_TIMEOUT_SECONDS = float(
            os.getenv("LINE_ITEM_STAGE_TIMEOUT_SECONDS", "75")
        )


settings = Settings()
