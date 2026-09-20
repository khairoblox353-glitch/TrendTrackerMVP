"""Resilient classifier wrapper and factory (ADR-005).

`ResilientClassifier` is the only classifier the ingestion pipeline sees. It asks the
primary (LLM) classifier first, and on any failure transparently falls back to keyword
classification. The article is still stored and still classified, so a broken or
misconfigured LLM degrades quality without breaking the pipeline (spec 15).
"""

from __future__ import annotations

import logging

from app.ai.base import ClassificationResult, Classifier
from app.ai.fallback import KeywordClassifier
from app.ai.llm import LLMClassifier, LLMError
from app.config import Settings
from app.config import settings as default_settings

logger = logging.getLogger(__name__)


class ResilientClassifier(Classifier):
    """Primary classifier with an automatic keyword fallback."""

    name = "resilient"

    def __init__(self, primary: Classifier, fallback: Classifier) -> None:
        self.primary = primary
        self.fallback = fallback
        self._degraded = False

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        try:
            result = self.primary.classify(title, description)
            self._degraded = False
            return result
        except LLMError as exc:
            # Expected operational failure path: log once, degrade, keep going.
            if not self._degraded:
                logger.warning("Primary classifier unavailable, using fallback: %s", exc)
            self._degraded = True
            degraded = self.fallback.classify(title, description)
            return ClassificationResult(
                category=degraded.category,
                topic=degraded.topic,
                confidence=degraded.confidence,
                summary=degraded.summary,
                provider=degraded.provider,
                degraded=True,
                error=str(exc),
            )

    def summarize(self, title: str, descriptions: list[str]) -> str | None:
        try:
            return self.primary.summarize(title, descriptions) or self.fallback.summarize(
                title, descriptions
            )
        except LLMError as exc:
            logger.warning("Trend summary unavailable: %s", exc)
            return self.fallback.summarize(title, descriptions)


def build_classifier(config: Settings | None = None) -> Classifier:
    """Return the classifier the pipeline should use.

    With `LLM_ENABLED=false` or no API key this is just the keyword classifier, which
    keeps the default developer experience offline and deterministic.
    """
    config = config or default_settings
    fallback = KeywordClassifier()

    if not config.llm_configured:
        return fallback

    try:
        return ResilientClassifier(LLMClassifier(config), fallback)
    except LLMError as exc:  # pragma: no cover - only when a key is malformed
        logger.warning("LLM classifier could not be created (%s); using keyword fallback", exc)
        return fallback


def classifier_status(config: Settings | None = None) -> str:
    """Short label reported by `GET /api/health`."""
    config = config or default_settings
    return "llm" if config.llm_configured else "fallback"
