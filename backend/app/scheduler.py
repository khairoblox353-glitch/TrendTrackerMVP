"""Scheduled jobs (spec 14).

Uses APScheduler in-process — no Celery, no Kafka, no broker (spec 19.3-19.5). Two
jobs mirror the cadence in the specification:

    every `INGEST_INTERVAL_MINUTES`  (default 60)  -> fetch feeds and classify
    every `RECALCULATE_INTERVAL_MINUTES` (default 360) -> recompute trend snapshots

Scheduling is **opt-in** via `RUN_SCHEDULER=true`, and `docker-compose.yml` runs a
single API replica, because two schedulers against one database would duplicate work
(R17). The same work is always available on demand through
`POST /api/ingestion/run` and `POST /api/trends/recalculate`, which is the recommended
path when an external cron is available.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import Settings
from app.config import settings as default_settings
from app.database import SessionLocal
from app.services import ingestion as ingestion_service
from app.services.summaries import refresh_all_summaries
from app.trend import engine as trend_engine

logger = logging.getLogger(__name__)

INGEST_JOB_ID = "ingest_feeds"
RECALCULATE_JOB_ID = "recalculate_trends"


def run_ingestion_job(config: Settings | None = None) -> dict:
    """Fetch every active source, store new articles and classify them."""
    config = config or default_settings
    db: Session = SessionLocal()
    try:
        summary = ingestion_service.ingest_all(db, config=config)
        logger.info(
            "ingestion finished: %s new, %s duplicate, %s classified, %s failed",
            summary.articles_new,
            summary.articles_duplicate,
            summary.articles_classified,
            summary.articles_failed,
        )
        return summary.as_dict()
    except Exception:  # noqa: BLE001 - a failed job must not kill the scheduler
        db.rollback()
        logger.exception("ingestion job failed")
        return {"error": "ingestion job failed"}
    finally:
        db.close()


def run_recalculation_job(config: Settings | None = None) -> dict:
    """Recompute snapshots for today and refresh trend summaries."""
    config = config or default_settings
    db: Session = SessionLocal()
    try:
        result = trend_engine.recalculate(db, config=config)
        payload = result.as_dict()

        summaries = refresh_all_summaries(db, limit=20, config=config)
        payload["summaries"] = summaries.as_dict()

        logger.info(
            "recalculation finished: %s snapshots over %s days, %s emerging",
            result.snapshots_written,
            len(result.dates_processed),
            result.emerging_topics,
        )
        return payload
    except Exception:  # noqa: BLE001 - a failed job must not kill the scheduler
        db.rollback()
        logger.exception("recalculation job failed")
        return {"error": "recalculation job failed"}
    finally:
        db.close()


def build_scheduler(config: Settings | None = None) -> BackgroundScheduler:
    """Create a scheduler with both jobs registered. Does not start it.

    The default in-memory jobstore is correct for this MVP: jobs are re-registered on
    every process start, so persisting them would only risk duplicate work (spec 19.1).
    """
    config = config or default_settings

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_ingestion_job,
        trigger="interval",
        minutes=config.ingest_interval_minutes,
        id=INGEST_JOB_ID,
        name="Fetch RSS feeds and classify articles",
        kwargs={"config": config},
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        run_recalculation_job,
        trigger="interval",
        minutes=config.recalculate_interval_minutes,
        id=RECALCULATE_JOB_ID,
        name="Recalculate trend snapshots and summaries",
        kwargs={"config": config},
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


def start_scheduler(config: Settings | None = None) -> BackgroundScheduler | None:
    """Start the scheduler when `RUN_SCHEDULER` is enabled."""
    config = config or default_settings
    if not config.run_scheduler:
        logger.info("scheduler disabled (RUN_SCHEDULER is not set)")
        return None

    scheduler = build_scheduler(config)
    scheduler.start()
    logger.info(
        "scheduler started: ingestion every %s min, trends every %s min",
        config.ingest_interval_minutes,
        config.recalculate_interval_minutes,
    )
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler | None) -> None:
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
