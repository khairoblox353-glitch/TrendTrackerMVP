"""Collector registry — the extension point for new data sources (ADR-004).

Registering another source type is a one-line change here; the ingestion service looks
collectors up by the `Source.feed_url` scheme or by an explicit name, so nothing else
in the pipeline needs to know which collector was used.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from app.collectors.base import Collector, CollectorError
from app.collectors.rss import RSSCollector
from app.config import Settings

CollectorFactory = Callable[[Settings | None], Collector]

_DEFAULT_FACTORIES: dict[str, CollectorFactory] = {
    "rss": lambda config=None: RSSCollector(config),
}

_FACTORIES: dict[str, CollectorFactory] = dict(_DEFAULT_FACTORIES)


def register(name: str, factory: CollectorFactory) -> None:
    """Register a collector factory under `name`."""
    _FACTORIES[name.lower()] = factory


def unregister(name: str) -> None:
    """Remove a registration (primarily for tests)."""
    _FACTORIES.pop(name.lower(), None)


def available_collectors() -> list[str]:
    return sorted(_FACTORIES)


def _name_for_url(feed_url: str) -> str:
    scheme = urlparse(feed_url).scheme.lower()
    if scheme in ("http", "https"):
        return "rss"
    raise CollectorError(f"no collector registered for scheme {scheme!r}")


def get_collector(
    feed_url: str | None = None,
    name: str | None = None,
    config: Settings | None = None,
) -> Collector:
    """Build the collector for a feed URL, or one by explicit name."""
    resolved = (name or _name_for_url(feed_url or "")).lower()
    factory = _FACTORIES.get(resolved)
    if factory is None:
        raise CollectorError(
            f"unknown collector {resolved!r}; available: {', '.join(available_collectors())}"
        )
    return factory(config)
