"""Data collectors (spec 3, ADR-004).

`RawArticle` is the stable interface between data sources and the ingestion pipeline,
which is what makes the RSS feed replaceable later (spec 19.15).
"""

from app.collectors.base import Collector, CollectorError, FetchResult, RawArticle
from app.collectors.registry import (
    available_collectors,
    get_collector,
    register,
    unregister,
)
from app.collectors.rss import RSSCollector

__all__ = [
    "Collector",
    "CollectorError",
    "FetchResult",
    "RSSCollector",
    "RawArticle",
    "available_collectors",
    "get_collector",
    "register",
    "unregister",
]
