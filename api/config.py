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
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Database & Security
    DATABASE_URL: str = "sqlite:///./disaster_healthcare.db"
    SECRET_KEY: str = "disaster-healthcare-ai-super-secret-key-change-in-prod"
    JWT_SECRET_KEY: Union[str, None] = None  # Canonical environment variable
    JWT_SECRET: Union[str, None] = None      # Documented legacy alias
    ADMIN_PASSWORD: Union[str, None] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    @property
    def get_jwt_secret(self) -> str:
        """
        Return the effective JWT secret key.
        Canonical precedence:
        1. JWT_SECRET_KEY (canonical environment variable matching docker-compose.yml)
        2. JWT_SECRET (supported documented alias)
        3. SECRET_KEY (development fallback only)
        """
        return self.JWT_SECRET_KEY or self.JWT_SECRET or self.SECRET_KEY

    def validate_security(self):
        """
        Validate security settings: fail startup in non-development mode if secrets are missing or default.
        Never logs or exposes actual secret values.
        """
        env_val = os.getenv("APP_ENV") or os.getenv("ENV") or self.APP_ENV or "development"
        env_lower = env_val.strip().lower()
        is_production = env_lower in ["production", "prod", "staging"] or env_lower not in ["development", "dev", "test", "testing"]

        effective_jwt = self.JWT_SECRET_KEY or self.JWT_SECRET or self.SECRET_KEY
        is_default = (
            not effective_jwt or
            "change-in-prod" in effective_jwt or
            "change-this" in effective_jwt or
            effective_jwt == "disaster-healthcare-ai-super-secret-key-change-in-prod"
        )
        if is_production:
            if is_default or not (self.JWT_SECRET_KEY or self.JWT_SECRET):
                raise ValueError(
                    "Security Validation Error: In production mode (APP_ENV=production), "
                    "a secure non-default JWT_SECRET_KEY (or JWT_SECRET) must be explicitly configured."
                )
            if not self.ADMIN_PASSWORD:
                raise ValueError(
                    "Security Validation Error: In production mode (APP_ENV=production), "
                    "an explicit ADMIN_PASSWORD must be configured."
                )

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
