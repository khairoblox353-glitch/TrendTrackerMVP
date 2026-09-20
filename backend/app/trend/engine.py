"""Trend engine: turns stored articles into trend snapshots (spec 7, spec 9).

This module orchestrates the pure math in `app.trend.scoring` against the database.
It imports nothing from `app.ai`: the LLM must never influence a Trend Score
(spec 19.8).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.config import settings as default_settings
from app.models import Article, ArticleTopic, Topic, TrendSnapshot
from app.models.types import utcnow
from app.trend import scoring
from app.trend.windows import resolve_window, trailing_dates


@dataclass(slots=True)
class TopicScore:
    """One computed row, before it is persisted."""

    topic_id: int
    category_id: int
    current_count: int
    previous_count: int
    growth_rate: float
    volume_share: float
    trend_score: float
    status: str
    is_emerging: bool


@dataclass(slots=True)
class RecalculationResult:
    snapshot_date: date
    window_days: int
    dates_processed: list[date] = field(default_factory=list)
    snapshots_written: int = 0
    topics_scored: int = 0
    emerging_topics: int = 0

    def as_dict(self) -> dict:
        return {
            "snapshot_date": self.snapshot_date.isoformat(),
            "window_days": self.window_days,
            "dates_processed": [day.isoformat() for day in self.dates_processed],
            "snapshots_written": self.snapshots_written,
            "topics_scored": self.topics_scored,
            "emerging_topics": self.emerging_topics,
        }


def _count_articles_by_topic(
    db: Session,
    start,
    end,
    topic_ids: Sequence[int] | None = None,
) -> dict[int, int]:
    """Article counts per topic inside `[start, end)`.

    Counts distinct articles because a topic can be linked to an article more than
    once in theory, and a duplicate link must not inflate a trend.
    """
    statement = (
        select(ArticleTopic.topic_id, func.count(func.distinct(ArticleTopic.article_id)))
        .join(Article, Article.id == ArticleTopic.article_id)
        .where(Article.published_at >= start, Article.published_at < end)
        .group_by(ArticleTopic.topic_id)
    )
    if topic_ids:
        statement = statement.where(ArticleTopic.topic_id.in_(topic_ids))

    return dict(db.execute(statement).all())


def score_topics(
    db: Session,
    snapshot_date: date,
    window_days: int | None = None,
    topic_ids: Sequence[int] | None = None,
    config: Settings | None = None,
) -> list[TopicScore]:
    """Compute a score for every topic (or the given subset) on one date.

    Volume normalization uses the busiest topic of *this* run as its denominator, so
    scores from different dates stay comparable (R6).
    """
    config = config or default_settings
    window_days = window_days or config.trend_window_days
    window = resolve_window(snapshot_date, window_days)

    topics = list(
        db.execute(
            select(Topic)
            .where(Topic.id.in_(topic_ids) if topic_ids else True)
            .order_by(Topic.id)
        ).scalars()
    )
    if not topics:
        return []

    ids = [topic.id for topic in topics]
    current_counts = _count_articles_by_topic(db, window.current_start, window.current_end, ids)
    previous_counts = _count_articles_by_topic(db, window.previous_start, window.previous_end, ids)

    max_current = max((current_counts.get(topic_id, 0) for topic_id in ids), default=0)

    scores: list[TopicScore] = []
    for topic in topics:
        current = current_counts.get(topic.id, 0)
        previous = previous_counts.get(topic.id, 0)

        growth = scoring.growth_rate(
            current,
            previous,
            cap=config.emerging_growth_cap,
            floor=config.growth_floor,
        )
        normalized_growth = scoring.normalize_growth(
            growth.growth_rate, saturation=config.growth_saturation
        )
        volume_share = scoring.normalize_volume(current, max_current)
        score = scoring.trend_score(
            normalized_growth,
            volume_share,
            weight_growth=config.weight_growth,
            weight_volume=config.weight_volume,
        )
        status = scoring.classify_status(
            growth.growth_rate,
            is_emerging=growth.is_emerging,
            growing_threshold=config.growing_threshold,
            declining_threshold=config.declining_threshold,
        )

        scores.append(
            TopicScore(
                topic_id=topic.id,
                category_id=topic.category_id,
                current_count=current,
                previous_count=previous,
                growth_rate=growth.growth_rate,
                volume_share=volume_share,
                trend_score=score,
                status=status.value,
                is_emerging=growth.is_emerging,
            )
        )

    return scores


def persist_snapshots(
    db: Session, scores: Iterable[TopicScore], snapshot_date: date, window_days: int
) -> int:
    """Upsert scores into `trend_snapshots`. Returns the number of rows written.

    Upserting (rather than inserting) makes recalculation safe to run repeatedly and
    is what the `uq_snapshot_topic_date_window` constraint enforces at the DB level.
    """
    scores = list(scores)
    if not scores:
        return 0

    existing = {
        snapshot.topic_id: snapshot
        for snapshot in db.execute(
            select(TrendSnapshot).where(
                TrendSnapshot.snapshot_date == snapshot_date,
                TrendSnapshot.window_days == window_days,
                TrendSnapshot.topic_id.in_([score.topic_id for score in scores]),
            )
        ).scalars()
    }

    written = 0
    for score in scores:
        snapshot = existing.get(score.topic_id)
        if snapshot is None:
            snapshot = TrendSnapshot(topic_id=score.topic_id)
            db.add(snapshot)

        snapshot.snapshot_date = snapshot_date
        snapshot.window_days = window_days
        snapshot.current_count = score.current_count
        snapshot.previous_count = score.previous_count
        snapshot.growth_rate = score.growth_rate
        snapshot.volume_share = score.volume_share
        snapshot.trend_score = score.trend_score
        snapshot.status = score.status
        snapshot.is_emerging = score.is_emerging
        written += 1

    db.flush()
    return written


def recalculate(
    db: Session,
    snapshot_date: date | None = None,
    window_days: int | None = None,
    days_back: int = 1,
    topic_ids: Sequence[int] | None = None,
    config: Settings | None = None,
) -> RecalculationResult:
    """Score the trailing `days_back` days and upsert one snapshot per day.

    `days_back=1` is what the 6-hourly job calls. A larger value rebuilds history using
    the same production code path, which is how seed data is generated (R13).
    """
    config = config or default_settings
    window_days = window_days or config.trend_window_days
    snapshot_date = snapshot_date or utcnow().date()

    result = RecalculationResult(snapshot_date=snapshot_date, window_days=window_days)
    latest_scores: list[TopicScore] = []

    for day in trailing_dates(snapshot_date, days_back):
        scores = score_topics(db, day, window_days, topic_ids, config)
        if not scores:
            continue
        result.snapshots_written += persist_snapshots(db, scores, day, window_days)
        result.dates_processed.append(day)
        latest_scores = scores

    result.topics_scored = len(latest_scores)
    result.emerging_topics = sum(1 for score in latest_scores if score.is_emerging)
    db.commit()
    return result
