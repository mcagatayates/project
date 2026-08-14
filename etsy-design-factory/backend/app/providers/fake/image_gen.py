"""Deterministic fake ImageGenProvider.

Renders a small synthetic PNG whose pixels actually encode the genome's
composition/palette/texture, plus an injected "quality_seed" that controls
how many visual artifacts are introduced. This makes the fake output
meaningful input to the real Vision QC / similarity logic instead of an
opaque stub — tests exercise genuine accept/reject/repair/dedup behavior.

Expected `params` keys (all optional, sensible defaults applied):
  primary_color_hex: str        e.g. "#7C8B6F"
  background_color_hex: str     e.g. "#F3EFE6"
  negative_space_ratio: float   0..1
  texture_intensity: float      0..1
  quality_seed: float           0..1 (1.0 = clean/high quality, 0.0 = heavily flawed)
  variation_seed: int           distinguishes sibling candidates from the same concept
"""

from __future__ import annotations

import io
import random
import time

from PIL import Image, ImageDraw

from app.providers.base import ImageGenResult

CANVAS = 512


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (200, 200, 200)
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class FakeImageGenProvider:
    name = "fake_image_gen"

    def __init__(self, price_per_image_usd: float = 0.02):
        self.price_per_image_usd = price_per_image_usd

    async def generate(self, *, prompt: str, width: int, height: int, params: dict | None = None) -> ImageGenResult:
        params = params or {}
        start = time.monotonic()

        primary = _hex_to_rgb(params.get("primary_color_hex", "#7C8B6F"))
        background = _hex_to_rgb(params.get("background_color_hex", "#F3EFE6"))
        negative_space_ratio = float(params.get("negative_space_ratio", 0.5))
        texture_intensity = float(params.get("texture_intensity", 0.2))
        quality_seed = float(params.get("quality_seed", 0.8))
        variation_seed = int(params.get("variation_seed", 0))

        rng = random.Random(hash((prompt, variation_seed)) & 0xFFFFFFFF)

        img = Image.new("RGB", (CANVAS, CANVAS), background)
        draw = ImageDraw.Draw(img)

        subject_fraction = max(0.15, 1.0 - negative_space_ratio)
        subject_size = int(CANVAS * subject_fraction)
        offset = (CANVAS - subject_size) // 2
        jitter = int(6 * (1 - quality_seed))
        ox = offset + rng.randint(-jitter, jitter)
        oy = offset + rng.randint(-jitter, jitter)
        draw.ellipse([ox, oy, ox + subject_size, oy + subject_size], fill=primary)

        # texture: grain dots
        grain_count = int(texture_intensity * 400)
        for _ in range(grain_count):
            x, y = rng.randint(0, CANVAS - 1), rng.randint(0, CANVAS - 1)
            shade = rng.randint(-25, 25)
            c = tuple(max(0, min(255, v + shade)) for v in background)
            draw.point((x, y), fill=c)

        # quality artifacts: low quality_seed injects visible defects
        artifact_count = int(((1.0 - quality_seed) ** 1.6) * 2600)
        for _ in range(artifact_count):
            x, y = rng.randint(0, CANVAS - 1), rng.randint(0, CANVAS - 1)
            r = rng.randint(2, 6)
            stray = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=stray)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        latency_ms = int((time.monotonic() - start) * 1000) + 1
        return ImageGenResult(
            image_bytes=data,
            width_px=CANVAS,
            height_px=CANVAS,
            cost_usd=self.price_per_image_usd,
            latency_ms=latency_ms,
            raw_metadata={"provider": self.name, "quality_seed": quality_seed},
        )
