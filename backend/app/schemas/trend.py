"""Trend transport types (spec 11, spec 12)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.article import ArticleSummary
from app.schemas.common import ORMModel
from app.schemas.refs import CategoryRef, SnapshotPoint


class TrendSummary(ORMModel):
    """A topic together with its most recent snapshot."""

    id: int
    slug: str
    name: str
    description: str | None = None
    summary: str | None = None
    category: CategoryRef
    trend_score: float = Field(ge=0.0, le=1.0)
    growth_rate: float
    growth_percent: float
    current_count: int = Field(ge=0)
    previous_count: int = Field(ge=0)
    volume_share: float = Field(ge=0.0, le=1.0)
    status: str
    is_emerging: bool
    snapshot_date: str
    window_days: int = Field(ge=1)


class TrendDetail(TrendSummary):
    """Trend detail adds the newest articles (spec 12)."""

    latest_articles: list[ArticleSummary] = Field(default_factory=list)
    history_days: int = Field(default=0, ge=0)


class TrendHistory(ORMModel):
    slug: str
    name: str
    window_days: int | None = None
    points: list[SnapshotPoint] = Field(default_factory=list)
