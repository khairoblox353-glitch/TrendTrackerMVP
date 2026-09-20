"""Collector interface (spec 3, ADR-004).

`RawArticle` is the only currency exchanged between a data source and the ingestion
pipeline. Adding a new source type later — a news API, a Hacker News collector, an
internal CMS export — means writing one class that returns `RawArticle` values and
registering it, with no change to validation, deduplication, classification or
scoring (spec 19.15).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from app.models import Source


class CollectorError(RuntimeError):
    """A source could not be read. Callers record it and continue (spec 15)."""


@dataclass(slots=True)
class RawArticle:
    """A single item from a data source, before validation or storage."""

    title: str
    url: str
    description: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    external_id: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def has_title(self) -> bool:
        return bool(self.title and self.title.strip())

    @property
    def has_url(self) -> bool:
        return bool(self.url and self.url.strip())


@dataclass(slots=True)
class FetchResult:
    """Everything one collector run produced for one source."""

    source_name: str
    articles: list[RawArticle] = field(default_factory=list)
    etag: str | None = None
    modified: str | None = None
    not_modified: bool = False
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def fetched(self) -> int:
        return len(self.articles)


class Collector(ABC):
    """Contract every data source implements."""

    name: ClassVar[str] = "collector"

    @abstractmethod
    def collect(self, source: Source) -> FetchResult:
        """Read one source. Raise `CollectorError` for source-level failures.

        Individual malformed entries must be skipped and counted in
        `FetchResult.skipped` rather than failing the whole source (spec 15).
        """

    def close(self) -> None:
        """Release any held resources. Optional."""
        return None
