"""Association model between articles and topics (spec 6, R2).

Modeled as a class rather than a `Table` so the extra `confidence` column can be
carried and so ingestion can upsert links idempotently.
"""

from __future__ import annotations

import decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.topic import Topic


class ArticleTopic(Base):
    __tablename__ = "article_topics"
    # `topic_id` is only the second column of the composite primary key, so the
    # primary-key index cannot serve topic-only lookups. Those are hot: the topic
    # article counts, the latest-articles list on the trend detail page and the
    # scoring engine all filter by `topic_id` alone.
    __table_args__ = (Index("ix_article_topics_topic_id", "topic_id"),)

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )
    confidence: Mapped[decimal.Decimal | None] = mapped_column(Numeric(4, 3))

    article: Mapped["Article"] = relationship(back_populates="topic_links")
    topic: Mapped["Topic"] = relationship(back_populates="article_links")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<ArticleTopic article={self.article_id} topic={self.topic_id}>"
