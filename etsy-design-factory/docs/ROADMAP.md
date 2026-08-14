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
**Status: see repository — implemented in `backend/`.**

## Phase 2 — Daily Production Controller & throughput
`DailyProductionPlan` generation (configurable, not hardcoded allocation),
Collection Planner, Discovery vs. Production mode with a graduation rule,
queue separation per `EVENTS.md`, budget enforcement. Exit criterion: the
30-design acceptance simulation (see below) passes using only fake
providers.
**Status: see repository.**

## Phase 3 — Evolution & memory
Controlled mutation/genealogy, `FailureMemory`, `ExperimentMemory`,
creative fatigue / similarity engine (perceptual hash + palette + genome
similarity), cost engine with per-design/collection/daily/monthly rollups
and budget gates wired into the Production Controller.
**Status: see repository.**

## Phase 4 — Print, Mockup, Etsy package
Real ratio exports (actual pixel operations, never DPI-metadata tricks),
mockup compositing kept strictly separate from the master asset, Etsy
listing package assembly with zero coupling from the creative pipeline to
any Etsy API call.
**Status: see repository.**

## Phase 5 — Market intelligence & commercial learning
Market intelligence / commercial-feedback adapters that return `null`
rather than fabricate data when unconfigured, Champion/Challenger family
tracking, learning engine that adjusts Production Controller allocation
from real outcomes only.
**Status: see repository — interfaces and data model land in Phase 1-3
groundwork; adapters are stubs pending real Etsy API credentials, which by
design this system must never assume it has.**

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

- No real Etsy publish integration (adapter interface + package data model
  exist; the network call is intentionally not implemented without live
  credentials).
- No real paid image-gen/vision-LLM vendor wired by default — provider
  config supports it (`PROVIDER_ARCHITECTURE.md`), but shipping with a
  vendor key baked in is out of scope and against the "never hardcode
  credentials" requirement.
- Frontend Control Center ships as a functional minimal dashboard
  (KPIs, candidate grid, approve/reject, bulk actions) rather than a fully
  polished production UI — the API contract it depends on is complete and
  stable; visual polish is intentionally deferred.
- Market intelligence adapters are interface-complete with a `null`
  (no-signal) default implementation; connecting a real trend-data source
  is a config change, not a code change, once one is chosen.

## Environment & running it

See `backend/README.md` for local setup (Postgres via Docker or SQLite for
tests, Redis via Docker or Celery eager mode for tests) and
`infra/docker-compose.yml` for the full stack.
