# DOMAIN MODEL

This document defines the entities, their relationships, and the state
machines that govern the pipeline. Table-level detail (columns, indexes,
types) is in `DATABASE.md`. Genome field-level detail is in
`DESIGN_GENOME_SCHEMA.md`.

## Entity map

```
DailyProductionPlan ──< allocates to >── Collection ──< contains >── DesignGenome
                                                              │
                                                              │ compiles to
                                                              ▼
                                                          Concept ──< gate >── (pass/reject)
                                                              │
                                                              ▼
                                                     GenerationCandidate ──< evaluated by >── Evaluation (7 scores)
                                                              │                                     │
                                                              │ on failure                          │
                                                              ▼                                     │
                                                     FailureRecord ──< diagnosed as >── FailureClass │
                                                              │                                     │
                                                              ▼                                     │
                                                     RepairAttempt (0..N) ──> new GenerationCandidate (repaired)
                                                              │
                                     tournament + diversity control selects survivors
                                                              ▼
                                                     (SELECTED candidates) ──< human decision >── Approval
                                                              │
                                                     approved  │  rejected
                                                              ▼
                                                          Artwork ──< exported as >── PrintExport (per ratio)
                                                              │
                                                              ├──< rendered as >── Mockup (per template)
                                                              │
                                                              └──< packaged as >── EtsyListingPackage
                                                                                        │
                                                                              (optional) published to Etsy
                                                                                        │
                                                                              CommercialObservation (performance)
                                                                                        │
                                                                              feeds CommercialMemory /
                                                                              CreativeFamily (Champion/Challenger)

DesignGenome ──< parent_genome_id (mutation lineage) >── DesignGenome (offspring)
DesignGenome ──< derived_from_version_id (in-place edit) >── DesignGenome (new version, same design_lineage_id)

Experiment ──references──> DesignGenome, Concept, GenerationCandidate[], Evaluation[], cost, outcome
CostEvent ──attributed to──> provider/model/operation + (project, collection, design, candidate)
ProviderHealthLog ──tracks──> provider adapter health/circuit-breaker state
```

## Core entities

### Collection
The primary production unit for most designs. Defines thesis, target
aesthetic, target customer hypothesis, palette boundaries, medium, subject
families, composition-diversity requirements, target design count,
experimental variables, and a `status`: `DISCOVERY → PRODUCTION →
SATURATED → RETIRED`. A collection graduates `DISCOVERY → PRODUCTION` when
its creative family's acceptance rate and (if available) commercial signal
cross configured thresholds (see `AGENT_CONTRACTS.md` /
`commercial_learning`).

### DesignGenome
Structured creative DNA (see `DESIGN_GENOME_SCHEMA.md`). Immutable once
created; edits (via approval actions) or mutations (via evolution) create a
**new row**, never an update. `design_lineage_id` groups all versions/edits
of what a human perceives as "the same design in progress."
`parent_genome_id` + `generation_number` track evolutionary descent from a
Champion/winner into offspring designs — a materially different lineage
concept from in-place editing.

### Concept
A single compiled creative brief: one `DesignGenome` + collection context +
production mode (`DISCOVERY`/`PRODUCTION`) + planned candidate count. A
concept is the unit the Concept Gate approves/rejects before any paid
generation happens (cheap LLM-only check: does this brief make sense, is it
too close to an existing concept already planned today, does it respect
collection boundaries).

### GenerationCandidate
One generated image attempt for a Concept. Tracks provider/model used,
prompt actually sent (compiled, stored verbatim for audit), storage key,
attempt number, and `status`:

```
QUEUED → GENERATING → GENERATED → QC_IN_PROGRESS → QC_PASSED
                                                  → QC_FAILED → DIAGNOSED ─┬─> TERMINAL
                                                                            └─> REPAIR_QUEUED → REPAIRING → REPAIRED (loops to QC_IN_PROGRESS)
QC_PASSED → SELECTION_PENDING → SELECTED → AWAITING_APPROVAL → APPROVED → PRINT_PROCESSING → PRINT_READY → PACKAGED
                               → ELIMINATED (lost tournament / diversity cut)
AWAITING_APPROVAL → REJECTED
```

Terminal states: `TERMINAL`, `ELIMINATED`, `REJECTED`, `PACKAGED`.

### Evaluation
One row per (candidate, scoring pass). Holds all seven independent scores
(`AestheticScore`, `OriginalityScore`, `CommercialPotentialScore`,
`TechnicalQualityScore`, `PrintabilityScore`, `CollectionFitScore`,
`DiversityScore`), each with `{value, confidence, reasoning, problems[]}`.
Never averaged into one silent "quality score" — thresholds and tournament
ranking operate on the vector, with configurable weights.

