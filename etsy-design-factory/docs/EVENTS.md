# EVENTS

The system is driven by Celery tasks, not a general pub/sub bus. This
document is the catalog of task "events" — their queue, payload,
idempotency key, retry policy and dead-letter behavior — since in this
architecture a Celery task *is* the event.

## Queues

`analysis`, `concepts`, `generation`, `vision_qc`, `repair`,
`image_processing`, `mockups`, `exports`. Each queue maps 1:1 to a Celery
worker pool that can be scaled independently
(`celery -A app.queue.celery_app worker -Q generation --concurrency=4`).
Each queue additionally has a `.dlq` counterpart
(`generation.dlq`, etc.) that dead letters route to.

## Payload envelope

Every task payload is a flat dict with at minimum:

```json
{
  "idempotency_key": "generate:concept-uuid:1",
  "entity_type": "concept",
  "entity_id": "uuid",
  "attempt": 1,
  "enqueued_at": "iso8601"
}
```

Handlers must be safe to receive the same envelope more than once
(Celery's broker gives at-least-once delivery). The standard pattern:
`INSERT ... ON CONFLICT (idempotency_key) DO NOTHING RETURNING id`-style
upsert, or a pre-check `SELECT` for the key before doing provider work.

## Task catalog

| Task | Queue | Triggered by | Idempotency key |
|---|---|---|---|
| `run_market_intelligence` | `analysis` | Celery beat (daily) | `market_intel:{date}` |
| `run_opportunity_engine` | `analysis` | after market intel | `opportunity_engine:{date}` |
| `plan_daily_production` | `analysis` | Celery beat (daily) / manual | `daily_plan:{date}` |
| `plan_collections` | `analysis` | after `plan_daily_production` | `collection_plan:{plan_id}` |
| `create_design_genome` | `concepts` | after collection plan, per slot | `genome_create:{collection_id}:{slot_index}:{date}` |
| `generate_concept` | `concepts` | after genome created | `concept:{design_genome_id}` |
| `gate_concept` | `concepts` | after concept created | `concept_gate:{concept_id}` |
| `generate_candidate` | `generation` | after gate pass, per attempt | `generate:{concept_id}:{attempt}` |
| `run_vision_qc` | `vision_qc` | after candidate generated | `vision_qc:{candidate_id}:{attempt}` |
| `diagnose_failure` | `vision_qc` | after QC fail | `diagnose:{candidate_id}` |
| `run_selective_repair` | `repair` | after diagnosis, if EV positive | `repair:{failure_record_id}:{attempt}` |
| `run_tournament_selection` | `analysis` | after all concept candidates resolved | `tournament:{concept_id}` |
| `run_diversity_control` | `analysis` | after tournament | `diversity_check:{candidate_id}` |
| `process_print_master` | `image_processing` | on `Approval(APPROVE)` | `print_export:{artwork_id}:{ratio}` (fans out per ratio) |
| `generate_mockups` | `mockups` | after print master done | `mockup:{artwork_id}:{template_id}` (fans out per template) |
| `build_etsy_package` | `exports` | after mockups done | `etsy_package:{artwork_id}` |
| `ingest_performance` | `analysis` | Celery beat (hourly/daily) | `perf_ingest:{listing_id}:{metric}:{observed_at}` |
| `run_commercial_learning` | `analysis` | after ingestion | `commercial_learning:{date}` |

## Retry & backoff

Default policy (overridable per task): `max_retries=5`,
`retry_backoff=True` (Celery exponential backoff), `retry_backoff_max=600`
seconds, `retry_jitter=True`. Provider-specific rate-limit errors (HTTP 429)
retry with the provider's `Retry-After` header when present.

## Dead-letter handling

On final retry exhaustion, the task handler:
1. Writes a `FailureRecord`/error row against the owning entity so the
   failure is visible in the domain data, not just infra logs.
2. Re-publishes the payload to `<queue>.dlq` for operator inspection/replay.
3. Never raises past the Celery boundary uncaught — every task has a
   top-level try/except that guarantees step 1 happens even if step 2's
   publish fails.

This is what "the pipeline survives worker/API failures without
corrupting projects" means concretely: a candidate that fails generation
forever still ends up in a well-defined terminal DB state
(`FailureRecord(TERMINAL_FAILURE)`), not stuck `GENERATING` forever and not
silently deleted.

## Fan-out / fan-in

- `generate_candidate` fans out N attempts per concept (N depends on
  Discovery vs Production mode — see `ROADMAP.md` Phase 2). Implemented as
  a Celery `group`.
- `run_tournament_selection` is the fan-in: a Celery `chord` callback that
  fires once all candidates for a concept have reached a terminal QC/repair
  state (`QC_PASSED`, `TERMINAL`, or repair-cap-exhausted). A periodic
  sweep task also catches concepts stuck mid-fan-in past a timeout
  (handles chord callback delivery failure, a known Celery edge case).

## Ordering guarantees

None assumed across queues. Every cross-stage dependency is expressed as
"read the DB state you need," not "trust that message N arrived before
message N+1." This is why every stage's contract in `AGENT_CONTRACTS.md`
lists its DB reads explicitly.
