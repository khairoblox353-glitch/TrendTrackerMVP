"""Operational endpoint transport types (spec 11, spec 14)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    source_ids: list[int] | None = Field(
        default=None, description="Restrict the run to these source ids."
    )
    limit_per_source: int | None = Field(
        default=None, ge=1, le=500, description="Cap articles read per feed."
    )
    classify: bool = Field(default=True, description="Run topic classification after storing.")


class RecalculateRequest(BaseModel):
    snapshot_date: str | None = Field(
        default=None, description="ISO date to score. Defaults to today (UTC)."
    )
    window_days: int | None = Field(default=None, ge=1, le=90)
    days_back: int = Field(default=1, ge=1, le=90, description="Trailing days to (re)score.")
    topic_id: int | None = Field(default=None, description="Score a single topic only.")


class HealthResponse(BaseModel):
    status: str
    database: str
    scheduler: str
    llm: str
    version: str
