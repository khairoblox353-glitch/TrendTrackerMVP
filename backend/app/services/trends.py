"""Read-side trend service (spec 11, spec 12).

Keeps every trend query and serialization detail out of the routers: a route only
validates input, calls one function here, and returns the result (spec 19.11).

Reads are served from the latest `trend_snapshots` row per topic — a materialized
value rather than a live aggregation — so list latency does not grow with the number
of stored articles (ADR-002).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.config import settings as default_settings
from app.models import Article, ArticleTopic, Category, Topic, TrendSnapshot
from app.services.text import normalize_name

# Sorting is whitelisted per endpoint (R16); client input never reaches SQL directly.
TREND_SORT_FIELDS: dict[str, object] = {
    "trend_score": TrendSnapshot.trend_score,
    "growth_rate": TrendSnapshot.growth_rate,
    "article_count": TrendSnapshot.current_count,
    "volume_share": TrendSnapshot.volume_share,
    "name": Topic.name,
    "snapshot_date": TrendSnapshot.snapshot_date,
}

ARTICLE_SORT_FIELDS: dict[str, object] = {
    "published_at": Article.published_at,
    "created_at": Article.created_at,
    "title": Article.title,
}

DEFAULT_TREND_SORT = "trend_score"
DEFAULT_ARTICLE_SORT = "published_at"

# Eager loading for article serialization, defined once and reused by the article
# service. Without it, `article_as_dict` lazy-loads `source`, `category` and `topics`
# for every row, so a five-article trend detail response becomes a burst of queries.
ARTICLE_EAGER_OPTIONS = (
    selectinload(Article.source),
    selectinload(Article.category),
    selectinload(Article.topics),
)


def apply_category_filter(statement: Select, category: str) -> Select:
    """Restrict a statement to one category, given its slug or its name.

    The single definition of the "category slug or name" rule, shared by every read
    path. The caller must already have `Category` joined. Accepts a slug (`ai`) or a
    name in any case with surrounding whitespace (`AI`, `ai`, `  AI  `).
    """
    normalized = normalize_name(category)
    return statement.where(
        or_(
            Category.slug == normalized.replace(" ", "-"),
            func.lower(Category.name) == normalized,
        )
    )


@dataclass(slots=True)
class TrendRow:
    """A topic joined with its latest snapshot."""

    topic_id: int
    slug: str
    name: str
    topic_description: str | None
    topic_summary: str | None
    category_id: int
    category_slug: str
    category_name: str
    snapshot_date: date
    window_days: int
    current_count: int
    previous_count: int
    growth_rate: float
    volume_share: float
    trend_score: float
    status: str
    is_emerging: bool

    @property
    def growth_percent(self) -> float:
        return round(self.growth_rate * 100, 2)


def parse_sort(sort: str | None, allowed: dict[str, object], default: str) -> tuple[object, bool]:
    """Resolve `sort` against a whitelist. Returns `(column, descending)`.

    Raises `ValueError` for anything unknown so the route can answer `422` (R16).
    """
    if not sort:
        return allowed[default], True

    descending = sort.startswith("-")
    key = sort.lstrip("-+")
    column = allowed.get(key)
    if column is None:
        raise ValueError(f"unsupported sort field {key!r}; allowed: {', '.join(sorted(allowed))}")
    return column, descending


def latest_snapshot_subquery(window_days: int):
    """The most recent snapshot date per topic **for one window size**.

    Scoping to a single window is essential: `trend_snapshots` is unique per
    `(topic, date, window)`, so a topic scored for both a 7-day and a 30-day window
    would otherwise match twice and appear as two rows in the trend list, breaking
    both the ranking and pagination.
    """
    return (
        select(
            TrendSnapshot.topic_id.label("topic_id"),
            func.max(TrendSnapshot.snapshot_date).label("snapshot_date"),
        )
        .where(TrendSnapshot.window_days == window_days)
        .group_by(TrendSnapshot.topic_id)
        .subquery()
    )


def _latest_snapshot_filter(window_days: int):
    latest = latest_snapshot_subquery(window_days)
    return latest, [
        TrendSnapshot.topic_id == latest.c.topic_id,
        TrendSnapshot.snapshot_date == latest.c.snapshot_date,
        TrendSnapshot.window_days == window_days,
    ]


def _base_trend_query(window_days: int) -> Select:
    latest, conditions = _latest_snapshot_filter(window_days)
    return (
        select(TrendSnapshot, Topic, Category)
        .join(latest, TrendSnapshot.topic_id == latest.c.topic_id)
        .join(Topic, Topic.id == TrendSnapshot.topic_id)
        .join(Category, Category.id == Topic.category_id)
        .where(*conditions)
    )


def _apply_trend_filters(
    statement: Select,
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    min_growth: float | None = None,
    include_fallback: bool = False,
) -> Select:
    # Each category has an `Other` bucket that absorbs everything the classifier could
    # not place. Those buckets are diagnostics, not trends: because real feeds contain
    # plenty of unmatched articles, they accumulate volume fast and would otherwise
    # occupy the top of the ranking with several identically named "Other" rows, pushing
    # real topics off the homepage. They are excluded unless explicitly requested.
    if not include_fallback:
        statement = statement.where(Topic.is_fallback.is_(False))
    if category:
        statement = apply_category_filter(statement, category)
    if status:
        statement = statement.where(TrendSnapshot.status == status.strip().lower())
    if query:
        statement = statement.where(Topic.name.ilike(f"%{query.strip()}%"))
    if min_growth is not None:
        statement = statement.where(TrendSnapshot.growth_rate >= min_growth)
    return statement


def _to_row(snapshot: TrendSnapshot, topic: Topic, category: Category) -> TrendRow:
    return TrendRow(
        topic_id=topic.id,
        slug=topic.slug,
        name=topic.name,
        topic_description=topic.description,
        topic_summary=topic.summary,
        category_id=category.id,
        category_slug=category.slug,
        category_name=category.name,
        snapshot_date=snapshot.snapshot_date,
        window_days=snapshot.window_days,
        current_count=snapshot.current_count,
        previous_count=snapshot.previous_count,
        growth_rate=snapshot.growth_rate,
        volume_share=snapshot.volume_share,
        trend_score=snapshot.trend_score,
        status=snapshot.status,
        is_emerging=snapshot.is_emerging,
    )


def _filtered_trend_query(
    window_days: int,
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    min_growth: float | None = None,
    include_fallback: bool = False,
) -> Select:
    return _apply_trend_filters(
        _base_trend_query(window_days),
        category=category,
        status=status,
        query=query,
        min_growth=min_growth,
        include_fallback=include_fallback,
    )


def _fetch_trend_rows(
    db: Session, statement: Select, *, sort: str | None, page: int, page_size: int
) -> list[TrendRow]:
    column, descending = parse_sort(sort, TREND_SORT_FIELDS, DEFAULT_TREND_SORT)
    rows = db.execute(
        statement.order_by(column.desc() if descending else column.asc(), Topic.id.asc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    ).all()
    return [_to_row(snapshot, topic, category) for snapshot, topic, category in rows]


def query_trends(
    db: Session,
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    min_growth: float | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
    window_days: int | None = None,
    include_fallback: bool = False,
    cfg: Settings | None = None,
) -> tuple[list[TrendRow], int]:
    """Latest snapshot per topic, filtered, sorted and paginated (spec 11).

    `include_fallback` is off by default so the ranking contains real topics only; the
    `Other` buckets remain reachable for diagnostics.
    """
    cfg = cfg or default_settings
    resolved_window = window_days or cfg.trend_window_days

    statement = _filtered_trend_query(
        resolved_window,
        category=category,
        status=status,
        query=query,
        min_growth=min_growth,
        include_fallback=include_fallback,
    )
    count_statement = _filtered_trend_query(
        resolved_window,
        category=category,
        status=status,
        query=query,
        min_growth=min_growth,
        include_fallback=include_fallback,
    ).with_only_columns(func.count()).order_by(None)

    total = int(db.execute(count_statement).scalar_one())
    rows = _fetch_trend_rows(db, statement, sort=sort, page=page, page_size=page_size)
    return rows, total


def query_trend_rows(
    db: Session,
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    min_growth: float | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
    window_days: int | None = None,
    include_fallback: bool = False,
    cfg: Settings | None = None,
) -> list[TrendRow]:
    """The rows of `query_trends` without paying for the COUNT query.

    Callers that only need rows (the per-category leader lookup, `top_trends`) must not
    execute an aggregate whose result they discard.
    """
    cfg = cfg or default_settings
    resolved_window = window_days or cfg.trend_window_days
    statement = _filtered_trend_query(
        resolved_window,
        category=category,
        status=status,
        query=query,
        min_growth=min_growth,
        include_fallback=include_fallback,
    )
    return _fetch_trend_rows(db, statement, sort=sort, page=page, page_size=page_size)


def top_trends(
    db: Session, limit: int = 10, category: str | None = None, cfg: Settings | None = None
) -> list[TrendRow]:
    """Highest-scoring trends, optionally limited to one category."""
    return query_trend_rows(db, category=category, page=1, page_size=limit, cfg=cfg)


def get_trend(db: Session, slug: str, cfg: Settings | None = None) -> TrendRow | None:
    """One trend by its globally unique slug (R10).

    Uses the configured default window so the detail page agrees with the list.
    """
    cfg = cfg or default_settings
    statement = _base_trend_query(cfg.trend_window_days).where(Topic.slug == slug).limit(1)
    row = db.execute(statement).first()
    if row is None:
        return None
    snapshot, topic, category = row
    return _to_row(snapshot, topic, category)


def get_history(
    db: Session,
    slug: str,
    *,
    days: int | None = None,
    window_days: int | None = None,
    cfg: Settings | None = None,
) -> list[TrendSnapshot]:
    """Ascending snapshot series for the chart on the trend detail page (spec 12)."""
    cfg = cfg or default_settings
    days = days or cfg.trend_history_days

    topic = db.execute(select(Topic).where(Topic.slug == slug)).scalar_one_or_none()
    if topic is None:
        raise LookupError(slug)

    statement = select(TrendSnapshot).where(TrendSnapshot.topic_id == topic.id)
    if window_days is not None:
        statement = statement.where(TrendSnapshot.window_days == window_days)
    else:
        # Default to the widest window that actually has data, so the chart is never
        # silently blank because of a window mismatch.
        window_days = db.execute(
            select(func.max(TrendSnapshot.window_days)).where(TrendSnapshot.topic_id == topic.id)
        ).scalar_one()
        if window_days is not None:
            statement = statement.where(TrendSnapshot.window_days == window_days)

    newest = db.execute(
        select(func.max(TrendSnapshot.snapshot_date)).where(TrendSnapshot.topic_id == topic.id)
    ).scalar_one()
    if newest is not None:
        statement = statement.where(TrendSnapshot.snapshot_date >= newest - timedelta(days=days - 1))

    return list(
        db.execute(statement.order_by(TrendSnapshot.snapshot_date.asc())).scalars()
    )


def _row_from_mapping(row) -> TrendRow:
    """Build a `TrendRow` from an explicitly selected column mapping."""
    return TrendRow(
        topic_id=row["topic_id"],
        slug=row["slug"],
        name=row["name"],
        topic_description=row["topic_description"],
        topic_summary=row["topic_summary"],
        category_id=row["category_id"],
        category_slug=row["category_slug"],
        category_name=row["category_name"],
        snapshot_date=row["snapshot_date"],
        window_days=row["window_days"],
        current_count=row["current_count"],
        previous_count=row["previous_count"],
        growth_rate=row["growth_rate"],
        volume_share=row["volume_share"],
        trend_score=row["trend_score"],
        status=row["status"],
        is_emerging=bool(row["is_emerging"]),
    )


def _category_leaders(
    db: Session, cfg: Settings | None = None, *, category_id: int | None = None
) -> dict[int, TrendRow]:
    """The highest-scoring topic per category, in a single query.

    Instead of materializing the whole topic population and picking the first row per
    category in Python, the filtered trend query is ranked with `row_number()`
    partitioned by category and only rank 1 survives. Window functions work on both
    PostgreSQL and SQLite (3.25+), so the API tests exercise the same query shape that
    production runs. The ordering mirrors the default trend sort
    (`trend_score DESC, topic_id ASC`), so the leader is unchanged.
    """
    cfg = cfg or default_settings

    statement = _filtered_trend_query(cfg.trend_window_days)
    if category_id is not None:
        statement = statement.where(Topic.category_id == category_id)

    ranked = (
        statement.with_only_columns(
            Topic.id.label("topic_id"),
            Topic.slug.label("slug"),
            Topic.name.label("name"),
            Topic.description.label("topic_description"),
            Topic.summary.label("topic_summary"),
            Category.id.label("category_id"),
            Category.slug.label("category_slug"),
            Category.name.label("category_name"),
            TrendSnapshot.snapshot_date.label("snapshot_date"),
            TrendSnapshot.window_days.label("window_days"),
            TrendSnapshot.current_count.label("current_count"),
            TrendSnapshot.previous_count.label("previous_count"),
            TrendSnapshot.growth_rate.label("growth_rate"),
            TrendSnapshot.volume_share.label("volume_share"),
            TrendSnapshot.trend_score.label("trend_score"),
            TrendSnapshot.status.label("status"),
            TrendSnapshot.is_emerging.label("is_emerging"),
        )
        .add_columns(
            func.row_number()
            .over(
                partition_by=Topic.category_id,
                order_by=(TrendSnapshot.trend_score.desc(), Topic.id.asc()),
            )
            .label("category_rank")
        )
        .subquery("category_ranked")
    )

    rows = db.execute(select(ranked).where(ranked.c.category_rank == 1)).mappings().all()
    return {row["category_id"]: _row_from_mapping(row) for row in rows}


def _category_counts(db: Session) -> tuple[dict[int, int], dict[int, int]]:
    topic_counts = dict(
        db.execute(
            select(Topic.category_id, func.count(Topic.id))
            .where(Topic.is_fallback.is_(False))
            .group_by(Topic.category_id)
        ).all()
    )
    article_counts = dict(
        db.execute(
            select(Article.category_id, func.count(Article.id))
            .where(Article.category_id.is_not(None))
            .group_by(Article.category_id)
        ).all()
    )
    return topic_counts, article_counts


def _category_summary(
    category: Category, topic_count: int, article_count: int, leader: TrendRow | None
) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "topic_count": int(topic_count),
        "article_count": int(article_count),
        "trending_topic": {
            "slug": leader.slug,
            "name": leader.name,
            "growth_rate": leader.growth_rate,
            "trend_score": leader.trend_score,
            "status": leader.status,
        }
        if leader
        else None,
    }


def category_summaries(db: Session, cfg: Settings | None = None) -> list[dict]:
    """Category list with article/topic counts and the current leading trend."""
    categories = list(db.execute(select(Category).order_by(Category.id)).scalars())
    topic_counts, article_counts = _category_counts(db)
    leaders = _category_leaders(db, cfg)

    return [
        _category_summary(
            category,
            topic_counts.get(category.id, 0),
            article_counts.get(category.id, 0),
            leaders.get(category.id),
        )
        for category in categories
    ]


def get_category(db: Session, slug: str, cfg: Settings | None = None) -> dict | None:
    """One category with its top trends, for `GET /api/categories/{slug}`.

    Loads only the requested category instead of building every category summary and
    discarding all but one.
    """
    cfg = cfg or default_settings
    category = db.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()
    if category is None:
        return None

    topic_counts, article_counts = _category_counts(db)
    leaders = _category_leaders(db, cfg, category_id=category.id)

    payload = _category_summary(
        category,
        topic_counts.get(category.id, 0),
        article_counts.get(category.id, 0),
        leaders.get(category.id),
    )
    payload["top_trends"] = [
        trend_row_as_dict(row) for row in top_trends(db, limit=10, category=slug, cfg=cfg)
    ]
    return payload


def articles_for_topic(db: Session, topic_id: int, limit: int = 5) -> list[Article]:
    statement = (
        select(Article)
        .options(*ARTICLE_EAGER_OPTIONS)
        .join(ArticleTopic, ArticleTopic.article_id == Article.id)
        .where(ArticleTopic.topic_id == topic_id)
        .order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit)
    )
    return list(db.execute(statement).unique().scalars())


def trend_row_as_dict(row: TrendRow) -> dict:
    """Wire shape shared by the list, detail and category endpoints."""
    return {
        "id": row.topic_id,
        "slug": row.slug,
        "name": row.name,
        "description": row.topic_description,
        "summary": row.topic_summary,
        "category": {"id": row.category_id, "slug": row.category_slug, "name": row.category_name},
        "trend_score": round(row.trend_score, 4),
        "growth_rate": round(row.growth_rate, 4),
        "growth_percent": row.growth_percent,
        "current_count": row.current_count,
        "previous_count": row.previous_count,
        "volume_share": round(row.volume_share, 4),
        "status": row.status,
        "is_emerging": row.is_emerging,
        "snapshot_date": row.snapshot_date.isoformat(),
        "window_days": row.window_days,
    }

