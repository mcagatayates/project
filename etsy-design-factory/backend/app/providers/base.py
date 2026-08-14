"""Provider interfaces. See docs/PROVIDER_ARCHITECTURE.md.

No module under app/pipeline or app/genome may import a vendor SDK
directly — only app/providers/<vendor>.py files may. Everything else asks
the ProviderRegistry for a *role* (see registry.py) and gets back one of
these Protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResult:
    text: str
    cost_usd: float
    latency_ms: int
    tokens_input: int = 0
    tokens_output: int = 0
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionRubric:
    dimensions: tuple[str, ...]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionScore:
    value: float
    confidence: float
    reasoning: str
    problems: list[str] = field(default_factory=list)


@dataclass
class VisionScoreResult:
    scores: dict[str, DimensionScore]
    cost_usd: float
    latency_ms: int
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenResult:
    image_bytes: bytes
    width_px: int
    height_px: int
    cost_usd: float
    latency_ms: int
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UpscaleResult:
    image_bytes: bytes
    width_px: int
    height_px: int
    cost_usd: float
    latency_ms: int


class LLMProvider(Protocol):
    name: str

    async def complete(
        self, *, system: str, prompt: str, temperature: float = 0.2, max_tokens: int = 800
    ) -> LLMResult: ...


class VisionProvider(Protocol):
    name: str

    async def score(self, *, image_bytes: bytes, rubric: VisionRubric) -> VisionScoreResult: ...


class ImageGenProvider(Protocol):
    name: str

    async def generate(
        self, *, prompt: str, width: int, height: int, params: dict[str, Any] | None = None
    ) -> ImageGenResult: ...


class UpscaleProvider(Protocol):
    name: str

    async def upscale(self, *, image_bytes: bytes, target_long_edge_px: int) -> UpscaleResult: ...


class StorageProvider(Protocol):
    name: str

    async def put(self, *, key: str, data: bytes, content_type: str = "image/png") -> str: ...

    async def get(self, *, key: str) -> bytes: ...

    def url_for(self, *, key: str) -> str: ...


class ProviderError(Exception):
    """Raised by adapters on a failed call; caught by the registry for
    retry/circuit-breaker/fallback handling."""


class RateLimitError(ProviderError):
    """Signals the caller should back off (maps to HTTP 429-style errors)."""
