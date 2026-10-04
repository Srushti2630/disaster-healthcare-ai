"""Configuration settings for Disaster Healthcare AI API."""
from pathlib import Path
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

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
