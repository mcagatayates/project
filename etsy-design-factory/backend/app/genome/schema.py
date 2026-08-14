"""Pydantic models for DesignGenome. See docs/DESIGN_GENOME_SCHEMA.md.

Prompts are compiled FROM these models (app/genome/compiler.py); nothing
else may originate prompt text. Every enum here is the single canonical
vocabulary shared by the compiler, the mutation engine, and the similarity
engine.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class SubjectCategory(StrEnum):
    BOTANICAL = "botanical"
    ANIMAL = "animal"
    ABSTRACT = "abstract"
    LANDSCAPE = "landscape"
    GEOMETRIC = "geometric"
    TYPOGRAPHY = "typography"
    FIGURATIVE = "figurative"
    ARCHITECTURAL = "architectural"
    STILL_LIFE = "still_life"


class Specificity(StrEnum):
    GENERIC = "generic"
    SPECIFIC_SPECIES = "specific_species"
    NAMED_LANDMARK = "named_landmark"


class RenderingStyle(StrEnum):
    FLAT = "flat"
    PAINTERLY = "painterly"
    PHOTOREAL = "photoreal"
    LINEWORK = "linework"
    COLLAGE = "collage"
    VECTOR = "vector"


class LayoutType(StrEnum):
    CENTERED = "centered"
    RULE_OF_THIRDS = "rule_of_thirds"
    ASYMMETRIC = "asymmetric"
    REPEATING_PATTERN = "repeating_pattern"
    BORDER_FRAMED = "border_framed"
    FULL_BLEED = "full_bleed"


class Balance(StrEnum):
    SYMMETRIC = "symmetric"
    ASYMMETRIC = "asymmetric"
    RADIAL = "radial"


class Temperature(StrEnum):
    WARM = "warm"
    COOL = "cool"
    NEUTRAL = "neutral"


class SurfaceTexture(StrEnum):
    SMOOTH = "smooth"
    PAPER_GRAIN = "paper_grain"
    CANVAS = "canvas"
    GRAINY_NOISE = "grainy_noise"
    BRUSHSTROKE = "brushstroke"


class Medium(StrEnum):
    DIGITAL_PAINTING = "digital_painting"
    GOUACHE = "gouache"
    WATERCOLOR = "watercolor"
    INK = "ink"
    RISOGRAPH = "risograph"
    VECTOR = "vector"
    PHOTOGRAPHY = "photography"
    RENDER_3D = "render_3d"


class DetailDensity(StrEnum):
    MINIMAL = "minimal"
    MODERATE = "moderate"
    INTRICATE = "intricate"


class LineWeight(StrEnum):
    THIN = "thin"
    MEDIUM = "medium"
    BOLD = "bold"


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


class PriceTier(StrEnum):
    BUDGET = "budget"
    MID = "mid"
    PREMIUM = "premium"


class SubjectDNA(BaseModel):
    primary_subject: str
    secondary_elements: list[str] = Field(default_factory=list)
    subject_category: SubjectCategory
    specificity: Specificity = Specificity.GENERIC
    subject_tags: list[str] = Field(default_factory=list)


class StyleDNA(BaseModel):
    art_movement: str
    rendering_style: RenderingStyle
    influence_tags: list[str] = Field(default_factory=list)


class CompositionDNA(BaseModel):
    layout_type: LayoutType
    focal_point: str
    negative_space_ratio: float = Field(ge=0.0, le=1.0)
    balance: Balance
    cropping: str = "standard"


class PaletteDNA(BaseModel):
    palette_name: str
    primary_colors: list[str]
    accent_colors: list[str] = Field(default_factory=list)
    background_color: str
    saturation_level: float = Field(ge=0.0, le=1.0)
    contrast_level: float = Field(ge=0.0, le=1.0)
    temperature: Temperature


class TextureDNA(BaseModel):
    surface_texture: SurfaceTexture
    texture_intensity: float = Field(ge=0.0, le=1.0)


class MediumDNA(BaseModel):
    medium: Medium
    medium_authenticity_tags: list[str] = Field(default_factory=list)


class EraDNA(BaseModel):
    era_reference: str = "timeless"
    nostalgia_level: float = Field(default=0.0, ge=0.0, le=1.0)


class MoodDNA(BaseModel):
    primary_mood: str
    secondary_mood: str | None = None
    energy_level: float = Field(ge=0.0, le=1.0)


class DetailDNA(BaseModel):
    detail_density: DetailDensity
    line_weight: LineWeight


class PrintDNA(BaseModel):
    recommended_min_long_edge_px: int = 6000
    safe_margin_ratio: float = Field(default=0.05, ge=0.0, le=0.3)
    orientation: Orientation
    works_as_pattern: bool = False


class CommercialDNA(BaseModel):
    target_customer_segment: str
    price_tier: PriceTier = PriceTier.MID
    seasonal_relevance: list[str] = Field(default_factory=list)
    gift_occasion: list[str] = Field(default_factory=list)
    room_type_fit: list[str] = Field(default_factory=list)
    trend_alignment_score: float = Field(default=0.5, ge=0.0, le=1.0)


DNA_BLOCK_NAMES = (
    "subject_dna",
    "style_dna",
    "composition_dna",
    "palette_dna",
    "texture_dna",
    "medium_dna",
    "era_dna",
    "mood_dna",
    "detail_dna",
    "print_dna",
    "commercial_dna",
)


class GenomeCreatedBy(StrEnum):
    SYSTEM_DISCOVERY = "SYSTEM_DISCOVERY"
    SYSTEM_MUTATION = "SYSTEM_MUTATION"
    HUMAN_EDIT = "HUMAN_EDIT"


class DesignGenome(BaseModel):
    """The full creative DNA object. Mirrors app/db/models/genome.py
    exactly; the DB row is this model serialized block-by-block."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    design_lineage_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    version: int = 1
    parent_genome_id: uuid.UUID | None = None
    derived_from_version_id: uuid.UUID | None = None
    generation_number: int = 0
    collection_id: uuid.UUID | None = None
    created_by: GenomeCreatedBy = GenomeCreatedBy.SYSTEM_DISCOVERY

    subject_dna: SubjectDNA
    style_dna: StyleDNA
    composition_dna: CompositionDNA
    palette_dna: PaletteDNA
    texture_dna: TextureDNA
    medium_dna: MediumDNA
    era_dna: EraDNA = Field(default_factory=EraDNA)
    mood_dna: MoodDNA
    detail_dna: DetailDNA
    print_dna: PrintDNA
    commercial_dna: CommercialDNA

    mutation_map: dict | None = None

    def dna_blocks(self) -> dict[str, BaseModel]:
        return {name: getattr(self, name) for name in DNA_BLOCK_NAMES}

    def primary_and_background_hex(self) -> tuple[str, str]:
        primary = self.palette_dna.primary_colors[0] if self.palette_dna.primary_colors else "#808080"
        return primary, self.palette_dna.background_color
