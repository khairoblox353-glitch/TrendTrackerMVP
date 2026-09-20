"""Trend scoring math (spec 9, spec 10).

Every function here is pure: numbers and dates in, numbers out. No database, no
settings object, no network, and **no LLM** (spec 19.8, ADR-003). That is what makes
the algorithm easy to explain and easy to test.

    growth_rate -> normalized_growth --+
                                       +--> trend_score --> status
    article_count -> normalized_volume +

Note that `growth_rate` stays the human-readable number shown in the UI ("+245%"),
while `trend_score` is the bounded 0..1 ranking value.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.snapshot import TrendStatus


@dataclass(frozen=True, slots=True)
class GrowthResult:
    """Outcome of the growth calculation, including the emerging special case."""

    growth_rate: float
    is_emerging: bool
    capped: bool


def growth_rate(
    current_count: int,
    previous_count: int,
    *,
    cap: float = 3.0,
    floor: float = -1.0,
) -> GrowthResult:
    """Growth of the current window relative to the previous one.

        growth_rate = (current - previous) / max(previous, 1)

    A topic with no activity at all in the previous window cannot grow by a finite
    percentage, so it is capped at `cap` and flagged `emerging` (spec 9, R8).
    """
    if current_count < 0 or previous_count < 0:
        raise ValueError("article counts must not be negative")
    if cap <= 0:
        raise ValueError("cap must be > 0")

    if previous_count == 0:
        if current_count == 0:
            return GrowthResult(growth_rate=0.0, is_emerging=False, capped=False)
        return GrowthResult(growth_rate=cap, is_emerging=True, capped=True)

    raw = (current_count - previous_count) / previous_count
    if raw > cap:
        return GrowthResult(growth_rate=cap, is_emerging=False, capped=True)
    if raw < floor:
        return GrowthResult(growth_rate=floor, is_emerging=False, capped=True)
    return GrowthResult(growth_rate=raw, is_emerging=False, capped=False)


def normalize_growth(growth: float, *, saturation: float = 1.0) -> float:
    """Squash an unbounded growth rate into `[0, 1)`.

        normalize_growth = growth / (growth + saturation)

    A linear scaling would let one viral topic push every other score to ~0. This
    keeps mid-range growth distinguishable while still rewarding the extremes.
    Negative growth maps symmetrically into `(-1, 0)`.
    """
    if saturation <= 0:
        raise ValueError("saturation must be > 0")

    magnitude = abs(growth)
    squashed = magnitude / (magnitude + saturation)
    return squashed if growth >= 0 else -squashed


def normalize_volume(article_count: int, max_article_count: int) -> float:
    """Relative volume within a single recalculation run (R6).

        normalize_volume = article_count / max_article_count

    The denominator is the busiest topic of the same run, so the value is stable over
    time and needs no historical baseline. Returns 0 when there is nothing to compare.
    """
    if article_count < 0 or max_article_count < 0:
        raise ValueError("article counts must not be negative")
    if max_article_count == 0:
        return 0.0
    return min(article_count / max_article_count, 1.0)


def trend_score(
    normalized_growth: float,
    normalized_volume: float,
    *,
    weight_growth: float = 0.7,
    weight_volume: float = 0.3,
) -> float:
    """Weighted blend of growth and volume, clamped to `[0, 1]` (spec 9).

        trend_score = normalized_growth * 0.7 + normalized_volume * 0.3

    Weights come from config so the emphasis can be retuned without a code change.
    """
    if abs((weight_growth + weight_volume) - 1.0) > 1e-6:
        raise ValueError("weight_growth + weight_volume must equal 1.0")

    score = normalized_growth * weight_growth + normalized_volume * weight_volume
    return min(max(score, 0.0), 1.0)


def classify_status(
    growth: float,
    *,
    is_emerging: bool = False,
    growing_threshold: float = 0.20,
    declining_threshold: float = -0.20,
) -> TrendStatus:
    """Map a growth rate onto one of the four statuses (spec 10, R7).

        previous window empty      -> emerging
        growth >=  20%             -> growing
        -20% <  growth <  20%      -> stable
        growth <= -20%             -> declining

    Thresholds are arguments, not constants, because spec 10 requires them to be
    configurable.
    """
    if is_emerging:
        return TrendStatus.EMERGING
    if growth >= growing_threshold:
        return TrendStatus.GROWING
    if growth <= declining_threshold:
        return TrendStatus.DECLINING
    return TrendStatus.STABLE
