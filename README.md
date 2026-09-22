# Trend Tracker MVP

Collects news articles from RSS feeds, classifies them into topics with an LLM (or an
offline fallback), scores how fast each topic is growing, and shows the result on a
small dashboard.

Five categories: **AI · Technology · Finance · Gaming · Health**.

The end-to-end path the MVP must satisfy (spec §20):

```text
RSS → Article → Category → Topic → Trend Score → API → Website
```

---

## 1. Quick start (Docker)

Requires Docker Desktop. No local Python or Node needed.

```bash
cp .env.example .env
docker compose up --build -d

# Load the demo dataset. The backend creates any missing tables at startup, so this
# step is about DATA, not schema; `seed` also runs `init_db` itself, so it is safe on
# a brand-new volume too.
docker compose exec backend python -m app.cli seed
```

| Service  | URL                            |
|----------|--------------------------------|
| Website  | http://localhost:3000          |
| API docs | http://localhost:8000/docs     |
| Health   | http://localhost:8000/api/health |

Then open http://localhost:3000 — you should see the five categories, a ranked list of
trending topics with growth percentages and a 30-day chart on each trend page.

No restart is needed between `docker compose up` and `seed`: the dashboard reads the API on
every request, so it shows an empty state first and live data immediately after seeding.
The order in the snippet above is the only order that matters.

On Windows, `.\scripts\dev.ps1 up` and `.\scripts\dev.ps1 seed` wrap the same commands.

## 2. Quick start (local processes)

Useful when you want autoreload.

```bash
# 1. Database only
docker compose up -d db

# 2. Backend (http://localhost:8000)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt   # macOS/Linux

# Point the backend at the database on localhost, not the `db` service name.
export DATABASE_URL="postgresql+psycopg://trend:trend@localhost:5432/trend_tracker"

python -m app.cli init
python -m app.cli seed
python -m uvicorn app.main:app --reload

# 3. Frontend (http://localhost:3000)
cd ../frontend
npm install
API_BASE_URL=http://localhost:8000 npm run dev
```

Helper scripts: `scripts/dev-backend.ps1`, `scripts/dev-frontend.ps1`.

The dashboard supports English and Vietnamese. The header's EN/VI control stores the
choice in `localStorage` (`trend-tracker.locale`, default English). Because the server
cannot read `localStorage`, pages are server-rendered in English and switch to Vietnamese
after hydration; `<title>`/meta stay English.

## 3. Verifying the definition of done

With the stack running and seeded:

1. Open http://localhost:3000 — homepage lists the five categories and the top trends.
2. Click a trend card — `/trends/ai-agents` shows score, growth, article counts, the
   7/30-day chart, the AI-generated summary and the newest related articles.
3. Click a category chip — `/ai` shows that category's top trends and latest articles.
4. Open http://localhost:8000/docs and try `GET /api/trends?category=ai&sort=-growth_rate`.

Automated checks:

```bash
cd backend
.venv/Scripts/python -m pytest -q        # 305 tests
.venv/Scripts/python -m ruff check app tests

cd ../frontend
npm run typecheck
npm run lint
npm run build
```

## 4. Repository layout

```text
backend/app/
  api/          HTTP routes; validate → call a service → serialize
  services/     business logic (ingestion, topics, trends, seed, summaries)
  trend/        trend math and the snapshot engine (no LLM imports)
  ai/           classifier interface, LLM client, offline keyword fallback
  collectors/   Collector interface + RSS implementation + registry
  models/       SQLAlchemy models
  schemas/      Pydantic transport types
  scheduler.py  APScheduler jobs (opt-in)
  cli.py        init / seed / status / ingest / recalculate / classify

frontend/
  app/          routes: /, /[category], /trends, /trends/[slug], /articles, /articles/[id]
  components/   presentational components (charts, cards, tables)
  lib/          API client + formatting
  types/api.ts  mirror of the backend schemas
```

