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
**Status: complete.** `app/pipeline/{print_factory,mockup_factory,
etsy_package}.py`.

## Phase 5 — Market intelligence & commercial learning
Market intelligence / commercial-feedback adapters that return `null`
rather than fabricate data when unconfigured, Champion/Challenger family
tracking, learning engine that adjusts Production Controller allocation
from real outcomes only.
**Status: complete as far as this system can go without live credentials.**
`app/pipeline/{market_intelligence,opportunity_engine,performance_ingestion,
champion_challenger,commercial_learning}.py`,
`app/providers/commercial_feedback.py`,
`app/memory/commercial_memory.py`. Every adapter's *only* shipped
implementation is a Null adapter returning no data — see "Explicit
non-goals" below for what that means in practice.

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

- **No Next.js frontend.** `docs/ARCHITECTURE.md` specifies Next.js/React/
  Tailwind for the Control Center; this repository ships the complete,
  tested FastAPI backend it would consume (`app/main.py`, `app/api/` —
  dashboard KPIs, candidate grid with images, single/bulk approval
  actions, production plan trigger) but not the UI itself. This is the
  single largest deferred piece of the mission brief — building and
  testing a real approval UI (image grid, keyboard-driven bulk actions,
  live KPI polling) is its own multi-day effort, and a stable, tested API
  contract was judged more valuable to ship first than a partial UI.
- No real Etsy publish integration (adapter interface + package data model
  exist; the network call is intentionally not implemented without live
  credentials).
- No real paid image-gen/vision-LLM vendor wired by default — provider
  config supports it (`PROVIDER_ARCHITECTURE.md`), but shipping with a
  vendor key baked in is out of scope and against the "never hardcode
  credentials" requirement.
- No real market-intelligence or commercial-feedback data source.
  `app/pipeline/market_intelligence.py` and
  `app/providers/commercial_feedback.py` ship a `Null*Adapter` that always
  returns "no data" — by design, since fabricating trend or sales data
  would violate the mission's explicit "never fabricate unavailable
  metrics" requirement. Concretely, this means Champion/Challenger
  promotion and collection graduation-by-acceptance-rate are real and
  tested, but nothing in this system will *autonomously* discover a
  trend or receive real Etsy sales numbers until a real adapter is
  written against `CommercialFeedbackAdapter`/`MarketIntelligenceAdapter`
  and a real API credential is supplied.
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

## Environment & running it

See `backend/README.md` for local setup (Postgres via Docker or SQLite for
tests, Redis via Docker or Celery eager mode for tests) and
`infra/docker-compose.yml` for the full stack (Postgres, Redis, backend,
worker, beat, frontend — the `frontend` service in `docker-compose.yml`
and its Dockerfile are placeholders for the deferred Next.js app above,
not yet buildable).
