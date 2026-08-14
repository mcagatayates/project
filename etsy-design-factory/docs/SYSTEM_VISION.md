# SYSTEM VISION

## What this is

The Design Factory is an autonomous commercial artwork R&D and production
operating system for an Etsy wall-art business. It is not an image generator
with a nice UI. It is a decision-making system that happens to call image
generators as one of its tools.

## What this is not

- Not a prompt-to-image playground.
- Not "generate N images and let a human pick." Selection is a first-class
  engineered stage with its own quality bar, not an afterthought.
- Not optimized for generation volume. Volume is a cost, not a goal.

## Production requirement

**30 approved, commercially testable, print-ready, unique designs per day**
(~900/month), produced autonomously, at a cost and quality profile that make
the business viable.

## Optimization target

```
maximize   QUALITY × ORIGINALITY × COMMERCIAL_POTENTIAL × THROUGHPUT
           ────────────────────────────────────────────────────────
                                  COST
```

Every architectural decision in this system is evaluated against this
ratio, not against "can we generate more images." A design that is
beautiful but a near-duplicate of last month's bestseller scores zero on
originality and must be rejected regardless of aesthetic score. A funnel
that produces 30 designs/day at 3x the sustainable cost-per-approved-design
is a failure even if the designs are good.

## Guiding principles

1. **Discovery before generation.** The system decides *what* is worth
   making (Daily Production Controller, Collection Planner, Opportunity
   Engine) before any pixels are produced.
2. **Structured creative DNA over prompt strings.** Every design is defined
   by a `DesignGenome`. Prompts are a compiled artifact, never the source of
   truth. This is what makes mutation, genealogy, similarity detection and
   learning possible.
3. **Selection is engineered, not incidental.** Multi-dimensional QC,
   tournament selection, diversity control and fatigue protection exist
   because generation is cheap and inventory-worthy designs are not.
4. **Experimentation is structured and remembered.** Discovery Mode and
   Production Mode are distinct regimes with an explicit graduation
   criterion. Nothing is generated without checking what was already tried.
5. **Learning closes the loop.** Commercial performance, when available,
   feeds back into genome-level and creative-family-level knowledge. The
   system never fabricates performance data it does not have.
6. **Providers are interchangeable.** No core domain logic may depend on a
   specific LLM, image model, or vision model vendor.
7. **Throughput is a scheduling and infrastructure problem, not a prompt
   problem.** 30 designs/day requires async workers, queues, budgets and
   concurrency control — not a bigger for-loop.
8. **Everything is traceable.** Every design, score, rejection, repair,
   mutation and dollar spent is attributable to a cause and retrievable
   later. Nothing is overwritten; history is append-only.

## Non-negotiables

- PostgreSQL is the single source of truth. No spreadsheets as a database.
- Long-running work never executes inside an HTTP request.
- Budgets (daily/monthly/per-design) are enforced by the Production
  Controller, not treated as a dashboard number to look at after the fact.
- The creative pipeline does not depend on Etsy. Etsy publishing is an
  isolated, optional integration.
- The system must be provably testable end-to-end (30-design simulation)
  without spending money on paid image APIs.

## Definition of done (acceptance test, summarized)

Given a daily target of 30, the system autonomously: builds a
`DailyProductionPlan` → creates/updates collections → generates
`DesignGenome`s and concepts → runs generation and vision QC
asynchronously → rejects, repairs, or accepts candidates → deduplicates
against history → ranks survivors → presents ≥30 qualified candidates for
human approval → on approval produces print masters, ratio exports,
mockups and an Etsy package → records every operation and cost → survives
injected worker/API failures without corrupting state. This is implemented
as an automated test suite using fake providers (see
`PROVIDER_ARCHITECTURE.md`), runnable in CI with no paid API calls.

See `ROADMAP.md` for what is implemented today versus deferred, and
`ARCHITECTURE.md` / `DOMAIN_MODEL.md` / `DATABASE.md` /
`DESIGN_GENOME_SCHEMA.md` / `AGENT_CONTRACTS.md` / `EVENTS.md` /
`PROVIDER_ARCHITECTURE.md` for the details this document intentionally
omits.
