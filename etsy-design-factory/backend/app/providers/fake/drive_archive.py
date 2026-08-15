"""Deterministic fake DriveArchiveProvider -- no network call, no real
Google credentials needed. Used whenever PROVIDER_MODE=fake / APP_ENV=test
(see app/providers/factory.py), so the archive pipeline and its tests can
run without a real Google Drive account."""

from __future__ import annotations

import hashlib

from app.providers.base import DriveArchiveResult


class FakeDriveArchiveProvider:
    name = "fake_drive_archive"

    async def upload(self, *, filename: str, data: bytes, content_type: str = "image/png") -> DriveArchiveResult:
        # A stable, deterministic fake file id derived from the real
        # content + filename -- distinct files/names never collide, and
        # the same (filename, data) pair always maps to the same id.
        digest = hashlib.sha256(filename.encode("utf-8") + data).hexdigest()[:20]
        file_id = f"fake-drive-{digest}"
        return DriveArchiveResult(file_id=file_id, file_url=f"https://drive.google.com/file/d/{file_id}/view")
