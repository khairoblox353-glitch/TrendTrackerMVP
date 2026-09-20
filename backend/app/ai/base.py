"""Abstract classifier interface (ADR-005).

The ingestion pipeline only ever sees `Classifier` and `ClassificationResult`, so the
LLM implementation can be replaced by the offline keyword classifier, by a different
provider, or by a test double without touching ingestion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.catalog import CATEGORIES


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """What a classifier returns for one article (spec 8).

    `degraded` and `error` let a resilient classifier report that the primary engine
    failed and a fallback answered instead (spec 15), without failing ingestion.
    """

    category: str
    topic: str | None
    confidence: float
    summary: str | None = None
    provider: str = "unknown"
    degraded: bool = False
    error: str | None = None

    @classmethod
    def fallback(
        cls,
        *,
        category: str = "Other",
        topic: str | None = None,
        summary: str | None = None,
        provider: str = "fallback",
    ) -> ClassificationResult:
        """Result used when a classifier cannot produce a usable answer.

        The category is deliberately `"Other"` rather than the first real category: an
        unrecognised article must never be silently filed under AI just because AI
        happens to be first in the taxonomy. `services.ingestion` resolves `"Other"`
        using the source's category hint, then the configured default.
        """
        return cls(
            category=category,
            topic=topic,
            confidence=0.0,
            summary=summary,
            provider=provider,
        )


CATEGORY_NAMES: tuple[str, ...] = tuple(category.name for category in CATEGORIES)
CATEGORY_BY_NAME: dict[str, str] = {name.lower(): name for name in CATEGORY_NAMES}


def canonical_category(value: str | None) -> str:
    """Map a loose category string onto one of the five allowed names (spec 8).

    Anything unrecognised becomes `Other`, which the ingestion service then routes to
    the `Other` topic of the article's default category.
    """
    if not value:
        return "Other"
    return CATEGORY_BY_NAME.get(value.strip().lower(), "Other")


class Classifier(ABC):
    """Contract every classifier implementation satisfies."""

    name: ClassVar[str] = "classifier"

    @abstractmethod
    def classify(
        self, title: str, description: str | None = None
    ) -> ClassificationResult:
        """Classify a single article. Must not raise for ordinary bad input."""

    def summarize(self, title: str, descriptions: list[str]) -> str | None:
        """Optional short trend summary (R12). Returns None when unsupported."""
        return None
