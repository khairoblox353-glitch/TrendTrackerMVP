"""Command line entrypoint.

    python -m app.cli init                 # create tables
    python -m app.cli seed                 # taxonomy + demo data + 30 days of snapshots
    python -m app.cli seed --reset         # rebuild the demo dataset
    python -m app.cli status               # row counts and pending classification
    python -m app.cli ingest               # run the RSS pipeline once
    python -m app.cli recalculate          # recompute trend snapshots
    python -m app.cli classify --pending   # retry classification of stored articles

The same services back the HTTP endpoints, so the CLI is only a thin wrapper for local
development and for cron.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from app.config import settings
from app.database import SessionLocal, init_db
from app.services import ingestion as ingestion_service
from app.services import seed as seed_service
from app.services.summaries import refresh_all_summaries
from app.trend import engine as trend_engine


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def _emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2, default=str))


def command_init(_: argparse.Namespace) -> int:
    init_db()
    _emit({"status": "ok", "message": "tables created", "database": settings.database_url})
    return 0


def command_seed(args: argparse.Namespace) -> int:
    init_db()
    db = SessionLocal()
    try:
        result = seed_service.seed_all(
            db,
            article_days=args.article_days,
            history_days=args.history_days,
            rng_seed=args.seed,
            reset=args.reset,
        )
        _emit({"status": "ok", **result.as_dict(), "totals": seed_service.seed_summary(db)})
    finally:
        db.close()
    return 0


def command_status(_: argparse.Namespace) -> int:
    init_db()
    db = SessionLocal()
    try:
        _emit(
            {
                "database": settings.database_url,
                "totals": seed_service.seed_summary(db),
                "pending_classification": ingestion_service.pending_count(db),
                "sources": _source_status(db),
            }
        )
    finally:
        db.close()
    return 0


def _source_status(db) -> list[dict]:
    from sqlalchemy import select

    from app.models import Source

    return [
        {
            "id": source.id,
            "name": source.name,
            "active": source.is_active,
            "last_fetched_at": source.last_fetched_at,
            "last_error": source.last_error,
        }
        for source in db.execute(select(Source).order_by(Source.id)).scalars()
    ]


def command_ingest(args: argparse.Namespace) -> int:
    init_db()
    db = SessionLocal()
    try:
        summary = ingestion_service.ingest_all(
            db,
            limit_per_source=args.limit,
            classify=not args.no_classify,
        )
        _emit(summary.as_dict())
    finally:
        db.close()
    return 0


def command_recalculate(args: argparse.Namespace) -> int:
    init_db()
    db = SessionLocal()
    try:
        result = trend_engine.recalculate(db, days_back=args.days_back)
        payload = result.as_dict()
        payload["summaries"] = refresh_all_summaries(db).as_dict()
        _emit(payload)
    finally:
        db.close()
    return 0


def command_classify(args: argparse.Namespace) -> int:
    init_db()
    db = SessionLocal()
    try:
        if args.pending:
            _emit(ingestion_service.reprocess_pending(db, limit=args.limit))
        else:
            _emit(refresh_all_summaries(db, limit=args.limit).as_dict())
    finally:
        db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Trend Tracker CLI")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="create database tables").set_defaults(func=command_init)

    seed_parser = subparsers.add_parser("seed", help="load taxonomy and demo data")
    seed_parser.add_argument("--reset", action="store_true", help="delete demo data first")
    seed_parser.add_argument("--article-days", type=int, default=seed_service.DEFAULT_ARTICLE_DAYS)
    seed_parser.add_argument("--history-days", type=int, default=seed_service.DEFAULT_HISTORY_DAYS)
    seed_parser.add_argument("--seed", type=int, default=seed_service.DEFAULT_SEED)
    seed_parser.set_defaults(func=command_seed)

    subparsers.add_parser("status", help="show row counts").set_defaults(func=command_status)

    ingest_parser = subparsers.add_parser("ingest", help="run the RSS pipeline once")
    ingest_parser.add_argument("--limit", type=int, default=None, help="max articles per source")
    ingest_parser.add_argument(
        "--no-classify", action="store_true", help="store without classifying"
    )
    ingest_parser.set_defaults(func=command_ingest)

    recalc_parser = subparsers.add_parser("recalculate", help="recompute trend snapshots")
    recalc_parser.add_argument("--days-back", type=int, default=1)
    recalc_parser.set_defaults(func=command_recalculate)

    classify_parser = subparsers.add_parser("classify", help="retry classification or summaries")
    classify_parser.add_argument(
        "--pending", action="store_true", help="reclassify pending/failed articles"
    )
    classify_parser.add_argument("--limit", type=int, default=50)
    classify_parser.set_defaults(func=command_classify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover - interactive use
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
