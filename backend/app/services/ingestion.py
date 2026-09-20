"""Article ingestion service (spec 7, spec 15).

Pipeline: collect -> validate -> deduplicate -> save -> classify -> link topics.

Two invariants matter and are enforced here, not in the routes:

1. **An article is committed before it is classified.** A slow, broken or
   misconfigured LLM therefore delays a run but never loses data (spec 15).
2. **Classification failure is not ingestion failure.** The article is kept with
   `processing_status = 'failed'` and can be reprocessed later.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import CATEGORY_NAMES, ClassificationResult, Classifier
from app.ai.factory import build_classifier
from app.collectors.base import Collector, CollectorError, FetchResult, RawArticle
from app.collectors.registry import get_collector
from app.collectors.rss import clamp_published_at
from app.config import Settings
from app.config import settings as default_settings
from app.models import Article, Category, ProcessingStatus, Source
from app.models.types import utcnow
from app.services import topics as topic_service
from app.services.text import MAX_TITLE_LENGTH, clean_whitespace, truncate

logger = logging.getLogger(__name__)

# Articles whose classification is older than this are eligible for reprocessing.
REPROCESS_BATCH_SIZE = 50


@dataclass(slots=True)
class SourceOutcome:
    source_id: int
    source_name: str
    ok: bool
    fetched: int = 0
    new: int = 0
    duplicate: int = 0
    skipped: int = 0
    classified: int = 0
    failed: int = 0
    not_modified: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source": self.source_name,
            "ok": self.ok,
            "fetched": self.fetched,
            "new": self.new,
            "duplicate": self.duplicate,
            "skipped": self.skipped,
            "classified": self.classified,
            "failed": self.failed,
            "not_modified": self.not_modified,
            "error": self.error,
            "warnings": self.warnings[:5],
        }


@dataclass(slots=True)
class IngestionSummary:
    started_at: datetime
    finished_at: datetime | None = None
    sources_total: int = 0
    sources_ok: int = 0
    sources_failed: int = 0
    articles_fetched: int = 0
    articles_new: int = 0
    articles_duplicate: int = 0
    articles_skipped: int = 0
    articles_classified: int = 0
    articles_failed: int = 0
    errors: list[dict] = field(default_factory=list)
    sources: list[SourceOutcome] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": (self.finished_at or utcnow()).isoformat(),
            "sources_total": self.sources_total,
            "sources_ok": self.sources_ok,
            "sources_failed": self.sources_failed,
            "articles_fetched": self.articles_fetched,
            "articles_new": self.articles_new,
            "articles_duplicate": self.articles_duplicate,
            "articles_skipped": self.articles_skipped,
            "articles_classified": self.articles_classified,
            "articles_failed": self.articles_failed,
            "errors": self.errors,
            "sources": [outcome.as_dict() for outcome in self.sources],
        }


# ---------------------------------------------------------------------------
# Validation and deduplication
# ---------------------------------------------------------------------------
def existing_urls(db: Session, urls: Sequence[str]) -> set[str]:
    """URLs already stored. One query per batch instead of one per article."""
    if not urls:
        return set()
    rows = db.execute(select(Article.url).where(Article.url.in_(list(urls)))).scalars()
    return set(rows)


def normalize_for_storage(
    raw: RawArticle, config: Settings | None = None
) -> tuple[dict | None, str | None]:
    """Validate and normalize one raw item.

    Returns `(payload, warning)`. A `None` payload means the item is unusable and must
    be skipped (spec 15: invalid URL, missing title, missing published date).
    """
    config = config or default_settings

    title = clean_whitespace(raw.title)
    if not title:
        return None, "missing title"

    url = clean_whitespace(raw.url)
    if not url or not url.lower().startswith(("http://", "https://")):
        return None, "invalid url"

    published_at, warning, dropped = clamp_published_at(raw.published_at)
    if dropped:
        return None, warning

    if published_at is None:
        # Feed entries without a date are common; fall back to ingestion time so the
        # article is still counted, and record why.
        published_at = datetime.now(UTC)
        warning = warning or "missing published date"

    return (
        {
            "title": truncate(title, MAX_TITLE_LENGTH),
            "url": url,
            "description": clean_whitespace(raw.description),
            "published_at": published_at,
            "processing_status": ProcessingStatus.PENDING.value,
        },
        warning,
    )


def save_articles(
    db: Session, source: Source, raws: Iterable[RawArticle], config: Settings | None = None
) -> tuple[list[Article], int, int, list[str]]:
    """Deduplicate and persist items for one source.

    Returns `(created_articles, duplicates, skipped, warnings)`.
    """
    config = config or default_settings
    raws = list(raws)
    warnings: list[str] = []

    seen_in_batch: set[str] = set()
    candidates: list[dict] = []
    skipped = 0

    for raw in raws:
        payload, warning = normalize_for_storage(raw, config)
        if payload is None:
            skipped += 1
            warnings.append(f"skipped an entry: {warning}")
            continue
        if payload["url"] in seen_in_batch:
            skipped += 1
            continue
        seen_in_batch.add(payload["url"])
        if warning:
            warnings.append(warning)
        candidates.append(payload)

    duplicates = 0
    if candidates:
        known = existing_urls(db, [item["url"] for item in candidates])
        duplicates = len(known)
        candidates = [item for item in candidates if item["url"] not in known]

    created: list[Article] = []
    for payload in candidates:
        # A per-article savepoint keeps one bad row from discarding the whole batch.
        try:
            with db.begin_nested():
                article = Article(source_id=source.id, **payload)
                db.add(article)
            created.append(article)
        except Exception as exc:  # noqa: BLE001 - reported, not raised (spec 15)
            logger.warning("failed to store article %s: %s", payload["url"], exc)
            warnings.append(f"storage failure: {exc}")
            skipped += 1

    if created:
        db.flush()
    return created, duplicates, skipped, warnings


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def _category_lookup(db: Session) -> dict[str, Category]:
    categories = list(db.execute(select(Category)).scalars())
    return {category.name.lower(): category for category in categories}


def _resolve_category(
    categories: dict[str, Category],
    result: ClassificationResult,
    source: Source | None,
    by_id: dict[int, Category],
) -> Category | None:
    """Pick the category for a classification result.

    Resolution order, most to least specific:

    1. the category the classifier actually named;
    2. for an unrecognised answer, the source's `category_id` hint;
    3. the `AI` category as a last resort once nothing else applies.

    Step 2 is what keeps a feed-level hint useful: a health feed whose article cannot be
    matched by the offline classifier is filed under Health rather than being dumped into
    whichever category happens to be first in the taxonomy, which would quietly corrupt
    every downstream count.
    """
    named = categories.get(result.category.lower())
    if named is not None:
        return named

    if source is not None and source.category_id is not None:
        hinted = by_id.get(source.category_id)
        if hinted is not None:
            return hinted

    # An article is only left without a category if the taxonomy was never seeded, in
    # which case the caller flags it rather than guessing.
    return categories.get(CATEGORY_NAMES[0].lower())


def classify_article(
    db: Session,
    article: Article,
    classifier: Classifier,
    categories: dict[str, Category],
    config: Settings | None = None,
    source: Source | None = None,
    categories_by_id: dict[int, Category] | None = None,
) -> bool:
    """Classify one stored article and link it to a topic.

    Returns True when the article ended up classified. Any classifier exception is
    captured on the article rather than propagated (spec 15).
    """
    config = config or default_settings

    try:
        result: ClassificationResult = classifier.classify(article.title, article.description)
    except Exception as exc:  # noqa: BLE001 - classification must never abort ingestion
        logger.warning("classification failed for article %s: %s", article.id, exc)
        article.processing_status = ProcessingStatus.FAILED.value
        article.processing_error = truncate(str(exc), 500)
        article.processed_at = utcnow()
        return False

    if categories_by_id is None:
        categories_by_id = {category.id: category for category in categories.values()}
    if source is None and article.source_id is not None:
        source = db.get(Source, article.source_id)

    category = _resolve_category(categories, result, source, categories_by_id)

    if category is None:
        # Only possible if the taxonomy was never seeded; keep the article, flag it.
        article.processing_status = ProcessingStatus.FAILED.value
        article.processing_error = "no categories configured"
        article.processed_at = utcnow()
        return False

    article.category_id = category.id
    article.summary = result.summary

    assignment = topic_service.resolve_for_classification(
        db,
        category,
        result.topic,
        result.confidence,
        config=config,
    )
    topic_service.link_article(db, article.id, assignment.topic.id, result.confidence)

    article.processing_status = ProcessingStatus.CLASSIFIED.value
    article.processing_error = result.error
    article.processed_at = utcnow()
    db.flush()
    return True


def ingest_source(
    db: Session,
    source: Source,
    classifier: Classifier,
    categories: dict[str, Category],
    *,
    limit: int | None = None,
    classify: bool = True,
    collector: Collector | None = None,
    config: Settings | None = None,
) -> SourceOutcome:
    """Run one source end to end. A source-level failure is returned, not raised.

    `collector` is injectable so tests (and future non-URL source types) can supply a
    collector without going through the registry; the default resolves one by feed URL.
    """
    config = config or default_settings
    outcome = SourceOutcome(source_id=source.id, source_name=source.name, ok=False)

    owns_collector = collector is None
    try:
        if collector is None:
            collector = get_collector(source.feed_url, config=config)
        result: FetchResult = collector.collect(source)
    except CollectorError as exc:
        outcome.error = str(exc)
        source.last_error = str(exc)
        source.last_fetched_at = utcnow()
        db.flush()
        return outcome
    finally:
        if owns_collector and collector is not None:
            collector.close()

    source.last_error = None
    source.last_fetched_at = utcnow()
    if result.etag:
        source.last_etag = result.etag
    if result.modified:
        source.last_modified = result.modified

    outcome.ok = True
    outcome.not_modified = result.not_modified
    outcome.fetched = result.fetched
    outcome.skipped = result.skipped

    if result.not_modified:
        db.commit()
        return outcome

    raws = result.articles[:limit] if limit else result.articles
    created, duplicates, skipped, warnings = save_articles(db, source, raws, config)
    outcome.new = len(created)
    outcome.duplicate = duplicates
    outcome.skipped += skipped
    outcome.warnings = warnings

    # Commit before classification so stored articles survive any later failure.
    db.commit()

    if classify:
        by_id = {category.id: category for category in categories.values()}
        for article in created:
            if classify_article(
                db, article, classifier, categories, config, source=source, categories_by_id=by_id
            ):
                outcome.classified += 1
            else:
                outcome.failed += 1
        db.commit()

    return outcome


def ingest_all(
    db: Session,
    source_ids: Sequence[int] | None = None,
    *,
    limit_per_source: int | None = None,
    classify: bool = True,
    classifier: Classifier | None = None,
    collector: Collector | None = None,
    config: Settings | None = None,
) -> IngestionSummary:
    """Run the whole ingestion pipeline over the active sources.

    `collector` injects the same collector instance for every source, which is how the
    tests exercise the pipeline without network access.
    """
    config = config or default_settings
    classifier = classifier or build_classifier(config)
    summary = IngestionSummary(started_at=utcnow())

    statement = select(Source).where(Source.is_active.is_(True)).order_by(Source.id)
    if source_ids:
        statement = select(Source).where(Source.id.in_(list(source_ids))).order_by(Source.id)

    sources = list(db.execute(statement).scalars())
    summary.sources_total = len(sources)

    if not sources:
        summary.finished_at = utcnow()
        return summary

    categories = _category_lookup(db)

    for source in sources:
        try:
            outcome = ingest_source(
                db,
                source,
                classifier,
                categories,
                limit=limit_per_source,
                classify=classify,
                collector=collector,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - one source must not stop the run
            db.rollback()
            logger.exception("unexpected failure ingesting source %s", source.id)
            outcome = SourceOutcome(
                source_id=source.id, source_name=source.name, ok=False, error=str(exc)
            )

        summary.sources.append(outcome)
        summary.articles_fetched += outcome.fetched
        summary.articles_new += outcome.new
        summary.articles_duplicate += outcome.duplicate
        summary.articles_skipped += outcome.skipped
        summary.articles_classified += outcome.classified
        summary.articles_failed += outcome.failed

        if outcome.ok:
            summary.sources_ok += 1
        else:
            summary.sources_failed += 1
            summary.errors.append({"source": source.name, "message": outcome.error or "unknown"})

        for warning in outcome.warnings[:2]:
            summary.errors.append({"source": source.name, "message": warning})

    summary.finished_at = utcnow()
    return summary


# ---------------------------------------------------------------------------
# Reprocessing
# ---------------------------------------------------------------------------
def pending_articles(db: Session, limit: int = REPROCESS_BATCH_SIZE) -> list[Article]:
    """Articles that were never successfully classified, newest first."""
    statement = (
        select(Article)
        .options(selectinload(Article.topics))
        .where(
            Article.processing_status.in_(
                [ProcessingStatus.PENDING.value, ProcessingStatus.FAILED.value]
            )
        )
        .order_by(Article.published_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).unique().scalars())


def reprocess_pending(
    db: Session,
    *,
    limit: int = REPROCESS_BATCH_SIZE,
    classifier: Classifier | None = None,
    config: Settings | None = None,
) -> dict:
    """Retry classification for stored articles. Used by the CLI and by operators."""
    config = config or default_settings
    classifier = classifier or build_classifier(config)
    categories = _category_lookup(db)

    articles = pending_articles(db, limit)
    classified = 0
    failed = 0

    for article in articles:
        if classify_article(db, article, classifier, categories, config):
            classified += 1
        else:
            failed += 1

    db.commit()
    return {
        "processed": len(articles),
        "classified": classified,
        "failed": failed,
        "remaining": pending_count(db),
    }


def pending_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(Article.id)).where(
                Article.processing_status.in_(
                    [ProcessingStatus.PENDING.value, ProcessingStatus.FAILED.value]
                )
            )
        ).scalar_one()
    )
