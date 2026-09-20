"""Read-side article service (spec 11, spec 12)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleTopic, Category, Topic
from app.services.trends import (
    ARTICLE_EAGER_OPTIONS,
    ARTICLE_SORT_FIELDS,
    DEFAULT_ARTICLE_SORT,
    apply_category_filter,
    parse_sort,
)


def _start_of_day(day: date) -> datetime:
    """Midnight UTC on `day`, timezone-aware so the comparison is unambiguous.

    `Article.published_at` is stored as `TIMESTAMPTZ`, so bounds must carry a timezone.
    """
    return datetime.combine(day, time.min, tzinfo=UTC)


def _base_query() -> Select:
    return select(Article).options(*ARTICLE_EAGER_OPTIONS)


def _apply_filters(
    statement: Select,
    *,
    category: str | None = None,
    topic: str | None = None,
    source_id: int | None = None,
    query: str | None = None,
    published_after: date | None = None,
    published_before: date | None = None,
) -> Select:
    if category:
        statement = apply_category_filter(
            statement.join(Category, Category.id == Article.category_id), category
        )
    if topic:
        statement = statement.join(ArticleTopic, ArticleTopic.article_id == Article.id).join(
            Topic, Topic.id == ArticleTopic.topic_id
        ).where(Topic.slug == topic)
    if source_id is not None:
        statement = statement.where(Article.source_id == source_id)
    if query:
        statement = statement.where(Article.title.ilike(f"%{query.strip()}%"))
    if published_after is not None:
        # Compare the raw column, not `func.date(published_at)`: wrapping the indexed
        # column makes the predicate non-sargable and the index is never used.
        # Semantics are unchanged - the whole of day D is included.
        statement = statement.where(Article.published_at >= _start_of_day(published_after))
    if published_before is not None:
        # `published_at < (D + 1 day)` rather than `<= D`, so the whole of day D is
        # included while missing precision (timestamps are not midnight) cannot slip
        # through. This is the equivalent, index-friendly form of `date(col) <= D`.
        statement = statement.where(
            Article.published_at < _start_of_day(published_before + timedelta(days=1))
        )
    return statement


def query_articles(
    db: Session,
    *,
    category: str | None = None,
    topic: str | None = None,
    source_id: int | None = None,
    query: str | None = None,
    published_after: date | None = None,
    published_before: date | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Article], int]:
    """Filtered, sorted, paginated article list (spec 11)."""
    filters: dict[str, Any] = {
        "category": category,
        "topic": topic,
        "source_id": source_id,
        "query": query,
        "published_after": published_after,
        "published_before": published_before,
    }

    statement = _apply_filters(_base_query(), **filters)
    count_statement = _apply_filters(
        select(func.count(func.distinct(Article.id))), **filters
    )

    column, descending = parse_sort(sort, ARTICLE_SORT_FIELDS, DEFAULT_ARTICLE_SORT)

    total = int(db.execute(count_statement).scalar_one())
    rows = db.execute(
        statement.order_by(column.desc() if descending else column.asc(), Article.id.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).unique().scalars()

    return list(rows), total


def get_article(db: Session, article_id: int) -> Article | None:
    statement = _base_query().where(Article.id == article_id).limit(1)
    return db.execute(statement).unique().scalars().first()


def article_as_dict(article: Article) -> dict:
    """Wire shape shared by the article list and detail endpoints."""
    return {
        "id": article.id,
        "title": article.title,
        "url": article.url,
        "description": article.description,
        "summary": article.summary,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "processing_status": article.processing_status,
        "source": {"id": article.source.id, "name": article.source.name}
        if article.source
        else None,
        "category": {"id": article.category.id, "slug": article.category.slug, "name": article.category.name}
        if article.category
        else None,
        "topics": [
            {"slug": topic.slug, "name": topic.name, "is_fallback": topic.is_fallback}
            for topic in article.topics
        ],
    }


