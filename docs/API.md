# REST API contract

Base path: `/api`. All responses are JSON (UTF-8). Interactive docs at `/docs`.

The API layer only validates, delegates to `app/services/`, and serializes. No scoring or
classification logic lives in a route (spec §19.11).

## Conventions

### Pagination
`page` (default `1`, ≥ 1) and `page_size` (default `20`, 1–100). List responses use a common
envelope:

```json
{
  "items": [],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "pages": 7
}
```

### Sorting
`sort` accepts a whitelisted field, optionally prefixed with `-` for descending. An unknown
field returns `422`. Each endpoint documents its allowed fields.

### Error envelope
Every failure returns the same shape, produced by handlers in `app/api/errors.py`:

```json
{
  "error": {
    "code": "not_found",
    "message": "Trend 'ai-agents' not found",
    "details": {"slug": "ai-agents"}
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 404 | `not_found` | Unknown category / topic / article |
| 422 | `validation_error` | Bad query or body value, including bad `sort` |
| 409 | `conflict` | Duplicate seed run into a non-empty database |
| 502 | `upstream_error` | Collector / LLM transport failure surfaced by an admin endpoint |
| 503 | `unavailable` | Database unreachable |
| 500 | `internal_error` | Unhandled exception (never leaks a traceback) |

Validation failures keep FastAPI's native `detail` list inside `error.details.fields` so
clients can map messages to inputs.

## Read endpoints

### `GET /api/categories`
All five categories with live trend counts.

```json
[
  {
    "id": 1,
    "name": "AI",
    "slug": "ai",
    "description": "Artificial intelligence, models, agents and tooling.",
    "topic_count": 4,
    "article_count": 96,
    "trending_topic": {"slug": "ai-agents", "name": "AI Agents", "growth_rate": 2.45}
  }
]
```

### `GET /api/categories/{slug}`
One category plus its top trends, computed from the latest snapshot.

```json
{
  "id": 1,
  "name": "AI",
  "slug": "ai",
  "description": "...",
  "topic_count": 4,
  "article_count": 96,
  "top_trends": [ /* TrendSummary */ ]
}
```

### `GET /api/trends`
Latest snapshot per topic.

| query | type | notes |
|---|---|---|
| `category` | string | category slug or name, case-insensitive |
| `status` | enum | `emerging` / `growing` / `stable` / `declining` |
| `q` | string | case-insensitive substring on topic name |
| `min_growth` | float | inclusive lower bound on `growth_rate` |
| `sort` | enum | `trend_score` (default), `growth_rate`, `article_count`, `volume_share`, `name`, `snapshot_date`; `-` variants allowed |
| `include_fallback` | bool | `false` (default); include the per-category `Other` buckets |
| `page`, `page_size` | int | pagination |

Each category owns an `Other` topic that absorbs every article the classifier could not
place. Those buckets are **excluded from the ranking by default**: real feeds contain many
unmatched articles, so the buckets accumulate volume quickly and would otherwise occupy the
top of the list with several identically named `Other` rows, pushing real topics off the
homepage. They remain reachable with `include_fallback=true` for diagnostics.

```json
{
  "items": [
    {
      "id": 3,
      "slug": "ai-agents",
      "name": "AI Agents",
      "description": "Autonomous and semi-autonomous agents that plan and use tools.",
      "summary": "AI agents moved from demos to production pilots.",
      "category": {"id": 1, "slug": "ai", "name": "AI"},
      "trend_score": 0.94,
      "growth_rate": 2.45,
      "growth_percent": 245.0,
      "current_count": 84,
      "previous_count": 24,
      "volume_share": 0.71,
      "status": "growing",
      "is_emerging": false,
      "snapshot_date": "2026-09-20",
      "window_days": 7
    }
  ],
  "total": 20,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

`growth_rate` is the raw ratio and `growth_percent` is the same number × 100, provided so
the frontend never has to rescale a value (spec 19.9).

### `GET /api/trends/{slug}`
`TrendSummary` plus `latest_articles` (the newest five articles attached to the topic).

Returns `404 not_found` when the slug is unknown **or** the topic has never been scored. A
trend is defined as a topic plus its latest snapshot, so a topic with no snapshot has no
trend to return. In practice this is transient: recalculation follows ingestion, and the
trend list only ever shows scored topics, so an unscored topic is not reachable from the UI.

### `GET /api/trends/{slug}/history`
Ascending snapshot series for charting. This is a sub-resource of the *topic*, so it
answers differently from the detail endpoint for a topic that exists but has no snapshots
yet: `204 No Content` rather than `404`.

| query | type | default |
|---|---|---|
| `days` | int 1–365 | `30` |
| `window_days` | int 1–90 | the topic's most recent window |

```json
{
  "slug": "ai-agents",
  "name": "AI Agents",
  "window_days": 7,
  "points": [
    {"date": "2026-08-22", "current_count": 11, "previous_count": 9, "growth_rate": 0.22, "trend_score": 0.41, "status": "growing"},
    {"date": "2026-08-23", "current_count": 15, "previous_count": 9, "growth_rate": 0.66, "trend_score": 0.58, "status": "growing"}
  ]
}
```

`404 not_found` when the slug is unknown. `204 No Content` when the topic exists but has no
snapshots yet — the difference matters, because a page should say "not scored yet" for the
latter and "no such trend" for the former.

### `GET /api/articles`
| query | type | notes |
|---|---|---|
| `category` | string | category slug or name |
| `topic` | string | topic slug |
| `source_id` | int | filter by source |
| `q` | string | substring on title |
| `published_after` / `published_before` | date | inclusive bounds |
| `sort` | enum | `published_at` (default, desc), `created_at`, `title` |
| `page`, `page_size` | int | pagination |

```json
{
  "items": [
    {
      "id": 912,
      "title": "OpenAI ships a production-grade agent runtime",
      "url": "https://example.com/openai-agent-runtime",
      "description": "...",
      "summary": "A managed runtime for long-running agents.",
      "published_at": "2026-09-19T08:12:00Z",
      "created_at": "2026-09-19T08:20:00Z",
      "processing_status": "classified",
      "source": {"id": 2, "name": "Example Feed"},
      "category": {"id": 1, "slug": "ai", "name": "AI"},
      "topics": [{"slug": "ai-agents", "name": "AI Agents"}]
    }
  ],
  "total": 412, "page": 1, "page_size": 20, "pages": 21
}
```

An inverted date range (`published_after` later than `published_before`) is rejected with
`422` rather than silently returning nothing.

### `GET /api/articles/{id}`
Single article as above, or `404 not_found`.

## Operational endpoints

### `GET /api/health`
```json
{"status": "ok", "database": "ok", "scheduler": "disabled", "llm": "fallback", "version": "0.1.0"}
```
Returns `503` with `{"status":"degraded","database":"error"}` when the DB check fails.

### `POST /api/ingestion/run`
Fetch every active source, dedupe, store, then classify. Blocking; returns a summary.

```json
{
  "started_at": "2026-09-20T12:00:00Z",
  "finished_at": "2026-09-20T12:00:06Z",
  "sources_total": 8, "sources_ok": 7, "sources_failed": 1,
  "articles_fetched": 143, "articles_new": 21, "articles_duplicate": 122,
  "articles_skipped": 3,
  "articles_classified": 19, "articles_failed": 2,
  "errors": [{"source": "Example Feed", "message": "timeout after 15s"}],
  "sources": [{"source_id": 1, "source": "Example Feed", "ok": false, "fetched": 0, "new": 0, "duplicate": 0, "skipped": 0, "classified": 0, "failed": 0, "not_modified": false, "error": "timeout after 15s", "warnings": []}]
}
```

Optional body: `{"source_ids": [1,2], "limit_per_source": 50, "classify": true}`.
`422` when a listed source does not exist. A failing source is reported in `errors` and does
not fail the request (spec §15). `articles_skipped` counts entries rejected by validation,
for example a missing title, a non-http URL or a year-old publication date.

### `POST /api/trends/recalculate`
Recompute snapshots for a date range and upsert them.

```json
{"snapshot_date": "2026-09-20", "window_days": 7, "dates_processed": ["2026-09-20"], "snapshots_written": 25, "topics_scored": 25, "emerging_topics": 2}
```

Optional body: `{"snapshot_date": "...", "window_days": 7, "days_back": 1, "topic_id": 3}`.
`days_back` (1–90) recomputes a trailing range, which is how the seed script builds history.
Until snapshots exist for a date, `GET /api/trends` returns an empty list rather than an error.

## Frontend contract notes

`frontend/types/api.ts` mirrors these schemas and `frontend/lib/api.ts` is the only place
that talks to this API. Two consequences worth knowing:

* A change to a schema here is a change to `types/api.ts`.
* The dashboard derives nothing: `growth_percent`, `status`, `is_emerging`, `volume_share`
  and `trend_score` are all computed by the backend and only formatted for display.
