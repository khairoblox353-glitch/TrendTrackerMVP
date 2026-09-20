"""FastAPI application factory and entrypoint.

Wiring only: routers, exception handlers, CORS and the optional scheduler. Business
logic lives in `app/services` and `app/trend` (spec 19.11).
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.api.errors import register_exception_handlers
from app.config import settings
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# A database that is still starting makes the first connection race. Retry briefly so
# a fresh `docker compose up` converges without relying on a container restart.
BOOT_DB_ATTEMPTS = 5
BOOT_DB_RETRY_SECONDS = 3.0


def _bootstrap_database(attempts: int = BOOT_DB_ATTEMPTS) -> bool:
    """Create any missing tables; returns False if the database is unreachable.

    `init_db()` is idempotent (`Base.metadata.create_all` only issues CREATE TABLE for
    tables that are absent), so calling it on every boot is safe. Deliberately no
    Alembic or any other migration framework (spec 19.1, "do not over-engineer"):
    `create_all` is the intended mechanism for this MVP.

    Limitation, by design: `create_all` never ALTERs an existing table. Adding or
    changing a column therefore does not reach a volume that already holds the old
    schema. That case still needs a manual ALTER or table rebuild; the API keeps
    serving the old columns until an operator does it, and `/api/health` cannot detect
    it, because the table it probes is present.

    A database that is briefly unreachable must not crash the process: a crash loop
    would restart the whole app (scheduler included) on a transient blip. Instead the
    failure is logged loudly, the app starts, and `/api/health` reports `503 degraded`
    until the database recovers. Docker Compose already orders startup with
    `depends_on: condition: service_healthy`, so this retry loop is a safety net
    rather than the normal path.
    """
    last_error: Exception | None = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            init_db()
            if attempt > 1:
                logger.info("database schema ready after %s attempts", attempt)
            return True
        except Exception as exc:  # noqa: BLE001 - a health check must not kill the app
            last_error = exc
            if attempt < attempts:
                logger.warning(
                    "database unavailable at startup (attempt %s/%s): %s",
                    attempt,
                    attempts,
                    exc,
                )
                time.sleep(BOOT_DB_RETRY_SECONDS)

    logger.error(
        "database unreachable at startup, schema was not created: %s. The API starts "
        "anyway and /api/health reports 503 degraded until the database is reachable.",
        last_error,
    )
    return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _bootstrap_database()

    scheduler = start_scheduler(settings)
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        stop_scheduler(scheduler)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Trend Tracker MVP API: RSS ingestion, topic classification, "
            "trend scoring and read endpoints for the Next.js dashboard."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)
    application.include_router(api_router)

    @application.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "api": "/api",
        }

    return application


app = create_app()
