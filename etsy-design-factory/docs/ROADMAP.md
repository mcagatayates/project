# ROADMAP

Implementation proceeds in the phases below, per the mission's explicit
instruction not to attempt the entire system at once. Each phase ends with:
tests, integration tests, type checking, linting, migrations, production
build, and worker-failure tests — failures are fixed before moving on. This
file is updated as phases land; **"Status" reflects the actual state of the
code in this repository, not aspiration.**

## Phase 0 — Architecture (this directory)
Deliverables: the 9 docs in `docs/`. Internally consistent entity names,
field names, queue names and stage names shared across all of them and
matched 1:1 by the code in later phases.
**Status: complete.**

## Phase 1 — Vertical creative pipeline
`DesignGenome → Concept → Generation → Vision QC → Repair → Selection →
Approval → Storage`, genuinely operational end-to-end for a single
candidate, using fake providers so it runs with no paid API calls.
Deliverables: DB models + Alembic migration, genome schema/compiler/
mutation, provider interfaces + fake adapters, the pipeline stage modules,
Celery task wiring (eager-mode compatible for tests), a pytest suite
exercising one full candidate through every stage including a repair
branch and an approval-triggered genome edit.
**Status: complete.** `app/genome/`, `app/db/models/`, `app/providers/`,
`app/pipeline/{concept_generation,concept_gate,generation,vision_qc,
failure_diagnosis,selective_repair,tournament_selection,similarity_engine,
diversity_control,approval,runner}.py`.

## Phase 2 — Daily Production Controller & throughput
`DailyProductionPlan` generation (configurable, not hardcoded allocation),
Collection Planner, Discovery vs. Production mode with a graduation rule,
queue separation per `EVENTS.md`, budget enforcement. Exit criterion: the
30-design acceptance simulation (see below) passes using only fake
providers.
**Status: complete.** `app/pipeline/production_controller.py`,
`app/pipeline/collection_planner.py`, `app/pipeline/portfolio.py`,
`app/queue/` (8-queue separation, `ResilientTask` retry/dead-letter,
worker-failure test coverage).

## Phase 3 — Evolution & memory
Controlled mutation/genealogy, `FailureMemory`, `ExperimentMemory`,
creative fatigue / similarity engine (perceptual hash + palette + genome
similarity), cost engine with per-design/collection/daily/monthly rollups
and budget gates wired into the Production Controller.
**Status: complete.** `app/genome/mutation.py`,
`app/memory/{failure_memory,experiment_memory}.py`,
`app/pipeline/similarity_engine.py`, `app/cost/{ledger,budgets}.py`.

## Phase 4 — Print, Mockup, Etsy package
Real ratio exports (actual pixel operations, never DPI-metadata tricks),
mockup compositing kept strictly separate from the master asset, Etsy
listing package assembly with zero coupling from the creative pipeline to
any Etsy API call.
**Status: complete**, plus a real Getvela CSV export path (below).
`app/pipeline/{print_factory,mockup_factory,etsy_package,getvela_export}.py`.

