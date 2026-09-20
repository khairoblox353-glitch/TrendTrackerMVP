"""RSS collector tests: parsing, malformed feeds and transport failures (spec 15, spec 16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.collectors.base import CollectorError
from app.collectors.registry import get_collector
from app.collectors.rss import RSSCollector, clamp_published_at

VALID_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <link>https://example.test</link>
    <description>Example</description>
    <item>
      <title>AI agents reach production</title>
      <link>https://example.test/agents</link>
      <description>Autonomous agents move into real deployments.</description>
      <pubDate>Wed, 17 Sep 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>New chip node ramps up</title>
      <link>https://example.test/chips</link>
      <description>Foundry output rises.</description>
      <pubDate>Thu, 18 Sep 2026 08:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

PARTIAL_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Partial Feed</title>
    <link>https://example.test</link>
    <item>
      <title>Item without a link</title>
      <description>Skipped because there is no URL.</description>
    </item>
    <item>
      <link>https://example.test/no-title</link>
      <description>No title.</description>
    </item>
    <item>
      <title>Item without a date</title>
      <link>https://example.test/no-date</link>
      <description>Uses the ingestion time instead.</description>
    </item>
    <item>
      <title>Usable item</title>
      <link>https://example.test/usable</link>
      <pubDate>Fri, 19 Sep 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

RELATIVE_LINK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Relative</title>
    <link>https://example.test/news/</link>
    <item>
      <title>Relative link item</title>
      <link>/articles/123</link>
    </item>
  </channel>
</rss>
"""

BAD_SCHEME_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bad scheme</title>
    <link>https://example.test</link>
    <item>
      <title>Javascript link</title>
      <link>javascript:alert(1)</link>
    </item>
    <item>
      <title>Valid sibling</title>
      <link>https://example.test/valid</link>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <link href="https://example.test"/>
  <updated>2026-09-19T10:00:00Z</updated>
  <entry>
    <title>Atom entry with content</title>
    <link rel="alternate" href="https://example.test/atom-entry"/>
    <updated>2026-09-19T09:00:00Z</updated>
    <content type="html">&lt;p&gt;Body text for the atom entry.&lt;/p&gt;</content>
  </entry>
