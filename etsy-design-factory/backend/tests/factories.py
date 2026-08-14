"""Test-only builders for a valid, minimal DesignGenome and friends."""
from __future__ import annotations

from app.genome.schema import (
    Balance,
    CommercialDNA,
    CompositionDNA,
    DesignGenome,
    DetailDensity,
    DetailDNA,
    EraDNA,
    LayoutType,
    LineWeight,
    Medium,
    MediumDNA,
    MoodDNA,
    Orientation,
    PaletteDNA,
    PriceTier,
    PrintDNA,
    RenderingStyle,
    SubjectCategory,
    SubjectDNA,
    SurfaceTexture,
    StyleDNA,
    Temperature,
    TextureDNA,
)


def make_genome(**overrides) -> DesignGenome:
    base = dict(
        subject_dna=SubjectDNA(
            primary_subject="monstera leaf study",
            subject_category=SubjectCategory.BOTANICAL,
            secondary_elements=["shadow"],
            subject_tags=["leaf", "tropical"],
        ),
        style_dna=StyleDNA(art_movement="japandi", rendering_style=RenderingStyle.FLAT),
        composition_dna=CompositionDNA(
            layout_type=LayoutType.CENTERED,
            focal_point="single leaf",
            negative_space_ratio=0.55,
            balance=Balance.ASYMMETRIC,
        ),
        palette_dna=PaletteDNA(
            palette_name="sage-clay",
            primary_colors=["#7C8B6F"],
            accent_colors=["#C77B4D"],
            background_color="#F3EFE6",
            saturation_level=0.3,
            contrast_level=0.4,
            temperature=Temperature.WARM,
        ),
        texture_dna=TextureDNA(surface_texture=SurfaceTexture.PAPER_GRAIN, texture_intensity=0.2),
        medium_dna=MediumDNA(medium=Medium.GOUACHE),
        era_dna=EraDNA(era_reference="timeless", nostalgia_level=0.1),
        mood_dna=MoodDNA(primary_mood="calm", secondary_mood="grounded", energy_level=0.2),
        detail_dna=DetailDNA(detail_density=DetailDensity.MODERATE, line_weight=LineWeight.THIN),
        print_dna=PrintDNA(orientation=Orientation.PORTRAIT),
        commercial_dna=CommercialDNA(
            target_customer_segment="modern-boho-renters",
            price_tier=PriceTier.MID,
            seasonal_relevance=["spring"],
        ),
    )
    base.update(overrides)
    return DesignGenome(**base)