See `docs/ARCHITECTURE.md` for the design review, diagrams and decision records;
`docs/DATABASE.md` for the schema; `docs/API.md` for the endpoint contract.

## 5. Configuration

Everything tunable lives in `.env` (see `.env.example`). The values that matter most:

| Variable | Default | Purpose |
|---|---|---|
| `TREND_WINDOW_DAYS` | `7` | Length of the compared periods |
| `TREND_HISTORY_DAYS` | `30` | Default `days` on `GET /api/trends/{slug}/history` |
| `WEIGHT_GROWTH` / `WEIGHT_VOLUME` | `0.7` / `0.3` | Trend score blend (must sum to 1) |
| `EMERGING_GROWTH_CAP` | `3.0` | Growth ceiling when the previous window is empty |
| `GROWING_THRESHOLD` | `0.20` | Growth at or above this is `growing` |
| `DECLINING_THRESHOLD` | `-0.20` | Growth at or below this is `declining` |
| `CLASSIFICATION_MIN_CONFIDENCE` | `0.55` | Below this, an article goes to `Other` |
| `LLM_ENABLED` | `false` | `true` switches classification to the LLM |
| `RUN_SCHEDULER` | `false` | Enables the in-process jobs |

### Enabling the LLM

The keyword classifier is used by default so the project runs offline and its tests are
deterministic. To use an LLM instead, set an OpenAI-compatible endpoint:

```bash
LLM_ENABLED=true
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# LLM_BASE_URL=https://openrouter.ai/api/v1   # or a local Ollama/vLLM server
```

Any failure in the LLM is non-fatal: the article is still stored (marked `failed`) and
reclassified on the next run — see `docs/ARCHITECTURE.md`, ADR-005.

## 6. Operating it

### CLI

```bash
python -m app.cli status          # row counts + pending classification
python -m app.cli ingest          # fetch feeds, dedupe, store, classify
python -m app.cli recalculate     # recompute today's snapshots + summaries
python -m app.cli classify --pending   # retry failed classifications
python -m app.cli seed            # add any missing demo data (never overwrites real data)
python -m app.cli seed --reset    # rebuild the demo dataset; keeps real ingested data
python -m app.cli seed --reset --include-ingested   # also wipe real articles + snapshots
```

### Upgrading an existing database

The application creates any missing tables at startup (`create_all`). That is enough for
a fresh volume, but `create_all` cannot ALTER an existing table, so the index added after
the first release must be created by hand on a database that already exists:

```sql
CREATE INDEX IF NOT EXISTS ix_article_topics_topic_id ON article_topics (topic_id);
```

A fresh database gets that index automatically. There is no migration framework by design
(no Alembic), so any future column or index change needs the same manual step.

### HTTP

```bash
curl -X POST localhost:8000/api/ingestion/run
curl -X POST localhost:8000/api/trends/recalculate -H 'content-type: application/json' \
     -d '{"days_back": 7}'
```

### Scheduling

Two options; pick one (see R17 in `docs/ARCHITECTURE.md`).

* **In-process** — set `RUN_SCHEDULER=true` and run a single backend replica. APScheduler
  then fetches RSS hourly and recalculates trends every 6 hours.
* **External cron** — keep `RUN_SCHEDULER=false` and call the two POST endpoints:

```cron
0  * * * * curl -fsS -X POST http://localhost:8000/api/ingestion/run
0 */6 * * * curl -fsS -X POST http://localhost:8000/api/trends/recalculate
```

## 7. How the trend score works

For every topic, over the last `TREND_WINDOW_DAYS` (default 7):

```text
current_count   = articles published in the current window
previous_count  = articles published in the window before it

growth_rate = (current_count - previous_count) / max(previous_count, 1)
```

If `previous_count` is 0 the growth rate is capped at `EMERGING_GROWTH_CAP` and the topic
is marked `emerging`, so a brand-new topic cannot report infinite growth.

