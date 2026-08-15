"""Getvela CSV export: turns approved Artwork + EtsyListingPackage rows
into a CSV matching the user's real Getvela "Import new listings"
template (Vela's own bulk-import format mirrors Etsy's own listing CSV
columns exactly -- see the column list below).

Physical print-on-demand, one Etsy listing per Artwork with a single
"Size" variation covering the print ratios app/pipeline/print_factory.py
actually exported for it (never invents a size nothing was cropped for).
Shop/account-level fields (category, shipping profile, return policy,
production partner) come from config/getvela_shop_defaults.yaml because
they depend on the seller's real Etsy shop configuration, not on
anything the creative pipeline knows -- see that file's "EDIT ME" notes.
Pricing comes from config/getvela_pricing.yaml, keyed by collection name.

This never calls the Etsy API and never touches Getvela itself -- it only
produces a CSV file for the human to upload through Getvela's own
"Import" button, matching the existing workflow: CSV in, listings land in
Getvela's archive, the human reviews and activates them day by day. See
app/memory/getvela_export_memory.py for how re-running this never
re-exports an artwork that's already been handed to Getvela once.
"""

from __future__ import annotations

import csv
import io
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.artwork import Artwork, EtsyListingPackage, Mockup, PrintExport
from app.db.models.collection import Collection
from app.pipeline.print_factory import RATIO_ASPECTS

DEFAULT_SHOP_DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "getvela_shop_defaults.yaml"
DEFAULT_PRICING_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "getvela_pricing.yaml"

# Exact header row from the user's real Getvela "Import new listings"
# template -- do not reorder or rename without confirming against a fresh
# export from Getvela, since a wrong header breaks the real import.
CSV_HEADERS = [
    "Title",
    "Description",
    "Category",
    "Who made it?",
    "What is it?",
    "When was it made?",
    "Renewal options",
    "Product type",
    "Tags",
    "Materials",
    "Production partners",
    "Section",
    "Price",
    "Quantity",
    "SKU",
    "Variation 1",
    "V1 Option",
    "Variation 2",
    "V2 Option",
    "Var Price",
    "Var Quantity",
    "Var SKU",
    "Var Visibility",
    "Var Photo",
    "Shipping profile",
    "Weight",
    "Length",
    "Width",
    "Height",
    "Return policy",
    "Photo 1",
    "Photo 2",
    "Photo 3",
    "Photo 4",
    "Photo 5",
    "Photo 6",
    "Photo 7",
    "Photo 8",
    "Photo 9",
    "Photo 10",
    "Video 1",
    "Digital file 1",
    "Digital file 2",
    "Digital file 3",
    "Digital file 4",
    "Digital file 5",
]

_MAX_PHOTOS = 10


@lru_cache
def _load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def get_shop_defaults(path: str | None = None) -> dict:
    return _load_yaml(path or str(DEFAULT_SHOP_DEFAULTS_PATH))


def get_pricing_policy(path: str | None = None) -> dict:
    return _load_yaml(path or str(DEFAULT_PRICING_PATH))


def _base_price(collection: Collection, pricing: dict) -> float:
    overrides = pricing.get("collection_base_price_usd") or {}
    return float(overrides.get(collection.name, pricing["default_base_price_usd"]))


def _variation_price(base_price: float, ratio: str, pricing: dict) -> float:
    multiplier = (pricing.get("size_price_multiplier") or {}).get(ratio, 1.0)
    return round(base_price * multiplier, 2)


def _final_title(package: EtsyListingPackage) -> str:
    # The first concept is the deterministic choice (see
    # app/pipeline/etsy_package.py:_title_concepts for how these are
    # built); a human reviews/edits inside Getvela before activating.
    if not package.title_concepts:
        raise ValueError(f"EtsyListingPackage {package.id} has no title_concepts")
    return str(package.title_concepts[0])[:140]


def _final_description(package: EtsyListingPackage) -> str:
    d = package.description_data
    room_fit = ", ".join(str(r).replace("_", " ") for r in (d.get("room_fit") or []))
    gift_occasion = ", ".join(str(g).replace("_", " ") for g in (d.get("gift_occasion") or []))
    lines = [
        f"{str(d['subject']).capitalize()} wall art print -- {d['style']} style, "
        f"{d['mood']} mood, {d['palette']} palette.",
        str(d.get("collection_thesis") or ""),
        f"Printed as {d['medium']} on premium archival paper. Frame not included.",
        f"Fits beautifully in a {room_fit}." if room_fit else "",
        f"A thoughtful {gift_occasion} gift." if gift_occasion else "",
    ]
    return "\n".join(line for line in lines if line)


def _photo_paths(artwork: Artwork, mockups: list[Mockup], print_exports: list[PrintExport]) -> list[str]:
    # Buyers see styled mockups first, then a flat shot of each printed
    # ratio actually exported -- never a size nothing was cropped for.
    paths = [f"/api/mockups/{m.id}/image" for m in mockups]
    paths += [f"/api/print-exports/{pe.id}/image" for pe in print_exports]
    return paths[:_MAX_PHOTOS]


def _fmt(value: object) -> str:
    return "" if value is None else str(value)


