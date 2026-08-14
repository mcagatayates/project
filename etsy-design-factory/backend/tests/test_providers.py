import asyncio

import pytest

from app.providers.base import ImageGenResult, ProviderError, VisionRubric
from app.providers.circuit_breaker import CircuitBreaker
from app.providers.fake.image_gen import FakeImageGenProvider
from app.providers.fake.vision import FakeVisionProvider
from app.providers.registry import AdapterSpec, ProviderRegistry


def test_fake_image_gen_produces_valid_png_of_requested_content():
    provider = FakeImageGenProvider()
    result = asyncio.run(
        provider.generate(
            prompt="test prompt",
            width=512,
            height=512,
            params={"primary_color_hex": "#7C8B6F", "background_color_hex": "#F3EFE6", "quality_seed": 0.9},
        )
    )
    assert isinstance(result, ImageGenResult)
    assert result.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.cost_usd > 0


def test_fake_vision_scores_low_quality_seed_lower_on_technical_quality():
    gen = FakeImageGenProvider()
    vis = FakeVisionProvider()

    good = asyncio.run(gen.generate(prompt="p", width=512, height=512, params={
        "primary_color_hex": "#7C8B6F", "background_color_hex": "#F3EFE6", "quality_seed": 0.95, "variation_seed": 1,
    }))
    bad = asyncio.run(gen.generate(prompt="p", width=512, height=512, params={
        "primary_color_hex": "#7C8B6F", "background_color_hex": "#F3EFE6", "quality_seed": 0.05, "variation_seed": 1,
    }))

    rubric = VisionRubric(dimensions=("technical_quality",), context={
        "expected_colors_rgb": [(124, 139, 111), (243, 239, 230)],
    })
    good_score = asyncio.run(vis.score(image_bytes=good.image_bytes, rubric=rubric))
    bad_score = asyncio.run(vis.score(image_bytes=bad.image_bytes, rubric=rubric))

    assert good_score.scores["technical_quality"].value > bad_score.scores["technical_quality"].value
    assert good_score.scores["technical_quality"].value - bad_score.scores["technical_quality"].value > 0.15


class _FlakyThenGoodAdapter:
    name = "flaky"

    def __init__(self):
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("simulated transient failure")
        return "ok"


class _AlwaysFailsAdapter:
    name = "always_fails"

    async def complete(self, **kwargs):
        raise RuntimeError("simulated permanent failure")


def test_registry_retries_then_succeeds():
    adapter = _FlakyThenGoodAdapter()
    registry = ProviderRegistry()
    registry.register_role("llm.cheap", primary=AdapterSpec(name="flaky", instance=adapter, max_retries=5, backoff_base_s=0.001, backoff_max_s=0.01, rate_per_minute=6000))

    result = asyncio.run(registry.call("llm.cheap", "complete", system="s", prompt="p"))
    assert result == "ok"
    assert adapter.calls == 3


def test_registry_falls_back_to_secondary_adapter():
    primary = _AlwaysFailsAdapter()
    secondary = _FlakyThenGoodAdapter()
    registry = ProviderRegistry()
    registry.register_role(
        "llm.cheap",
        primary=AdapterSpec(name="always_fails", instance=primary, max_retries=2, backoff_base_s=0.001, backoff_max_s=0.01, rate_per_minute=6000),
        fallbacks=[AdapterSpec(name="flaky", instance=secondary, max_retries=5, backoff_base_s=0.001, backoff_max_s=0.01, rate_per_minute=6000)],
    )

    result = asyncio.run(registry.call("llm.cheap", "complete", system="s", prompt="p"))
    assert result == "ok"


def test_registry_raises_when_all_adapters_exhausted():
    registry = ProviderRegistry()
    registry.register_role(
        "llm.cheap",
        primary=AdapterSpec(name="always_fails", instance=_AlwaysFailsAdapter(), max_retries=2, backoff_base_s=0.001, backoff_max_s=0.01, rate_per_minute=6000),
    )
    with pytest.raises(ProviderError):
        asyncio.run(registry.call("llm.cheap", "complete", system="s", prompt="p"))


def test_circuit_breaker_opens_after_repeated_failures():
    cb = CircuitBreaker(failure_threshold=0.5, window_size=8, cooldown_seconds=1000)
    for _ in range(8):
        cb.record(success=False)
    assert cb.state == "OPEN"
    assert cb.allow_request() is False
