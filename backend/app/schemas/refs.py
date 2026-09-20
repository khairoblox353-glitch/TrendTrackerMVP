"""Nested reference types.

Kept in their own module so `category` and `trend` schemas can both use them without
importing each other (which would create a cycle).
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel


class CategoryRef(ORMModel):
    id: int
    slug: str
    name: str


class SourceRef(ORMModel):
    id: int
    name: str


class TopicRef(ORMModel):
    slug: str
    name: str
    # Lets a client hide the per-category `Other` bucket, which is a diagnostic rather
    # than a real topic. The API still reports it, so the data stays truthful.
    is_fallback: bool = False


class TrendingTopicRef(ORMModel):
    slug: str
    name: str
    growth_rate: float
    trend_score: float
    status: str


class SnapshotPoint(ORMModel):
    """One point on a trend growth chart (spec 12)."""

    date: str
    current_count: int = Field(ge=0)
    previous_count: int = Field(ge=0)
    growth_rate: float
    trend_score: float
    status: str
