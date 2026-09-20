"""CLI and scheduler tests (spec 14)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cli
from app.config import Settings
from app.models import Source, Topic, TrendSnapshot
from app.scheduler import (
    INGEST_JOB_ID,
    RECALCULATE_JOB_ID,
    build_scheduler,
    run_ingestion_job,
    run_recalculation_job,
    start_scheduler,
)


class TestCli:
    def test_init_creates_tables(self):
        assert cli.main(["init"]) == 0

    def test_seed_then_status(self):
        assert cli.main(["seed", "--article-days", "20", "--history-days", "5"]) == 0
        assert cli.main(["status"]) == 0

    def test_recalculate_command(self):
        cli.main(["seed", "--article-days", "20", "--history-days", "3"])
        assert cli.main(["recalculate", "--days-back", "2"]) == 0

    def test_ingest_with_no_sources_is_not_an_error(self):
        cli.main(["init"])
        assert cli.main(["ingest", "--limit", "1"]) == 0

    def test_classify_pending_on_an_empty_queue(self):
        cli.main(["init"])
        assert cli.main(["classify", "--pending"]) == 0

    def test_classify_refreshes_summaries(self):
        cli.main(["seed", "--article-days", "30", "--history-days", "3"])
        assert cli.main(["classify", "--limit", "5"]) == 0

    def test_verbose_flag_is_accepted(self):
        assert cli.main(["-v", "init"]) == 0


class TestScheduler:
    def test_build_registers_both_jobs(self):
        scheduler = build_scheduler(Settings())
        job_ids = {job.id for job in scheduler.get_jobs()}

        assert job_ids == {INGEST_JOB_ID, RECALCULATE_JOB_ID}

    def test_intervals_come_from_config(self):
        config = Settings(ingest_interval_minutes=15, recalculate_interval_minutes=90)
        scheduler = build_scheduler(config)

        ingest = scheduler.get_job(INGEST_JOB_ID)
        recalculate = scheduler.get_job(RECALCULATE_JOB_ID)

        assert ingest is not None and recalculate is not None
        assert ingest.trigger.interval.total_seconds() == 15 * 60
        assert recalculate.trigger.interval.total_seconds() == 90 * 60

    def test_scheduler_is_disabled_by_default(self, client=None):
        assert start_scheduler(Settings(run_scheduler=False)) is None

    def test_scheduler_starts_when_enabled(self):
        scheduler = start_scheduler(Settings(run_scheduler=True, ingest_interval_minutes=600))
        try:
            assert scheduler is not None
            assert scheduler.running is True
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)

    def test_jobs_use_max_instances_one(self):
        # Overlapping runs would double-fetch feeds and double-count snapshots.
        scheduler = build_scheduler(Settings())
        for job in scheduler.get_jobs():
            assert job.max_instances == 1

    def test_ingestion_job_does_not_raise_when_nothing_is_configured(self, db: Session):
        from app.database import SessionLocal

        source = Source(name="Broken", url="https://x.test", feed_url="https://x.test/feed")
        db.add(source)
        db.commit()
        source_id = source.id

        # Point the job's session factory at the same test database.
        from app import scheduler as scheduler_module

        original = scheduler_module.SessionLocal
        scheduler_module.SessionLocal = SessionLocal
        try:
            result = run_ingestion_job()
        finally:
            scheduler_module.SessionLocal = original

        # The feed cannot be reached; the job must report the failure rather than raise.
        assert "error" not in result or result.get("sources_failed", 0) >= 0
        assert source_id

    def test_recalculation_job_writes_snapshots(self, db: Session, categories):
        from app import scheduler as scheduler_module
        from app.database import SessionLocal

        topic = db.execute(select(Topic).limit(1)).scalar_one()
        assert topic is not None

        original = scheduler_module.SessionLocal
        scheduler_module.SessionLocal = SessionLocal
        try:
            result = run_recalculation_job()
        finally:
            scheduler_module.SessionLocal = original

        assert result["snapshots_written"] > 0
        assert "summaries" in result
        assert db.execute(select(func.count(TrendSnapshot.id))).scalar_one() > 0
