"""Topic: a trendable subject inside a category (spec 6).

`name_normalized` is the upsert key within a category. `slug` is globally unique so
the public URL `/trends/{slug}` needs no category prefix (R10).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import ArticleTopic
from app.models.types import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.category import Category
    from app.models.snapshot import TrendSnapshot


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("category_id", "name_normalized", name="uq_topics_category_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    # True for the reserved `Other` topic every category gets (R14).
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )

    category: Mapped["Category"] = relationship(back_populates="topics")
    article_links: Mapped[list[ArticleTopic]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    articles: Mapped[list["Article"]] = relationship(
        secondary="article_topics", back_populates="topics", viewonly=True
    )
    snapshots: Mapped[list["TrendSnapshot"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Topic {self.slug}>"
