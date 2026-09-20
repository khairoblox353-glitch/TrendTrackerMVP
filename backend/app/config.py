"""Application settings.

Every tunable business value from the specification lives here so that the trend
thresholds (spec 10), the score weights (spec 9) and the scheduler cadence (spec 14)
can be changed without touching code. Values are overridable through environment
variables or a `.env` file sitting next to `docker-compose.yml`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Trend Tracker API"
    # Deliberately not called `debug`: a generic DEBUG variable is commonly set in
    # developer environments (and is here) and would collide with this setting.
    app_debug: bool = False

    database_url: str = "postgresql+psycopg://trend:trend@localhost:5432/trend_tracker"
    sql_echo: bool = False

    cors_origins: str = "http://localhost:3000"

    # ---- Trend windows -------------------------------------------------
    trend_window_days: int = Field(default=7, ge=1, le=90)
    trend_history_days: int = Field(default=30, ge=1, le=365)

    # ---- Trend score weights (spec 9) ----------------------------------
    weight_growth: float = Field(default=0.7, ge=0.0, le=1.0)
    weight_volume: float = Field(default=0.3, ge=0.0, le=1.0)

    # A topic with no articles in the previous window would otherwise produce
    # an infinite growth rate. Cap it instead and flag the topic as emerging.
    emerging_growth_cap: float = Field(default=3.0, gt=0.0)
    growth_floor: float = Field(default=-1.0, ge=-1.0, le=0.0)

    # Growth is squashed into [0, 1] with growth / (growth + growth_saturation)
    # so a single viral topic cannot flatten everything else to zero.
    growth_saturation: float = Field(default=1.0, gt=0.0)

    # ---- Trend status thresholds (spec 10) -----------------------------
    growing_threshold: float = Field(default=0.20)
    declining_threshold: float = Field(default=-0.20)

    # ---- Classification (spec 8) ---------------------------------------
    classification_min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    fallback_topic_name: str = "Other"

    # ---- LLM (optional; the keyword classifier runs when unset) --------
    llm_enabled: bool = False
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=20.0, gt=0.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # ---- Collector (spec 15) -------------------------------------------
    collector_timeout_seconds: float = Field(default=15.0, gt=0.0)
    collector_user_agent: str = "TrendTrackerBot/0.1 (+https://example.com/bot)"
    collector_max_articles_per_source: int = Field(default=50, ge=1, le=500)

    # ---- Scheduler (spec 14) -------------------------------------------
    run_scheduler: bool = False
    ingest_interval_minutes: int = Field(default=60, ge=1)
    recalculate_interval_minutes: int = Field(default=360, ge=1)

    @field_validator("weight_volume")
    @classmethod
    def _weights_must_sum_to_one(cls, value: float, info) -> float:
        growth = info.data.get("weight_growth")
        if growth is not None and abs((growth + value) - 1.0) > 1e-6:
            raise ValueError("weight_growth + weight_volume must equal 1.0")
        return value

    @field_validator("declining_threshold")
    @classmethod
    def _thresholds_must_be_ordered(cls, value: float, info) -> float:
        growing = info.data.get("growing_threshold", 0.20)
        if value >= 0:
            raise ValueError("declining_threshold must be negative")
        if value >= growing:
            raise ValueError("declining_threshold must be below growing_threshold")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_enabled and self.llm_api_key)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
