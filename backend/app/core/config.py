import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""
    
    # Service settings
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/wind_procurement.db"

    # Elexon BMRS API
    ELEXON_BASE_URL: str = "https://data.elexon.co.uk/bmrs/api/v1"
    ELEXON_TIMEOUT_SECONDS: float = 30.0
    ELEXON_MAX_RETRIES: int = 3

    # Procurement Domain Defaults
    # 11:00 UK local time on D-1 is the initial default assumption
    DEFAULT_DECISION_CUTOFF: str = "11:00"
    DEFAULT_TIMEZONE: str = "Europe/London"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                return json.loads(v)
            except Exception:
                return ["*"]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
