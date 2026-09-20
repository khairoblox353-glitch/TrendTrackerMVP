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
  upserts atomically (`ON CONFLICT ... DO UPDATE`, dialect-selected), so it is safe to
  re-run and two overlapping runs cannot raise a unique violation.
* **`seed --reset` preserves real ingested data.** Seeded rows are identified by the URL
  prefix `SEED_URL_PREFIX` (`https://seed.trend-tracker.local/`); `reset_demo_data` deletes
  only articles with that prefix plus their links, and never deletes topics or categories
  (shared taxonomy that real articles link to). `seed --reset --include-ingested` is the
  destructive flag: it wipes every article and every snapshot. Do not make `reset`
  destructive by default.
* **A plain `seed` is additive.** It rebuilds snapshot history only on `--reset` or when
  the database has no snapshots at all (`_has_snapshots`), and it only generates summaries
  for topics whose `summary IS NULL` (`_fill_missing_summaries`). Both used to overwrite
  data derived from real articles; do not restore the unconditional versions.
* **The new `ix_article_topics_topic_id` index needs a manual `CREATE INDEX` on existing
  databases**: `CREATE INDEX IF NOT EXISTS ix_article_topics_topic_id ON article_topics
  (topic_id);`. `create_all` only creates missing tables and never ALTERs an existing one,
  and there is no migration framework by design. A fresh volume gets it automatically.
* **The volume denominator must stay global.** `volume_share` is normalized against the
  busiest topic of the whole population (`_max_current_count`), never of a run's
  `topic_ids`. If a scoped `POST /api/trends/recalculate {"topic_id": N}` used the scoped
  maximum, it would write `volume_share = 1.0` over the correct score.
* **API responses must never include raw exception text.** Only our own `CollectorError`
  messages (written for operators, e.g. `HTTP 404`, `timeout after 15s`) are safe to return
  and to store in `sources.last_error`. Everything else is replaced: `storage failure` for a
  failed write, `unexpected error during ingestion` for an unexpected ingestion exception.
  Generated SQL embeds column names and bound parameter values, so keep the detail in the
  server log.
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
