"""Ingestion pipeline tests: validation, deduplication and LLM failure (spec 15, spec 16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import ClassificationResult, Classifier
from app.collectors.base import CollectorError, FetchResult, RawArticle
from app.models import Article, ArticleTopic, ProcessingStatus, Source
from app.services import ingestion

from .conftest import AlwaysFailingClassifier, days_ago, make_article, topic_by_name


def raw(title: str, url: str, days: int = 1, description: str | None = None) -> RawArticle:
    return RawArticle(
        title=title,
        url=url,
        description=description,
        published_at=datetime.now(UTC) - timedelta(days=days, hours=2),
    )


class TestNormalizeForStorage:
    def test_accepts_a_well_formed_item(self):
        payload, warning = ingestion.normalize_for_storage(raw("Good", "https://example.test/1"))
        assert payload is not None
        assert payload["title"] == "Good"
        assert warning is None

    def test_rejects_a_missing_title(self):
        payload, warning = ingestion.normalize_for_storage(raw("   ", "https://example.test/2"))
        assert payload is None
        assert "title" in warning

    def test_rejects_a_non_http_url(self):
        payload, warning = ingestion.normalize_for_storage(raw("Title", "javascript:alert(1)"))
        assert payload is None
        assert "url" in warning

    def test_missing_date_falls_back_to_now(self):
        item = RawArticle(title="No date", url="https://example.test/3")
        payload, warning = ingestion.normalize_for_storage(item)
        assert payload is not None
        assert payload["published_at"] is not None
        assert "date" in warning

    def test_future_date_is_clamped(self):
        item = RawArticle(
            title="From the future",
            url="https://example.test/4",
            published_at=datetime.now(UTC) + timedelta(days=3),
        )
        payload, warning = ingestion.normalize_for_storage(item)
        assert payload["published_at"] <= datetime.now(UTC) + timedelta(seconds=5)
        assert "future" in warning

    def test_very_old_item_is_skipped(self):
        item = RawArticle(
            title="Ancient",
            url="https://example.test/5",
            published_at=datetime.now(UTC) - timedelta(days=800),
        )
        payload, warning = ingestion.normalize_for_storage(item)
        assert payload is None
        assert "older" in warning

    def test_description_whitespace_is_collapsed(self):
        payload, _ = ingestion.normalize_for_storage(
            raw("Titled", "https://example.test/6", description="  lots   of\n\nspace  ")
        )
        assert payload["description"] == "lots of space"


class TestSaveArticles:
    def test_stores_new_articles(self, db: Session, source: Source):
        created, duplicates, skipped, warnings = ingestion.save_articles(
            db, source, [raw("A", "https://example.test/a"), raw("B", "https://example.test/b")]
        )
        assert len(created) == 2
        assert duplicates == 0
        assert skipped == 0
        assert warnings == []
        assert db.execute(select(func.count(Article.id))).scalar_one() == 2

    def test_duplicate_urls_inside_one_batch_are_dropped(self, db: Session, source: Source):
        created, duplicates, skipped, _ = ingestion.save_articles(
            db, source, [raw("A", "https://example.test/same"), raw("A copy", "https://example.test/same")]
        )
        assert len(created) == 1
        assert skipped == 1
        assert duplicates == 0

    def test_urls_already_in_the_database_are_duplicates(self, db: Session, source: Source):
        ingestion.save_articles(db, source, [raw("First", "https://example.test/known")])
        db.commit()

        created, duplicates, _, _ = ingestion.save_articles(
            db, source, [raw("First again", "https://example.test/known")]
        )
        assert created == []
        assert duplicates == 1
        assert db.execute(select(func.count(Article.id))).scalar_one() == 1

    def test_invalid_items_are_skipped_not_fatal(self, db: Session, source: Source):
        created, _, skipped, warnings = ingestion.save_articles(
            db,
            source,
            [
                raw("Good", "https://example.test/good"),
                raw("", "https://example.test/no-title"),
                raw("Bad url", "not-a-url"),
            ],
        )
        assert len(created) == 1
        assert skipped == 2
        assert len(warnings) == 2

    def test_storage_failure_is_sanitized(self, db: Session, source: Source, monkeypatch):
        # The exception text from a real PostgreSQL constraint violation contains the
        # generated INSERT, the column names and the bound parameter values. This warning
        # is returned by POST /api/ingestion/run, so only a generic message may survive.
        leak = (
            "INSERT INTO articles (title, url, published_at) "
            "VALUES (...) [parameters: ('Doomed', 'https://example.test/doomed')]"
        )

        def explode(_article):
            raise RuntimeError(leak)

        # SQLite does not enforce VARCHAR(1000), so the real failure cannot be reproduced
        # here. Making `Session.add` raise lands on the same per-article failure branch the
        # nested savepoint takes on PostgreSQL.
        monkeypatch.setattr(db, "add", explode, raising=False)

        created, _, skipped, warnings = ingestion.save_articles(
            db, source, [raw("Doomed", "https://example.test/doomed")]
        )

        assert created == []
        assert skipped == 1
        assert warnings == ["storage failure"]
        for warning in warnings:
            assert leak not in warning
            for internal in ("INSERT", "SELECT", "articles", "RuntimeError"):
                assert internal not in warning


class TestClassifyArticle:
    def test_links_a_confident_article_to_a_topic(
        self, db: Session, source: Source, categories, keyword_classifier: Classifier
    ):
        article = make_article(
            db,
            title="New AI agent framework ships for autonomous tool use",
            url="https://example.test/agent",
            published_at=days_ago(1),
            category=None,
            status=ProcessingStatus.PENDING.value,
        )
        lookup = {category.name.lower(): category for category in categories.values()}

        ok = ingestion.classify_article(db, article, keyword_classifier, lookup)
        db.commit()

        assert ok is True
        assert article.processing_status == ProcessingStatus.CLASSIFIED.value
        assert article.category_id == categories["ai"].id
        assert article.summary is not None

        linked = db.execute(
            select(ArticleTopic.topic_id).where(ArticleTopic.article_id == article.id)
        ).scalars().all()
        assert linked

    def test_low_confidence_lands_in_the_fallback_topic(
        self, db: Session, source: Source, categories
    ):
        class UnsureClassifier(Classifier):
            name = "unsure"

            def classify(self, title, description=None):
                return ClassificationResult(
                    category="AI", topic="Something Very Specific", confidence=0.10
                )

        article = make_article(
            db,
            title="Ambiguous item",
            url="https://example.test/unsure",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        lookup = {category.name.lower(): category for category in categories.values()}

        assert ingestion.classify_article(db, article, UnsureClassifier(), lookup) is True
        db.commit()

        linked = db.execute(
            select(ArticleTopic.topic_id).where(ArticleTopic.article_id == article.id)
        ).scalars().all()
        other = topic_by_name(db, "Other", category_slug="ai")

        assert linked == [other.id]
        assert article.processing_status == ProcessingStatus.CLASSIFIED.value

    def test_llm_failure_keeps_the_article_and_flags_it(
        self, db: Session, source: Source, categories, failing_classifier
    ):
        article = make_article(
            db,
            title="Article that the LLM cannot classify",
            url="https://example.test/failing",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        lookup = {category.name.lower(): category for category in categories.values()}

        ok = ingestion.classify_article(db, article, failing_classifier, lookup)
        db.commit()

        assert ok is False
        assert failing_classifier.calls == 1
        assert article.processing_status == ProcessingStatus.FAILED.value
        assert "simulated LLM outage" in (article.processing_error or "")
        # The article is still stored: AI failure must not lose data (spec 15).
        assert db.execute(select(func.count(Article.id))).scalar_one() == 1

    def test_an_unmatched_article_uses_the_source_category_hint(
        self, db: Session, source: Source, categories, keyword_classifier
    ):
        # Regression: `ClassificationResult.fallback()` used to name the first category,
        # so every article the offline classifier could not match was filed under AI —
        # including health and gaming articles. The source's hint must win instead.
        health_source = Source(
            name="Health Feed",
            url="https://health.example.test",
            feed_url="https://health.example.test/feed",
            category_id=categories["health"].id,
        )
        db.add(health_source)
        db.commit()

        article = make_article(
            db,
            title="Opinion: More young men are coming to me for plastic surgery",
            url="https://example.test/unmatched",
            published_at=days_ago(1),
            source=health_source,
            status=ProcessingStatus.PENDING.value,
        )
        db.commit()

        lookup = {category.name.lower(): category for category in categories.values()}
        assert ingestion.classify_article(db, article, keyword_classifier, lookup) is True
        db.commit()

        assert article.category_id == categories["health"].id
        assert article.processing_status == ProcessingStatus.CLASSIFIED.value

    def test_an_unmatched_article_without_a_hint_still_gets_a_category(
        self, db: Session, source: Source, categories, keyword_classifier
    ):
        # With a source hint available, that hint is authoritative even for an article
        # the classifier cannot match, so a gaming feed never leaks into AI.
        source.category_id = categories["gaming"].id
        db.commit()

        article = make_article(
            db,
            title="A completely unclassifiable headline",
            url="https://example.test/no-hint",
            published_at=days_ago(1),
            source=source,
            status=ProcessingStatus.PENDING.value,
        )
        db.commit()

        lookup = {category.name.lower(): category for category in categories.values()}
        assert ingestion.classify_article(db, article, keyword_classifier, lookup) is True
        assert article.category_id == categories["gaming"].id

    def test_an_unmatched_article_without_any_hint_uses_the_configured_default(
        self, db: Session, categories, keyword_classifier
    ):
        # Only reachable when the source has no category hint at all (for example an
        # article stored by a future non-feed collector). There is nothing to infer from,
        # so the article is still given a valid category rather than left uncategorised.
        article = make_article(
            db,
            title="A completely unclassifiable headline",
            url="https://example.test/no-source",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        db.commit()

        lookup = {category.name.lower(): category for category in categories.values()}
        assert ingestion.classify_article(db, article, keyword_classifier, lookup) is True
        assert article.category_id is not None
        assert article.category_id == categories["ai"].id

    def test_unknown_category_name_falls_back_to_the_first_category(
        self, db: Session, source: Source, categories
    ):
        class BogusClassifier(Classifier):
            name = "bogus"

            def classify(self, title, description=None):
                return ClassificationResult(category="Astrology", topic=None, confidence=0.9)

        article = make_article(
            db,
            title="Unmappable category",
            url="https://example.test/bogus",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        lookup = {category.name.lower(): category for category in categories.values()}

        assert ingestion.classify_article(db, article, BogusClassifier(), lookup) is True
        assert article.category_id == categories["ai"].id


class TestIngestSource:
    def test_collector_failure_is_reported_not_raised(self, db: Session, source: Source, categories):
        class BrokenCollector:
            name = "broken"

            def collect(self, _source):
                raise CollectorError("timeout after 15s")

            def close(self):
                return None

        lookup = {category.name.lower(): category for category in categories.values()}

        outcome = ingestion.ingest_source(
            db, source, None, lookup, collector=BrokenCollector()  # type: ignore[arg-type]
        )

        assert outcome.ok is False
        assert "timeout" in (outcome.error or "")
        assert source.last_error is not None

    def test_successful_run_stores_and_classifies(
        self, db: Session, source: Source, categories, keyword_classifier
    ):
        class StubCollector:
            name = "stub"

            def collect(self, _source):
                return FetchResult(
                    source_name=_source.name,
                    articles=[
                        raw(
                            "OpenAI ships a new agent runtime for autonomous tool use",
                            "https://example.test/agent-runtime",
                        ),
                        raw(
                            "Central bank signals interest rate decision next week",
                            "https://example.test/rates",
                        ),
                    ],
                )

            def close(self):
                return None

        lookup = {category.name.lower(): category for category in categories.values()}

        outcome = ingestion.ingest_source(
            db, source, keyword_classifier, lookup, collector=StubCollector()
        )

        assert outcome.ok is True
        assert outcome.new == 2
        assert outcome.classified == 2
        assert outcome.failed == 0

    def test_second_run_of_the_same_feed_adds_nothing(
        self, db: Session, source: Source, categories, keyword_classifier
    ):
        class StubCollector:
            name = "stub"

            def collect(self, _source):
                return FetchResult(
                    source_name=_source.name,
                    articles=[raw("Repeatable item", "https://example.test/repeat")],
                )

            def close(self):
                return None

        lookup = {category.name.lower(): category for category in categories.values()}
        collector = StubCollector()

        first = ingestion.ingest_source(db, source, keyword_classifier, lookup, collector=collector)
        second = ingestion.ingest_source(db, source, keyword_classifier, lookup, collector=collector)

        assert first.new == 1
        assert second.new == 0
        assert second.duplicate == 1
        assert db.execute(select(func.count(Article.id))).scalar_one() == 1

    def test_not_modified_response_creates_no_articles(
        self, db: Session, source: Source, categories, keyword_classifier
    ):
        class NotModifiedCollector:
            name = "not-modified"

            def collect(self, _source):
                return FetchResult(source_name=_source.name, not_modified=True)

            def close(self):
                return None

        lookup = {category.name.lower(): category for category in categories.values()}

        outcome = ingestion.ingest_source(
            db, source, keyword_classifier, lookup, collector=NotModifiedCollector()
        )

        assert outcome.ok is True
        assert outcome.not_modified is True
        assert outcome.new == 0


class TestIngestAll:
    def test_runs_every_active_source_and_survives_failures(
        self, db: Session, categories, keyword_classifier
    ):
        good = Source(name="Good", url="https://good.test", feed_url="https://good.test/feed")
        bad = Source(name="Bad", url="https://bad.test", feed_url="https://bad.test/feed")
        inactive = Source(
            name="Inactive", url="https://off.test", feed_url="https://off.test/feed", is_active=False
        )
        db.add_all([good, bad, inactive])
        db.commit()

        class Router:
            name = "router"

            def collect(self, source):
                if source.name == "Bad":
                    raise CollectorError("HTTP 500")
                return FetchResult(
                    source_name=source.name,
                    articles=[raw(f"{source.name} item", f"https://{source.name}.test/1")],
                )

            def close(self):
                return None

        summary = ingestion.ingest_all(
            db, classifier=keyword_classifier, collector=Router()
        )

        assert summary.sources_total == 2  # the inactive source is skipped
        assert summary.sources_ok == 1
        assert summary.sources_failed == 1
        assert summary.articles_new == 1
        assert summary.errors[0]["source"] == "Bad"

    def test_unexpected_failure_is_sanitized(
        self, db: Session, categories, keyword_classifier, monkeypatch
    ):
        # An unanticipated exception may carry SQL, filesystem paths or credentials. It
        # must still fail only its own source, and the client must get a fixed message.
        source = Source(name="Trap", url="https://trap.test", feed_url="https://trap.test/feed")
        db.add(source)
        db.commit()

        secret = 'relation "sources" does not exist at /srv/app/db.py:42'

        def explode(*_args, **_kwargs):
            raise RuntimeError(secret)

        # Force the catch-all in `ingest_all`; `CollectorError` is handled separately.
        monkeypatch.setattr(ingestion, "ingest_source", explode)

        summary = ingestion.ingest_all(db, classifier=keyword_classifier)

        assert summary.sources_total == 1
        assert summary.sources_failed == 1
        assert summary.articles_new == 0
        assert len(summary.errors) == 1
        assert summary.errors[0]["source"] == "Trap"
        assert summary.errors[0]["message"] == "unexpected error during ingestion"
        assert secret not in summary.errors[0]["message"]

    def test_collector_error_message_still_reaches_the_summary(
        self, db: Session, categories, keyword_classifier
    ):
        # Guard against over-sanitizing: a CollectorError message is authored for
        # operators and is expected to be useful in the API response and `cli status`.
        source = Source(name="Missing", url="https://missing.test", feed_url="https://missing.test/feed")
        db.add(source)
        db.commit()

        class NotFoundCollector:
            name = "not-found"

            def collect(self, _source):
                raise CollectorError("HTTP 404")

            def close(self):
                return None

        summary = ingestion.ingest_all(
            db, classifier=keyword_classifier, collector=NotFoundCollector()
        )

        assert summary.sources_failed == 1
        assert summary.errors[0]["source"] == "Missing"
        assert summary.errors[0]["message"] == "HTTP 404"
        assert db.get(Source, source.id).last_error == "HTTP 404"

    def test_failure_is_durable_for_the_trailing_source(
        self, db: Session, categories, keyword_classifier
    ):
        # Regression: the CollectorError branch only `flush()`ed `last_error`. When the
        # failing source was the last one in the run, nothing committed it and the
        # request-scoped session was closed with `db.close()`, which rolled the update
        # back. `summary.errors` reported the failure but a fresh session saw no trace.
        source = Source(
            name="Trailing", url="https://trailing.test", feed_url="https://trailing.test/feed"
        )
        db.add(source)
        db.commit()
        source_id = source.id

        class LastCollector:
            name = "last"

            def collect(self, _source):
                raise CollectorError("HTTP 503")

            def close(self):
                return None

        summary = ingestion.ingest_all(
            db, classifier=keyword_classifier, collector=LastCollector()
        )

        assert summary.sources_failed == 1
        assert summary.errors[0]["message"] == "HTTP 503"

        # Simulate what `get_db` does when the request ends: it calls `db.close()` on the
        # request-scoped session, which rolls back any transaction still pending. Without
        # an explicit commit the flushed `last_error` update dies here, which is exactly
        # the bug this test pins.
        db.rollback()

        # A fresh session is what `cli status` and `/api/ingestion/run` use; it can only
        # see committed state, so reading there is what proves durability.
        from app.database import SessionLocal

        fresh = SessionLocal()
        try:
            stored = fresh.get(Source, source_id)
            assert stored.last_error == "HTTP 503"
            assert stored.last_fetched_at is not None
        finally:
            fresh.close()

    def test_an_earlier_failure_still_reaches_the_next_source(
        self, db: Session, categories, keyword_classifier
    ):
        # Committing per source must not disturb the run: the second source is still
        # ingested after the first one fails.
        bad = Source(name="Bad", url="https://bad2.test", feed_url="https://bad2.test/feed")
        good = Source(name="Good", url="https://good2.test", feed_url="https://good2.test/feed")
        db.add_all([bad, good])
        db.commit()

        class Router:
            name = "router"

            def collect(self, source):
                if source.name == "Bad":
                    raise CollectorError("HTTP 500")
                return FetchResult(
                    source_name=source.name,
                    articles=[raw("Good item", "https://good2.test/1")],
                )

            def close(self):
                return None

        from app.database import SessionLocal

        summary = ingestion.ingest_all(db, classifier=keyword_classifier, collector=Router())

        assert summary.sources_ok == 1
        assert summary.sources_failed == 1
        assert summary.articles_new == 1

        fresh = SessionLocal()
        try:
            assert fresh.get(Source, bad.id).last_error == "HTTP 500"
            assert fresh.get(Source, good.id).last_error is None
        finally:
            fresh.close()

    def test_successful_source_still_stores_and_classifies(
        self, db: Session, categories, keyword_classifier
    ):
        # Guard the explicit commits inside `ingest_source`: the per-source commit added
        # to `ingest_all` must not change what a successful run persists (spec 15).
        source = Source(name="Healthy", url="https://healthy.test", feed_url="https://healthy.test/feed")
        db.add(source)
        db.commit()

        class HealthyCollector:
            name = "healthy"

            def collect(self, _source):
                return FetchResult(
                    source_name=_source.name,
                    articles=[
                        raw(
                            "OpenAI releases a new agent runtime for autonomous tool use",
                            "https://healthy.test/agent",
                        ),
                        raw(
                            "New AI chip startup raises a Series B round",
                            "https://healthy.test/chip",
                        ),
                    ],
                )

            def close(self):
                return None

        summary = ingestion.ingest_all(
            db, classifier=keyword_classifier, collector=HealthyCollector()
        )

        assert summary.sources_ok == 1
        assert summary.articles_new == 2
        assert summary.articles_classified == 2
        assert summary.articles_failed == 0

        from app.database import SessionLocal

        fresh = SessionLocal()
        try:
            stored = fresh.execute(
                select(Article).where(Article.url.like("https://healthy.test/%"))
            ).scalars().all()
            assert len(stored) == 2
            assert all(
                article.processing_status == ProcessingStatus.CLASSIFIED.value
                for article in stored
            )
        finally:
            fresh.close()

    def test_empty_database_is_not_an_error(self, db: Session, keyword_classifier):
        summary = ingestion.ingest_all(db, classifier=keyword_classifier)
        assert summary.sources_total == 0
        assert summary.articles_new == 0


class TestReprocessPending:
    def test_retries_failed_articles_after_the_classifier_recovers(
        self, db: Session, categories, keyword_classifier
    ):
        article = make_article(
            db,
            title="OpenAI agent framework reaches production",
            url="https://example.test/retry",
            published_at=days_ago(1),
            status=ProcessingStatus.FAILED.value,
        )
        db.commit()

        result = ingestion.reprocess_pending(db, classifier=keyword_classifier)

        assert result["processed"] == 1
        assert result["classified"] == 1
        assert result["remaining"] == 0
        assert article.processing_status == ProcessingStatus.CLASSIFIED.value

    def test_remaining_count_tracks_the_queue(self, db: Session, source: Source):
        make_article(
            db,
            title="Pending one",
            url="https://example.test/p1",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        make_article(
            db,
            title="Done",
            url="https://example.test/p2",
            published_at=days_ago(1),
            status=ProcessingStatus.CLASSIFIED.value,
        )
        db.commit()

        assert ingestion.pending_count(db) == 1

    def test_always_failing_classifier_leaves_the_queue_intact(
        self, db: Session, source: Source, categories
    ):
        make_article(
            db,
            title="Still failing",
            url="https://example.test/p3",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        db.commit()

        result = ingestion.reprocess_pending(db, classifier=AlwaysFailingClassifier())

        assert result["classified"] == 0
        assert result["failed"] == 1
        assert result["remaining"] == 1
