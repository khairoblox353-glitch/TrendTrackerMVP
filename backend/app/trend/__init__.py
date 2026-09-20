"""Trend scoring package (spec 9, spec 10)."""

from app.trend.engine import RecalculationResult, TopicScore, recalculate, score_topics
from app.trend.scoring import classify_status, growth_rate, normalize_volume, trend_score
from app.trend.windows import DateWindow, resolve_window, trailing_dates

__all__ = [
    "DateWindow",
    "RecalculationResult",
    "TopicScore",
    "classify_status",
    "growth_rate",
    "normalize_volume",
    "recalculate",
    "resolve_window",
    "score_topics",
    "trailing_dates",
    "trend_score",
]
