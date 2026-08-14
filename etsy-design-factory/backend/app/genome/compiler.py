"""Compile a DesignGenome (+ collection context) into a prompt string.

Pure function: same genome + same variation_seed -> same prompt, always.
This is the ONLY place in the codebase allowed to construct prompt text.
Approval actions and repair must mutate the genome and recompile — never
touch the string directly.
"""
from __future__ import annotations

from app.genome.schema import DesignGenome


def compile_prompt(
    genome: DesignGenome,
    *,
    collection_thesis: str | None = None,
    variation_seed: int = 0,
) -> str:
    subj = genome.subject_dna
    style = genome.style_dna
    comp = genome.composition_dna
    palette = genome.palette_dna
    texture = genome.texture_dna
    medium = genome.medium_dna
    era = genome.era_dna
    mood = genome.mood_dna
    detail = genome.detail_dna
    printd = genome.print_dna

    parts: list[str] = []
    parts.append(
        f"{style.rendering_style.value} {medium.medium.value.replace('_', ' ')} artwork of "
        f"{subj.primary_subject}"
    )
    if subj.secondary_elements:
        parts.append("with " + ", ".join(subj.secondary_elements))
    parts.append(f"in the {style.art_movement} style")
    parts.append(
        f"{comp.layout_type.value.replace('_', ' ')} composition, "
        f"{comp.balance.value} balance, focal point on {comp.focal_point}, "
        f"negative space ratio approximately {comp.negative_space_ratio:.2f}"
    )
    parts.append(
        f"palette '{palette.palette_name}': primary {', '.join(palette.primary_colors)}, "
        f"accents {', '.join(palette.accent_colors) or 'none'}, "
        f"background {palette.background_color}, {palette.temperature.value} tones, "
        f"saturation {palette.saturation_level:.2f}, contrast {palette.contrast_level:.2f}"
    )
    parts.append(
        f"{texture.surface_texture.value.replace('_', ' ')} texture at intensity "
        f"{texture.texture_intensity:.2f}"
    )
    parts.append(f"era reference: {era.era_reference}")
    parts.append(
        f"mood: {mood.primary_mood}"
        + (f" with a hint of {mood.secondary_mood}" if mood.secondary_mood else "")
    )
    parts.append(
        f"{detail.detail_density.value} detail density, {detail.line_weight.value} line weight"
    )
    parts.append(
        f"{printd.orientation.value} orientation, print-ready, min long edge "
        f"{printd.recommended_min_long_edge_px}px, safe margins"
    )
    if collection_thesis:
        parts.append(f"consistent with collection thesis: {collection_thesis}")
    if variation_seed:
        parts.append(f"[variation seed {variation_seed}]")

    return ". ".join(parts) + "."
