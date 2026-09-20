"""Classifier implementations (spec 3, spec 8, ADR-005).

Nothing in `app.trend` may import from this package: the LLM must never influence a
Trend Score (spec 19.8).
"""

from app.ai.base import (
    CATEGORY_NAMES,
    ClassificationResult,
    Classifier,
    canonical_category,
)
from app.ai.factory import build_classifier, classifier_status
from app.ai.fallback import KeywordClassifier
from app.ai.llm import LLMClassifier, LLMError

__all__ = [
    "CATEGORY_NAMES",
    "ClassificationResult",
    "Classifier",
    "KeywordClassifier",
    "LLMClassifier",
    "LLMError",
    "build_classifier",
    "canonical_category",
    "classifier_status",
]
