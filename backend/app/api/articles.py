"""Article endpoints (spec 11, spec 12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_db, pagination_params, parse_iso_date
from app.api.errors import NotFoundError, ValidationError
from app.schemas.article import ArticleDetail
from app.schemas.common import Page
from app.services import articles as article_service

router = APIRouter(prefix="/articles", tags=["articles"])

SORT_DESCRIPTION = "Sort field. Allowed: published_at (default), created_at, title"


@router.get("", response_model=Page[ArticleDetail], summary="Paginated article list")
def list_articles(
    category: str | None = Query(None, description="Category slug or name"),
    topic: str | None = Query(None, description="Topic slug"),
    source_id: int | None = Query(None, ge=1),
    q: str | None = Query(None, description="Substring match on the title"),
    published_after: str | None = Query(None, description="ISO date, inclusive"),
    published_before: str | None = Query(None, description="ISO date, inclusive"),
    sort: str | None = Query(None, description=SORT_DESCRIPTION),
    pagination: Pagination = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> Page[ArticleDetail]:
    after = parse_iso_date(published_after, "published_after")
    before = parse_iso_date(published_before, "published_before")

    if after and before and after > before:
        raise ValidationError(
            "published_after must not be later than published_before",
            {"published_after": str(after), "published_before": str(before)},
        )

    try:
        rows, total = article_service.query_articles(
            db,
            category=category,
            topic=topic,
            source_id=source_id,
            query=q,
            published_after=after,
            published_before=before,
            sort=sort,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    except ValueError as exc:
        raise ValidationError(str(exc), {"parameter": "sort"}) from exc

    items = [
        ArticleDetail.model_validate(article_service.article_as_dict(article)) for article in rows
    ]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.get("/{article_id}", response_model=ArticleDetail, summary="One article")
def get_article(article_id: int, db: Session = Depends(get_db)) -> ArticleDetail:
    article = article_service.get_article(db, article_id)
    if article is None:
        raise NotFoundError(f"Article {article_id} not found", {"id": article_id})
    return ArticleDetail.model_validate(article_service.article_as_dict(article))
