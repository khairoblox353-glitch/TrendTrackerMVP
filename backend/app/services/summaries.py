"""Topic summary refresh (R12).

`GET /api/trends/{slug}` shows an AI-generated summary of the trend. Generating it
inline would put an LLM call in the request path, so summaries are refreshed by a job
and stored on `topics.summary`. The API only ever reads the stored value.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import Classifier
from app.ai.factory import build_classifier
from app.config import Settings
from app.config import settings as default_settings
from app.models import Topic
from app.services.text import clean_whitespace, truncate
from app.services.trends import articles_for_topic

logger = logging.getLogger(__name__)

TITLES_PER_SUMMARY = 10
MIN_TITLES = 2


@dataclass(slots=True)
class SummaryResult:
    refreshed: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {"refreshed": self.refreshed, "skipped": self.skipped, "failed": self.failed}


def refresh_topic_summary(
    db: Session,
    topic: Topic,
    classifier: Classifier,
    config: Settings | None = None,
) -> bool:
    """Regenerate one topic summary. Returns True when it was updated."""
    articles = articles_for_topic(db, topic.id, limit=TITLES_PER_SUMMARY)
    titles = [article.title for article in articles if article.title]
    if len(titles) < MIN_TITLES:
        return False

    try:
        summary = classifier.summarize(topic.name, titles)
    except Exception as exc:  # noqa: BLE001 - summary failure must not break a job
        logger.warning("summary generation failed for topic %s: %s", topic.id, exc)
        return False

    cleaned = clean_whitespace(summary)
    if not cleaned or cleaned == clean_whitespace(topic.summary):
        return False

    topic.summary = truncate(cleaned, 500)
    return True


def refresh_all_summaries(
    db: Session,
    *,
    limit: int | None = None,
    classifier: Classifier | None = None,
    config: Settings | None = None,
) -> SummaryResult:
    """Refresh summaries for topics that have enough recent articles."""
    config = config or default_settings
    classifier = classifier or build_classifier(config)
    result = SummaryResult()

    statement = (
        select(Topic)
        .where(Topic.is_fallback.is_(False))
        .order_by(Topic.updated_at.desc())
    )
    if limit:
        statement = statement.limit(limit)

    for topic in db.execute(statement).scalars():
        if refresh_topic_summary(db, topic, classifier, config):
            result.refreshed += 1
        elif topic.summary:
            result.skipped += 1

    db.commit()
    return result