### FailureRecord / RepairAttempt
`FailureRecord` captures a QC failure plus its diagnosis
(`failure_class ∈ {TERMINAL_FAILURE, REPAIRABLE_FAILURE, PROMISING}`,
detected problems, diagnosis reasoning). `RepairAttempt` captures the
repair action taken (genome/prompt delta, provider used) and its result,
linking back to a new `GenerationCandidate`. Together these form
`FailureMemory` — queryable history of what tends to fail and what repairs
tend to work, per failure category and per creative family.

### Experiment
Wraps a hypothesis-driven unit of work (e.g. "test whether a muted
palette variant of Family X outperforms the saturated original") with its
`DesignGenome`(s), variables tested, provider/model/params, outputs,
scores, winner/failure, cost, and (later) commercial outcome. Concept
Generation queries relevant past experiments before creating new concepts.

### Artwork
The approved, canonical output of a `GenerationCandidate`. One-to-one with
an approved candidate. Root of `PrintExport`, `Mockup`, and
`EtsyListingPackage`.

### PrintExport
One row per (artwork, ratio). Stores actual pixel dimensions and storage
key. Never claims DPI metadata changes resolution — `DATABASE.md` /
`print_factory.py` enforce that upscaling is a real pixel operation via an
`UpscaleProvider`, not a metadata edit.

### Mockup
One row per (artwork, mockup template). Generated from the print master but
stored as a wholly separate asset; the master `Artwork` image is never
overwritten or composited in place.

### EtsyListingPackage
Structured bundle (title concepts, description data, keyword candidates,
tags, style/subject/palette/orientation/collection metadata, internal SKU,
references to `PrintExport`s and `Mockup`s). Publishing to Etsy is a
separate, optional adapter call keyed off this package — the creative
pipeline has no Etsy dependency.

### CommercialObservation / CommercialMemory
Records whatever performance data an adapter actually returns (views,
favorites, sales — whatever Etsy exposes and the user has connected).
Fields the adapter cannot supply stay `NULL`; the system never fabricates a
number. Aggregated per `DesignGenome`, collection, creative family and
experiment to build `CommercialMemory`.

### CreativeFamily (Champion/Challenger)
A named cluster of `DesignGenome`s sharing high-level DNA characteristics
(style + subject + palette signature) that has enough history to be scored
as a group. `status ∈ {CHALLENGER, CHAMPION, RETIRED}`. Champions are never
copied directly — `commercial_learning.py` extracts characteristics
(DNA-field distributions correlated with performance) and feeds them as
*constraints*, not templates, into new challenger concepts.

### DailyProductionPlan
One row per production day. `target_final_designs`, `portfolio_allocation`
(counts per `PROVEN/GROWING/EXPERIMENTAL/WINNER_MUTATION/WILDCARD`),
`collections[]` (collection_id, allocated slots, mode), `experimental_slots`,
`winner_mutation_slots`, `production_slots`, `budget_cap_usd`, and the
policy/config version that produced it (traceability for why the plan
looked the way it did).

### CostEvent
One row per paid operation: provider, model, operation, tokens (nullable),
generation_cost_usd, processing_cost_usd, and attribution
(project/collection/design/candidate), timestamp.

### ProviderHealthLog
Rolling health signal per provider adapter (success rate, latency,
consecutive failures, circuit-breaker state) used for fallback routing. See
`PROVIDER_ARCHITECTURE.md`.

## Invariants

1. `DesignGenome`, `Evaluation`, `GenerationCandidate`, `FailureRecord`,
   `RepairAttempt`, `Experiment`, and `CommercialObservation` rows are
   **never updated in place** after creation, only inserted. Status fields
   on mutable aggregates (`Collection`, `CreativeFamily`,
   `DailyProductionPlan`) are the only sanctioned in-place updates.
2. Every `GenerationCandidate` that reaches `APPROVED` must have a
   traceable chain: `DailyProductionPlan → Collection → DesignGenome →
   Concept → GenerationCandidate → Evaluation(s) → [FailureRecord →
   RepairAttempt]* → Artwork`.
3. No `Artwork` exists without a human `Approval` action row referencing a
   specific `GenerationCandidate`.
4. No `CostEvent` exists without a provider call actually made (fake
   providers in test mode still emit `CostEvent`s using configured
   simulated pricing, clearly flagged `is_simulated=true`).