### Getvela CSV export (not the Etsy API)
The mission's Etsy publish path was intentionally never built against
Etsy's own API — the account owner does not want direct API access, over
concern that automated listing activity risks a shop suspension. Instead
the existing real workflow is: bulk-import a CSV into
[Getvela](https://getvela.com) (an Etsy shop-management tool), where
listings land in Getvela's archive and get activated by hand, day by day.
`POST /api/getvela/export` (`app/pipeline/getvela_export.py`) produces
that CSV directly from real approved `Artwork` + `EtsyListingPackage`
rows — the exact column header row was taken from the account owner's
real Getvela "Import new listings" template (`CSV_HEADERS` in that
module — do not reorder/rename without re-confirming against a fresh
Getvela export).

One Etsy listing per Artwork, physical print-on-demand fulfilled via
Printify, with **two** Etsy variations — Size and Material — not one.
The full 28-size × 9-material × price grid
(`config/getvela_variation_template.csv`, 252 rows) was copied verbatim
from a real export of the account owner's actual Getvela listing, and is
reused unchanged for every new listing (only Title/Description/Category/
Tags/Section/SKU/Photos/Price differ per design). This is deliberate,
not a shortcut: real per-(size,material) pricing is driven by Printify's
actual fulfillment costs, which this system has no way to compute or
infer, so guessing a formula would have meant fabricating prices. The
listing-level "Price" column is the lowest price among only the
*visible* (`Var Visibility=On`) offers, matching what a buyer can
actually purchase. Shop/account-level fields that depend on the seller's
actual Etsy configuration (category, shipping profile, return policy,
production partner) similarly came from that same real export, in
`config/getvela_shop_defaults.yaml` — not guessed, not placeholders.

Photo columns are real, absolute URLs (`app/api/routes/artwork_assets.py`
serves print-export and mockup images the same way
`app/api/routes/candidates.py` already serves candidate images) built
from `PUBLIC_BASE_URL` — the export raises a clear error rather than emit
an unreachable `localhost` URL if that setting is unset, following the
same pattern as every other real-integration point in this codebase
(`SERPAPI_KEY`, `MARKET_SIGNAL_INGESTION_TOKEN`). `getvela_export_batches`
/ `getvela_export_records` (`app/memory/getvela_export_memory.py`) track
which artworks have already been handed to Getvela, so re-running the
export never re-includes a design already in Getvela's archive — the
Control Center's `/getvela` page shows how many approved designs are
still waiting, triggers an export, and downloads the CSV.

This was verified end-to-end during development: a real daily-simulation
run producing approved artworks with real print exports, mockups, and an
`EtsyListingPackage`, exported through this exact endpoint from a real
running backend, downloaded through the Next.js `/getvela` page in an
actual browser, and confirmed byte-for-byte matching the real Getvela
template's header row and the real variation grid's values.

### Google Drive master-image archive
The other half of the "no direct Etsy API" workflow: once a design has a
real SKU (every listing gets one -- see `SKU` in `build_listing_rows`
above), the account owner's actual operational pain point was that when
an Etsy order comes in, they can't find the corresponding master image
in Google Drive to fulfill it. `app/pipeline/drive_archive.py` +
`POST /api/drive-archive/sync` uploads each approved Artwork's master
image to a Drive folder, named `{sku}.png`, via a real Google Drive API
call (`app/providers/google_drive.py`, a service-account adapter -- see
its docstring for the one-time, no-interactive-login setup). This
follows the same `ProviderRegistry`/fake-adapter pattern as every other
vendor integration in this codebase (`FakeDriveArchiveProvider` in
`app/providers/fake/drive_archive.py` — deterministic, no network call —
is what `PROVIDER_MODE=fake`/tests use; the `archive.drive` role in
`config/providers.yaml` stays on `fake` until
`GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` and `GOOGLE_DRIVE_FOLDER_ID` are set).

`drive_archive_records` (`app/memory/drive_archive_memory.py`) tracks
what's already been archived, so re-running the sync never re-uploads a
design, and backs `GET /api/drive-archive/lookup?sku=...` -- the actual
fix for the stated problem: paste an order's SKU into the Control
Center's `/drive-archive` page (or call the endpoint directly) and land
on the master file immediately, instead of searching Drive by hand.
Scope is deliberately narrow: only the master image, not ratio exports
or mockups, since that's what a POD partner/human needs to fulfill an
order.

Verified end-to-end with the fake adapter (no real Google credentials
needed for this): synced real approved artworks from a live backend,
confirmed a SKU search on `/drive-archive` correctly reported "not
found" before syncing and returned the correct Drive link after.

## Phase 5 — Market intelligence & commercial learning
Market intelligence / commercial-feedback adapters that return `null`
rather than fabricate data when unconfigured, Champion/Challenger family
tracking, learning engine that adjusts Production Controller allocation
from real outcomes only.
**Status: complete, including a working real market-intelligence path.**
`app/pipeline/{market_intelligence,opportunity_engine,performance_ingestion,
champion_challenger,commercial_learning}.py`,
`app/providers/{commercial_feedback,web_search_market_intelligence}.py`,
`app/memory/{commercial_memory,market_signal_memory}.py`,
`app/db/models/market_signal.py`, `app/api/routes/market_intelligence.py`.

Market intelligence has two real (non-Null) paths in, both landing in the
same `market_signals` table and both read back by
`DatabaseMarketIntelligenceAdapter`:
1. **Code-level**: `WebSearchMarketIntelligenceAdapter` calls a real search
   API (SerpAPI) inline from a Celery worker — needs `SERPAPI_KEY`.
2. **Externally submitted**: `POST /api/market-intelligence/signals` lets
   an out-of-process researcher write real findings directly — this is
   what an agent-driven web research job (a Claude session with web
   search, running on a schedule) is meant to call. See "Agent-driven
   market research" below for how to wire that up once the backend is
   deployed somewhere reachable. Verified end-to-end during development:
   a real web search for current Etsy wall-art trends, posted through
   this endpoint, persisted, and read back through the Opportunity Engine
   producing correctly-ranked opportunities — no fabricated data at any
   step.

Both paths query *what to research today* from
`app/pipeline/market_research_planner.py`, not a static list:
continuous Etsy-bestseller-tracking queries every day
(`config/market_research_queries.yaml`) plus whichever seasonal
occasions are currently inside their research lead-time window
(`config/seasonal_calendar.yaml`, `app/pipeline/seasonal_calendar.py`) --
e.g. Halloween starts appearing in the plan ~12 weeks out, not the week
of, matching how Etsy print-on-demand sellers actually need to list
seasonal designs well ahead of the search-volume spike. Verified live on
2026-08-14: the plan correctly included Halloween (11.1 weeks out, inside
its 12-week window) alongside Back to School and Fall/Autumn, on top of
the always-on bestseller/evergreen queries.
`GET /api/market-intelligence/research-queries` exposes this same plan so
an agent-driven research job can ask "what should I look for today"
instead of carrying its own copy of the calendar logic.

The daily cycle now consumes this ranking, closing the loop the
"Explicit non-goals" section used to name as open: before
`app/pipeline/collection_planner.py::plan_collections()` bootstraps a new
DISCOVERY collection for an EXPERIMENTAL/WILDCARD slot, it asks
`app/pipeline/opportunity_engine.py::fetch_current_opportunities()` for
today's ranked real signals and biases which bootstrap archetype
(`config/production_policy.yaml`) gets used via
`app/pipeline/archetype_affinity.py::rank_archetypes_by_opportunities()` --
a bounded, stopword-filtered word-overlap score between each archetype's
declared vocabulary (name/thesis/target_aesthetic/medium/subject_families)
and each real signal's description, weighted by the signal's confidence.
Only genuine external signals participate (the Opportunity Engine's
"continue proven collection" fallback for when no signal exists is
explicitly excluded, so an empty signal day never fabricates a bias); when
nothing overlaps, bootstrapping falls back to the archetypes' declared
order exactly as before. Every biased pick is traceable: the winning
archetype's note (which signal, at what confidence) is stored on the
`SlotAssignment` and written into `DailyProductionPlan.collections`.
Wired into both `app/queue/tasks/analysis.py::plan_collections_task` (the
real Celery path) and `app/simulation/daily_simulation.py` (so the
acceptance test exercises the same call shape, with an empty signal set on
a fresh test DB producing identical behavior to before this change).

Commercial feedback (`CommercialFeedbackAdapter`) still ships only the
Null adapter — see "Explicit non-goals" below for why that one is
different (it needs Etsy credentials, not just web search).

## Acceptance test

`backend/tests/test_acceptance_30_designs.py` runs the full mission
acceptance scenario using fake providers: autonomous `DailyProductionPlan`
for a target of 30 → multiple collections → genomes → concepts →
asynchronous (Celery-eager) generation → QC → rejection of poor candidates
→ selective repair of promising failures → duplicate/fatigue detection →
tournament ranking → ≥30 qualified candidates surfaced for approval →
simulated bulk-approve → print masters → ratio exports → mockups → Etsy
packages → full cost ledger → full traceability chain per approved design.
A companion test injects a mid-pipeline provider failure and asserts the
affected candidate reaches a well-defined terminal state (dead-lettered,
diagnosed) without corrupting sibling candidates or the collection.

## Explicit non-goals of the current implementation

These are named, not silently skipped, so nothing is mistaken for "done":

- **Next.js frontend is an MVP, not the full mission-brief UI.**
  `frontend/` is a working Next.js (App Router) + TypeScript + Tailwind
  Control Center consuming the FastAPI backend end-to-end: a dashboard
  (`GET /api/dashboard/today`, production plan trigger via
  `POST /api/production/plan`), an approval queue (`GET /api/candidates`,
  single and multi-select bulk approve/reject via
  `POST /api/candidates/{id}/approval` and
  `/bulk-approval`), and a read-only market-signals view
  (`GET /api/market-intelligence/signals`,
  `GET /api/market-intelligence/research-queries`). Verified with a real
  end-to-end browser smoke test against a live backend seeded by the
  daily simulation: real generated images rendered, a production plan
  triggered, a bulk approval submitted and persisted (`approved` count
  moved 3 → 10 in the dashboard KPI). What's still missing versus the
  mission brief's fuller vision: keyboard-driven bulk actions, live
  KPI polling/websockets (currently load-on-navigate), and per-candidate
  refinement actions beyond approve/reject (`MORE_ORIGINAL`,
  `CHANGE_PALETTE`, etc. — the API supports these via `ApprovalAction`,
  the UI doesn't expose them yet). See `frontend/README.md`.
- **No direct Etsy API integration, by deliberate choice, not omission.**
  The account owner does not want Etsy API credentials in this system at
  all, over concern that automated listing activity risks a shop
  suspension. The adapter interface + package data model
  (`app/db/models/artwork.py:EtsyListingPackage`) still exist for anyone
  who later decides otherwise, but the real publish path this system
  actually ships is the Getvela CSV export (Phase 4 above) — CSV in,
  human review and activation in Getvela, exactly matching the account
  owner's existing workflow and risk tolerance.
- No real paid image-gen/vision-LLM vendor wired by default — provider
  config supports it (`PROVIDER_ARCHITECTURE.md`), but shipping with a
  vendor key baked in is out of scope and against the "never hardcode
  credentials" requirement.
- No real commercial-feedback (sales/favorites/views) data source.
  `app/providers/commercial_feedback.py` ships only
  `NullCommercialFeedbackAdapter` — this one genuinely needs Etsy
  credentials (OAuth token + shop ID), which this system must never
  assume it has. Champion/Challenger promotion and collection
  graduation-by-acceptance-rate are real and tested against whatever
  `CommercialObservation` rows exist, but none will exist until a real
  adapter is written against `CommercialFeedbackAdapter` and a real Etsy
  credential is supplied.
- Market intelligence, by contrast, **does** have a working real path now
  (see Phase 5 above), and it is wired into the daily cycle: real, ranked
  opportunities bias which bootstrap archetype a new EXPERIMENTAL/WILDCARD
  collection gets (`app/pipeline/archetype_affinity.py`, see Phase 5
  above for details). `production_controller.build_daily_plan()` still
  computes portfolio *allocation* (slot counts per bucket) purely from
  `config/production_policy.yaml` fractions + budget, not from
  `market_signals` — a real signal changes *which* collection an
  EXPERIMENTAL slot goes to, not *how many* EXPERIMENTAL slots exist
  today. Feeding signal strength back into the slot-count math itself
  (e.g. temporarily growing the EXPERIMENTAL fraction when an unusually
  strong signal appears) is a bigger policy decision than this repository
  makes unilaterally, and is left for a deliberate follow-up.
- The Redis-backed, cross-process rate limiter and dead-letter queue
  described in `docs/PROVIDER_ARCHITECTURE.md` / `docs/EVENTS.md` are
  implemented as in-memory/best-effort in this single-process-per-worker
  codebase (`app/providers/rate_limit.py`, `app/queue/base_task.py`) — the
  *pattern* and its tests are real (retry, backoff, circuit breaker,
  dead-letter routing all pass under test, including a genuine worker-
  failure scenario), but a multi-worker production deployment should swap
  the rate limiter for a Redis-backed one sharing state across processes,
  exactly as those docs already say.
- Real vendor adapters (OpenAI/Anthropic/Stability/Topaz/S3/...) are not
  implemented; `app/providers/factory.py` raises a clear `ProviderError`
  naming the missing adapter rather than silently falling back to fake
  behavior outside of `PROVIDER_MODE=fake`/`APP_ENV=test`.

## Agent-driven market research

`POST /api/market-intelligence/signals` (guarded by
`MARKET_SIGNAL_INGESTION_TOKEN` when set — see `.env.example`) is designed
to be called by a scheduled Claude session that does real web research and
reports what it actually found. This was **not** wired up as a live
recurring job during development, because doing so requires a backend
deployed somewhere reachable from outside this sandbox — creating a
recurring trigger against an ephemeral dev container would just fail
silently forever. It **was** verified working manually: a real
`WebSearch` for current Etsy wall-art trends, submitted through this exact
endpoint against a locally running instance, persisted to `market_signals`
and read back correctly-ranked through the Opportunity Engine.

Once the backend is deployed somewhere with a stable URL, wire up the
daily job with a Routine (via the `create_trigger` MCP tool available to
Claude Code sessions) along these lines:

```
create_trigger(
  name="Design Factory market research",
  cron_expression="0 13 * * *",  # once daily, in UTC
  create_new_session_on_fire=true,
  prompt="""
    1. GET https://<your-deployed-backend>/api/market-intelligence/research-queries
       This returns today's query list: continuous Etsy-bestseller-tracking
       queries every day, plus seasonal queries for any occasion (Halloween,
       Christmas, ...) currently inside its research lead-time window --
       already computed for you, don't guess what season it is.
    2. Run a real web search for each query returned.
    3. For each real finding, extract: category (use the query's own
       category from step 1), a one-sentence description of what you
       actually found, a confidence 0-1 reflecting how strong the signal
       looked, and source (a URL or "web_search:<date>").
    4. POST them as one batch to:
       https://<your-deployed-backend>/api/market-intelligence/signals
       Header: X-Ingestion-Token: <the configured MARKET_SIGNAL_INGESTION_TOKEN>
       Body: {"signals": [{"category": ..., "description": ..., "confidence": ..., "source": ...}, ...]}
    Only submit things you actually found in search results this run --
    never invent a trend to fill out the batch, and don't skip the
    seasonal queries from step 1 even if they look premature -- the
    lead-time window is already accounted for server-side.
  """,
)
```

The `frontend/market-signals` page already shows
`GET /api/market-intelligence/signals` and today's research plan, making
this research visible to the human, and it already feeds
`rank_opportunities()` (and now `archetype_affinity.py`, see Phase 5
above) for free.

## Environment & running it

See `backend/README.md` for local setup (Postgres via Docker or SQLite for
tests, Redis via Docker or Celery eager mode for tests) and
`frontend/README.md` for the Control Center. `infra/docker-compose.yml`
builds the full stack (Postgres, Redis, backend, worker, beat, frontend)
via `infra/Dockerfile.backend`, `infra/Dockerfile.worker`, and
`infra/Dockerfile.frontend`.
