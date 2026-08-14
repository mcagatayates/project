# ARCHITECTURE

## Component overview

```
                         ┌──────────────────────┐
                         │   Next.js Frontend    │  Production Dashboard,
                         │  (Control Center UI)  │  Candidate Grid, Approval
                         └──────────┬────────────┘
                                    │ HTTPS / REST (JSON)
                         ┌──────────▼────────────┐
                         │      FastAPI API       │  thin: validates, reads/
                         │   (backend/app/api)    │  writes DB, enqueues jobs.
                         └──────────┬────────────┘   Never runs pipeline work
                                    │                  inline.
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
     ┌────────▼───────┐   ┌─────────▼────────┐   ┌────────▼────────┐
     │   PostgreSQL     │   │   Redis (broker/  │   │  Object Storage  │
     │ source of truth  │   │   result backend) │   │ (S3-compatible / │
     └────────▲─────────┘   └─────────▲────────┘   │  local / Drive)  │
              │                       │              └────────▲────────┘
              │              ┌────────▼─────────┐              │
              │              │   Celery workers   │             │
              └──────────────┤  (queue-separated) ├─────────────┘
                              └────────┬───────────┘
                                       │
                          ┌────────────▼─────────────┐
                          │   Provider Registry        │
                          │ (LLM / Vision / ImageGen /  │
                          │  Upscale / Storage adapters)│
                          └────────────┬─────────────┘
                                       │
                     External paid APIs (image gen, vision,
                     LLM) OR Fake/local providers in test mode
```

## Pipeline stages → modules → queues

Each stage in the mission's primary pipeline maps to a backend module and,
where it does non-trivial or paid work, a Celery queue. Stages are pure
functions of their inputs plus explicitly-declared reads from the DB; they
never share in-memory state across a task boundary — every handoff is a row
in Postgres.

| Stage | Module | Queue |
|---|---|---|
| Market Intelligence | `app/pipeline/market_intelligence.py` | `analysis` |
| Opportunity Engine | `app/pipeline/opportunity_engine.py` | `analysis` |
| Daily Production Controller | `app/pipeline/production_controller.py` | `analysis` (invoked synchronously by a scheduled job, writes a plan) |
| Collection Planner | `app/pipeline/collection_planner.py` | `analysis` |
| Design Genome (creation/mutation) | `app/genome/*` | `concepts` |
| Concept Generation | `app/pipeline/concept_generation.py` | `concepts` |
| Concept Gate | `app/pipeline/concept_gate.py` | `concepts` |
| Generation | `app/pipeline/generation.py` | `generation` |
| Multi-dimensional Vision QC | `app/pipeline/vision_qc.py` | `vision_qc` |
| Failure Diagnosis | `app/pipeline/failure_diagnosis.py` | `vision_qc` |
| Selective Repair | `app/pipeline/selective_repair.py` | `repair` |
| Tournament Selection | `app/pipeline/tournament_selection.py` | `analysis` |
| Diversity / Fatigue Control | `app/pipeline/similarity_engine.py`, `diversity_control.py` | `analysis` |
| Human Approval | `app/api/routes/approvals.py` + `app/pipeline/approval.py` | n/a (interactive, API-triggered) |
| Print Master / Ratio Exports | `app/pipeline/print_factory.py` | `image_processing` |
| Mockup Factory | `app/pipeline/mockup_factory.py` | `mockups` |
| Etsy Listing Package | `app/pipeline/etsy_package.py` | `exports` |
| Performance Ingestion | `app/pipeline/performance_ingestion.py` | `analysis` |
| Commercial Learning | `app/pipeline/commercial_learning.py` | `analysis` |

Queue separation exists so that a spike in, e.g., vision QC retries cannot
starve print/export work for already-approved designs, and so concurrency
and rate limits can be tuned per external dependency (image-gen APIs need
tight concurrency caps; DB-only analysis tasks do not).

## Request path vs. background path

- The API never calls a provider or does image processing synchronously.
  It creates/reads rows and enqueues Celery tasks.
- The only synchronous, non-trivial compute allowed in the API process is
  reading already-computed state for the dashboard, and applying an
  approval action's genome mutation (pure in-process transform + DB write,
  no provider calls) before enqueuing the next stage.
- Long chains (concept → generate → QC → repair → QC → select) are modeled
  as a Celery chain/chord per candidate, not as one giant task, so any step
  can retry independently and dead-letter without losing the rest of the
  batch.

## Concurrency, rate limiting, idempotency

- Each provider adapter declares a `max_concurrency` and `rate_limit`
  (requests/minute). The registry enforces this with a Redis-backed token
  bucket/semaphore, independent of Celery's own worker concurrency.
- Every task is idempotent: task payloads carry a deterministic
  `idempotency_key` (e.g. `f"generate:{candidate_id}:{attempt}"}`). Handlers
  upsert on this key so redelivery (Celery's at-least-once semantics) never
  double-charges cost or creates duplicate rows.
- Retries use exponential backoff with jitter (`autoretry_for`, capped
  attempts). Exhausted retries route to a dead-letter queue
  (`<queue>.dlq`) with the failure recorded on the entity, never silently
  dropped. See `EVENTS.md`.

## Scheduling the daily cycle

A scheduled job (Celery beat / cron) triggers `production_controller.plan_day()`
at a configured time. Everything downstream is reactive: creating a plan
enqueues collection planning, which enqueues concept generation for each
collection slot, which fans out generation jobs, etc. The system does not
require a human to kick off a day, but a human can also trigger it manually
from the dashboard for testing or catch-up runs.

## Storage

Master artwork, ratio exports and mockups are written through a
`StorageProvider` interface (`app/providers/base.py`) with an S3-compatible
implementation and a local-filesystem implementation (used in tests and
optionally in dev). A Google Drive adapter is optional and implements the
same interface. The DB never stores binary image data — only storage keys
and derived metadata (dimensions, hashes, checksums).

## Deployment topology (Docker Compose)

Services: `postgres`, `redis`, `backend` (FastAPI/uvicorn), `worker`
(Celery, one process group per queue via `--queues` flag, scaled
independently), `beat` (Celery beat scheduler), `frontend` (Next.js).
See `infra/docker-compose.yml`.

## Why this shape supports 30/day

- Generation and QC are the expensive, parallelizable steps — they are the
  only ones with dedicated, concurrency-capped queues talking to paid APIs.
- Analysis/planning/selection are cheap and run against the DB, so they can
  run frequently without touching budgets.
- Because every stage persists its output before the next stage is
  enqueued, a full container restart or worker crash loses at most the
  in-flight task (which redelivers), never the batch.
