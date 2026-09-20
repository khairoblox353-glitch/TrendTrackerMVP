"""Category transport types (spec 11)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel
from app.schemas.refs import TrendingTopicRef
from app.schemas.trend import TrendSummary


class CategorySummary(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    topic_count: int = Field(ge=0)
    article_count: int = Field(ge=0)
    trending_topic: TrendingTopicRef | None = None


class CategoryDetail(CategorySummary):
    """Category page payload: the category plus its leading trends (spec 12)."""

    top_trends: list[TrendSummary] = Field(default_factory=list)
