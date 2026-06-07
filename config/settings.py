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
        self.OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")
        self.DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "th_TH")


settings = Settings()