```text
normalized_growth = growth_rate / (growth_rate + GROWTH_SATURATION)   # squashed to 0..1
normalized_volume = current_count / busiest_topic_current_count       # 0..1 per run

trend_score = normalized_growth * WEIGHT_GROWTH + normalized_volume * WEIGHT_VOLUME
```

Status, from `growth_rate`:

| Condition | Status |
|---|---|
| previous window empty and activity now | `emerging` |
| `growth_rate >= GROWING_THRESHOLD` | `growing` |
| `DECLINING_THRESHOLD < growth_rate < GROWING_THRESHOLD` | `stable` |
| `growth_rate <= DECLINING_THRESHOLD` | `declining` |

**The LLM never participates in scoring.** `app/trend/` does not import `app/ai/`.

## 8. Adding a data source

The collector is an interface (ADR-004). To add one:

1. Subclass `app.collectors.base.Collector` and return `RawArticle` values from `collect`.
2. Register it in `app/collectors/registry.py` under a name or URL scheme.

Validation, deduplication, storage, classification and scoring are untouched by that
change — that is the whole point of the `RawArticle` boundary.

## 9. Seed data

`python -m app.cli seed` creates 5 categories, 25 topics (20 curated + an `Other`
fallback per category) and ~250 synthetic articles across 45 days. On a fresh database it
also builds 30 days of trend snapshots; snapshots are produced by the **real** trend
engine rather than by fabricated numbers, so the seeded history cannot drift from the
algorithm.

Seeding is additive once the dataset exists, and the taxonomy is never deleted (real
articles link to those topics). Seeded articles are identified by the URL prefix
`https://seed.trend-tracker.local/`, a constant in `app/services/seed.py`:

* a plain `seed` only inserts the seeded articles that are missing, rebuilds snapshot
  history when the database has **no** snapshots yet, and generates summaries only for
  topics whose `summary` is still empty - so it never overwrites snapshots or summaries
  that real ingested articles produced;
* `seed --reset` deletes just the seeded articles (matched by that URL prefix) and their
  topic links, drops snapshots of topics that are left with no articles at all, and then
  regenerates the demo dataset; real articles, their topics and their snapshots survive;
* `seed --reset --include-ingested` additionally wipes every article and snapshot. It is
  the explicit destructive full wipe, and the only way to remove real ingested data.

Each topic has a momentum multiplier applied to its most recent comparison window, which
makes the demo charts predictable: `momentum - 1` is the growth rate the engine reports.
`AI Agents` therefore shows about +250% and `Startup Funding` about -50%. Article history
is generated in whole window-length blocks for the same reason — the momentum boundary has
to fall between the current and previous windows, or every topic would score as flat.

The per-category `Other` buckets are excluded from the trending ranking. They absorb
everything the classifier cannot place, so with real feeds they accumulate volume fast and
would otherwise fill the top of the homepage with several identically named rows. They
remain available via `GET /api/trends?include_fallback=true` for diagnostics.

## 10. Definition of done

| Requirement (spec §20) | Status |
|---|---|
| RSS → Article → Category → Topic → Score → API → Website | Working end-to-end |
| Homepage with the 5 categories and trending topics | Done |
| Category pages with top trends, growth, counts, chart, articles | Done |
| Trend detail with score, growth, 7/30-day history, articles, summary | Done |
| REST API with schemas, validation, pagination, sorting, errors | Done |
| Unit tests for growth, score, status and dedupe | Done |
| API tests for trends, categories and articles | Done |
| Collector tests for parsing, invalid feeds and duplicates | Done |
| Docker Compose, `.env.example`, README | Done |

## 11. Known scope limits (deliberate)

No authentication, no payments, no microservices, no Kubernetes, no Kafka, no Redis, no
vector database, no graph database, no recommendation engine, no real-time streaming, no
mobile app. Trend scoring is statistical only — no ML model. See the non-goals section of
`docs/ARCHITECTURE.md`.
