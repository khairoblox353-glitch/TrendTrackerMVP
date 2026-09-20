"""Unit tests for the growth / score / status math (spec 16)."""

from __future__ import annotations

import pytest

from app.models.snapshot import TrendStatus
from app.trend.scoring import (
    classify_status,
    growth_rate,
    normalize_growth,
    normalize_volume,
    trend_score,
)


class TestGrowthRate:
    def test_doubling_is_one_hundred_percent(self):
        result = growth_rate(20, 10)
        assert result.growth_rate == pytest.approx(1.0)
        assert result.is_emerging is False

    def test_no_change_is_zero(self):
        assert growth_rate(10, 10).growth_rate == pytest.approx(0.0)

    def test_decline_is_negative(self):
        assert growth_rate(5, 10).growth_rate == pytest.approx(-0.5)

    def test_previous_window_empty_is_capped_and_emerging(self):
        result = growth_rate(30, 0, cap=3.0)
        assert result.growth_rate == pytest.approx(3.0)
        assert result.is_emerging is True
        assert result.capped is True

    def test_no_activity_at_all_is_not_emerging(self):
        result = growth_rate(0, 0)
        assert result.growth_rate == pytest.approx(0.0)
        assert result.is_emerging is False

    def test_growth_never_exceeds_the_cap(self):
        assert growth_rate(10_000, 1, cap=3.0).growth_rate == pytest.approx(3.0)

    def test_decline_is_floored(self):
        assert growth_rate(0, 1000, floor=-1.0).growth_rate == pytest.approx(-1.0)

    def test_two_x_is_not_emerging(self):
        assert growth_rate(200, 1).is_emerging is False

    def test_rejects_negative_counts(self):
        with pytest.raises(ValueError):
            growth_rate(-1, 5)


class TestNormalizeGrowth:
    def test_zero_maps_to_zero(self):
        assert normalize_growth(0.0) == pytest.approx(0.0)

    def test_result_is_bounded_below_one(self):
        assert 0.0 < normalize_growth(50.0) < 1.0

    def test_growth_of_one_is_half(self):
        assert normalize_growth(1.0, saturation=1.0) == pytest.approx(0.5)

    def test_is_monotonic(self):
        assert normalize_growth(0.2) < normalize_growth(0.5) < normalize_growth(3.0)

    def test_negative_growth_is_mirrored(self):
        assert normalize_growth(-1.0) == pytest.approx(-0.5)


class TestNormalizeVolume:
    def test_busiest_topic_is_one(self):
        assert normalize_volume(84, 84) == pytest.approx(1.0)

    def test_half_of_the_busiest(self):
        assert normalize_volume(42, 84) == pytest.approx(0.5)

    def test_single_topic_reaches_full_volume(self):
        assert normalize_volume(7, 7) == pytest.approx(1.0)

    def test_no_topics_yields_zero(self):
        assert normalize_volume(0, 0) == pytest.approx(0.0)


class TestTrendScore:
    def test_weights_are_applied(self):
        assert trend_score(1.0, 1.0) == pytest.approx(1.0)
        assert trend_score(0.5, 0.5) == pytest.approx(0.5)

    def test_growth_outweighs_volume(self):
        high_growth = trend_score(1.0, 0.0)
        high_volume = trend_score(0.0, 1.0)
        assert high_growth > high_volume
        assert high_volume == pytest.approx(0.3)

    def test_score_is_clamped_to_unit_range(self):
        assert trend_score(1.0, 1.0, weight_growth=2.0, weight_volume=-1.0) == pytest.approx(1.0)

    def test_negative_growth_does_not_go_below_zero(self):
        assert trend_score(-0.9, 0.0) == pytest.approx(0.0)

    def test_rejects_weights_that_do_not_sum_to_one(self):
        with pytest.raises(ValueError):
            trend_score(0.5, 0.5, weight_growth=0.9, weight_volume=0.9)


class TestClassifyStatus:
    @pytest.mark.parametrize(
        ("growth", "expected"),
        [
            (2.45, TrendStatus.GROWING),
            (1.00, TrendStatus.GROWING),
            (0.20, TrendStatus.GROWING),
            (0.199, TrendStatus.STABLE),
            (0.0, TrendStatus.STABLE),
            (-0.199, TrendStatus.STABLE),
            (-0.20, TrendStatus.DECLINING),
            (-0.75, TrendStatus.DECLINING),
        ],
    )
    def test_thresholds(self, growth, expected):
        assert classify_status(growth) == expected

    def test_emerging_overrides_growth(self):
        assert classify_status(3.0, is_emerging=True) == TrendStatus.EMERGING

    def test_no_activity_is_stable_not_emerging(self):
        assert classify_status(0.0, is_emerging=False) == TrendStatus.STABLE

    def test_thresholds_are_configurable(self):
        assert classify_status(0.15, growing_threshold=0.10) == TrendStatus.GROWING
        assert classify_status(-0.05, declining_threshold=-0.01) == TrendStatus.DECLINING
