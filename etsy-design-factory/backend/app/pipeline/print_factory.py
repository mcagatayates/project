"""Print Master / Ratio Exports: real pixel operations only. Never claims
DPI-metadata edits increase resolution -- if a ratio's crop comes out
below the genome's recommended minimum long edge, an UpscaleProvider is
actually invoked to produce more pixels; otherwise the export is a plain
crop of the master. Actual pixel dimensions are always recorded.
"""

from __future__ import annotations

import io

from PIL import Image
from sqlalchemy.orm import Session

from app.cost.ledger import record_cost
from app.db.models.artwork import Artwork, PrintExport
from app.genome.schema import DesignGenome
from app.providers.registry import ProviderRegistry

RATIO_ASPECTS: dict[str, float] = {
    "2:3": 2 / 3,
    "3:4": 3 / 4,
    "4:5": 4 / 5,
    "5:7": 5 / 7,
    "11:14": 11 / 14,
    "A": 1 / 1.4142,  # ISO 216 (A4, A3, ...)
}


def _center_crop_to_aspect(img: Image.Image, target_aspect: float) -> Image.Image:
    """target_aspect = width / height for a portrait-oriented crop; if the
    source is landscape, the inverse aspect is used so we never rotate the
    artwork -- only crop within its existing orientation."""
    w, h = img.size
    source_aspect = w / h
    portrait_source = source_aspect <= 1.0
    aspect = target_aspect if portrait_source else 1 / target_aspect

    current_aspect = w / h
    if current_aspect > aspect:
        new_w = int(h * aspect)
        x0 = (w - new_w) // 2
        box = (x0, 0, x0 + new_w, h)
    else:
        new_h = int(w / aspect)
        y0 = (h - new_h) // 2
        box = (0, y0, w, y0 + new_h)
    return img.crop(box)


async def export_ratio(
    session: Session,
    registry: ProviderRegistry,
    *,
    artwork: Artwork,
    genome: DesignGenome,
    ratio: str,
) -> PrintExport:
    if ratio not in RATIO_ASPECTS:
        raise ValueError(f"unsupported print ratio '{ratio}'")

    master_bytes = await registry.call("storage.default", "get", key=artwork.master_storage_key)
    img = Image.open(io.BytesIO(master_bytes)).convert("RGB")

    cropped = _center_crop_to_aspect(img, RATIO_ASPECTS[ratio])
    target_long_edge = genome.print_dna.recommended_min_long_edge_px

    width, height = cropped.size
    upscaled = False
    upscale_provider_name: str | None = None

    if max(width, height) < target_long_edge:
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        result = await registry.call(
            "upscale.default", "upscale", image_bytes=buf.getvalue(), target_long_edge_px=target_long_edge
        )
        final_bytes = result.image_bytes
        width, height = result.width_px, result.height_px
        upscaled = True
        upscale_provider_name = str(registry.get("upscale.default").name)
        record_cost(
            session,
            provider=upscale_provider_name,
            model="upscale",
            operation="print_export_upscale",
            processing_cost_usd=result.cost_usd,
            collection_id=artwork.collection_id,
        )
    else:
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        final_bytes = buf.getvalue()

    storage_key = f"prints/{artwork.id}/{ratio.replace(':', 'x')}.png"
    await registry.call("storage.default", "put", key=storage_key, data=final_bytes, content_type="image/png")

    export = PrintExport(
        artwork_id=artwork.id,
        ratio=ratio,
        target_long_edge_px=target_long_edge,
        actual_width_px=width,
        actual_height_px=height,
        storage_key=storage_key,
        upscaled=upscaled,
        upscale_provider=upscale_provider_name,
    )
    session.add(export)
    session.flush()
    return export


async def export_all_ratios(
    session: Session,
    registry: ProviderRegistry,
    *,
    artwork: Artwork,
    genome: DesignGenome,
    ratios: tuple[str, ...] = tuple(RATIO_ASPECTS),
) -> list[PrintExport]:
    return [await export_ratio(session, registry, artwork=artwork, genome=genome, ratio=r) for r in ratios]
