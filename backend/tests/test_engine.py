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


class _EmptyScalars:
    def scalars(self):
        return []


class _StaleReadSession:
    """A session proxy that reports no existing snapshot rows.

    This is the precise state of the losing writer in the reported race: it had already
    read the conflicting key as absent before the winning writer committed. Everything
    else is delegated to the real session, so the write path runs unchanged.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def execute(self, statement, *args, **kwargs):
        text = str(statement)
        if text.lstrip().upper().startswith("SELECT") and "trend_snapshots" in text:
            return _EmptyScalars()
        return self._session.execute(statement, *args, **kwargs)


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


class TestScopedRunsUseThePopulationDenominator:
    """Regression tests for the scoped-run volume inflation bug (finding #3).

    `topic_ids` must scope only which topics are scored and written. The volume
    denominator stays the busiest topic of the whole population, otherwise a run scoped
    to one topic would compute `volume_share = 1.0` and upsert that inflated value over
    the correct full-run snapshot.
    """

    def test_scoped_run_matches_the_full_run(self, db, categories):
        busy = topic_by_name(db, "AI Agents")
        target = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 10, 2, "busy-parity")
        _add(db, target, categories["ai"], 4, 2, "target-parity")
        _add(db, target, categories["ai"], 2, 10, "target-parity-prev")
        db.commit()
        day = datetime.now(UTC).date()

        full = next(
            item
            for item in engine.score_topics(db, day, window_days=7)
            if item.topic_id == target.id
        )
        scoped = next(
            item
            for item in engine.score_topics(db, day, window_days=7, topic_ids=[target.id])
            if item.topic_id == target.id
        )

        assert scoped.volume_share == pytest.approx(full.volume_share)
        assert scoped.trend_score == pytest.approx(full.trend_score)

    def test_scoped_run_does_not_inflate_a_quiet_topic(self, db, categories):
        busy = topic_by_name(db, "AI Agents")
        quiet = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 10, 2, "busy-inflate")
        _add(db, quiet, categories["ai"], 2, 2, "quiet-inflate")
        db.commit()

        scoped = next(
            item
            for item in engine.score_topics(
                db, datetime.now(UTC).date(), window_days=7, topic_ids=[quiet.id]
            )
            if item.topic_id == quiet.id
        )

        # On the buggy code the denominator was the scoped max (2), forcing 1.0.
        assert scoped.volume_share < 1.0

    def test_denominator_is_the_population_max(self, db, categories):
        busy = topic_by_name(db, "AI Agents")
        quiet = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 12, 2, "busy-denominator")
        _add(db, quiet, categories["ai"], 3, 2, "quiet-denominator")
        db.commit()

        scoped = next(
            item
            for item in engine.score_topics(
                db, datetime.now(UTC).date(), window_days=7, topic_ids=[quiet.id]
            )
            if item.topic_id == quiet.id
        )

        assert scoped.current_count == 3
        assert scoped.volume_share == pytest.approx(3 / 12)

    def test_scoped_recalculation_only_writes_the_requested_topic(self, db, categories):
        busy = topic_by_name(db, "AI Agents")
        other = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 5, 2, "busy-write")
        _add(db, other, categories["ai"], 5, 2, "other-write")
        db.commit()

        result = engine.recalculate(
            db, snapshot_date=datetime.now(UTC).date(), days_back=1, topic_ids=[busy.id]
        )

        assert result.topics_scored == 1
        written = set(db.execute(select(TrendSnapshot.topic_id)).scalars().all())
        assert written == {busy.id}

    def test_scoped_recalculation_does_not_overwrite_the_full_run_snapshot(
        self, db, categories
    ):
        busy = topic_by_name(db, "AI Agents")
        target = topic_by_name(db, "AI Policy")
        _add(db, busy, categories["ai"], 10, 2, "busy-persist")
        _add(db, target, categories["ai"], 4, 2, "target-persist")
        _add(db, target, categories["ai"], 2, 10, "target-persist-prev")
        db.commit()
        day = datetime.now(UTC).date()

        def _snapshot() -> TrendSnapshot:
            return db.execute(
                select(TrendSnapshot).where(
                    TrendSnapshot.topic_id == target.id,
                    TrendSnapshot.snapshot_date == day,
                    TrendSnapshot.window_days == 7,
                )
            ).scalars().one()

        engine.recalculate(db, snapshot_date=day, days_back=1)
        full_volume = _snapshot().volume_share
        full_score = _snapshot().trend_score

        engine.recalculate(db, snapshot_date=day, days_back=1, topic_ids=[target.id])
        db.expire_all()
        rescored = _snapshot()

        assert rescored.volume_share == pytest.approx(full_volume)
        assert rescored.trend_score == pytest.approx(full_score)


class TestSnapshotUpsertIsAtomic:
    """Regression tests for the non-atomic snapshot write (finding: concurrent runs).

    `persist_snapshots` used to read the existing rows and insert the keys it believed
    were missing. Two overlapping runs (the 6-hourly job vs a manual recalculation, or a
    second replica) could both observe a key as absent, both INSERT, and the second one
    raised `IntegrityError` on `uq_snapshot_topic_date_window`. These tests pin the
    atomic `INSERT ... ON CONFLICT DO UPDATE` replacement.
    """

    def test_conflicting_insert_does_not_raise_and_keeps_one_row(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        day = datetime.now(UTC).date()

        # A row for the same key already exists when the recalculation starts, which is
        # exactly the state the losing writer saw before it tried to INSERT.
        db.add(
            TrendSnapshot(
                topic_id=topic.id,
                snapshot_date=day,
                window_days=7,
                current_count=0,
                previous_count=0,
                growth_rate=0.0,
                volume_share=0.0,
                trend_score=0.0,
                status=TrendStatus.STABLE.value,
                is_emerging=False,
            )
        )
        db.commit()

        _add(db, topic, categories["ai"], 6, 2, "conflict")
        db.commit()

        # Must not raise IntegrityError, despite the pre-existing conflicting row.
        engine.recalculate(db, snapshot_date=day, days_back=1)
        db.expire_all()

        rows = (
            db.execute(
                select(TrendSnapshot).where(
                    TrendSnapshot.topic_id == topic.id,
                    TrendSnapshot.snapshot_date == day,
                    TrendSnapshot.window_days == 7,
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].current_count == 6

    def test_upsert_updates_rather_than_duplicates(self, db, categories):
        topic = topic_by_name(db, "AI Agents")
        day = datetime.now(UTC).date()
        category_id = categories["ai"].id
        window_days = 7

        def score(current_count: int) -> engine.TopicScore:
            return engine.TopicScore(
                topic_id=topic.id,
                category_id=category_id,
                current_count=current_count,
                previous_count=1,
                growth_rate=0.5,
                volume_share=0.5,
                trend_score=0.5,
                status=TrendStatus.GROWING.value,
                is_emerging=False,
            )

        engine.persist_snapshots(db, [score(1)], day, window_days)
        db.commit()
        # The second write of the same key must overwrite, not add a second row.
        written = engine.persist_snapshots(db, [score(9)], day, window_days)
        db.commit()
        db.expire_all()

        rows = (
            db.execute(
                select(TrendSnapshot).where(
                    TrendSnapshot.topic_id == topic.id,
                    TrendSnapshot.snapshot_date == day,
                    TrendSnapshot.window_days == window_days,
                )
            )
            .scalars()
            .all()
        )
        assert written == 1
        assert len(rows) == 1
        assert rows[0].current_count == 9

    def test_a_stale_writer_is_resolved_by_the_database(self, db, categories):
        # A deterministic reproduction of the reported race. The losing writer is the
        # state where a session has already observed the key as absent before the winning
        # writer committed. `_StaleReadSession` forces exactly that observation, so on the
        # old read-then-insert code the subsequent INSERT collides and raises
        # IntegrityError; the atomic upsert routes it through ON CONFLICT DO UPDATE.
        topic = topic_by_name(db, "AI Agents")
        day = datetime.now(UTC).date()
        category_id = categories["ai"].id

        def score(current_count: int) -> engine.TopicScore:
            return engine.TopicScore(
                topic_id=topic.id,
                category_id=category_id,
                current_count=current_count,
                previous_count=0,
                growth_rate=1.0,
                volume_share=1.0,
                trend_score=0.7,
                status=TrendStatus.GROWING.value,
                is_emerging=False,
            )

        # The winning writer lands its row first.
        engine.persist_snapshots(db, [score(5)], day, 7)
        db.commit()

        stale = _StaleReadSession(db)
        # Must not raise IntegrityError (the pre-fix code did) and must not duplicate.
        engine.persist_snapshots(stale, [score(999)], day, 7)
        db.commit()
        db.expire_all()

        rows = (
            db.execute(
                select(TrendSnapshot).where(
                    TrendSnapshot.topic_id == topic.id,
                    TrendSnapshot.snapshot_date == day,
                    TrendSnapshot.window_days == 7,
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].current_count == 999