</feed>
"""


def make_source(feed_url: str = "https://example.test/feed.xml"):
    from app.models import Source

    return Source(name="Example", url="https://example.test", feed_url=feed_url)


def make_collector(body: str | bytes, status: int = 200, headers: dict | None = None):  # noqa: B008
    """Build an RSSCollector backed by a mock transport."""
    if isinstance(body, str):
        body = body.encode("utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers=headers or {})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return RSSCollector(client=client)


class TestParsing:
    def test_parses_valid_entries(self):
        collector = make_collector(VALID_RSS)
        result = collector.collect(make_source())

        assert result.fetched == 2
        assert result.skipped == 0
        assert result.articles[0].title == "AI agents reach production"
        assert result.articles[0].url == "https://example.test/agents"
        assert result.articles[0].published_at is not None

    def test_parses_atom_entries_and_content(self):
        collector = make_collector(ATOM_FEED)
        result = collector.collect(make_source())

        assert result.fetched == 1
        assert result.articles[0].url == "https://example.test/atom-entry"
        assert "atom entry" in (result.articles[0].description or "").lower()

    def test_published_dates_are_timezone_aware_utc(self):
        collector = make_collector(VALID_RSS)
        result = collector.collect(make_source())

        published = result.articles[0].published_at
        assert published is not None
        assert published.tzinfo is not None
        assert published.utcoffset() == timedelta(0)

    def test_relative_links_are_resolved_against_the_site(self):
        collector = make_collector(RELATIVE_LINK_RSS)
        result = collector.collect(make_source())

        assert result.articles[0].url == "https://example.test/articles/123"

    def test_unusable_entries_are_skipped_not_fatal(self):
        collector = make_collector(PARTIAL_RSS)
        result = collector.collect(make_source())

        assert result.fetched == 2
        assert result.skipped == 2
        assert {article.url for article in result.articles} == {
            "https://example.test/no-date",
            "https://example.test/usable",
        }

    def test_non_http_links_are_skipped(self):
        collector = make_collector(BAD_SCHEME_RSS)
        result = collector.collect(make_source())

        assert result.fetched == 1
        assert result.skipped == 1
        assert result.articles[0].url == "https://example.test/valid"

    def test_per_source_limit_is_enforced(self):
        from app.config import Settings

        collector = make_collector(VALID_RSS)
        collector.config = Settings(collector_max_articles_per_source=1)

        result = collector.collect(make_source())

        assert result.fetched == 1
        assert any("truncated" in warning for warning in result.warnings)


class TestFailures:
    def test_invalid_xml_raises_collector_error(self):
        collector = make_collector("<rss><channel><title>broken")
        with pytest.raises(CollectorError, match="invalid feed"):
            collector.collect(make_source())

    def test_http_error_raises_collector_error(self):
        collector = make_collector("nope", status=503)
        with pytest.raises(CollectorError, match="HTTP 503"):
            collector.collect(make_source())

    def test_timeout_is_reported_as_a_timeout(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("too slow", request=request)

        collector = RSSCollector(client=httpx.Client(transport=httpx.MockTransport(handler)))
        with pytest.raises(CollectorError, match="timeout"):
            collector.collect(make_source())

    def test_connection_failure_is_reported(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        collector = RSSCollector(client=httpx.Client(transport=httpx.MockTransport(handler)))
        with pytest.raises(CollectorError, match="request failed"):
            collector.collect(make_source())

    def test_empty_body_raises_collector_error(self):
        collector = make_collector("")
        with pytest.raises(CollectorError, match="empty response body"):
            collector.collect(make_source())

    def test_a_valid_but_empty_feed_is_not_an_error(self):
        # A well-formed feed with no items is legitimately empty, not a failure. It
        # must not be reported in `errors`, or every quiet feed would look broken.
        empty_feed = VALID_RSS.split("<item>")[0] + "</channel></rss>"
        collector = make_collector(empty_feed)

        result = collector.collect(make_source())

        assert result.fetched == 0
        assert result.skipped == 0

    def test_document_without_feed_metadata_raises(self):
        collector = make_collector("<html><body>not a feed</body></html>")
        with pytest.raises(CollectorError):
            collector.collect(make_source())


class TestConditionalRequests:
    def test_not_modified_returns_an_empty_result(self):
        collector = make_collector("", status=304)
        result = collector.collect(make_source())

        assert result.not_modified is True
        assert result.fetched == 0

    def test_etag_and_modified_are_sent_back(self):
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update(dict(request.headers))
            return httpx.Response(200, content=VALID_RSS.encode(), headers={"ETag": '"v2"'})

        source = make_source()
        source.last_etag = '"v1"'
        source.last_modified = "Wed, 17 Sep 2026 10:00:00 GMT"

        collector = RSSCollector(client=httpx.Client(transport=httpx.MockTransport(handler)))
        result = collector.collect(source)

        assert seen.get("if-none-match") == '"v1"'
        assert seen.get("if-modified-since") == "Wed, 17 Sep 2026 10:00:00 GMT"
        assert result.etag == '"v2"'


class TestClampPublishedAt:
    def test_none_is_not_dropped(self):
        value, warning, dropped = clamp_published_at(None)
        assert value is None
        assert dropped is False
        assert "missing" in warning

    def test_naive_datetime_becomes_utc(self):
        value, _, dropped = clamp_published_at(datetime(2026, 9, 19, 10, 0))
        assert dropped is False
        assert value is not None
        assert value.tzinfo == UTC

    def test_future_date_is_clamped_to_now(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
        value, warning, dropped = clamp_published_at(now + timedelta(days=2), now=now)
        assert dropped is False
        assert value == now
        assert "future" in warning

    def test_small_clock_skew_is_tolerated(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
        value, warning, dropped = clamp_published_at(now + timedelta(minutes=30), now=now)
        assert dropped is False
        assert warning is None
        assert value is not None

    def test_very_old_date_is_dropped(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
        value, warning, dropped = clamp_published_at(now - timedelta(days=400), now=now)
        assert dropped is True
        assert value is None
        assert "older" in warning


class TestRegistry:
    def test_http_urls_resolve_to_the_rss_collector(self):
        assert isinstance(get_collector("https://example.test/feed.xml"), RSSCollector)

    def test_unknown_scheme_is_rejected(self):
        with pytest.raises(CollectorError, match="no collector registered"):
            get_collector("ftp://example.test/feed.xml")

    def test_explicit_name_wins(self):
        assert isinstance(get_collector(name="rss"), RSSCollector)

    def test_unknown_name_is_rejected(self):
        with pytest.raises(CollectorError, match="unknown collector"):
            get_collector(name="telepathy")
