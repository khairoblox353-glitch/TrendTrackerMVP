"""Article: the unit ingested from a collector (spec 6).

`url` is UNIQUE and is the deduplication key (R1). `category_id` stays NULL until
classification succeeds so that an LLM failure never blocks storage (R9, spec 15).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import ArticleTopic
from app.models.types import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.source import Source
    from app.models.topic import Topic


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    CLASSIFIED = "classified"
    FAILED = "failed"
    SKIPPED = "skipped"


class Article(Base):
    __tablename__ = "articles"
    # Declared with `text()` because `__table_args__` is evaluated before the mapped
    # columns exist. DESC matches the dominant `ORDER BY published_at DESC` reads.
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('pending','classified','failed','skipped')",
            name="ck_articles_processing_status",
        ),
        Index("ix_articles_published_at_desc", text("published_at DESC")),
        Index("ix_articles_category_published", "category_id", text("published_at DESC")),
        # Partial index: the reprocess queue only ever scans unclassified rows.
        Index(
            "ix_articles_pending",
            "processing_status",
            postgresql_where=text("processing_status IN ('pending','failed')"),
            sqlite_where=text("processing_status IN ('pending','failed')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)

    published_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProcessingStatus.PENDING.value, index=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False, default=utcnow)

    source: Mapped["Source | None"] = relationship(back_populates="articles")
    category: Mapped["Category | None"] = relationship(back_populates="articles")
    topic_links: Mapped[list[ArticleTopic]] = relationship(
        back_populates="article", cascade="all, delete-orphan", passive_deletes=True
    )
    topics: Mapped[list["Topic"]] = relationship(
        secondary="article_topics", back_populates="articles", viewonly=True
    )

    @property
    def is_classified(self) -> bool:
        return self.processing_status == ProcessingStatus.CLASSIFIED.value

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Article {self.id} {self.title[:40]!r}>"

    @property
    def topic_slugs(self) -> list[str]:
        return [topic.slug for topic in self.topics]
