"""Trend endpoints (spec 11, spec 12).

Routes validate query parameters, delegate to `app.services.trends`, and serialize.
No scoring math lives here (spec 19.10, spec 19.11).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import Pagination, get_db, pagination_params
from app.api.errors import NotFoundError, ValidationError
from app.models import TrendStatus
from app.schemas.article import ArticleSummary
from app.schemas.common import Page
from app.schemas.refs import SnapshotPoint
from app.schemas.trend import TrendDetail, TrendHistory, TrendSummary
from app.services import articles as article_service
from app.services import topics as topic_service
from app.services import trends as trend_service

router = APIRouter(prefix="/trends", tags=["trends"])

SORT_DESCRIPTION = (
    "Sort field. Prefix with '-' for descending. "
    "Allowed: trend_score, growth_rate, article_count, volume_share, name, snapshot_date"
)

FALLBACK_DESCRIPTION = (
    "Include the per-category 'Other' buckets, which hold articles the classifier could "
    "not place. Excluded by default because they are diagnostics rather than trends."
)


@router.get("", response_model=Page[TrendSummary], summary="Latest trend snapshot per topic")
def list_trends(
    category: str | None = Query(None, description="Category slug or name"),
    status: str | None = Query(None, description="emerging | growing | stable | declining"),
    q: str | None = Query(None, description="Substring match on the topic name"),
    min_growth: float | None = Query(None, description="Minimum growth_rate, inclusive"),
    sort: str | None = Query(None, description=SORT_DESCRIPTION),
    include_fallback: bool = Query(False, description=FALLBACK_DESCRIPTION),
    pagination: Pagination = Depends(pagination_params),
    db: Session = Depends(get_db),
) -> Page[TrendSummary]:
    if status and status.lower() not in {item.value for item in TrendStatus}:
        raise ValidationError(
            f"Unknown status '{status}'",
            {"allowed": [item.value for item in TrendStatus]},
        )

    try:
        rows, total = trend_service.query_trends(
            db,
            category=category,
            status=status,
            query=q,
            min_growth=min_growth,
            sort=sort,
            page=pagination.page,
            page_size=pagination.page_size,
            include_fallback=include_fallback,
        )
    except ValueError as exc:
        raise ValidationError(str(exc), {"parameter": "sort"}) from exc

    items = [TrendSummary.model_validate(trend_service.trend_row_as_dict(row)) for row in rows]
    return Page.build(items, total, pagination.page, pagination.page_size)


@router.get("/{slug}", response_model=TrendDetail, summary="One trend with recent articles")
def get_trend(slug: str, db: Session = Depends(get_db)) -> TrendDetail:
    row = trend_service.get_trend(db, slug)
    if row is None:
        raise NotFoundError(f"Trend '{slug}' not found", {"slug": slug})

    payload = trend_service.trend_row_as_dict(row)
    article_models = trend_service.articles_for_topic(db, row.topic_id, limit=5)

    return TrendDetail(
        **payload,
        latest_articles=[
            ArticleSummary.model_validate(article_service.article_as_dict(article))
            for article in article_models
        ],
    )


@router.get(
    "/{slug}/history",
    response_model=TrendHistory,
    responses={
        204: {"description": "Topic exists but has no snapshots yet"},
        404: {"description": "No topic with that slug"},
    },
    summary="Snapshot series for the growth chart",
)
def get_trend_history(
    slug: str,
    response: Response,
    days: int = Query(30, ge=1, le=365, description="Trailing days to return"),
    window_days: int | None = Query(None, ge=1, le=90),
    db: Session = Depends(get_db),
) -> TrendHistory | Response:
    # Existence is decided by the topic, not by a snapshot: a topic that has been
    # created but not yet scored is a 204, while an unknown slug is a 404.
    topic = topic_service.find_by_slug(db, slug)
    if topic is None:
        raise NotFoundError(f"Trend '{slug}' not found", {"slug": slug})

    snapshots = trend_service.get_history(db, slug, days=days, window_days=window_days)

    if not snapshots:
        response.status_code = 204
        return Response(status_code=204)

    points = [
        SnapshotPoint(
            date=snapshot.snapshot_date.isoformat(),
            current_count=snapshot.current_count,
            previous_count=snapshot.previous_count,
            growth_rate=round(snapshot.growth_rate, 4),
            trend_score=round(snapshot.trend_score, 4),
            status=snapshot.status,
        )
        for snapshot in snapshots
    ]

    return TrendHistory(
        slug=slug,
        name=topic.name,
        window_days=snapshots[0].window_days,
        points=points,
    )
