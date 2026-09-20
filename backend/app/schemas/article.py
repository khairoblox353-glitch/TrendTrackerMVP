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


class ArticleListParams(ORMModel):
    """Documentation-only model describing the article list query (spec 11)."""

    category: str | None = None
    topic: str | None = None
    source_id: int | None = None
    q: str | None = None
    published_after: str | None = None
    published_before: str | None = None
    sort: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
