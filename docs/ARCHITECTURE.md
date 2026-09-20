# Trend Tracker — Architecture

Status: MVP design, agreed before implementation (spec §21).

## 1. Review of the proposed architecture

The proposed architecture is sound for an MVP: monotonic data flow (RSS → store → classify →
score → API → UI), one repository, one database, no distributed infrastructure. There is
nothing in it that needs to be removed.

The following points were **underspecified or internally inconsistent** and are resolved by
this document. Each resolution is deliberately the simplest option that satisfies the MVP.

| # | Issue in spec | Resolution |
|---|---|---|
| R1 | §6 `articles` has no uniqueness rule, but §7/§15 require deduplication. | `articles.url` is `UNIQUE`. Ingestion is an upsert-by-URL, so re-running a collector is idempotent. |
| R2 | §6 `article_topics` has only two columns, so the same pair can be inserted twice. | Composite primary key `(article_id, topic_id)` + `confidence` column. |
| R3 | §6 `trend_snapshots` has no uniqueness rule, so recalculating twice duplicates history. | `UNIQUE (topic_id, snapshot_date, window_days)`. Recalculation upserts. |
| R4 | §6 `trend_snapshots` cannot explain its own `growth_rate` later. | Store `previous_count` and `current_count` in the snapshot. |
| R5 | §10 stores nothing about status, so a trend page cannot show historical status. | `status` and `is_emerging` are persisted per snapshot. Thresholds stay in config; only the computed label is stored. |
| R6 | §9 `normalized_volume` has no denominator. | `volume_share = current_count / max(current_count)` across all topics **in the same recalculation run**, so it is comparable within a period and stable over time. |
| R7 | §9/§10 conflict: "growth > 100% → emerging/growing" then "20–100% → growing". | `previous_count == 0` → `emerging`; growth above `GROWING_THRESHOLD` with non-zero previous → `growing`; `0.20 ≤ growth ≤ 1.00` → `growing` (merged, same label); `-0.20 < growth < 0.20` → `stable`; `growth ≤ -0.20` → `declining`. |
| R8 | §9 says "don't allow infinite growth" but gives no cap. | `growth_rate` is clamped to `EMERGING_GROWTH_CAP` (default `3.0`) when `previous_count == 0`, and the topic is flagged `is_emerging`. |
| R9 | §15 requires "LLM failure must not break ingestion" but §6 has no state for it. | `articles.processing_status` (`pending`/`classified`/`failed`) + `processing_error`. Articles are always committed before classification. |
| R10 | §11 exposes `/api/trends/{slug}`, but `topics.slug` is only unique per category. | `topics.slug` is **globally unique**; collisions get a numeric suffix (`ai-agents`, `ai-agents-2`). Flat URLs, one lookup. |
| R11 | §5 has no `.env` for the threshold config required by §10. | All thresholds, windows, weights and caps live in `backend/app/config.py`, overridable by env vars. |
| R12 | §12 needs an "AI-generated summary" of a **trend**, but §3 only asks the LLM for a per-article summary. | Both: `articles.summary` (one line, from the article) and `topics.summary` (refreshed from the topic's recent titles). Same LLM call path, no new component. |
| R13 | §12/§17 seed data expects trend snapshots, but snapshots are derived. | Seeding generates 60 days of synthetic **articles**, then runs the **real** `TrendEngine` once per day for the last 30 days. Seed data therefore exercises production code instead of faking its output. |
| R14 | §8 allows new topics but never defines the fallback topic. | Every category is seeded with a reserved topic `Other` (`is_fallback = true`). Low-confidence or rejected labels land there. |
| R15 | §14 fetches RSS hourly with no politeness/state controls. | `sources` stores `last_fetched_at`, `last_etag`, `last_modified`, `last_error` so the collector can send conditional requests and skip inactive sources. |
| R16 | §11 requires sorting but sorting on arbitrary client input is a SQL-injection vector. | Sort fields are validated against an explicit whitelist per endpoint; unknown values are rejected with `422`. |
| R17 | Not specified anywhere: multiple scheduler instances against one DB. | Scheduling is opt-in via `RUN_SCHEDULER`; `docker-compose` runs a single API replica. Documented as an MVP constraint. |
| R18 | §8 gives no category for an article the classifier cannot place, and the LLM may name a category outside the five. | `ClassificationResult` carries the literal `"Other"`, never a real category. Ingestion resolves it against the source's `category_id` hint, then the `AI` category as a last resort. A fallback that named a real category would silently dump every unmatched article into whichever category happened to be first. |
| R19 | §12 implies loading states, but a Suspense boundary conflicts with §11's 404 contract. | No `loading.tsx` above any page that calls `notFound()`. A `loading.tsx` streams the shell with HTTP 200 before the page resolves, so a real 404 becomes a 200 with a 404 body. Verified across `/trends/<unknown>`, `/<unknown>` and `/articles/<unknown>`. |

### Scope guardrails honored

No auth, no payments, no microservices, no Kubernetes, no Kafka, no Redis, no vector DB, no
graph DB, no recommendation engine, no streaming, no mobile app. **The LLM never
participates in scoring** — `app/trend/engine.py` imports nothing from `app/ai/`.

## 2. Architecture diagram

```mermaid
flowchart TD
    RSS["RSS / Atom feeds"] --> COL

    subgraph COL["backend/app/collectors"]
        RSSCOL["RSSCollector<br/>(Collector interface)"]
    end

    COL --> ING["services/ingestion.py<br/>validate → dedupe → save"]
    ING --> DB[("PostgreSQL")]

    ING --> CLS["ai/classifier.py<br/>classify(title, description)"]
    CLS -->|"category + topic + summary"| ING
    CLS -.->|"LLM error → fallback, article kept"| FB["FallbackClassifier<br/>keyword rules / Other"]

    ING --> TOP["services/topics.py<br/>upsert topic by normalized name"]
    TOP --> DB

    DB --> ENG["trend/engine.py<br/>group by topic → count → growth → score"]
    ENG --> SNP["trend_snapshots"]
    SNP --> DB

    DB --> API["api/ FastAPI routers"]
    API --> SCH["schemas/ Pydantic"]
    API --> WEB["Next.js App Router"]
    WEB --> USER(("User"))

    SCHED["scheduler.py<br/>APScheduler"] -.->|"hourly"| COL
    SCHED -.->|"6-hourly"| ENG
    CRON["cron / external trigger"] -.->|"POST /api/ingestion/run"| API
    CRON -.->|"POST /api/trends/recalculate"| API
```

Runtime layering (dependencies point downward only):

```text
api/  ──► services/ ──► trend/ , ai/ ──► models/ ──► database.py
  │                                              └──► collectors/
  └──► schemas/   (pure transport types, no DB imports)
```

## 3. Repository structure

```text
trend-tracker/                  (= D:\projects\DuyKhai)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             FastAPI app, lifespan, exception handlers, CORS
│   │   ├── config.py           Settings (env-driven thresholds, LLM, DB)
│   │   ├── database.py         engine, SessionLocal, Base, get_db
│   │   ├── scheduler.py        APScheduler wiring (Hourly RSS, 6-hourly trends)
│   │   ├── cli.py              python -m app.cli init|seed|ingest|recalculate
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py         get_db, pagination params, sort whitelist helper
│   │   │   ├── errors.py       AppError + handlers, consistent error envelope
│   │   │   ├── categories.py   /api/categories
│   │   │   ├── trends.py       /api/trends
│   │   │   ├── articles.py     /api/articles
│   │   │   └── ingestion.py    /api/ingestion/run, /api/trends/recalculate, /api/health
│   │   ├── models/             SQLAlchemy 2.0 declarative models
│   │   │   ├── category.py  source.py  article.py  topic.py  snapshot.py
│   │   │   └── associations.py article_topics
│   │   ├── schemas/            Pydantic v2 request/response models
│   │   │   ├── common.py  category.py  article.py  trend.py  ingestion.py
│   │   ├── services/           business logic, no HTTP, no SQL-in-route
│   │   │   ├── ingestion.py    collector → validate → dedupe → save → classify
│   │   │   ├── topics.py       topic upsert, slug allocation, summary refresh
│   │   │   ├── trends.py       queries/serialization used by API + jobs
│   │   │   └── seed.py         deterministic demo dataset
│   │   ├── collectors/
│   │   │   ├── base.py         Collector ABC + RawArticle dataclass
│   │   │   ├── rss.py          feedparser-based RSS/Atom collector
│   │   │   └── registry.py     name → collector factory (extensibility point)
│   │   ├── ai/
│   │   │   ├── base.py         Classifier ABC + ClassificationResult
│   │   │   ├── llm.py          OpenAI-compatible chat-completions client
│   │   │   ├── fallback.py     keyword classifier (no network, always available)
│   │   │   ├── prompts.py      system/user prompt templates
│   │   │   └── factory.py      picks LLM vs fallback from config
│   │   └── trend/
│   │       ├── windows.py      pure date-window helpers
│   │       ├── scoring.py      pure growth/score/status functions
│   │       └── engine.py       DB orchestration → trend_snapshots upsert
│   ├── tests/
│   │   ├── conftest.py         sqlite in-memory app + client fixtures
│   │   ├── test_scoring.py     growth, score, normalization, status
│   │   ├── test_windows.py     window boundaries
│   │   ├── test_engine.py      recalculation + idempotency
│   │   ├── test_ingestion.py   dedupe, missing fields, LLM failure
│   │   ├── test_rss_collector.py parsing, invalid feed, timeout
│   │   ├── test_api_categories.py
│   │   ├── test_api_trends.py
│   │   └── test_api_articles.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml          pytest + ruff config
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx          shell + nav (categories fetched from API)
│   │   ├── page.tsx            homepage
│   │   ├── error.tsx  not-found.tsx  loading.tsx
│   │   ├── [category]/page.tsx /ai /technology /finance /gaming /health
│   │   ├── trends/page.tsx     trend list (filters, sort, pagination)
│   │   ├── trends/[slug]/page.tsx
│   │   ├── articles/page.tsx
│   │   ├── articles/[id]/page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Header.tsx  Footer.tsx  CategoryChips.tsx
│   │   ├── TrendCard.tsx  TrendTable.tsx  TrendStatusBadge.tsx
│   │   ├── GrowthChart.tsx     dependency-free SVG sparkline/line chart
│   │   ├── VolumeBar.tsx  ArticleList.tsx  ArticleRow.tsx
│   │   ├── StatCard.tsx  Pagination.tsx  SearchBox.tsx  SortSelect.tsx
│   │   └── EmptyState.tsx  ErrorState.tsx  Skeleton.tsx
│   ├── lib/
│   │   ├── api.ts              typed server-side fetch to the backend
│   │   ├── format.ts           percent / number / relative-date formatting
│   │   └── config.ts           API base URL resolution
│   ├── types/api.ts            mirrors backend Pydantic schemas
│   ├── package.json  tsconfig.json  next.config.ts
│   ├── tailwind.config.ts  postcss.config.mjs  .eslintrc.json
│   └── Dockerfile
├── scripts/
│   ├── dev-backend.ps1  dev-frontend.ps1  seed.ps1
├── docs/
│   ├── ARCHITECTURE.md         this file: review, diagram, structure, ADRs
│   ├── DATABASE.md             schema, indexes, constraints
│   └── API.md                  endpoint contract, params, error envelope
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 4. Architecture decision records

**ADR-001 — Synchronous SQLAlchemy 2.0 with psycopg 3.**
Ingestion and classification are already blocking network I/O (feedparser, HTTP). Making the
whole stack `async` would add an event-loop/session-concurrency layer with no MVP benefit.
FastAPI runs sync `def` endpoints in a threadpool. Simpler to read, simpler to test with
`TestClient`, and SQLite-compatible for tests.

**ADR-002 — Trends are derived; snapshots are a materialized time series.**
`GET /api/trends` reads the latest snapshot per topic (join + `DISTINCT ON`), not a live
aggregation. This keeps read latency flat and makes history a plain `ORDER BY snapshot_date`.
Snapshots are written only by `trend/engine.py`, never by an API route.

**ADR-003 — Pure functions for all scoring math.**
`trend/scoring.py` and `trend/windows.py` take numbers/dates and return numbers. No DB, no
settings lookups inside. This is what makes spec §16's unit tests trivial and keeps the
algorithm explainable.

**ADR-004 — `Collector` is an abstract interface.**
`RawArticle` is the only currency between collectors and the ingestion service. Adding a
Hacker News or news-API collector later means one new class in `collectors/` plus one registry
entry; the ingestion pipeline is untouched.

**ADR-005 — The classifier is swappable, and its failure is non-fatal.**
`Classifier` ABC with two implementations: `LLMClassifier` and `KeywordFallbackClassifier`.
`ai/factory.py` returns the LLM client when configured and reachable, otherwise the fallback.
Any exception inside classification marks the article `failed` but leaves it committed.
**`app/trend/` never imports `app/ai/`.**

An unrecognised answer is reported as the literal category `"Other"`, not as a real
category. `services/ingestion.py` then resolves it in order: the source's `category_id`
hint, then `AI` as a last resort. This keeps a health feed's unmatched articles out of the
AI counts (R18) — a fallback that named a real category would corrupt every downstream
aggregate the moment the classifier met something it did not recognise.

**ADR-006 — Two ways to trigger work: in-process scheduler and HTTP endpoints.**
`RUN_SCHEDULER=true` starts APScheduler inside the FastAPI lifespan (single replica only).
`POST /api/ingestion/run` and `POST /api/trends/recalculate` do the same work on demand, so
cron/CI/external orchestration needs no scheduler at all. No Celery, no Kafka, no broker.

**ADR-007 — Zero-dependency charting.**
`GrowthChart.tsx` renders inline SVG. A charting library would be the single largest
frontend dependency for one line chart.

**ADR-008 — Every dashboard route is rendered on demand; the API client is uncached.**
Pages declare `dynamic = "force-dynamic"` and `lib/api.ts` fetches with `cache: "no-store"`.
Two reasons: trend data is time-sensitive, and the documented setup builds the frontend
image *before* the database is seeded, so any prerendered or cached response would pin an
empty snapshot until revalidation. This is also why `generateStaticParams` is not used —
it takes precedence over `dynamic` and would make Next.js prerender the category routes.

## 5. Non-goals for this repository

Authentication, multi-tenancy, per-user state, full-text search infrastructure, real-time
updates, alerting, LLM-based scoring, topic merge/split tooling, backfilling on schema change.
All are additive later; none are required by the definition of done in spec §20.
