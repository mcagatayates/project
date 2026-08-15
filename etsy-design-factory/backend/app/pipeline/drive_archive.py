"""Google Drive master-image archive: uploads each approved Artwork's
master image to a Drive folder, named by SKU, so a human fulfilling an
Etsy order can find the right file immediately -- searching either this
system (see app/api/routes/drive_archive.py's /lookup endpoint) or Drive
itself -- instead of hunting through unlabeled files.

Deliberately narrow scope: only the master image (not ratio exports or
mockups, which aren't what a POD partner or a human needs to fulfill an
order), one upload per Artwork, never re-uploaded once archived (see
app/memory/drive_archive_memory.py).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models.artwork import Artwork
from app.memory.drive_archive_memory import record_archive
from app.providers.registry import ProviderRegistry


def _drive_filename(artwork: Artwork) -> str:
    return f"{artwork.sku}.png"


async def archive_artwork(session: Session, registry: ProviderRegistry, *, artwork: Artwork):
    """Uploads one Artwork's master image and records the archive. Raises
    ProviderError (from the registry) if the upload fails -- callers
    processing a batch should let one failure not corrupt the others, the
    same isolation pattern used throughout this pipeline (see
    app/simulation/daily_simulation.py's per-concept ProviderError
    handling)."""
    data = await registry.call("storage.default", "get", key=artwork.master_storage_key)
    result = await registry.call("archive.drive", "upload", filename=_drive_filename(artwork), data=data)
    return record_archive(
        session, artwork_id=artwork.id, sku=artwork.sku, drive_file_id=result.file_id, drive_file_url=result.file_url
    )


async def archive_artworks(session: Session, registry: ProviderRegistry, *, artworks: list[Artwork]) -> list:
    """Archives each given Artwork in turn. Returns the successfully
    archived records; an artwork whose upload fails is skipped (not
    recorded, so it's retried on the next sync) rather than aborting the
    whole batch."""
    from app.providers.base import ProviderError

    records = []
    for artwork in artworks:
        try:
            record = await archive_artwork(session, registry, artwork=artwork)
        except ProviderError:
            continue
        records.append(record)
    return records
