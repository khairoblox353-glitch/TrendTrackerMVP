"""Shared pytest fixtures.

Tests run against an in-memory SQLite database so the suite needs no running
PostgreSQL. `DATABASE_URL` is set before the application modules are imported, because
`app.config.settings` is created at import time.

The PostgreSQL-only `DISTINCT ON` query used by `services.trends` is covered by the
manual end-to-end check against the Docker database described in README.md, not here.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("LLM_ENABLED", "false")
os.environ.setdefault("RUN_SCHEDULER", "false")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.ai.base import ClassificationResult, Classifier  # noqa: E402
from app.ai.fallback import KeywordClassifier  # noqa: E402
from app.catalog import CATEGORIES  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import (  # noqa: E402
    Article,
    ArticleTopic,
    Category,
    ProcessingStatus,
    Source,
    Topic,
)
from app.services.topics import ensure_fallback_topic, get_or_create  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Iterator[Session]:
    """A session with all tables emptied before use."""
    session = SessionLocal()
    _truncate(session)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _truncate(session: Session) -> None:
    from app.models import TrendSnapshot

    for model in (TrendSnapshot, ArticleTopic, Article, Topic, Source, Category):
        session.execute(model.__table__.delete())
    session.commit()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """A TestClient whose handlers share the test session."""
    from app.api.deps import get_db

    def _override_get_db() -> Iterator[Session]:
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class AlwaysFailingClassifier(Classifier):
    """Simulates an unreachable LLM (spec 15)."""

    name = "failing"

    def __init__(self) -> None:
        self.calls = 0

    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        self.calls += 1
        raise RuntimeError("simulated LLM outage")


class ScriptedClassifier(Classifier):
    """Returns a fixed answer, or falls back when the script is missing."""

    name = "scripted"

    def __init__(self, script: dict[str, ClassificationResult] | None = None) -> None:
        self.script = script or {}
        self._fallback = KeywordClassifier()

    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        for needle, result in self.script.items():
            if needle.lower() in (title or "").lower():
                return result
        return self._fallback.classify(title, description)


@pytest.fixture
def failing_classifier() -> AlwaysFailingClassifier:
    return AlwaysFailingClassifier()


@pytest.fixture
def keyword_classifier() -> KeywordClassifier:
    return KeywordClassifier()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def categories(db: Session) -> dict[str, Category]:
    """The five categories with the full topic vocabulary and fallback topics."""
    created: dict[str, Category] = {}
    for seed in CATEGORIES:
        category = Category(name=seed.name, slug=seed.slug, description=seed.description)
        db.add(category)
        db.flush()
        created[seed.slug] = category

    for seed in CATEGORIES:
        category = created[seed.slug]
        for topic_seed in seed.topics:
            get_or_create(db, category.id, topic_seed.name, description=topic_seed.description)
        ensure_fallback_topic(db, category)

    db.commit()
    return created


@pytest.fixture
def source(db: Session, categories: dict[str, Category]) -> Source:
    source = Source(
        name="Test Feed",
        url="https://example.test",
        feed_url="https://example.test/feed.xml",
        category_id=categories["ai"].id,
    )
    db.add(source)
    db.commit()
    return source


def make_article(
    db: Session,
    *,
    title: str,
    url: str,
    published_at: datetime,
    category: Category | None = None,
    source: Source | None = None,
    description: str | None = None,
    status: str = ProcessingStatus.CLASSIFIED.value,
) -> Article:
    article = Article(
        source_id=source.id if source else None,
        category_id=category.id if category else None,
        title=title,
        url=url,
        description=description,
        published_at=published_at,
        processing_status=status,
    )
    db.add(article)
    db.flush()
    return article


def link(article: Article, topic: Topic, confidence: float = 0.9) -> None:
    from app.models import ArticleTopic as _ArticleTopic

    article.topic_links.append(_ArticleTopic(topic_id=topic.id, confidence=confidence))


def days_ago(days: int, hours: int = 12) -> datetime:
    return datetime.now(UTC) - timedelta(days=days, hours=hours)


def topic_by_name(db: Session, name: str, category_slug: str | None = None) -> Topic:
    """Look a topic up by name.

    Topic names are only unique per category — every category has an `Other` topic —
    so a category must be given when the name is not globally unique.
    """
    statement = select(Topic).where(Topic.name == name)
    if category_slug:
        statement = statement.join(Category).where(Category.slug == category_slug)
    return db.execute(statement.limit(1)).scalar_one()
