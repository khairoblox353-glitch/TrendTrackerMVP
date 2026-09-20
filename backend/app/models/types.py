"""Reusable column types shared by the models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime


def utcnow() -> datetime:
    """Timezone-aware UTC now. Used as a Python-side default."""
    return datetime.now(UTC)


def TZDateTime():
    """Timestamps are always timezone-aware so comparisons never mix naive values."""
    return DateTime(timezone=True)
