from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import GUID, Base, CreatedAtMixin, UUIDPKMixin


class DriveArchiveRecord(UUIDPKMixin, CreatedAtMixin, Base):
    """One row per Artwork whose master image has actually been uploaded
    to the Google Drive archive folder -- see
    app/pipeline/drive_archive.py. Exists so a human fulfilling an Etsy
    order can search this system (or Drive itself) by SKU and land
    directly on the master file, instead of hunting for it by hand.
    Append-only, and unique on artwork_id so re-running the sync never
    re-uploads a design already archived."""

    __tablename__ = "drive_archive_records"

    artwork_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("artworks.id"), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(50), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(200))
    drive_file_url: Mapped[str] = mapped_column(String(1000))
