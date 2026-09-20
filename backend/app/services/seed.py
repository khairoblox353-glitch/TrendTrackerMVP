"""Seed data (spec 17, R13).

Generates a deterministic demo dataset so the API and the dashboard can be built
before any real feed is wired up:

  * 5 categories, 20 topics plus one reserved `Other` fallback per category;
  * synthetic articles spread over the last 60 days;
  * trend snapshots for the last 30 days, produced by the **real** `TrendEngine`
    rather than by synthetic numbers.

Because snapshots come from the production code path, seed data cannot drift from the
algorithm, and the seeded history already exercises the growing, emerging and
declining branches.

A fixed RNG seed means two runs produce identical data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.base import ClassificationResult, Classifier
from app.catalog import CATEGORIES, DEFAULT_SOURCES
from app.config import Settings
from app.config import settings as default_settings
from app.models import (
    Article,
    ArticleTopic,
    Category,
    ProcessingStatus,
    Source,
    Topic,
    TrendSnapshot,
)
from app.services import topics as topic_service
from app.services.text import MAX_TITLE_LENGTH, truncate
from app.services.topics import ensure_fallback_topic, get_or_create
from app.trend import engine as trend_engine

DEFAULT_SEED = 20260920
DEFAULT_HISTORY_DAYS = 30
DEFAULT_ARTICLE_DAYS = 45

# Marker carried by every URL `_unique_url` generates. Seeded articles are identified
# by this prefix, and both the generator and `reset_demo_data` read the constant, so
# the marker cannot drift between writing and deleting seeded rows. Real ingested
# articles always use a real URL, so they never match.
SEED_URL_PREFIX = "https://seed.trend-tracker.local/"

# Article density per topic per day in a baseline window. At the default 7-day window
# this rounds to two articles per topic per window, which puts a default run in the
# 200-300 range: inside the 100-500 the specification asks for, with enough articles per
# topic for a readable chart.
ARTICLES_PER_TOPIC_PER_DAY = 0.3

# Per-topic momentum: a multiplier applied to the most recent comparison window.
#
#   momentum 3.2  -> current window ~3.2x the previous one -> growth ~+250%
#   momentum 1.0  -> current window matches the previous one -> growth ~0% (stable)
#   momentum 0.35 -> current window ~35% of the previous     -> growth ~-50%
#
# Momentum is applied only inside the current window (see `_make_articles`), which makes
# the seeded growth equal to `momentum - 1` and the demo charts predictable (spec 17).
TOPIC_MOMENTUM: dict[str, float] = {
    "AI Agents": 3.2,
    "AI Infrastructure": 1.9,
    "Large Language Models": 1.15,
    "AI Policy": 0.6,
    "Semiconductors": 1.5,
    "Cloud Computing": 1.05,
    "Cybersecurity": 1.25,
    "Consumer Devices": 0.75,
    "Crypto Markets": 1.7,
    "Interest Rates": 0.45,
    "Startup Funding": 0.35,
    "Digital Banking": 0.8,
    "Game Releases": 1.35,
    "Esports": 0.5,
    "Game Engines": 2.0,
    "Console Hardware": 1.0,
    "Biotech": 0.95,
    "Mental Health": 1.1,
    "Digital Health": 2.4,
    "Public Health": 0.55,
}
DEFAULT_MOMENTUM = 1.0

# Floor on the per-window count. Without it a low-momentum topic could round down to zero
# articles in a window, which would read as a broken trend rather than a declining one.
MIN_ARTICLES_PER_WINDOW = 1

TITLE_PATTERNS: tuple[str, ...] = (
    "{topic}: what changed this week",
    "Inside the latest {topic} push",
    "{topic} is having a moment",
    "Why {topic} matters right now",
    "{topic} update draws industry attention",
    "Analysts weigh in on {topic}",
    "A closer look at {topic}",
    "{topic} hits a new milestone",
    "The state of {topic} in 2026",
    "{topic} adoption keeps climbing",
    "New report questions the pace of {topic}",
    "{topic} spending shifts to new buyers",
    "{topic} faces fresh scrutiny",
    "{topic} roadmap points to a busier quarter",
    "Teams rethink their {topic} plans",
)

DESCRIPTION_PATTERNS: tuple[str, ...] = (
    "A short briefing on recent {topic} developments and what they mean for the sector.",
    "Coverage of the newest {topic} announcements, with context on the wider market.",
    "Practical notes on {topic}: costs, timelines and the trade-offs teams are weighing.",
    "An analysis of {topic} momentum based on vendor statements and public data.",
    "The key numbers behind the latest {topic} headlines, explained in plain language.",
)


@dataclass(slots=True)
class SeedResult:
    categories: int = 0
    topics: int = 0
    topics_curated: int = 0
    topics_fallback: int = 0
    sources: int = 0
    articles: int = 0
    snapshots: int = 0
    history_days: int = 0

    def as_dict(self) -> dict:
        return {
            "categories": self.categories,
            "topics": self.topics,
            "topics_curated": self.topics_curated,
            "topics_fallback": self.topics_fallback,
            "sources": self.sources,
            "articles": self.articles,
            "snapshots": self.snapshots,
            "history_days": self.history_days,
        }


class OfflineSummarizer(Classifier):
    """Deterministic stand-in for the LLM during seeding.

    Seeding must never need a network call, so trend summaries are composed from the
    recent article titles locally. Real deployments refresh them through the LLM job.
    """

    name = "offline"

    def classify(self, title: str, description: str | None = None) -> ClassificationResult:
        return ClassificationResult.fallback(provider=self.name)

    def summarize(self, title: str, descriptions: list[str]) -> str | None:
        if not descriptions:
            return None
        sample = "; ".join(descriptions[:2])
        return truncate(
            f"{title} appears in {len(descriptions)} recent articles, including: {sample}.",
            240,
        )


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
def seed_categories(db: Session) -> dict[str, Category]:
    """Create the five categories. Idempotent by slug."""
    by_slug: dict[str, Category] = {}

    for seed in CATEGORIES:
        category = db.execute(
            select(Category).where(Category.slug == seed.slug)
        ).scalar_one_or_none()
        if category is None:
            category = Category(name=seed.name, slug=seed.slug, description=seed.description)
            db.add(category)
            db.flush()
        by_slug[seed.slug] = category

    db.flush()
    return by_slug


def seed_topics(db: Session, categories: dict[str, Category]) -> int:
    """Create the initial topic vocabulary and one `Other` topic per category (R14).

    Returns the number of topics created by this call, which is 0 on a re-run.
    """
    created = 0
    for seed in CATEGORIES:
        category = categories[seed.slug]
        for topic_seed in seed.topics:
            assignment = get_or_create(
                db, category.id, topic_seed.name, description=topic_seed.description
            )
            if assignment.created:
                created += 1
        ensure_fallback_topic(db, category)
    db.commit()
    return created


def topic_counts(db: Session) -> dict[str, int]:
    """Topic totals split by purpose, so `seed` output is unambiguous."""
    curated = int(
        db.execute(select(func.count(Topic.id)).where(Topic.is_fallback.is_(False))).scalar_one()
    )
    fallback = int(
        db.execute(select(func.count(Topic.id)).where(Topic.is_fallback.is_(True))).scalar_one()
    )
    return {"curated": curated, "fallback": fallback, "total": curated + fallback}


def seed_sources(db: Session, categories: dict[str, Category]) -> int:
    """Install the default RSS feeds. Seeding never fetches them."""
    created = 0
    for seed in DEFAULT_SOURCES:
        exists = db.execute(
            select(Source.id).where(Source.feed_url == seed.feed_url).limit(1)
        ).first()
        if exists:
            continue
        category = categories.get(seed.category_slug) if seed.category_slug else None
        db.add(
            Source(
                name=seed.name,
                url=seed.url,
                feed_url=seed.feed_url,
                category_id=category.id if category else None,
            )
        )
        created += 1
    db.commit()
    return created


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------
def _articles_per_window(momentum: float, window_days: int) -> int:
    """Deterministic article count for one topic in one comparison window.

    Derived from the baseline density and the topic's momentum, then floored. Because
    the count is computed rather than sampled, a topic's current and previous window
    counts are exactly proportional to its momentum, so the resulting growth rate is
    predictable and can be asserted on in tests.
    """
    baseline = ARTICLES_PER_TOPIC_PER_DAY * window_days
    return max(int(round(baseline * momentum)), MIN_ARTICLES_PER_WINDOW)


def _spread_articles(
    rng: random.Random,
    count: int,
    block_start: int,
    window_days: int,
    now: datetime,
) -> list[datetime]:
    """Spread `count` publication times across one window-length block.

    `block_start` is the offset in days *before* yesterday, so block 0 covers the most
    recent window and block 1 the window before it. Articles are rotated across the days
    of the block rather than stacked on one day, which keeps the chart continuous.
    """
    moments: list[datetime] = []
    for index in range(count):
        days_ago = block_start + (index % window_days)
        moments.append(_random_moment(rng, now, days_ago))
    return moments


def _random_moment(rng: random.Random, now: datetime, days_ago: int) -> datetime:
    """A random moment within a past day.

    Never "today": the scoring window is half-open and excludes the snapshot date, so
    articles stamped today would not be counted and the newest topics would look empty.
    """
    day = (now - timedelta(days=days_ago + 1)).date()
    return datetime.combine(day, time.min, tzinfo=UTC) + timedelta(
        hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
    )


def _make_articles(
    rng: random.Random,
    categories: dict[str, Category],
    topics_by_category: dict[str, list[Topic]],
    now: datetime,
    days: int,
    window_days: int,
) -> list[tuple[Article, int]]:
    """Build `(article, topic_id)` pairs block by block.

    Structure of a `days == 45`, `window_days == 7` default run:

        block 0  days 0-6    current window   -> count scaled by momentum
        block 1  days 7-13   previous window  -> baseline count
        block 2+ days 14+    older history    -> baseline count, charted but not compared

    Anchoring momentum to the *current window* is what makes the seeded growth equal to
    `momentum - 1`. The topic is attached explicitly rather than recovered from the URL,
    so seeding and scoring can never disagree.
    """
    created: list[tuple[Article, int]] = []
    used_urls: set[str] = set()

    blocks = max(1, days // window_days)

    for category_seed in CATEGORIES:
        category = categories[category_seed.slug]
        real_topics = [t for t in topics_by_category[category_seed.slug] if not t.is_fallback]
        if not real_topics:
            continue

        for block in range(blocks):
            # Only the newest block carries momentum; every older block is baseline.
            for topic in real_topics:
                momentum = TOPIC_MOMENTUM.get(topic.name, DEFAULT_MOMENTUM) if block == 0 else 1.0
                count = _articles_per_window(momentum, window_days)

                for published_at in _spread_articles(
                    rng, count, block * window_days, window_days, now
                ):
                    url = _unique_url(category_seed.slug, topic.slug, published_at, used_urls)
                    article = Article(
                        source_id=None,
                        category_id=category.id,
                        title=truncate(
                            rng.choice(TITLE_PATTERNS).format(topic=topic.name),
                            MAX_TITLE_LENGTH,
                        ),
                        description=rng.choice(DESCRIPTION_PATTERNS).format(topic=topic.name),
                        summary=None,
                        url=url,
                        published_at=published_at,
                        processing_status=ProcessingStatus.CLASSIFIED.value,
                        processed_at=published_at,
                    )
                    created.append((article, topic.id))

    return created


def _unique_url(category_slug: str, topic_slug: str, published_at: datetime, used: set[str]) -> str:
    base = f"{SEED_URL_PREFIX}{category_slug}/{topic_slug}/{published_at:%Y%m%d%H%M}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def seed_articles(
    db: Session,
    categories: dict[str, Category],
    *,
    days: int = DEFAULT_ARTICLE_DAYS,
    window_days: int | None = None,
    rng_seed: int = DEFAULT_SEED,
    now: datetime | None = None,
    config: Settings | None = None,
) -> int:
    """Create synthetic articles and their topic links.

    `window_days` must match the window the engine will score with, because it is the
    boundary at which each topic's momentum starts (see `_daily_rate`).
    """
    config = config or default_settings
    window_days = window_days or config.trend_window_days
    now = now or datetime.now(UTC)
    rng = random.Random(rng_seed)

    topics_by_category: dict[str, list[Topic]] = {
        seed.slug: list(
            db.execute(
                select(Topic).where(Topic.category_id == categories[seed.slug].id)
            ).scalars()
        )
        for seed in CATEGORIES
    }

    pairs = _make_articles(rng, categories, topics_by_category, now, days, window_days)
    if not pairs:
        return 0

    existing = set(db.execute(select(Article.url)).scalars())
    fresh = [(article, topic_id) for article, topic_id in pairs if article.url not in existing]
    if not fresh:
        return 0

    db.add_all([article for article, _ in fresh])
    db.flush()

    for article, topic_id in fresh:
        topic_service.link_article(db, article.id, topic_id, 0.95)

    db.commit()
    return len(fresh)


def seed_history(
    db: Session,
    *,
    days: int = DEFAULT_HISTORY_DAYS,
    window_days: int | None = None,
    config: Settings | None = None,
) -> tuple[int, int]:
    """Build snapshot history with the real engine (R13).

    Returns `(snapshots_written, days_processed)`.
    """
    config = config or default_settings
    window_days = window_days or config.trend_window_days

    result = trend_engine.recalculate(
        db,
        snapshot_date=datetime.now(UTC).date(),
        window_days=window_days,
        days_back=days,
        config=config,
    )
    return result.snapshots_written, len(result.dates_processed)


def _has_snapshots(db: Session) -> bool:
    """True when any trend snapshot already exists.

    Distinguishes a fresh database (nothing to lose) from a populated one, where a plain
    `seed` must not recalculate history that real articles produced.
    """
    return db.execute(select(TrendSnapshot.id).limit(1)).first() is not None


def _fill_missing_summaries(db: Session, *, classifier: Classifier, config: Settings) -> int:
    """Generate summaries only for topics that have none yet.

    `refresh_all_summaries` skips a topic when the generated text equals the stored one,
    but it would still replace a *different* summary, and on a populated database that
    summary may have come from real articles. Restricting the topic set to
    `summary IS NULL` keeps a plain `seed` additive while still filling the dashboard on
    a fresh database.
    """
    from app.services.summaries import refresh_topic_summary

    refreshed = 0
    statement = (
        select(Topic)
        .where(Topic.is_fallback.is_(False), Topic.summary.is_(None))
        .order_by(Topic.id)
    )
    for topic in db.execute(statement).scalars():
        if refresh_topic_summary(db, topic, classifier, config):
            refreshed += 1

    db.commit()
    return refreshed


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def seed_all(
    db: Session,
    *,
    article_days: int = DEFAULT_ARTICLE_DAYS,
    history_days: int = DEFAULT_HISTORY_DAYS,
    window_days: int | None = None,
    rng_seed: int = DEFAULT_SEED,
    with_sources: bool = True,
    config: Settings | None = None,
    reset: bool = False,
    include_ingested: bool = False,
) -> SeedResult:
    """Seed everything in dependency order. Idempotent unless `reset` is set.

    `reset` only removes seeded articles, so `seed --reset` can never destroy real
    ingested data. Passing `include_ingested=True` additionally wipes real articles and
    every snapshot; it is an explicit opt-in and defaults to the safe behaviour.

    Seeding is additive once the dataset exists: snapshot history is only rebuilt for a
    reset or on a database that has no snapshots yet, and summaries are only generated
    for topics that have none. Both would otherwise overwrite values that real ingested
    articles produced.
    """
    from app.services.summaries import refresh_all_summaries

    config = config or default_settings
    window_days = window_days or config.trend_window_days
    result = SeedResult()

    if reset:
        reset_demo_data(db, include_ingested=include_ingested)

    categories = seed_categories(db)
    result.categories = len(categories)

    seed_topics(db, categories)
    counts = topic_counts(db)
    result.topics = counts["total"]
    result.topics_curated = counts["curated"]
    result.topics_fallback = counts["fallback"]

    if with_sources:
        result.sources = seed_sources(db, categories)

    result.articles = seed_articles(
        db,
        categories,
        days=article_days,
        window_days=window_days,
        rng_seed=rng_seed,
        config=config,
    )

    # History is rebuilt on a reset, and on a fresh database where there is nothing to
    # lose. On a populated database the existing snapshots may have been derived from
    # real articles, so recalculating every topic from seed data alone would silently
    # rewrite that history (finding #22).
    if reset or not _has_snapshots(db):
        snapshots, days_processed = seed_history(
            db, days=history_days, window_days=window_days, config=config
        )
        result.snapshots = snapshots
        result.history_days = days_processed

    # A reset owns the whole demo dataset, so refreshing every summary is correct there.
    # Otherwise only fill topics that have no summary yet, so text derived from real
    # articles survives a plain `seed` (finding #4).
    if reset:
        refresh_all_summaries(db, classifier=OfflineSummarizer(), config=config)
    else:
        _fill_missing_summaries(db, classifier=OfflineSummarizer(), config=config)

    return result


def reset_demo_data(db: Session, *, include_ingested: bool = False) -> None:
    """Delete the seeded demo dataset. Real data and the taxonomy are kept.

    Seeded articles are matched by their URL prefix (`SEED_URL_PREFIX`) rather than by a
    table-wide delete. Real ingested articles share the `articles`, `article_topics` and
    `topics` tables with the demo dataset, so the old unconditional deletes destroyed
    them (finding #1).

    Topics are never deleted: they are a shared taxonomy that real articles link to, and
    removing a topic cascades into `article_topics`, silently unlinking those articles.
    Categories and sources are kept for the same reason. Only snapshots whose topic has
    no articles left are dropped, which is enough to clear the demo history.

    `include_ingested=True` opts into a full wipe of every article and snapshot. It has
    to be requested explicitly, so the default is non-destructive to real data.
    """
    if include_ingested:
        db.execute(TrendSnapshot.__table__.delete())
        db.execute(ArticleTopic.__table__.delete())
        db.execute(Article.__table__.delete())
        db.commit()
        return

    seeded_ids = select(Article.id).where(Article.url.startswith(SEED_URL_PREFIX))

    # Links go first: these rows belong to the seeded articles being removed, and SQLite
    # does not apply the ON DELETE CASCADE unless foreign key enforcement is enabled.
    db.execute(ArticleTopic.__table__.delete().where(ArticleTopic.article_id.in_(seeded_ids)))
    db.execute(Article.__table__.delete().where(Article.url.startswith(SEED_URL_PREFIX)))

    # Snapshots are keyed to topics, not to articles, so they cannot be narrowed by URL.
    # Drop only the snapshots of topics that now have no articles at all: any topic a
    # real article still links to keeps its history.
    db.execute(
        TrendSnapshot.__table__.delete().where(
            ~TrendSnapshot.topic_id.in_(select(ArticleTopic.topic_id))
        )
    )
    db.commit()


def seed_summary(db: Session) -> dict:
    """Row counts used by `seed --status`."""
    return {
        "categories": int(db.execute(select(func.count(Category.id))).scalar_one()),
        "sources": int(db.execute(select(func.count(Source.id))).scalar_one()),
        "topics": int(db.execute(select(func.count(Topic.id))).scalar_one()),
        "articles": int(db.execute(select(func.count(Article.id))).scalar_one()),
        "snapshots": int(db.execute(select(func.count(TrendSnapshot.id))).scalar_one()),
    }
