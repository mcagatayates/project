# AGENT CONTRACTS

Each pipeline stage ("agent") has a fixed input contract, output contract,
idempotency rule, and failure policy. "Agent" here means the deterministic
or LLM-backed unit of decision-making at that stage — not necessarily an
autonomous chat agent. Every contract below is implemented as a plain
Python function (`app/pipeline/<stage>.py`) invoked either directly (cheap,
DB-only stages) or via a Celery task (stages that call a provider).

Common rules for every stage:
- Reads only from Postgres (+ its own provider call); no hidden in-memory
  state carried between stages.
- Writes are append-only except for the explicit status-field updates
  named per stage.
- Every stage that calls a provider records exactly one `CostEvent` per
  provider call (`$0` allowed, but the row must exist for traceability).
- Every stage that calls a provider records a `ProviderHealthLog` entry.

---

### Market Intelligence
- **Input:** none (scheduled) or manual trigger.
- **Output:** `OpportunitySignal` rows (transient analysis output, stored as
  part of `Experiment`-adjacent analysis records) summarizing external
  signal categories (trend tags, saturation warnings) available to the
  Opportunity Engine. Uses whatever adapters are configured; if none are
  configured, returns an empty signal set — never fabricated trends.
- **Idempotency key:** `market_intel:{date}`.
- **Failure policy:** non-fatal to the daily cycle; Production Controller
  proceeds using historical data alone if this stage fails or is empty.

### Opportunity Engine
- **Input:** Market Intelligence signals, `CommercialMemory`, collection
  saturation state.
- **Output:** ranked list of `{opportunity, rationale, confidence}` consumed
  by the Production Controller and Collection Planner.
- **Idempotency key:** `opportunity_engine:{date}`.
- **Failure policy:** falls back to "continue proven collections only."

### Daily Production Controller
- **Input:** historical designs/winners/failures, active collections +
  saturation, recent experiments, opportunity signals, commercial
  performance, cost-to-date, provider availability, diversity state,
  configured allocation policy (`config/production_policy.yaml`).
- **Output:** one `DailyProductionPlan` row.
- **Idempotency key:** `daily_plan:{date}` (unique constraint on
  `plan_date`; re-invocation for the same date updates the existing plan's
  mutable fields rather than creating a duplicate).
- **Failure policy:** if a hard dependency (DB) is unavailable, no plan is
  created and downstream stages have nothing to act on — fails loudly, does
  not guess a plan.
- **Budget contract:** never emits a plan whose `budget_cap_usd` exceeds the
  configured daily budget; reduces `production_slots`/`experimental_slots`
  proportionally under a tight budget rather than dropping a whole
  portfolio bucket to zero.

### Collection Planner
- **Input:** `DailyProductionPlan` (unpersisted candidate allocation),
  existing `Collection` rows.
- **Output:** creates new `Collection` rows for `EXPERIMENTAL`/`WILDCARD`
  slots when no suitable existing collection exists; otherwise assigns
  slots to existing collections. Never creates a collection with fewer than
  its configured minimum design count worth of allocated slots in one plan
  unless it's explicitly a single-design wildcard probe.
- **Idempotency key:** `collection_plan:{plan_id}`.

### Design Genome (creation)
- **Input:** `Collection`, production mode, optional parent genome (for
  mutation) or opportunity rationale (for novel).
- **Output:** one `DesignGenome` row (`created_by = SYSTEM_DISCOVERY` or
  `SYSTEM_MUTATION`).
- **Idempotency key:** `genome_create:{collection_id}:{slot_index}:{date}`.

### Concept Generation
- **Input:** `DesignGenome`, `Collection`, relevant `Experiment` history
  (queried before creating the concept — mandatory per mission spec).
- **Output:** one `Concept` row, `gate_status = PENDING`.
- **Idempotency key:** `concept:{design_genome_id}`.

### Concept Gate
- **Input:** `Concept`, sibling concepts already planned today, collection
  boundaries.
- **Output:** updates `Concept.gate_status` to `PASSED` or `REJECTED` +
  `gate_reasoning`. Uses a cheap LLM/rule check — no image generation yet.
- **Idempotency key:** `concept_gate:{concept_id}` (re-running with the same
  inputs must yield the same verdict — gate logic is deterministic given
  the same DB state plus a fixed-temperature LLM call).

### Generation
- **Input:** `Concept` (gate-passed), `attempt_number`.
- **Output:** one `GenerationCandidate` per attempt, `status=GENERATED`,
  image bytes written through `StorageProvider`.
