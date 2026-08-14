# DESIGN GENOME SCHEMA

`DesignGenome` is the single source of creative truth. Prompts are always
*compiled from* a genome (`app/genome/compiler.py`); no pipeline stage may
construct or edit a prompt string directly. This document is the contract
between the Pydantic models in `backend/app/genome/schema.py` and every
consumer (concept generation, mutation, similarity engine, approval
actions).

## Top-level object

```jsonc
{
  "id": "uuid",
  "design_lineage_id": "uuid",     // stable across in-place edits of the "same" design
  "version": 1,                     // increments on in-place edit (approval action)
  "parent_genome_id": null,         // set when this genome is an EVOLUTIONARY offspring of another
  "derived_from_version_id": null,  // set when this is a new version of the SAME lineage (edit)
  "generation_number": 0,           // evolutionary distance from a root/novel genome
  "collection_id": "uuid | null",
  "created_by": "SYSTEM_DISCOVERY | SYSTEM_MUTATION | HUMAN_EDIT",

  "subject_dna": { ... },
  "style_dna": { ... },
  "composition_dna": { ... },
  "palette_dna": { ... },
  "texture_dna": { ... },
  "medium_dna": { ... },
  "era_dna": { ... },
  "mood_dna": { ... },
  "detail_dna": { ... },
  "print_dna": { ... },
  "commercial_dna": { ... },

  "mutation_map": null // see "Mutation map" below
}
```

`parent_genome_id` and `derived_from_version_id` are mutually exclusive per
row: a genome is either a fresh evolutionary child of a parent, or a new
version of its own lineage from an edit — never both in one row.

## DNA sub-objects

### SubjectDNA
- `primary_subject: str` — e.g. "monstera leaf", "abstract arches"
- `secondary_elements: list[str]`
- `subject_category: enum` — `botanical | animal | abstract | landscape |
  geometric | typography | figurative | architectural | still_life`
- `specificity: enum` — `generic | specific_species | named_landmark`
- `subject_tags: list[str]`

### StyleDNA
- `art_movement: str` — e.g. "art-deco", "mid-century-modern", "boho",
  "japandi", "cottagecore", "bauhaus"
- `rendering_style: enum` — `flat | painterly | photoreal | linework |
  collage | vector`
- `influence_tags: list[str]`

### CompositionDNA
- `layout_type: enum` — `centered | rule_of_thirds | asymmetric |
  repeating_pattern | border_framed | full_bleed`
- `focal_point: str`
- `negative_space_ratio: float [0,1]`
- `balance: enum` — `symmetric | asymmetric | radial`
- `cropping: str`

### PaletteDNA
- `palette_name: str`
- `primary_colors: list[str]` (hex)
- `accent_colors: list[str]` (hex)
- `background_color: str` (hex)
- `saturation_level: float [0,1]`
- `contrast_level: float [0,1]`
- `temperature: enum` — `warm | cool | neutral`

### TextureDNA
- `surface_texture: enum` — `smooth | paper_grain | canvas | grainy_noise |
  brushstroke`
- `texture_intensity: float [0,1]`

### MediumDNA
- `medium: enum` — `digital_painting | gouache | watercolor | ink |
  risograph | vector | photography | render_3d`
- `medium_authenticity_tags: list[str]`

### EraDNA
- `era_reference: str` — e.g. "1960s", "victorian", "futuristic", "timeless"
- `nostalgia_level: float [0,1]`

### MoodDNA
- `primary_mood: str`
- `secondary_mood: str | null`
- `energy_level: float [0,1]` (calm → energetic)

### DetailDNA
- `detail_density: enum` — `minimal | moderate | intricate`
- `line_weight: enum` — `thin | medium | bold`

### PrintDNA
- `recommended_min_long_edge_px: int` (production default: 6000)
- `safe_margin_ratio: float [0,1]`
- `orientation: enum` — `portrait | landscape | square`
- `works_as_pattern: bool`

### CommercialDNA
- `target_customer_segment: str`
- `price_tier: enum` — `budget | mid | premium`
- `seasonal_relevance: list[str]`
- `gift_occasion: list[str]`
- `room_type_fit: list[str]`
- `trend_alignment_score: float [0,1]`

All enums are defined once in `app/genome/schema.py` and imported by the
compiler, the mutation engine, and the similarity engine — no stage may
maintain its own copy of these value sets.

## Prompt compilation

