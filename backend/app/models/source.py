"""Source: one row per RSS/Atom feed (spec 6, R15)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.category import Category


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)

    # A hint only: the classifier decides the real category of every article.
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_fetched_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    last_etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False, default=utcnow)

    category: Mapped["Category | None"] = relationship(back_populates="sources")
    articles: Mapped[list["Article"]] = relationship(back_populates="source")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Source {self.name!r}>"
