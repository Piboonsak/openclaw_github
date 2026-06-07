"""Configuration settings."""

import os


class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")
        self.DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "th_TH")


settings = Settings()
