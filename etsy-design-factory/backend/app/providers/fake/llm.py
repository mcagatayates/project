"""Deterministic fake LLMProvider — input-aware canned completions.

Used for Concept Gate (pass/reject reasoning) and any other cheap-LLM
check in test mode. Never calls a network.
"""
from __future__ import annotations

import time

from app.providers.base import LLMResult


class FakeLLMProvider:
    name = "fake_llm"

    def __init__(self, price_per_call_usd: float = 0.001):
        self.price_per_call_usd = price_per_call_usd

    async def complete(self, *, system: str, prompt: str, temperature: float = 0.2, max_tokens: int = 800) -> LLMResult:
        start = time.monotonic()
        text = f"[fake-llm] reviewed prompt ({len(prompt)} chars) under system '{system[:40]}': looks coherent."
        latency_ms = int((time.monotonic() - start) * 1000) + 1
        return LLMResult(
            text=text,
            cost_usd=self.price_per_call_usd,
            latency_ms=latency_ms,
            tokens_input=max(1, len(prompt) // 4),
            tokens_output=max(1, len(text) // 4),
            raw_metadata={"provider": self.name},
        )
