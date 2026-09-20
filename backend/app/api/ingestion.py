"""Operational endpoints (spec 11, spec 14).

These endpoints run the same services the scheduler runs, so an external cron job,
a CI smoke test and the in-process scheduler all take one code path.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import __version__
from app.ai.factory import classifier_status
from app.api.deps import get_db
from app.api.errors import ValidationError
from app.config import settings
from app.models import Source
from app.schemas.ingestion import HealthResponse, IngestionRequest, RecalculateRequest
from app.services import ingestion as ingestion_service
from app.trend import engine as trend_engine

router = APIRouter(tags=["operations"])


@router.get("/health", response_model=HealthResponse, summary="Liveness and dependency check")
def health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    """Report whether this instance can actually serve traffic (spec 11).

    The probe touches a real table instead of only opening a connection: `SELECT 1`
    succeeds against an empty database, so it reported "ok" on a fresh volume where
    every data endpoint returned 503. Querying `categories` makes the signal match
    what the read endpoints need. `/api/health` is the Docker healthcheck, and the
    frontend's `depends_on: service_healthy` gates on it, so a false "ok" here hides
    an unseeded deployment.

    A failing check returns 503, matching the contract in docs/API.md, but still uses
    the `HealthResponse` envelope so callers always get `status`, `database`,
    `scheduler`, `llm` and `version`. This handler never raises: a broken database
    must degrade the response, not turn the endpoint into a 500.
    """
    try:
        db.execute(text("SELECT 1 FROM categories LIMIT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health must never raise
        database = "error"

    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        scheduler="enabled" if settings.run_scheduler else "disabled",
        llm=classifier_status(settings),
        version=__version__,
    )


@router.post("/ingestion/run", summary="Fetch all active sources and classify new articles")
def run_ingestion(
    payload: IngestionRequest | None = None, db: Session = Depends(get_db)
) -> dict:
    payload = payload or IngestionRequest()

    if payload.source_ids:
        found = set(
            db.execute(select(Source.id).where(Source.id.in_(payload.source_ids))).scalars()
        )
        missing = sorted(set(payload.source_ids) - found)
        if missing:
            raise ValidationError(
                "Unknown source ids", {"missing_source_ids": missing}
            )

    summary = ingestion_service.ingest_all(
        db,
        source_ids=payload.source_ids,
        limit_per_source=payload.limit_per_source,
        classify=payload.classify,
        config=settings,
    )
    return summary.as_dict()


@router.post("/trends/recalculate", summary="Recompute and upsert trend snapshots")
def run_recalculation(
    payload: RecalculateRequest | None = None, db: Session = Depends(get_db)
) -> dict:
    payload = payload or RecalculateRequest()

    snapshot_date: date | None = None
    if payload.snapshot_date:
        try:
            snapshot_date = date.fromisoformat(payload.snapshot_date)
        except ValueError as exc:
            raise ValidationError(
                f"'{payload.snapshot_date}' is not a valid ISO date",
                {"field": "snapshot_date"},
            ) from exc

    result = trend_engine.recalculate(
        db,
        snapshot_date=snapshot_date,
        window_days=payload.window_days,
        days_back=payload.days_back,
        topic_ids=[payload.topic_id] if payload.topic_id else None,
        config=settings,
    )
    if payload.topic_id and result.topics_scored == 0:
        raise ValidationError(
            f"Topic {payload.topic_id} does not exist", {"topic_id": payload.topic_id}
        )

    return result.as_dict()
