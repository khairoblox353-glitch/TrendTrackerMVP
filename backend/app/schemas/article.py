"""Article transport types (spec 11, spec 12)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ORMModel
from app.schemas.refs import CategoryRef, SourceRef, TopicRef


class ArticleSummary(ORMModel):
    """Compact form used inside trend and category payloads."""

    id: int
    title: str
    url: str
    published_at: str | None = None
    source: SourceRef | None = None


class ArticleDetail(ArticleSummary):
    """Full article as returned by the article endpoints."""

    description: str | None = None
    summary: str | None = None
    created_at: str | None = None
    processing_status: str
    category: CategoryRef | None = None
    topics: list[TopicRef] = Field(default_factory=list)

