"""Seeding tests (spec 17, R13).

The important guarantee is that seeded history comes from the real trend engine, so
these tests score the seeded data and assert the resulting series behaves like a trend
rather than just checking row counts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Article, ArticleTopic, Category, Topic, TrendSnapshot
from app.services import seed as seed_service


class TestSeedAll:
    def test_creates_the_five_categories(self, db: Session):
        seed_service.seed_all(db, article_days=20, history_days=5)
        assert db.execute(select(func.count(Category.id))).scalar_one() == 5

    def test_creates_the_topic_vocabulary_plus_fallbacks(self, db: Session):
        result = seed_service.seed_all(db, article_days=20, history_days=5)

        assert result.topics_curated == 20
        assert result.topics_fallback == 5
        assert result.topics == 25

        fallbacks = db.execute(
            select(func.count(Topic.id)).where(Topic.is_fallback.is_(True))
        ).scalar_one()
        assert fallbacks == 5

    def test_installs_the_default_sources(self, db: Session):
        result = seed_service.seed_all(db, article_days=20, history_days=5)
        assert result.sources > 0

    def test_generates_articles_with_topic_links(self, db: Session):
        result = seed_service.seed_all(db, article_days=60, history_days=5)

        assert result.articles > 100
        assert db.execute(select(func.count(Article.id))).scalar_one() == result.articles

        # Every seeded article must be attached to a topic, or it can never be counted.
        unlinked = db.execute(
            select(func.count(Article.id)).where(
                ~Article.id.in_(select(ArticleTopic.article_id))
            )
        ).scalar_one()
        assert unlinked == 0

    def test_default_volume_matches_the_specification(self, db: Session):
        # The specification asks for 100-500 seeded articles.
        result = seed_service.seed_all(db)
        assert 100 <= result.articles <= 500

    def test_every_topic_has_recent_activity(self, db: Session):
        # A topic with no articles in the current window would make the dashboard look
        # broken, so the generator guarantees coverage of the last 7 days.
        seed_service.seed_all(db)

        cutoff = datetime.now(UTC) - timedelta(days=7)
        recent = db.execute(
            select(func.count(func.distinct(ArticleTopic.topic_id)))
            .join(Article, Article.id == ArticleTopic.article_id)
            .where(Article.published_at >= cutoff)
            .join(Topic, Topic.id == ArticleTopic.topic_id)
            .where(Topic.is_fallback.is_(False))
        ).scalar_one()

        assert recent == 20

    def test_articles_span_whole_comparison_windows(self, db: Session):
        # Article history is generated in whole window-length blocks, because that
        # alignment is what makes a topic's momentum equal its measured growth. A 30-day
        # request therefore covers four full 7-day windows, not 30 arbitrary days.
        seed_service.seed_all(db, article_days=30, history_days=5, window_days=7)

        oldest, newest = db.execute(
            select(func.min(Article.published_at), func.max(Article.published_at))
        ).one()
        span_days = (newest - oldest).days

        expected_blocks = 30 // 7
        assert span_days >= (expected_blocks - 1) * 7
        assert span_days <= expected_blocks * 7

    def test_seeded_history_comes_from_the_real_engine(self, db: Session):
        result = seed_service.seed_all(db, article_days=40, history_days=10)

        assert result.history_days == 10
        assert result.snapshots > 0

        distinct_dates = db.execute(
            select(func.count(func.distinct(TrendSnapshot.snapshot_date)))
        ).scalar_one()
        assert distinct_dates == 10

    def test_seeded_snapshots_are_internally_consistent(self, db: Session):
        seed_service.seed_all(db, article_days=40, history_days=10)

        snapshots = list(db.execute(select(TrendSnapshot)).scalars())
        assert snapshots

        for snapshot in snapshots:
            assert snapshot.current_count >= 0
            assert snapshot.previous_count >= 0
            assert 0.0 <= snapshot.trend_score <= 1.0
            assert 0.0 <= snapshot.volume_share <= 1.0
            assert snapshot.status in {"emerging", "growing", "stable", "declining"}

    def test_seeded_growth_matches_the_declared_momentum(self, db: Session):
        # The generator applies each topic's momentum to the current window and leaves
        # every earlier window at baseline, so the engine must report a growth rate
        # close to `momentum - 1`. This is what makes the demo charts meaningful rather
        # than arbitrary noise, and it is the property the whole layout depends on.
        seed_service.seed_all(db)

        latest_date = db.execute(select(func.max(TrendSnapshot.snapshot_date))).scalar_one()
        rows = db.execute(
            select(Topic.name, TrendSnapshot.status, TrendSnapshot.growth_rate).join(
                TrendSnapshot, TrendSnapshot.topic_id == Topic.id
            ).where(TrendSnapshot.snapshot_date == latest_date)
        ).all()

        assert rows
        by_name = {name: (status, growth) for name, status, growth in rows}

        # Highest momentum topic: strongly growing, well above the threshold.
        agents_status, agents_growth = by_name["AI Agents"]
        assert agents_status == "growing"
        assert agents_growth > 1.0

        # Momentum below 1.0 with a non-empty previous window: declining.
        funding_status, funding_growth = by_name["Startup Funding"]
        assert funding_status == "declining"
        assert funding_growth < -0.2

        # Momentum of exactly 1.0: no change, so stable.
        console_status, console_growth = by_name["Console Hardware"]
        assert console_status == "stable"
        assert abs(console_growth) < 0.2

    def test_seeded_history_contains_score_movement(self, db: Session):
        # A flat history would make the trend charts look broken.
        seed_service.seed_all(db)

        topic = db.execute(select(Topic).where(Topic.slug == "ai-agents")).scalar_one()
        scores = db.execute(
            select(TrendSnapshot.trend_score)
            .where(TrendSnapshot.topic_id == topic.id)
            .order_by(TrendSnapshot.snapshot_date)
        ).scalars().all()

        assert len(scores) == 30
        assert max(scores) > min(scores)

    def test_history_contains_more_than_one_status(self, db: Session):
        # A healthy demo dataset exercises several branches of the status logic.
        seed_service.seed_all(db, article_days=60, history_days=30)

        statuses = set(db.execute(select(func.distinct(TrendSnapshot.status))).scalars())
        assert len(statuses) >= 2

    def test_summaries_are_generated_offline(self, db: Session):
        seed_service.seed_all(db, article_days=40, history_days=5)

        with_summary = db.execute(
            select(func.count(Topic.id)).where(Topic.summary.is_not(None))
        ).scalar_one()
        assert with_summary > 0


class TestIdempotency:
    def test_running_twice_does_not_duplicate(self, db: Session):
        first = seed_service.seed_all(db, article_days=20, history_days=5)
        articles_after_first = db.execute(select(func.count(Article.id))).scalar_one()

        second = seed_service.seed_all(db, article_days=20, history_days=5)
        articles_after_second = db.execute(select(func.count(Article.id))).scalar_one()

        assert first.articles > 0
        assert second.articles == 0
        assert articles_after_first == articles_after_second

    def test_reset_rebuilds_the_dataset(self, db: Session):
        seed_service.seed_all(db, article_days=20, history_days=5)
        before = db.execute(select(func.count(Article.id))).scalar_one()

        result = seed_service.seed_all(db, article_days=20, history_days=5, reset=True)
        after = db.execute(select(func.count(Article.id))).scalar_one()

        assert result.articles > 0
        assert after == before

    def test_seed_is_deterministic_for_a_fixed_rng_seed(self, db: Session):
        seed_service.seed_all(db, article_days=20, history_days=5, rng_seed=1234)
        first_titles = db.execute(
            select(Article.title).order_by(Article.id).limit(50)
        ).scalars().all()

        seed_service.seed_all(db, article_days=20, history_days=5, rng_seed=1234, reset=True)
        second_titles = db.execute(
            select(Article.title).order_by(Article.id).limit(50)
        ).scalars().all()

        assert first_titles == second_titles


class TestSeedSummary:
    def test_reports_row_counts(self, db: Session):
        seed_service.seed_all(db, article_days=20, history_days=5)
        summary = seed_service.seed_summary(db)

        assert summary["categories"] == 5
        assert summary["topics"] == 25
        assert summary["articles"] > 0
        assert summary["snapshots"] > 0
