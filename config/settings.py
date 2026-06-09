"""Configuration settings."""

import os


class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
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


settings = Settings()