`app/genome/compiler.py:compile_prompt(genome, collection, mode) -> str`
deterministically renders a genome into a natural-language prompt template
using every DNA block. The same genome always compiles to the same prompt
(pure function) except for a `variation_seed` explicitly passed in for
distinct candidates within one concept. The compiled prompt is stored
verbatim on `generation_jobs.compiled_prompt` for audit — it is a derived
artifact, not user-editable, not the thing mutation operates on.

## Mutation map

When a genome is produced by controlled mutation from a parent, `parent
_genome_id` is set and `mutation_map` records, per DNA block, whether it
was `kept` or `mutated` and the mutation probability applied:

```jsonc
"mutation_map": {
  "style_dna": {"action": "kept"},
  "texture_dna": {"action": "kept"},
  "era_dna": {"action": "kept"},
  "composition_dna": {"action": "mutated", "probability": 0.7},
  "subject_dna": {"action": "mutated", "probability": 0.4},
  "palette_dna": {"action": "mutated", "probability": 0.2}
}
```

`app/genome/mutation.py:mutate(parent_genome, mutation_spec) -> DesignGenome`
implements this: for each DNA block in `mutation_spec`, roll against its
probability; if triggered, replace the block using constrained randomness
within enum/range domains (never fully random — mutation stays inside
collection boundaries and existing enum vocabularies unless discovery mode
explicitly widens the domain).

## Approval-action → genome mutation mapping

Human approval actions (`MORE_ORIGINAL`, `CLOSER_TO_COLLECTION`,
`CHANGE_COMPOSITION`, `CHANGE_PALETTE`, `MORE_TEXTURE`, `LESS_TEXTURE`,
`MORE_MINIMAL`, `MORE_DETAILED`, `CREATE_VARIATIONS`) are implemented in
`app/pipeline/approval.py` as **structured genome transforms**, e.g.:

- `CHANGE_PALETTE` → forces `palette_dna` mutation at probability 1.0,
  samples a new palette outside the current one but inside collection
  `palette_boundaries`.
- `MORE_TEXTURE` → `texture_dna.texture_intensity = min(1.0, x + 0.25)`.
- `MORE_MINIMAL` → `detail_dna.detail_density = "minimal"`,
  `composition_dna.negative_space_ratio = max(current, 0.6)`.
- `MORE_ORIGINAL` → increases mutation probability across `subject_dna`
  and `composition_dna` and records the resulting genome as
  `created_by = HUMAN_EDIT`.

Every action produces a **new `DesignGenome` version** (never a prompt
string edit) and re-enters the pipeline at Concept Generation. This is the
mechanism, referenced in `SYSTEM_VISION.md`, that guarantees approval
feedback is structured, not string concatenation.

## Example (abbreviated)

```json
{
  "id": "3b1e...",
  "design_lineage_id": "9a02...",
  "version": 1,
  "parent_genome_id": null,
  "generation_number": 0,
  "created_by": "SYSTEM_DISCOVERY",
  "subject_dna": {"primary_subject": "monstera leaf study", "subject_category": "botanical", "specificity": "specific_species", "secondary_elements": ["shadow"], "subject_tags": ["leaf", "tropical"]},
  "style_dna": {"art_movement": "japandi", "rendering_style": "flat", "influence_tags": ["minimal-botanical"]},
  "composition_dna": {"layout_type": "centered", "focal_point": "single leaf", "negative_space_ratio": 0.55, "balance": "asymmetric", "cropping": "full-bleed edge"},
  "palette_dna": {"palette_name": "sage-clay", "primary_colors": ["#7C8B6F"], "accent_colors": ["#C77B4D"], "background_color": "#F3EFE6", "saturation_level": 0.3, "contrast_level": 0.4, "temperature": "warm"},
  "texture_dna": {"surface_texture": "paper_grain", "texture_intensity": 0.2},
  "medium_dna": {"medium": "gouache", "medium_authenticity_tags": ["visible-brush"]},
  "era_dna": {"era_reference": "timeless", "nostalgia_level": 0.1},
  "mood_dna": {"primary_mood": "calm", "secondary_mood": "grounded", "energy_level": 0.2},
  "detail_dna": {"detail_density": "moderate", "line_weight": "thin"},
  "print_dna": {"recommended_min_long_edge_px": 6000, "safe_margin_ratio": 0.05, "orientation": "portrait", "works_as_pattern": false},
  "commercial_dna": {"target_customer_segment": "modern-boho-renters", "price_tier": "mid", "seasonal_relevance": ["spring"], "gift_occasion": ["housewarming"], "room_type_fit": ["living-room", "bedroom"], "trend_alignment_score": 0.6}
}
```
