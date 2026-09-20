# AGENTS.md — working notes for this repository

This project is a learning/MVP codebase. Read `docs/ARCHITECTURE.md` before making
structural changes.

## Commands

Backend (`backend/`):

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # tests (SQLite in-memory, no DB needed)
.\.venv\Scripts\python.exe -m ruff check app tests
```

Frontend (`frontend/`): use `npm.cmd`, not `npm` (PowerShell execution policy blocks `npm.ps1`).

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Full stack:

```powershell
docker compose up --build -d
docker compose exec backend python -m app.cli seed
```

## Engineering rules (from the project specification)

1. Do not over-engineer. The simplest solution that satisfies the MVP wins.
2. No microservices, Kubernetes, Kafka or Redis. No vector or graph databases.
3. **The LLM must never influence a Trend Score.** `app/trend/` must not import `app/ai/`.
4. The backend is the source of truth. No business logic in the frontend — it only
   formats and displays values the API returns.
5. Business logic lives in `app/services/` and `app/trend/`, never in an API route. A
   route validates, calls one service function, and serializes.
6. Keep the collector boundary (`RawArticle`) intact so a data source can be replaced.
7. Secrets go in `.env`, never in code or in a committed file.

## Layout conventions

* One new endpoint means: a schema in `app/schemas/`, a service function in
  `app/services/`, and a thin route in `app/api/`. Update `frontend/types/api.ts` and
  `docs/API.md` to match.
* Scoring math belongs in `app/trend/scoring.py` as a pure function (numbers in, numbers
  out, no DB and no settings lookups) so it stays trivially testable.
* Every tunable threshold belongs in `app/config.py`, overridable by env var.

## Gotchas

* `DEBUG` is set globally in this developer's environment, so the settings field is named
  `APP_DEBUG`. Do not rename it back to `debug`.
* The `sort` query parameter is validated against a whitelist (`TREND_SORT_FIELDS`,
  `ARTICLE_SORT_FIELDS`). Never interpolate a client string into SQL.
* `trend_snapshots` is unique per `(topic_id, snapshot_date, window_days)`. Recalculation
  upserts, so it is safe to re-run.
* `GET /api/trends` must be window-scoped; two window sizes for the same topic would
  otherwise duplicate rows in the list.
* Tests run against SQLite. `services/trends.py` avoids PostgreSQL-only SQL deliberately
  so the API tests can exercise the same query path.
* Do not add a `loading.tsx` anywhere above a page that calls `notFound()`. It creates a
  Suspense boundary, so the shell is streamed with HTTP 200 before the page resolves and
  `notFound()` can no longer produce a real 404. Verified: with `app/loading.tsx`,
  `app/trends/loading.tsx` or `app/[category]/loading.tsx` present, unknown routes
  returned 200 with a 404 body; removing them restored real 404s on
  `/trends/<unknown>`, `/<unknown>` and `/articles/<unknown>`. `error.tsx` and
  `not-found.tsx` are unaffected.
* An unrecognised classification is reported as category `"Other"`, never as a real
  category (`ClassificationResult.fallback`). `services/ingestion.py` resolves `"Other"`
  via the source's `category_id` hint before falling back to `AI`. A fallback that named a
  real category silently polluted that category with every unmatched article — observed as
  health and gaming articles landing in `AI`.
