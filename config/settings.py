"""Configuration settings."""

import os


class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")
    DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "th_TH")


settings = Settings()
