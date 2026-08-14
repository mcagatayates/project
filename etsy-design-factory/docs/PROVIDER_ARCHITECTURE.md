# PROVIDER ARCHITECTURE

No domain module (`app/pipeline/*`, `app/genome/*`) may import a specific
vendor SDK. All external calls go through an interface in
`app/providers/base.py` and a concrete adapter registered in
`app/providers/registry.py`.

## Interfaces

```python
class LLMProvider(Protocol):
    async def complete(self, *, system: str, prompt: str, temperature: float,
                        max_tokens: int) -> LLMResult: ...

class VisionProvider(Protocol):
    async def score(self, *, image_bytes: bytes, rubric: VisionRubric) -> VisionScoreResult: ...

class ImageGenProvider(Protocol):
    async def generate(self, *, prompt: str, width: int, height: int,
                        params: dict) -> ImageGenResult: ...

class UpscaleProvider(Protocol):
    async def upscale(self, *, image_bytes: bytes, target_long_edge_px: int) -> UpscaleResult: ...

class StorageProvider(Protocol):
    async def put(self, *, key: str, data: bytes, content_type: str) -> str: ...
    async def get(self, *, key: str) -> bytes: ...
    def url_for(self, *, key: str) -> str: ...
```

Every `*Result` dataclass carries `cost_usd`, `latency_ms`, and
`raw_metadata` so the calling stage can write a `CostEvent` and
`ProviderHealthLog` without knowing provider-specific response shapes.

## Registry

`ProviderRegistry` holds named adapter instances per role
(`llm.cheap`, `llm.premium`, `image_gen.exploration`,
`image_gen.finalist`, `vision.qc`, `upscale.default`, `storage.default`).
Pipeline stages ask the registry for a *role*, not a vendor name — e.g.
Concept Gate always asks for `llm.cheap`; Print Factory finalist upscaling
asks for `upscale.default`. Swapping vendors is a config change
(`config/providers.yaml` + `.env`), never a code change in `app/pipeline`.

```yaml
# config/providers.yaml (example)
roles:
  llm.cheap: { adapter: openai_compatible, model: gpt-4o-mini }
  llm.premium: { adapter: anthropic, model: claude-sonnet-5 }
  image_gen.exploration: { adapter: stability, model: sdxl-turbo }
  image_gen.finalist: { adapter: midjourney_proxy, model: v6 }
  vision.qc: { adapter: anthropic_vision, model: claude-sonnet-5 }
  upscale.default: { adapter: topaz }
  storage.default: { adapter: s3 }
test_mode:
  # when APP_ENV=test or PROVIDER_MODE=fake, the registry substitutes the
  # `fake` adapter for every role regardless of the mapping above.
```

## Cheap exploration vs. premium finalist

Discovery/exploration generation attempts use `image_gen.exploration`
(cheap/fast model). Once a candidate survives QC + tournament + diversity
control and is `SELECTED`, an optional "finalist pass" can re-render or
upscale via `image_gen.finalist` / `upscale.default` before presenting for
approval — configurable per collection, defaulting off in Phase 1/2 to keep
cost predictable, and intended to be enabled per the funnel-economics
learning described in `SYSTEM_VISION.md`.

## Health monitoring, retry, rate limits, fallback

- **Health:** every call writes a `ProviderHealthLog` row. A rolling
  failure-rate window (config: `window_minutes`, `failure_threshold`) trips
  a per-adapter circuit breaker: `CLOSED → OPEN` (fail fast, do not call the
  vendor) `→ HALF_OPEN` (allow one probe call after a cooldown) `→ CLOSED`
  on success or back to `OPEN` on failure.
- **Retry:** adapter-level retry for transient errors (timeouts, 5xx) with
  exponential backoff + jitter, bounded attempts, distinct from the Celery
  task-level retry in `EVENTS.md` (adapter retry handles "flaky single
  call"; task retry handles "the whole task attempt failed, try again
  later").
- **Rate limits:** each adapter declares `max_concurrency` and
  `requests_per_minute`; enforced via a Redis token bucket keyed by
  `provider:{name}` so limits hold across all worker processes, not just
  within one.
- **Fallback:** a role can declare an ordered `fallback_chain`
  (e.g. `image_gen.exploration → [stability, replicate_sdxl]`). On circuit
  `OPEN` or exhausted retries, the registry tries the next adapter in the
  chain before failing the task. Fallback use is recorded on the
  `CostEvent`/`ProviderHealthLog` so cost/quality drift from a fallback
  vendor is visible, not silent.

## Fake providers (test mode)

`app/providers/fake/` implements every interface deterministically so the
full pipeline — including the 30-design acceptance simulation — runs with
**no network calls and no paid API usage**:

- `FakeImageGenProvider` renders a small synthetic PNG (via Pillow) encoding
  the genome's palette and composition as actual pixels (color blocks sized
  by `negative_space_ratio`, hued by `palette_dna`), plus a deterministic
  "quality seed" derived from a hash of the genome id and a per-test
  scenario knob — so some candidates are engineered to pass QC, some to
  fail repairably, some terminally, and some to be near-duplicates for the
  fatigue/diversity tests to catch. This makes the fake output *meaningful*
  input to the real similarity/QC logic instead of a blank stub.
- `FakeVisionProvider` derives the seven scores from real, cheap image
  statistics on the synthetic PNG (color histogram spread, edge density,
  size) plus the embedded quality seed — deterministic, not random, so
  tests are reproducible.
- `FakeLLMProvider` returns canned but input-aware structured completions
  (e.g. concept-gate reasoning references the actual subject/style tags it
  was given).
- `FakeStorageProvider` is the local-filesystem `StorageProvider` used in
  tests and available in dev/self-hosted deployments without S3.

All fake adapters still emit `CostEvent`s using a configured simulated
price table with `is_simulated=true`, so cost-tracking and budget logic are
exercised by the same tests without touching a real bill.

## Provider-independence rule (enforced)

A lint rule / CI check (`scripts/check_no_vendor_imports.py`) fails the
build if any file under `app/pipeline/` or `app/genome/` imports a
vendor SDK module directly. Only `app/providers/<vendor>.py` files may.
