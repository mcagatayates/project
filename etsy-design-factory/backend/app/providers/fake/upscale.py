"""Deterministic fake UpscaleProvider — performs a REAL pixel resize (not a
DPI-metadata trick) so print_factory's "never claim DPI edits increase
resolution" invariant is exercised honestly even in test mode."""

from __future__ import annotations

import io
import time

from PIL import Image

from app.providers.base import UpscaleResult


class FakeUpscaleProvider:
    name = "fake_upscale"

    def __init__(self, price_per_image_usd: float = 0.03):
        self.price_per_image_usd = price_per_image_usd

    async def upscale(self, *, image_bytes: bytes, target_long_edge_px: int) -> UpscaleResult:
        start = time.monotonic()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        scale = target_long_edge_px / max(w, h)
        new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        data = buf.getvalue()
        latency_ms = int((time.monotonic() - start) * 1000) + 1
        return UpscaleResult(
            image_bytes=data,
            width_px=new_size[0],
            height_px=new_size[1],
            cost_usd=self.price_per_image_usd,
            latency_ms=latency_ms,
        )
