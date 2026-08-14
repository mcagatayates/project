"""Etsy Listing Package: structured product data assembled from the
DesignGenome + Artwork + its exports. Pure data -- no Etsy API call lives
here or anywhere in the creative pipeline (docs/ARCHITECTURE.md /
docs/DOMAIN_MODEL.md EtsyListingPackage: "Publishing to Etsy is a
separate, optional adapter call keyed off this package")."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork, EtsyListingPackage, Mockup, PrintExport
from app.db.models.collection import Collection
from app.genome.schema import DesignGenome

_MAX_TAGS = 13
_MAX_TAG_LEN = 20


def _title_concepts(genome: DesignGenome, collection: Collection) -> list[str]:
    subject = genome.subject_dna.primary_subject.title()
    style = genome.style_dna.art_movement.title()
    return [
        f"{subject} Wall Art Print | {style} {collection.medium.title()} Poster",
        f"{style} {subject} Print | {collection.name} Collection Wall Decor",
        f"{subject} Art Print | {genome.mood_dna.primary_mood.title()} {style} Home Decor",
    ]


def _description_data(genome: DesignGenome, collection: Collection) -> dict:
    return {
        "subject": genome.subject_dna.primary_subject,
        "style": genome.style_dna.art_movement,
        "mood": genome.mood_dna.primary_mood,
        "medium": collection.medium,
        "palette": genome.palette_dna.palette_name,
        "room_fit": genome.commercial_dna.room_type_fit,
        "gift_occasion": genome.commercial_dna.gift_occasion,
        "collection_thesis": collection.thesis,
        "care_note": "Digital print on premium archival paper. Frame not included.",
    }


def _keyword_candidates(genome: DesignGenome) -> list[str]:
    raw = [
        genome.subject_dna.primary_subject,
        genome.style_dna.art_movement,
        *genome.subject_dna.subject_tags,
        *genome.style_dna.influence_tags,
        genome.mood_dna.primary_mood,
        genome.palette_dna.palette_name,
        f"{genome.print_dna.orientation.value} wall art",
    ]
    seen: list[str] = []
    for kw in raw:
        kw = kw.strip().lower()
        if kw and kw not in seen:
            seen.append(kw)
    return seen


def _tags(keywords: list[str]) -> list[str]:
    tags = [kw.replace("_", " ")[:_MAX_TAG_LEN] for kw in keywords]
    return tags[:_MAX_TAGS]


def build_etsy_package(
    session: Session,
    *,
    artwork: Artwork,
    genome: DesignGenome,
    collection: Collection,
    print_exports: list[PrintExport],
    mockups: list[Mockup],
) -> EtsyListingPackage:
    keywords = _keyword_candidates(genome)
    package = EtsyListingPackage(
        artwork_id=artwork.id,
        title_concepts=_title_concepts(genome, collection),
        description_data=_description_data(genome, collection),
        keyword_candidates=keywords,
        tags=_tags(keywords),
        style=genome.style_dna.art_movement,
        subject=genome.subject_dna.primary_subject,
        palette=genome.palette_dna.palette_name,
        orientation=genome.print_dna.orientation.value,
        collection_id=collection.id,
        internal_sku=artwork.sku,
        print_export_ids=[str(pe.id) for pe in print_exports],
        mockup_ids=[str(m.id) for m in mockups],
    )
    session.add(package)
    session.flush()
    return package
