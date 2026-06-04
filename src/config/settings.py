import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    STAGE: str = "SIT"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_accounting_sit"
    
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
    MAX_TOKENS_PER_INVOICE: int = 1500
    
    # Thresholds
    CONFIDENCE_THRESHOLD: float = 0.85
    ALLOWED_SCOPES: str = "all"

    # Select environment config based on STAGE environment variable
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"../../config/environments/{os.getenv('STAGE', 'SIT').lower()}.env"
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )


def get_settings() -> Settings:
    """Load settings for the selected STAGE."""
    # Ensure STAGE is set normalized as uppercase (SIT, UAT, PROD)
    stage = os.getenv("STAGE", "SIT").upper()
    os.environ["STAGE"] = stage
    return Settings()
p = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    f"../../config/environments/{os.getenv('STAGE', 'SIT').lower()}.env"
)
