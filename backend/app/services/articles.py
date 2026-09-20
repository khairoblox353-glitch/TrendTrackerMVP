"""Read-side article service (spec 11, spec 12)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Article, ArticleTopic, Category, Topic
from app.services.text import normalize_name
from app.services.trends import ARTICLE_SORT_FIELDS, DEFAULT_ARTICLE_SORT, parse_sort


def _base_query() -> Select:
    return (
        select(Article)
        .options(selectinload(Article.source), selectinload(Article.category), selectinload(Article.topics))
    )


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
        needle = normalize_name(category)
        statement = statement.join(Category, Category.id == Article.category_id).where(
            or_(
                Category.slug == needle.replace(" ", "-"),
                func.lower(Category.name) == needle,
            )
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
        statement = statement.where(func.date(Article.published_at) >= published_after)
    if published_before is not None:
        statement = statement.where(func.date(Article.published_at) <= published_before)
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


def count_articles(db: Session) -> int:
    return int(db.execute(select(func.count(Article.id))).scalar_one())


def latest_published_at(db: Session) -> datetime | None:
    return db.execute(select(func.max(Article.published_at))).scalar_one()
