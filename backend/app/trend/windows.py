"""Date window helpers for the trend algorithm (spec 9).

Pure functions over dates; no database and no settings lookups, so they are trivial
to unit test.

Windows are half-open `[start, end)` so an article always falls in exactly one of
the two compared periods:

        previous window        current window
   <---------------------><--------------------->
   snapshot - 2*window    snapshot - window   snapshot
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class DateWindow:
    """A resolved pair of comparison windows, as aware UTC datetimes."""

    snapshot_date: date
    window_days: int
    current_start: datetime
    current_end: datetime
    previous_start: datetime
    previous_end: datetime


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def resolve_window(snapshot_date: date, window_days: int) -> DateWindow:
    """Build the current and previous windows ending at the start of `snapshot_date`.

    `snapshot_date` itself is excluded: the day is still in progress and including it
    would make scores jitter depending on the hour the job runs.
    """
    if window_days < 1:
        raise ValueError("window_days must be >= 1")

    current_end = _start_of_day(snapshot_date)
    current_start = current_end - timedelta(days=window_days)

    return DateWindow(
        snapshot_date=snapshot_date,
        window_days=window_days,
        current_start=current_start,
        current_end=current_end,
        previous_start=current_start - timedelta(days=window_days),
        previous_end=current_start,
    )


def trailing_dates(snapshot_date: date, days_back: int) -> list[date]:
    """The `days_back` dates ending at `snapshot_date`, oldest first.

    Used by the seed script and by `POST /api/trends/recalculate` to backfill history
    with the real scoring engine instead of synthetic numbers (R13).
    """
    if days_back < 1:
        raise ValueError("days_back must be >= 1")
    return [snapshot_date - timedelta(days=offset) for offset in range(days_back - 1, -1, -1)]