def build_listing_rows(
    *,
    artwork: Artwork,
    package: EtsyListingPackage,
    collection: Collection,
    print_exports: list[PrintExport],
    mockups: list[Mockup],
    public_base_url: str,
    shop_defaults: dict | None = None,
    pricing: dict | None = None,
) -> list[dict[str, str]]:
    """One or more CSV rows for a single Etsy listing: the first row
    carries every listing-level field plus the first Size variation; any
    additional print ratios become continuation rows (blank Title etc.),
    matching Etsy/Getvela's own multi-row variation CSV convention."""
    shop = shop_defaults if shop_defaults is not None else get_shop_defaults()
    price_policy = pricing if pricing is not None else get_pricing_policy()

    ratios = [pe.ratio for pe in print_exports if pe.ratio in RATIO_ASPECTS]
    if not ratios:
        raise ValueError(f"artwork {artwork.id} has no print exports for a known ratio")

    size_labels = shop.get("size_labels") or {}
    variation_name = shop.get("variation_name", "Size")
    base_price = _base_price(collection, price_policy)
    quantity = shop.get("quantity_per_variation", 999)

    photo_urls = [f"{public_base_url.rstrip('/')}{p}" for p in _photo_paths(artwork, mockups, print_exports)]

    title = _final_title(package)
    description = _final_description(package)
    tags = ",".join(package.tags)
    materials = ", ".join(shop.get("materials") or [])

    rows: list[dict[str, str]] = []
    for i, ratio in enumerate(ratios):
        variation_price = _variation_price(base_price, ratio, price_policy)
        row = {h: "" for h in CSV_HEADERS}
        row["Variation 1"] = variation_name
        row["V1 Option"] = size_labels.get(ratio, ratio)
        row["Var Price"] = f"{variation_price:.2f}"
        row["Var Quantity"] = str(quantity)
        row["Var SKU"] = f"{artwork.sku}-{ratio.replace(':', 'x')}"
        row["Var Visibility"] = "visible"

        if i == 0:
            lowest_price = min(_variation_price(base_price, r, price_policy) for r in ratios)
            row.update(
                {
                    "Title": title,
                    "Description": description,
                    "Category": shop.get("category", ""),
                    "Who made it?": shop.get("who_made_it", ""),
                    "What is it?": shop.get("what_is_it", ""),
                    "When was it made?": shop.get("when_was_it_made", ""),
                    "Renewal options": shop.get("renewal_options", ""),
                    "Product type": shop.get("product_type", "Physical"),
                    "Tags": tags,
                    "Materials": materials,
                    "Production partners": shop.get("production_partners", ""),
                    "Section": collection.name,
                    "Price": f"{lowest_price:.2f}",
                    "Quantity": str(quantity),
                    "SKU": artwork.sku,
                    "Shipping profile": shop.get("shipping_profile", ""),
                    "Weight": _fmt(shop.get("weight_oz")),
                    "Length": _fmt(shop.get("length_in")),
                    "Width": _fmt(shop.get("width_in")),
                    "Height": _fmt(shop.get("height_in")),
                    "Return policy": shop.get("return_policy", ""),
                }
            )
            for idx, url in enumerate(photo_urls):
                row[f"Photo {idx + 1}"] = url
        rows.append(row)
    return rows


def render_csv(rows: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def build_export_for_artworks(session: Session, *, artworks: list[Artwork]) -> tuple[str, list[str], int]:
    """Resolves each Artwork's EtsyListingPackage/PrintExports/Mockups
    from the DB and renders the full CSV. Returns (csv_text, skus,
    row_count) -- skus purely for a human-readable confirmation, not used
    for lookups. Raises ValueError naming the artwork if it has no
    listing package or no known-ratio print exports yet (nothing here
    fabricates a listing for a design that isn't actually ready)."""
    settings = get_settings()
    if not settings.public_base_url:
        raise ValueError(
            "Getvela export requires PUBLIC_BASE_URL to be set (see .env.example) -- "
            "Getvela fetches Photo columns as real URLs, and this system never emits "
            "an unreachable localhost URL as if it were real."
        )

    shop_defaults = get_shop_defaults()
    pricing = get_pricing_policy()

    all_rows: list[dict[str, str]] = []
    skus: list[str] = []
    for artwork in artworks:
        package = (
            session.query(EtsyListingPackage).filter(EtsyListingPackage.artwork_id == artwork.id).one_or_none()
        )
        if package is None:
            raise ValueError(f"artwork {artwork.id} has no EtsyListingPackage yet")
        collection = session.get(Collection, artwork.collection_id)
        if collection is None:
            raise ValueError(f"artwork {artwork.id} has no collection (data integrity issue)")
        print_exports = session.query(PrintExport).filter(PrintExport.artwork_id == artwork.id).all()
        mockups = session.query(Mockup).filter(Mockup.artwork_id == artwork.id).all()

        rows = build_listing_rows(
            artwork=artwork,
            package=package,
            collection=collection,
            print_exports=print_exports,
            mockups=mockups,
            public_base_url=settings.public_base_url,
            shop_defaults=shop_defaults,
            pricing=pricing,
        )
        all_rows.extend(rows)
        skus.append(artwork.sku)

    return render_csv(all_rows), skus, len(all_rows)
