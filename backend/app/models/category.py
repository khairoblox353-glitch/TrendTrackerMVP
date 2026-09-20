"""Category: the five industries tracked by the MVP (spec 8)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import TZDateTime, utcnow

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.source import Source
    from app.models.topic import Topic


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False, default=utcnow)

    topics: Mapped[list["Topic"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", passive_deletes=True
    )
    articles: Mapped[list["Article"]] = relationship(back_populates="category")
    sources: Mapped[list["Source"]] = relationship(back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Category {self.slug}>"
