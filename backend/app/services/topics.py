"""Topic service: lookup, upsert and slug allocation (spec 8, R10, R14).

Topics are created from classifier output, so this module owns the rule "create a new
topic when confidence is high enough, otherwise fall back to `Other`".
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.config import settings as default_settings
from app.models import ArticleTopic, Category, Topic
from app.services.text import (
    MAX_SLUG_LENGTH,
    MAX_TOPIC_NAME_LENGTH,
    normalize_name,
    slugify,
    truncate,
)


@dataclass(frozen=True, slots=True)
class TopicAssignment:
    topic: Topic
    created: bool
    used_fallback: bool


def slug_exists(db: Session, slug: str) -> bool:
    return db.execute(select(Topic.id).where(Topic.slug == slug).limit(1)).first() is not None


def allocate_slug(db: Session, name: str) -> str:
    """Globally unique slug, numeric suffix on collision (R10).

    Uniqueness is global rather than per-category so `/trends/{slug}` stays flat.
    """
    base = slugify(name, max_length=MAX_SLUG_LENGTH - 6) or "topic"
    candidate = base
    suffix = 2
    while slug_exists(db, candidate):
        candidate = f"{truncate(base, MAX_SLUG_LENGTH - len(str(suffix)) - 1)}-{suffix}"
        suffix += 1
    return candidate


def find_by_slug(db: Session, slug: str) -> Topic | None:
    return db.execute(select(Topic).where(Topic.slug == slug)).scalar_one_or_none()


def find_by_name(db: Session, category_id: int, name: str) -> Topic | None:
    normalized = normalize_name(name)
    return db.execute(
        select(Topic).where(
            Topic.category_id == category_id, Topic.name_normalized == normalized
        )
    ).scalar_one_or_none()


def get_or_create(
    db: Session,
    category_id: int,
    name: str,
    *,
    description: str | None = None,
    is_fallback: bool = False,
) -> TopicAssignment:
    """Return the topic for `name` inside a category, creating it if needed."""
    cleaned = truncate((name or "").strip(), MAX_TOPIC_NAME_LENGTH)
    if not cleaned:
        cleaned = "Unnamed"

    existing = find_by_name(db, category_id, cleaned)
    if existing is not None:
        return TopicAssignment(topic=existing, created=False, used_fallback=existing.is_fallback)

    topic = Topic(
        category_id=category_id,
        name=cleaned,
        name_normalized=normalize_name(cleaned),
        slug=allocate_slug(db, cleaned),
        description=description,
        is_fallback=is_fallback,
    )
    db.add(topic)
    db.flush()
    return TopicAssignment(topic=topic, created=True, used_fallback=is_fallback)


def ensure_fallback_topic(
    db: Session, category: Category, config: Settings | None = None
) -> Topic:
    """The reserved `Other` topic every category has (R14)."""
    config = config or default_settings
    assignment = get_or_create(
        db,
        category.id,
        config.fallback_topic_name,
        description=f"Unclassified {category.name} articles.",
        is_fallback=True,
    )
    return assignment.topic


def resolve_for_classification(
    db: Session,
    category: Category,
    topic_name: str | None,
    confidence: float,
    *,
    description: str | None = None,
    config: Settings | None = None,
) -> TopicAssignment:
    """Apply the confidence rule from spec 8.

    A confident, specific label creates or reuses a real topic. Anything missing or
    below `classification_min_confidence` lands in the category's `Other` topic so an
    uncertain LLM answer can never invent a trend.
    """
    config = config or default_settings
    confident = bool(topic_name) and confidence >= config.classification_min_confidence

    if confident:
        return get_or_create(db, category.id, topic_name, description=description)

    fallback = ensure_fallback_topic(db, category, config)
    return TopicAssignment(topic=fallback, created=False, used_fallback=True)


def link_article(db: Session, article_id: int, topic_id: int, confidence: float | None) -> bool:
    """Idempotently attach an article to a topic. Returns True when a link was added.

    The session runs with `autoflush=False`, so pending links are flushed first;
    otherwise a link added earlier in the same transaction would not be seen and the
    composite primary key would be violated on the second call.
    """
    db.flush()

    exists = db.execute(
        select(ArticleTopic.article_id).where(
            ArticleTopic.article_id == article_id, ArticleTopic.topic_id == topic_id
        )
    ).first()
    if exists:
        return False

    db.add(ArticleTopic(article_id=article_id, topic_id=topic_id, confidence=confidence))
    db.flush()
    return True

