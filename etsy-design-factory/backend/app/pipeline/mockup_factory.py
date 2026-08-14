"""Mockup Factory: product presentation assets generated separately from
the master artwork. Never contaminates the master with frames/rooms/walls/
furniture/shadows -- compositing happens on a fresh canvas, written to its
own storage key (see docs/DOMAIN_MODEL.md Mockup entity)."""

from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

import yaml
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork, Mockup
from app.providers.registry import ProviderRegistry

DEFAULT_TEMPLATES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "mockup_templates.yaml"


@lru_cache
def get_mockup_templates(path: str | None = None) -> list[dict]:
    p = Path(path) if path else DEFAULT_TEMPLATES_PATH
    return yaml.safe_load(p.read_text())["templates"]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _render_mockup(master_bytes: bytes, template: dict) -> bytes:
    canvas_w, canvas_h = template["canvas_size"]
    canvas = Image.new("RGB", (canvas_w, canvas_h), _hex_to_rgb(template["wall_color"]))
    draw = ImageDraw.Draw(canvas)

    x0f, y0f, x1f, y1f = template["artwork_area"]
    x0, y0, x1, y1 = int(x0f * canvas_w), int(y0f * canvas_h), int(x1f * canvas_w), int(y1f * canvas_h)
    area_w, area_h = x1 - x0, y1 - y0

    artwork = Image.open(io.BytesIO(master_bytes)).convert("RGB")
    aw, ah = artwork.size
    scale = min(area_w / aw, area_h / ah)
    new_size = (max(1, int(aw * scale)), max(1, int(ah * scale)))
    artwork = artwork.resize(new_size, Image.Resampling.LANCZOS)

    paste_x = x0 + (area_w - new_size[0]) // 2
    paste_y = y0 + (area_h - new_size[1]) // 2

    frame_color = template.get("frame_color")
    frame_ratio = template.get("frame_width_ratio", 0)
    if frame_color and frame_ratio:
        frame_w = max(1, int(min(new_size) * frame_ratio))
        draw.rectangle(
            [paste_x - frame_w, paste_y - frame_w, paste_x + new_size[0] + frame_w, paste_y + new_size[1] + frame_w],
            outline=_hex_to_rgb(frame_color),
            width=frame_w,
        )

    canvas.paste(artwork, (paste_x, paste_y))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


async def generate_mockup(
    session: Session,
    registry: ProviderRegistry,
    *,
    artwork: Artwork,
    template_id: str,
    templates_path: str | None = None,
) -> Mockup:
    templates = {t["id"]: t for t in get_mockup_templates(templates_path)}
    if template_id not in templates:
        raise ValueError(f"unknown mockup template '{template_id}'")

    master_bytes = await registry.call("storage.default", "get", key=artwork.master_storage_key)
    rendered = _render_mockup(master_bytes, templates[template_id])

    storage_key = f"mockups/{artwork.id}/{template_id}.png"
    await registry.call("storage.default", "put", key=storage_key, data=rendered, content_type="image/png")

    mockup = Mockup(artwork_id=artwork.id, template_id=template_id, storage_key=storage_key)
    session.add(mockup)
    session.flush()
    return mockup


async def generate_all_mockups(
    session: Session, registry: ProviderRegistry, *, artwork: Artwork, template_ids: list[str] | None = None
) -> list[Mockup]:
    ids = template_ids or [t["id"] for t in get_mockup_templates()]
    return [await generate_mockup(session, registry, artwork=artwork, template_id=t) for t in ids]
