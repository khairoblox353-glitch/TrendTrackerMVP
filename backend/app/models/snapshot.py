"""TrendSnapshot: a materialized daily score for one topic (spec 6, R3-R5).

Written only by `app.trend.engine`. The unique constraint on
`(topic_id, snapshot_date, window_days)` makes recalculation idempotent.
`previous_count` and `current_count` are stored so a snapshot remains
self-explanatory months later.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.topic import Topic


class TrendStatus(str, enum.Enum):
    EMERGING = "emerging"
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "topic_id", "snapshot_date", "window_days", name="uq_snapshot_topic_date_window"
        ),
        CheckConstraint(
            "status IN ('emerging','growing','stable','declining')",
            name="ck_snapshots_status",
        ),
        Index("ix_snapshots_date_desc", "snapshot_date"),
        Index("ix_snapshots_topic_date", "topic_id", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=7)

    current_count: Mapped[int] = mapped_column(nullable=False, default=0)
    previous_count: Mapped[int] = mapped_column(nullable=False, default=0)

    growth_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    volume_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TrendStatus.STABLE.value)
    is_emerging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False, default=utcnow)

    topic: Mapped["Topic"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<TrendSnapshot topic={self.topic_id} {self.snapshot_date} "
            f"score={self.trend_score:.2f}>"
        )
