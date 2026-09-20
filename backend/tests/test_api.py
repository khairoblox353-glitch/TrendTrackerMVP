"""Integration tests for the HTTP API (spec 16).

Covered here: categories, trends, articles, history, pagination, sorting, validation
and the operational endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fallback import KeywordClassifier
from app.models import ArticleTopic, Category, ProcessingStatus, Source, Topic
from app.services.ingestion import classify_article
from app.trend import engine

from .conftest import days_ago, link, make_article, topic_by_name


@pytest.fixture
def seeded(db: Session, categories) -> dict:
    """A small deterministic dataset with known growth, plus snapshots."""
    today = datetime.now(UTC).date()

    agents = topic_by_name(db, "AI Agents")
    policy = topic_by_name(db, "AI Policy")
    ai = categories["ai"]

    # AI Agents: 8 recent vs 2 previous -> strongly growing.
    for index in range(2):
        article = make_article(
            db,
            title=f"AI agent platform update {index}",
            url=f"https://example.test/agents-prev-{index}",
            published_at=days_ago(10, hours=index),
            category=ai,
        )
        link(article, agents)

    for index in range(8):
        article = make_article(
            db,
            title=f"AI agent platform release {index}",
            url=f"https://example.test/agents-now-{index}",
            published_at=days_ago(2, hours=index),
            category=ai,
        )
        link(article, agents)

    # AI Policy: 3 recent vs 6 previous -> declining.
    for index in range(6):
        article = make_article(
            db,
            title=f"AI regulation briefing {index}",
            url=f"https://example.test/policy-prev-{index}",
            published_at=days_ago(9, hours=index),
            category=ai,
        )
        link(article, policy)

    for index in range(3):
        article = make_article(
            db,
            title=f"AI regulation update {index}",
            url=f"https://example.test/policy-now-{index}",
            published_at=days_ago(3, hours=index),
            category=ai,
        )
        link(article, policy)

    db.commit()
    engine.recalculate(db, snapshot_date=today, window_days=7, days_back=5)

    return {"agents": agents, "policy": policy, "category": ai, "today": today}


class TestHealth:
    def test_health_reports_dependencies(self, client: TestClient):
        response = client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["scheduler"] == "disabled"
        assert body["llm"] == "fallback"

    def test_root_describes_the_service(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["api"] == "/api"


class TestCategories:
    def test_lists_all_five_categories(self, client: TestClient, categories):
        response = client.get("/api/categories")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 5
        assert {item["slug"] for item in body} == {
            "ai",
            "technology",
            "finance",
            "gaming",
            "health",
        }

    def test_category_includes_counts(self, client: TestClient, seeded):
        response = client.get("/api/categories/ai")
        body = response.json()

        assert response.status_code == 200
        assert body["name"] == "AI"
        assert body["topic_count"] == 4
        assert body["article_count"] == 19
        assert body["trending_topic"]["slug"] == "ai-agents"
        assert len(body["top_trends"]) > 0

    def test_unknown_category_returns_404_envelope(self, client: TestClient, categories):
        response = client.get("/api/categories/nonexistent")

        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "not_found"
        assert error["details"]["slug"] == "nonexistent"

    def test_topic_count_excludes_the_fallback_topic(self, client: TestClient, categories):
        body = client.get("/api/categories/ai").json()
        assert body["topic_count"] == 4  # `Other` is not a real topic


class TestTrends:
    def test_lists_trends_sorted_by_score(self, client: TestClient, seeded):
        response = client.get("/api/trends")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] > 0
        assert body["page"] == 1
        scores = [item["trend_score"] for item in body["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_growing_topic_reports_positive_growth(self, client: TestClient, seeded):
        body = client.get("/api/trends?category=ai").json()
        agents = next(item for item in body["items"] if item["slug"] == "ai-agents")

        assert agents["current_count"] == 8
        assert agents["previous_count"] == 2
        assert agents["growth_rate"] == pytest.approx(3.0)
        assert agents["growth_percent"] == pytest.approx(300.0)
        assert agents["status"] == "growing"
        assert agents["category"]["slug"] == "ai"

    def test_declining_topic_is_flagged(self, client: TestClient, seeded):
        body = client.get("/api/trends?category=ai&status=declining").json()
        slugs = [item["slug"] for item in body["items"]]

        assert "ai-policy" in slugs
        assert "ai-agents" not in slugs

    def test_category_filter_accepts_name_or_slug(self, client: TestClient, seeded):
        by_slug = client.get("/api/trends?category=ai").json()
        by_name = client.get("/api/trends?category=AI").json()
        assert by_slug["total"] == by_name["total"] > 0

    def test_query_filter_matches_topic_names(self, client: TestClient, seeded):
        body = client.get("/api/trends?q=agent").json()
        assert [item["slug"] for item in body["items"]] == ["ai-agents"]

    def test_min_growth_filter(self, client: TestClient, seeded):
        body = client.get("/api/trends?min_growth=1.0").json()
        assert all(item["growth_rate"] >= 1.0 for item in body["items"])

    def test_sorting_by_name_ascending(self, client: TestClient, seeded):
        # `sort=name` (no dash) must mean ascending; Database collation ordering is
        # not assumed, so compare case-insensitively.
        body = client.get("/api/trends?sort=name").json()
        names = [item["name"] for item in body["items"]]
        assert names == sorted(names, key=str.lower)

    def test_unknown_sort_field_is_rejected(self, client: TestClient, seeded):
        response = client.get("/api/trends?sort=drop_table")
        assert response.status_code == 422
        assert "sort" in response.json()["error"]["details"]["parameter"]

    def test_unknown_status_is_rejected(self, client: TestClient, seeded):
        response = client.get("/api/trends?status=exploding")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_pagination_is_applied(self, client: TestClient, seeded):
        first = client.get("/api/trends?page_size=2&page=1").json()
        second = client.get("/api/trends?page_size=2&page=2").json()

        assert len(first["items"]) == 2
        assert first["pages"] == second["pages"]
        assert {item["id"] for item in first["items"]}.isdisjoint(
            {item["id"] for item in second["items"]}
        )

    def test_page_size_above_the_maximum_is_rejected(self, client: TestClient, seeded):
        assert client.get("/api/trends?page_size=5000").status_code == 422

    def test_empty_database_returns_an_empty_page(self, client: TestClient, categories):
        body = client.get("/api/trends").json()
        assert body == {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}

    def test_trend_detail_includes_recent_articles(self, client: TestClient, seeded):
        response = client.get("/api/trends/ai-agents")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "AI Agents"
        assert len(body["latest_articles"]) == 5
        assert all(item["published_at"] for item in body["latest_articles"])

    def test_trend_summary_is_exposed(self, client: TestClient, seeded, db: Session):
        row = db.get(Topic, seeded["agents"].id)
        row.summary = "AI agents are moving into production use."
        db.commit()

        body = client.get("/api/trends/ai-agents").json()
        assert body["summary"] == "AI agents are moving into production use."

    def test_unknown_trend_returns_404(self, client: TestClient, seeded):
        response = client.get("/api/trends/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_fallback_topics_are_excluded_from_the_ranking(self, client: TestClient, seeded, db: Session):
        # Regression: every category owns an `Other` bucket that absorbs unmatched
        # articles. Real feeds produce many of those, so the buckets outranked real
        # topics and the homepage filled up with several identically named "Other" rows.
        trends = client.get("/api/trends?page_size=100").json()
        names = [item["name"] for item in trends["items"]]

        assert "Other" not in names
        assert trends["total"] == len(names)
        assert trends["total"] == 20  # the 20 curated topics, no fallback buckets

    def test_fallback_topics_can_be_requested_explicitly(self, client: TestClient, seeded, db: Session):
        # The buckets stay reachable for diagnostics rather than being deleted, and
        # including them must yield strictly more rows than the default ranking.
        from app.services import trends as trend_service

        default_rows, default_total = trend_service.query_trends(db, page_size=100)
        all_rows, all_total = trend_service.query_trends(db, include_fallback=True, page_size=100)

        assert all_total > default_total
        assert all(row.name != "Other" for row in default_rows)
        assert any(row.name == "Other" for row in all_rows)

    def test_category_fallback_is_not_counted_as_a_trend(self, client: TestClient, seeded):
        body = client.get("/api/categories/ai").json()
        names = [trend["name"] for trend in body["top_trends"]]
        assert "Other" not in names

    def test_topic_scored_for_two_windows_appears_once(self, client: TestClient, seeded, db: Session):
        # Regression: `trend_snapshots` is unique per (topic, date, window), so two
        # window sizes for the same topic used to produce two rows in the trend list,
        # duplicating the topic and corrupting the ranking and pagination.
        engine.recalculate(
            db, snapshot_date=datetime.now(UTC).date(), window_days=30, days_back=1
        )

        body = client.get("/api/trends?page_size=100").json()
        slugs = [item["slug"] for item in body["items"]]

        assert len(slugs) == len(set(slugs)), "a topic was returned more than once"
        assert body["total"] == len(slugs)
        assert all(item["window_days"] == 7 for item in body["items"])


class TestTrendHistory:
    def test_history_returns_an_ascending_series(self, client: TestClient, seeded):
        response = client.get("/api/trends/ai-agents/history")

        assert response.status_code == 200
        body = response.json()
        assert body["slug"] == "ai-agents"
        assert body["window_days"] == 7
        assert len(body["points"]) == 5

        dates = [point["date"] for point in body["points"]]
        assert dates == sorted(dates)

    def test_history_points_carry_scoring_fields(self, client: TestClient, seeded):
        point = client.get("/api/trends/ai-agents/history").json()["points"][-1]

        assert set(point) == {
            "date",
            "current_count",
            "previous_count",
            "growth_rate",
            "trend_score",
            "status",
        }
        assert 0.0 <= point["trend_score"] <= 1.0

    def test_history_window_is_clamped_to_the_requested_days(self, client: TestClient, seeded):
        body = client.get("/api/trends/ai-agents/history?days=2").json()
        assert len(body["points"]) == 2

    def test_history_for_an_unknown_trend_returns_404(self, client: TestClient, seeded):
        assert client.get("/api/trends/nope/history").status_code == 404

    def test_history_for_a_topic_without_snapshots_returns_204(
        self, client: TestClient, categories
    ):
        response = client.get("/api/trends/ai-agents/history")
        assert response.status_code == 204
        assert response.content == b""


class TestArticles:
    def test_lists_articles_newest_first(self, client: TestClient, seeded):
        response = client.get("/api/articles")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 19
        dates = [item["published_at"] for item in body["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_article_includes_category_and_topics(self, client: TestClient, seeded):
        body = client.get("/api/articles?topic=ai-agents").json()
        article = body["items"][0]

        assert article["category"]["slug"] == "ai"
        assert {"slug": "ai-agents", "name": "AI Agents", "is_fallback": False} in article["topics"]
        assert article["processing_status"] == ProcessingStatus.CLASSIFIED.value

    def test_articles_on_the_fallback_topic_are_flagged(self, client: TestClient, seeded, db: Session):
        # The `Other` bucket is a diagnostic, so the API marks it and lets the UI hide it
        # instead of showing several identical "Other" tags. The data stays truthful.
        article = make_article(
            db,
            title="Completely unclassifiable headline",
            url="https://example.test/fallback-flag",
            published_at=days_ago(1),
            status=ProcessingStatus.PENDING.value,
        )
        db.commit()

        categories = {c.name.lower(): c for c in db.execute(select(Category)).scalars()}
        classify_article(db, article, KeywordClassifier(), categories)
        db.commit()

        listed = client.get(f"/api/articles/{article.id}").json()
        fallback_topics = [t for t in listed["topics"] if t["is_fallback"]]

        assert fallback_topics, "expected the article to be linked to an Other bucket"
        assert all(topic["name"] == "Other" for topic in fallback_topics)
        assert db.execute(select(func.count(ArticleTopic.article_id))).scalar_one() > 0

    def test_topic_filter(self, client: TestClient, seeded):
        body = client.get("/api/articles?topic=ai-policy").json()
        assert body["total"] == 9

    def test_category_filter(self, client: TestClient, seeded):
        assert client.get("/api/articles?category=ai").json()["total"] == 19
        assert client.get("/api/articles?category=gaming").json()["total"] == 0

    def test_title_search(self, client: TestClient, seeded):
        body = client.get("/api/articles?q=regulation").json()
        assert body["total"] == 9

    def test_date_filters(self, client: TestClient, seeded):
        # 8 recent AI-agent articles (2 days ago) + 3 recent AI-policy articles
        # (3 days ago); the older batches are 9-10 days old and must be excluded.
        after = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
        body = client.get(f"/api/articles?published_after={after}").json()
        assert body["total"] == 11
        assert all(item["published_at"][:10] >= after for item in body["items"])

    def test_date_range_excludes_older_batches(self, client: TestClient, seeded):
        before = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
        body = client.get(f"/api/articles?published_before={before}").json()
        assert body["total"] == 8

    def test_invalid_date_is_rejected(self, client: TestClient, seeded):
        response = client.get("/api/articles?published_after=not-a-date")
        assert response.status_code == 422
        assert response.json()["error"]["details"]["field"] == "published_after"

    def test_inverted_date_range_is_rejected(self, client: TestClient, seeded):
        response = client.get(
            "/api/articles?published_after=2026-05-01&published_before=2026-01-01"
        )
        assert response.status_code == 422

    def test_sorting_by_title(self, client: TestClient, seeded):
        body = client.get("/api/articles?sort=title&page_size=100").json()
        titles = [item["title"] for item in body["items"]]
        assert titles == sorted(titles)

    def test_pagination_metadata(self, client: TestClient, seeded):
        body = client.get("/api/articles?page_size=5&page=2").json()
        assert body["total"] == 19
        assert body["pages"] == 4
        assert len(body["items"]) == 5

    def test_article_detail(self, client: TestClient, seeded):
        listed = client.get("/api/articles?page_size=1").json()["items"][0]
        detail = client.get(f"/api/articles/{listed['id']}")

        assert detail.status_code == 200
        assert detail.json()["id"] == listed["id"]
        assert detail.json()["url"] == listed["url"]

    def test_unknown_article_returns_404(self, client: TestClient, seeded):
        response = client.get("/api/articles/999999")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestOperationalEndpoints:
    def test_recalculate_returns_a_summary(self, client: TestClient, seeded):
        response = client.post("/api/trends/recalculate", json={"days_back": 1})

        assert response.status_code == 200
        body = response.json()
        assert body["window_days"] == 7
        assert body["topics_scored"] > 0
        assert body["snapshots_written"] > 0

    def test_recalculate_accepts_a_specific_date(self, client: TestClient, seeded):
        day = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
        body = client.post(
            "/api/trends/recalculate", json={"snapshot_date": day, "days_back": 1}
        ).json()
        assert body["snapshot_date"] == day

    def test_recalculate_rejects_a_bad_date(self, client: TestClient, seeded):
        response = client.post("/api/trends/recalculate", json={"snapshot_date": "yesterday"})
        assert response.status_code == 422

    def test_recalculate_rejects_an_unknown_topic(self, client: TestClient, seeded):
        response = client.post("/api/trends/recalculate", json={"topic_id": 999999})
        assert response.status_code == 422

    def test_ingestion_rejects_unknown_source_ids(self, client: TestClient, seeded):
        response = client.post("/api/ingestion/run", json={"source_ids": [424242]})

        assert response.status_code == 422
        assert response.json()["error"]["details"]["missing_source_ids"] == [424242]

    def test_ingestion_runs_a_source_without_network(
        self, client: TestClient, db: Session, categories
    ):
        from app.collectors import registry
        from app.collectors.base import Collector, FetchResult, RawArticle

        source = Source(
            name="Stubbed", url="https://stub.test", feed_url="https://stub.test/feed"
        )
        db.add(source)
        db.commit()

        class StubCollector(Collector):
            name = "stub"

            def collect(self, inner_source):
                return FetchResult(
                    source_name=inner_source.name,
                    articles=[
                        RawArticle(
                            title="Fresh AI agent story",
                            url="https://stub.test/1",
                            published_at=datetime.now(UTC),
                        )
                    ],
                )

        original = registry._FACTORIES["rss"]
        registry.register("rss", lambda config=None: StubCollector())
        try:
            response = client.post("/api/ingestion/run", json={"source_ids": [source.id]})
        finally:
            registry.register("rss", original)

        assert response.status_code == 200
        body = response.json()
        assert body["articles_new"] == 1
        assert body["articles_classified"] == 1
        assert body["sources_ok"] == 1

    def test_ingestion_on_an_empty_database_is_not_an_error(self, client: TestClient, categories):
        response = client.post("/api/ingestion/run", json={})

        assert response.status_code == 200
        assert response.json()["sources_total"] == 0


class TestErrorEnvelope:
    def test_not_found_uses_the_standard_envelope(self, client: TestClient, seeded):
        body = client.get("/api/trends/missing").json()
        assert set(body) == {"error"}
        assert set(body["error"]) <= {"code", "message", "details"}

    def test_validation_errors_keep_field_details(self, client: TestClient, seeded):
        body = client.get("/api/articles?page=0").json()["error"]
        assert body["code"] == "validation_error"
        assert body["details"]["fields"]

    def test_method_not_allowed_uses_the_envelope(self, client: TestClient, seeded):
        response = client.delete("/api/trends")
        assert response.status_code == 405
        assert response.json()["error"]["code"] == "method_not_allowed"
