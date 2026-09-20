"""Trend engine tests: counting, grouping, normalization and idempotency (spec 16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, TrendSnapshot, TrendStatus
from app.services import topics as topic_service
from app.trend import engine

from .conftest import days_ago, link, make_article, topic_by_name


def _add(db: Session, topic, category: Category, count: int, days: int, prefix: str) -> None:
    for index in range(count):
        article = make_article(
            db,
            title=f"{prefix} {index}",
            url=f"https://example.test/{prefix}-{index}",
            published_at=days_ago(days, hours=1 + (index % 20)),
            category=category,
        )
        link(article, topic)
    db.flush()


class TestScoreTopics:
    def test_growth_uses_the_current_and_previous_windows(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        category = categories["ai"]

        _add(db, topic, category, 10, 3, "current")
        _add(db, topic, category, 5, 10, "previous")
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        score = next(item for item in scores if item.topic_id == topic.id)

        assert score.current_count == 10
        assert score.previous_count == 5
        assert score.growth_rate == pytest.approx(1.0)
        assert score.status == TrendStatus.GROWING.value

    def test_topics_without_articles_are_still_scored(self, db, categories):
        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        names = {item.topic_id for item in scores}
        assert len(scores) == len(names) > 0
        assert all(item.current_count == 0 for item in scores)

    def test_article_outside_both_windows_is_ignored(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        _add(db, topic, categories["ai"], 3, 30, "old")
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        score = next(item for item in scores if item.topic_id == topic.id)

        assert score.current_count == 0
        assert score.previous_count == 0

    def test_new_topic_is_emerging_and_capped(self, db, categories):
        topic = topic_by_name(db, "Biotech")
        _add(db, topic, categories["health"], 8, 2, "new")
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        score = next(item for item in scores if item.topic_id == topic.id)

        assert score.is_emerging is True
        assert score.status == TrendStatus.EMERGING.value
        assert score.growth_rate <= 3.0

    def test_declining_topic_loses_volume(self, db, categories):
        topic = topic_by_name(db, "Startup Funding")
        _add(db, topic, categories["finance"], 8, 10, "before")
        _add(db, topic, categories["finance"], 1, 2, "now")
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        score = next(item for item in scores if item.topic_id == topic.id)

        assert score.current_count == 1
        assert score.previous_count == 8
        assert score.growth_rate < 0
        assert score.status == TrendStatus.DECLINING.value

    def test_the_busiest_topic_gets_full_volume_share(self, db, categories):
        busy = topic_by_name(db, "AI Agents")
        quiet = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 12, 2, "busy")
        _add(db, quiet, categories["ai"], 2, 2, "quiet")
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        volume = {item.topic_id: item.volume_share for item in scores}

        assert volume[busy.id] == pytest.approx(1.0)
        assert volume[quiet.id] == pytest.approx(2 / 12)

    def test_article_linked_twice_is_counted_once(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        article = make_article(
            db,
            title="Duplicate link",
            url="https://example.test/dupe",
            published_at=days_ago(1),
            category=categories["ai"],
        )
        db.flush()

        # The topic service is the only writer of article/topic links and must be
        # idempotent, because re-ingesting a feed re-runs classification.
        assert topic_service.link_article(db, article.id, topic.id, 0.9) is True
        assert topic_service.link_article(db, article.id, topic.id, 0.9) is False
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        score = next(item for item in scores if item.topic_id == topic.id)
        assert score.current_count == 1

    def test_score_stays_within_bounds(self, db, categories):
        for name, count, days in (("AI Agents", 40, 1), ("AI Policy", 2, 6)):
            _add(db, topic_by_name(db, name), categories["ai"], count, days, name.replace(" ", ""))
        db.commit()

        scores = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        assert all(0.0 <= item.trend_score <= 1.0 for item in scores)

    def test_windowing_is_configurable(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        _add(db, topic, categories["ai"], 4, 20, "wide")
        db.commit()

        narrow = engine.score_topics(db, datetime.now(UTC).date(), window_days=7)
        wide = engine.score_topics(db, datetime.now(UTC).date(), window_days=30)

        assert next(i for i in narrow if i.topic_id == topic.id).current_count == 0
        assert next(i for i in wide if i.topic_id == topic.id).current_count == 4


class TestRecalculate:
    def test_writes_one_snapshot_per_topic(self, db, categories):
        db.commit()
        before = db.execute(select(func.count(TrendSnapshot.id))).scalar_one()

        result = engine.recalculate(db, snapshot_date=datetime.now(UTC).date(), days_back=1)

        after = db.execute(select(func.count(TrendSnapshot.id))).scalar_one()
        assert result.snapshots_written > 0
        assert after == before + result.snapshots_written
        assert result.topics_scored > 0

    def test_recalculation_is_idempotent(self, db, categories):
        db.commit()
        day = datetime.now(UTC).date()

        engine.recalculate(db, snapshot_date=day, days_back=1)
        first = db.execute(select(func.count(TrendSnapshot.id))).scalar_one()

        engine.recalculate(db, snapshot_date=day, days_back=1)
        second = db.execute(select(func.count(TrendSnapshot.id))).scalar_one()

        assert first == second

    def test_rescoring_updates_the_existing_row(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        _add(db, topic, categories["ai"], 2, 2, "first")
        db.commit()
        day = datetime.now(UTC).date()

        engine.recalculate(db, snapshot_date=day, days_back=1)
        _add(db, topic, categories["ai"], 6, 3, "second")
        db.commit()
        engine.recalculate(db, snapshot_date=day, days_back=1)

        snapshot = db.execute(
            select(TrendSnapshot).where(TrendSnapshot.topic_id == topic.id)
        ).scalars().one()
        assert snapshot.current_count == 8
        assert db.execute(select(func.count(TrendSnapshot.id))).scalar_one() > 0

    def test_backfilling_history_creates_one_row_per_day(self, db, categories):
        db.commit()
        day = datetime.now(UTC).date()

        result = engine.recalculate(db, snapshot_date=day, days_back=5)

        assert len(result.dates_processed) == 5
        dates = db.execute(select(func.distinct(TrendSnapshot.snapshot_date))).scalars().all()
        assert len(dates) == 5

    def test_single_topic_recalculation(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        db.commit()

        result = engine.recalculate(
            db, snapshot_date=datetime.now(UTC).date(), days_back=1, topic_ids=[topic.id]
        )

        rows = db.execute(select(TrendSnapshot.topic_id)).scalars().all()
        assert set(rows) == {topic.id}
        assert result.topics_scored == 1

    def test_snapshots_are_ordered_in_time(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        _add(db, topic, categories["ai"], 1, 20, "historic")
        _add(db, topic, categories["ai"], 8, 1, "recent")
        db.commit()
        day = datetime.now(UTC).date()

        engine.recalculate(db, snapshot_date=day, days_back=20)

        snapshots = list(
            db.execute(
                select(TrendSnapshot)
                .where(TrendSnapshot.topic_id == topic.id)
                .order_by(TrendSnapshot.snapshot_date)
            ).scalars()
        )
        assert len(snapshots) == 20

        # Backfilled history must reflect the article timeline as it moves forward:
        # early days mostly see neither article set, while the final day sees the whole
        # recent burst. That shape is what makes the 30-day chart meaningful.
        counts = [snapshot.current_count for snapshot in snapshots]
        assert snapshots[0].snapshot_date == day - timedelta(days=19)
        assert snapshots[-1].snapshot_date == day
        assert counts[-1] == 8
        assert counts[-1] > counts[0]
        assert min(counts) == 0