"""Local-filesystem StorageProvider. Real implementation (not a fake) —
used in tests and available for self-hosted deployments without S3. Master
artwork, ratio exports and mockups are always stored through this
interface; the DB never holds binary image data."""
from __future__ import annotations

from pathlib import Path

from app.config import get_settings


class LocalStorageProvider:
    name = "local_storage"

    def __init__(self, root: str | None = None):
        self.root = Path(root or get_settings().storage_local_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    async def put(self, *, key: str, data: bytes, content_type: str = "image/png") -> str:
        self._path(key).write_bytes(data)
        return key

    async def get(self, *, key: str) -> bytes:
        return self._path(key).read_bytes()

    def url_for(self, *, key: str) -> str:
        return f"file://{self._path(key)}"