- **Idempotency key:** `generate:{concept_id}:{attempt_number}`.
- **Failure policy:** provider error → retry with backoff (see
  `PROVIDER_ARCHITECTURE.md`); exhausted retries → candidate marked
  `status=GENERATED` is never set; a `FailureRecord` with
  `failure_class=TERMINAL_FAILURE` and `diagnosed_by="provider_exhausted"`
  is written instead so the concept doesn't silently vanish.

### Multi-dimensional Vision QC
- **Input:** `GenerationCandidate` image.
- **Output:** one `Evaluation` row with all seven scores.
  `overall_pass` is computed from configurable per-score thresholds (not a
  single blended number). Candidate status → `QC_PASSED` or `QC_FAILED`.
- **Idempotency key:** `vision_qc:{generation_candidate_id}:{attempt}`.

### Failure Diagnosis
- **Input:** `GenerationCandidate` with `status=QC_FAILED`, its `Evaluation`.
- **Output:** one `FailureRecord` with `failure_class`.
  Classification rule (default, configurable): `TERMINAL_FAILURE` if
  technical_quality or printability score is below the hard floor (e.g.
  anatomy/artifact-level defects that repair cannot fix); `PROMISING` if
  aesthetic/originality/commercial scores are strong but one fixable
  dimension failed; otherwise `REPAIRABLE_FAILURE`.
- **Idempotency key:** `diagnose:{generation_candidate_id}`.

### Selective Repair
- **Input:** `FailureRecord` where `failure_class ∈ {REPAIRABLE_FAILURE,
  PROMISING}` **and** expected-value check passes (historical repair
  success rate for this failure signature × remaining budget for this
  concept > cost of one more generation attempt — queried from
  `FailureMemory`).
- **Output:** one `RepairAttempt` row + a new `GenerationCandidate`
  (`is_repair=true`) re-entering Vision QC.
- **Idempotency key:** `repair:{failure_record_id}:{attempt}`.
- **Cap:** max repair attempts per concept is configurable (default 2).

### Tournament Selection
- **Input:** all `QC_PASSED` candidates for a `Concept` (or a collection's
  batch, for cross-concept tournaments in Production Mode).
- **Output:** candidate `status → SELECTED` for winner(s), `ELIMINATED` for
  the rest, ranked by the score vector under configured weights.
- **Idempotency key:** `tournament:{concept_id_or_batch_id}`.

### Diversity / Fatigue Control
- **Input:** `SELECTED` candidates, historical artwork library (embeddings
  + perceptual hashes + genome fields), same-day sibling selections.
- **Output:** demotes a `SELECTED` candidate back to `ELIMINATED` if
  similarity to existing inventory or to another selection made *today*
  exceeds configured thresholds; records the comparison basis
  (which prior artwork, which similarity method, score) for auditability.
- **Idempotency key:** `diversity_check:{generation_candidate_id}`.

### Human Approval
- **Input:** `SELECTED` candidate presented in the dashboard, human action.
- **Output:** one `Approval` row. `APPROVE` → creates `Artwork`,
  candidate `status → APPROVED`. `REJECT` → `status → REJECTED`. Any
  DNA-mutating action → new `DesignGenome` version + new `Concept` +
  candidate `status → AWAITING_APPROVAL` superseded, loops back to
  Generation.
- **Idempotency key:** none required (human-triggered, single write per
  click; API layer disables the control after first response).

### Print Master / Ratio Exports
- **Input:** `Artwork`.
- **Output:** one `PrintExport` row per configured ratio, real pixel
  dimensions recorded, optional real upscale via `UpscaleProvider` when
  master resolution is below a ratio's requirement.
- **Idempotency key:** `print_export:{artwork_id}:{ratio}`.

### Mockup Factory
- **Input:** `Artwork` + configured mockup templates.
- **Output:** one `Mockup` row per template, stored separately from the
  master.
- **Idempotency key:** `mockup:{artwork_id}:{template_id}`.

### Etsy Listing Package
- **Input:** `Artwork`, its `PrintExport`s, `Mockup`s, `Collection` context.
- **Output:** one `EtsyListingPackage` row. Does not call any Etsy API.
- **Idempotency key:** `etsy_package:{artwork_id}`.

### Performance Ingestion
- **Input:** whatever a configured commercial adapter (e.g. Etsy) returns
  for published listings.
- **Output:** `CommercialObservation` rows, one per metric actually
  returned. No adapter configured → no rows, no error.
- **Idempotency key:** `perf_ingest:{external_listing_id}:{metric_name}:{observed_at}`.

### Commercial Learning
- **Input:** `CommercialObservation`s aggregated by genome/collection/family.
- **Output:** updates `CreativeFamily.performance_summary` and
  `Collection.status` (graduation), never rewrites historical
  `DesignGenome`/`Experiment` rows.
- **Idempotency key:** `commercial_learning:{date}`.
