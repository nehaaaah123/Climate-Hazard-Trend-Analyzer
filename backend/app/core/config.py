"""Application configuration module using pydantic-settings."""

from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Climate Hazard Trend Analyzer"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "climate_analyzer"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Climate & Data settings
    GRID_SIZE: float = 0.25
    MAX_BBOX_SIZE: float = 10.0  # Max bounding box width/height in degrees
    BASELINE_START_YEAR: int = 1991
    BASELINE_END_YEAR: int = 2020
    BASELINE_WINDOW_DAYS: int = 15  # Centered 15-day window (+/- 7 days)
    MIN_VALID_YEAR_PCT: float = 85.0  # Require >= 85% valid days for yearly metrics

    # Open-Meteo API
    OPEN_METEO_BASE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    OPEN_METEO_TIMEOUT_SECONDS: float = 30.0
    OPEN_METEO_MAX_RETRIES: int = 3
    RAW_DAILY_CURRENT_YEAR_TTL_HOURS: int = 24

    # Rate Limiting
    RATE_LIMIT_ANALYSIS: str = "30/minute"
    RATE_LIMIT_EXPORT: str = "10/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
