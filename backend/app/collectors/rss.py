"""RSS/Atom collector (spec 3, spec 7).

Feeds are fetched with httpx so that timeouts, conditional requests and the user
agent are under our control, then parsed with feedparser. Every per-item problem is
counted and skipped; only a source-level problem raises `CollectorError` (spec 15).
"""

from __future__ import annotations

import logging
from calendar import timegm
from datetime import UTC, datetime, timedelta
from html import unescape
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from app.collectors.base import Collector, CollectorError, FetchResult, RawArticle
from app.config import Settings
from app.config import settings as default_settings
from app.models import Source
from app.services.text import clean_whitespace, truncate

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 500
MAX_URL_LENGTH = 1000
MAX_DESCRIPTION_LENGTH = 4000

# Feeds occasionally contain future-dated or absurdly old items; both distort windows.
MAX_FUTURE_SKEW = timedelta(hours=6)
MAX_AGE = timedelta(days=365)


class RSSCollector(Collector):
    """Collector for RSS 2.0 and Atom feeds."""

    name = "rss"

    def __init__(
        self,
        config: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or default_settings
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.config.collector_timeout_seconds,
                headers={
                    "User-Agent": self.config.collector_user_agent,
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
                },
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
            self._client = None

    # ---- Fetch ---------------------------------------------------------
    def _fetch(self, source: Source) -> tuple[bytes | None, str | None, str | None, bool]:
        """Return `(body, etag, modified, not_modified)` for one feed."""
        headers: dict[str, str] = {}
        if source.last_etag:
            headers["If-None-Match"] = source.last_etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified

        try:
            response = self.client.get(source.feed_url, headers=headers)
        except httpx.TimeoutException as exc:
            raise CollectorError(f"timeout after {self.config.collector_timeout_seconds:g}s") from exc
        except httpx.HTTPError as exc:
            raise CollectorError(f"request failed: {exc}") from exc

        if response.status_code == 304:
            return None, source.last_etag, source.last_modified, True
        if response.status_code >= 400:
            raise CollectorError(f"HTTP {response.status_code}")

        return (
            response.content,
            response.headers.get("ETag"),
            response.headers.get("Last-Modified"),
            False,
        )

    # ---- Parse ---------------------------------------------------------
    def collect(self, source: Source) -> FetchResult:
        body, etag, modified, not_modified = self._fetch(source)

        if not_modified:
            return FetchResult(
                source_name=source.name,
                etag=etag,
                modified=modified,
                not_modified=True,
            )

        result = FetchResult(source_name=source.name, etag=etag, modified=modified)
        if not body:
            raise CollectorError("empty response body")

        parsed = feedparser.parse(body)

        # A malformed document yields no entries plus a bozo flag. Feeds with entries
        # are still usable even when flagged, so only an entryless bozo feed fails.
        if getattr(parsed, "bozo", 0) and not parsed.entries:
            reason = getattr(parsed, "bozo_exception", "invalid XML")
            raise CollectorError(f"invalid feed: {reason}")

        # A non-feed document (an HTML error page, for instance) parses without a bozo
        # flag but is detected by the absent format version. Without this check a
        # captcha or login page would be treated as a legitimately empty feed and
        # silently record zero articles forever.
        if not parsed.entries and not parsed.version:
            raise CollectorError("response was not a recognised RSS or Atom feed")

        if not parsed.entries and not parsed.feed:
            raise CollectorError("feed contained no entries and no metadata")

        limit = self.config.collector_max_articles_per_source
        for entry in parsed.entries[:limit]:
            article = self._to_raw_article(entry, source)
            if article is None:
                result.skipped += 1
                continue
            result.articles.append(article)

        if len(parsed.entries) > limit:
            result.warnings.append(
                f"truncated {len(parsed.entries) - limit} entries beyond the per-source limit"
            )

        return result

    def _to_raw_article(self, entry, source: Source) -> RawArticle | None:
        """Convert one feed entry, returning None when it cannot be used."""
        title = clean_whitespace(str(entry.get("title", "")))
        if not title:
            return None

        url = self._resolve_url(entry, source)
        if url is None:
            return None

        description = self._extract_description(entry)
        published_at = self._extract_published(entry)

        return RawArticle(
            title=truncate(unescape(title), MAX_TITLE_LENGTH),
            url=truncate(url, MAX_URL_LENGTH),
            description=truncate(unescape(description), MAX_DESCRIPTION_LENGTH)
            if description
            else None,
            published_at=published_at,
            author=clean_whitespace(str(entry.get("author", "")) or None),
            external_id=clean_whitespace(str(entry.get("id", "")) or None),
        )

    @staticmethod
    def _resolve_url(entry, source: Source) -> str | None:
        """Absolute http(s) link for the entry, or None when there is no usable link."""
        raw_link = entry.get("link")
        if not raw_link:
            links = entry.get("links") or []
            raw_link = next(
                (
                    link.get("href")
                    for link in links
                    if link.get("rel") in (None, "alternate") and link.get("href")
                ),
                None,
            )
        if not raw_link:
            return None

        absolute = urljoin(source.url or source.feed_url, str(raw_link).strip())
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return absolute

    @staticmethod
    def _extract_description(entry) -> str | None:
        """Best available summary text, in order of richness."""
        for key in ("summary", "description"):
            value = entry.get(key)
            if value:
                return clean_whitespace(str(value))

        content = entry.get("content") or []
        if content and isinstance(content, list):
            value = content[0].get("value")
            if value:
                return clean_whitespace(str(value))
        return None

    @staticmethod
    def _extract_published(entry) -> datetime | None:
        """Published time as aware UTC, adjusted for `published_parsed` quirks."""
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            struct_time = entry.get(key)
            if struct_time:
                try:
                    return datetime.fromtimestamp(timegm(struct_time), tz=UTC)
                except (OverflowError, ValueError, TypeError):
                    continue
        return None


def clamp_published_at(
    published_at: datetime | None, now: datetime | None = None
) -> tuple[datetime | None, str | None, bool]:
    """Normalize a publication date.

    Returns `(value, warning, dropped)`. `dropped=True` means the item must be
    discarded entirely: an item dated more than a year ago would silently distort a
    7-day window (spec 15). A missing date is *not* dropped — it is resolved by the
    caller — hence the explicit flag rather than a bare `None`.
    """
    now = now or datetime.now(UTC)

    if published_at is None:
        return None, "missing published date", False

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    else:
        published_at = published_at.astimezone(UTC)

    if published_at > now + MAX_FUTURE_SKEW:
        return now, "published date was in the future and was clamped", False

    if published_at < now - MAX_AGE:
        return None, "published date was older than one year", True

    return published_at, None, False
