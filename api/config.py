"""Configuration settings for Disaster Healthcare AI API."""
from pathlib import Path
from typing import List, Union
import os
import json
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "Disaster Healthcare AI API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Database & Security
    DATABASE_URL: str = "sqlite:///./disaster_healthcare.db"
    SECRET_KEY: str = "disaster-healthcare-ai-super-secret-key-change-in-prod"
    JWT_SECRET: Union[str, None] = None
    ADMIN_PASSWORD: Union[str, None] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    @property
    def get_jwt_secret(self) -> str:
        return self.JWT_SECRET or self.SECRET_KEY

    def validate_security(self):
        """Validate security settings: fail startup in non-development mode if secrets are missing or default."""
        env_val = os.getenv("ENV") or os.getenv("APP_ENV") or self.APP_ENV or "development"
        env_lower = env_val.strip().lower()
        if env_lower not in ["development", "dev", "test", "testing"]:
            effective_jwt = self.JWT_SECRET or self.SECRET_KEY
            is_default = (
                not effective_jwt or
                "change-in-prod" in effective_jwt or
                "change-this" in effective_jwt or
                effective_jwt == "disaster-healthcare-ai-super-secret-key-change-in-prod"
            )
            if is_default or not self.JWT_SECRET:
                raise ValueError("JWT_SECRET environment variable must be explicitly configured in non-development mode.")
            if not self.ADMIN_PASSWORD:
                raise ValueError("ADMIN_PASSWORD environment variable must be explicitly configured in non-development mode.")

    # CORS configuration
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8501"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Paths to artifacts and datasets
    DATA_DIR: Path = BASE_DIR / "data"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    BOUNDARIES_FILE: Path = BASE_DIR / "data" / "raw" / "boundaries" / "maharashtra_districts.geojson"
    MODELS_DIR: Path = BASE_DIR / "models"
    REPORTS_DIR: Path = BASE_DIR / "reports"
    CONFIG_YAML: Path = BASE_DIR / "config.yaml"
    PROVENANCE_YAML: Path = BASE_DIR / "data" / "provenance.yaml"

settings = Settings()
