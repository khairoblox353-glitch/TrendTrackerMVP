"""Unit tests for the trend comparison windows (spec 16)."""

from __future__ import annotations

from datetime import date

import pytest

from app.trend.windows import resolve_window, trailing_dates

SNAPSHOT = date(2026, 9, 20)


def test_current_window_is_the_last_seven_days():
    window = resolve_window(SNAPSHOT, 7)
    assert window.current_start.date() == date(2026, 9, 13)
    assert window.current_end.date() == date(2026, 9, 20)


def test_previous_window_ends_where_the_current_one_starts():
    window = resolve_window(SNAPSHOT, 7)
    assert window.previous_end == window.current_start
    assert window.previous_start.date() == date(2026, 9, 6)


def test_windows_are_adjacent_and_do_not_overlap():
    window = resolve_window(SNAPSHOT, 7)
    assert window.previous_end == window.current_start
    assert (window.current_end - window.current_start).days == 7
    assert (window.previous_end - window.previous_start).days == 7


def test_snapshot_day_itself_is_excluded():
    window = resolve_window(SNAPSHOT, 7)
    assert window.current_end.date() == SNAPSHOT


def test_window_length_is_configurable():
    window = resolve_window(SNAPSHOT, 30)
    assert window.current_start.date() == date(2026, 8, 21)
    assert window.previous_start.date() == date(2026, 7, 22)


def test_window_must_be_positive():
    with pytest.raises(ValueError):
        resolve_window(SNAPSHOT, 0)


class TestTrailingDates:
    def test_returns_oldest_first_and_includes_the_snapshot_date(self):
        assert trailing_dates(SNAPSHOT, 3) == [
            date(2026, 9, 18),
            date(2026, 9, 19),
            date(2026, 9, 20),
        ]

    def test_single_day(self):
        assert trailing_dates(SNAPSHOT, 1) == [SNAPSHOT]

    def test_length_matches_request(self):
        assert len(trailing_dates(SNAPSHOT, 30)) == 30

    def test_must_be_positive(self):
        with pytest.raises(ValueError):
            trailing_dates(SNAPSHOT, 0)
