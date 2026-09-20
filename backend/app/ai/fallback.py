"""Offline keyword classifier (ADR-005).

Always available, needs no API key and no network, and is deterministic — which makes
the ingestion tests stable. It is both the default classifier and the safety net when
the LLM is unconfigured, unreachable, or returns something unusable.

Scoring is deliberately simple and explainable:

  * a phrase match on the category vocabulary contributes the category's weight;
  * a phrase match on a topic vocabulary contributes that topic's weight at
    `TOPIC_EVIDENCE_WEIGHT` of the category weight, because a topic keyword is
    narrower evidence about *which* subject is being discussed but still strong
    evidence about which category it belongs to;
  * title matches count double, because a title is a much stronger signal than a
    one-line description.

Weighing topic evidence into the category decision matters in practice: a headline
about "Unreal Engine ray tracing" may never say "game", and without this rule it would
be filed under Technology on a tie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.ai.base import ClassificationResult, Classifier
from app.catalog import CATEGORIES, CATEGORY_KEYWORDS, TOPIC_KEYWORDS
from app.services.text import clean_whitespace, truncate

TITLE_WEIGHT = 2.0
DESCRIPTION_WEIGHT = 1.0
TOPIC_EVIDENCE_WEIGHT = 0.75
CONFIDENCE_SATURATION = 3.0

# A topic must carry at least this share of its category's evidence to be trusted;
# otherwise a single coincidental word would invent a brand-new trend.
MIN_TOPIC_SHARE = 0.5

DEFAULT_CATEGORY = "Other"


@dataclass(frozen=True, slots=True)
class _CategoryMatch:
    name: str
    slug: str
    score: float
    topic_name: str | None
    topic_score: float


class KeywordClassifier(Classifier):
    """Deterministic classifier used as default, fallback and test double."""

    name = "keyword"

    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        title_text = (title or "").lower()
        description_text = (description or "").lower()

        if not title_text.strip() and not description_text.strip():
            return ClassificationResult.fallback(provider=self.name)

        matches = _score_categories(title_text, description_text)
        if not matches:
            return ClassificationResult(
                category=DEFAULT_CATEGORY,
                topic=None,
                confidence=0.0,
                summary=self._summary(title, description),
                provider=self.name,
            )

        best = max(matches, key=lambda item: (item.score, item.name))

        return ClassificationResult(
            category=best.name,
            topic=best.topic_name,
            confidence=_confidence(best.topic_score),
            summary=self._summary(title, description),
            provider=self.name,
        )

    def _summary(self, title: str, description: str | None) -> str | None:
        cleaned = clean_whitespace(description) or clean_whitespace(title)
        return truncate(cleaned, 200) if cleaned else None


@lru_cache(maxsize=512)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a word-boundary pattern for one keyword.

    Plain substring matching is wrong here: the AI category keyword "ai" would match
    inside "rain", "chair" and "domain", classifying weather articles as AI news.
    `\\b` is not enough on its own either, because keywords such as "on-chain" and
    "zero-day" contain non-word characters, so the boundary is expressed as "not
    preceded or followed by an alphanumeric character".
    """
    escaped = re.escape(keyword)
    # Optional trailing "s" so plural headlines ("chips", "GPUs") still match a
    # singular keyword, without letting one word spill into another.
    return re.compile(rf"(?<![a-z0-9]){escaped}s?(?![a-z0-9])")


def _count_matches(haystack: str, keywords) -> int:
    return sum(1 for keyword in keywords if _keyword_pattern(keyword).search(haystack))


def _weighted_hits(title: str, description: str, keywords) -> float:
    return (
        _count_matches(title, keywords) * TITLE_WEIGHT
        + _count_matches(description, keywords) * DESCRIPTION_WEIGHT
    )


def _score_categories(title: str, description: str) -> list[_CategoryMatch]:
    """Score every category, including the best topic inside each one."""
    matches: list[_CategoryMatch] = []

    for category in CATEGORIES:
        category_score = _weighted_hits(
            title, description, CATEGORY_KEYWORDS.get(category.slug, ())
        )

        topic_name: str | None = None
        topic_score = 0.0
        for candidate_name, candidate_keywords in TOPIC_KEYWORDS.get(category.slug, ()):
            score = _weighted_hits(title, description, candidate_keywords)
            if score > topic_score:
                topic_name, topic_score = candidate_name, score

        total = category_score + topic_score * TOPIC_EVIDENCE_WEIGHT
        if total <= 0:
            continue

        # An article classified purely by topic evidence (a chip article that never
        # says "technology") still needs a credible topic, so the share test applies
        # to whichever evidence produced the score.
        best_evidence = max(category_score, topic_score * TOPIC_EVIDENCE_WEIGHT)
        if topic_score * TOPIC_EVIDENCE_WEIGHT < MIN_TOPIC_SHARE * best_evidence:
            topic_name = None

        matches.append(
            _CategoryMatch(
                name=category.name,
                slug=category.slug,
                score=total,
                topic_name=topic_name,
                topic_score=topic_score,
            )
        )

    return matches


def _confidence(topic_score: float) -> float:
    """Map an unbounded keyword score into 0..1 via the saturating curve.

    Three independent keyword hits is enough to be considered confident, which lines
    up with the default `classification_min_confidence` of 0.55.
    """
    if topic_score <= 0:
        return 0.0
    return round(topic_score / (topic_score + CONFIDENCE_SATURATION), 3)
