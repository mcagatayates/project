"""Real DriveArchiveProvider: uploads a file to a Google Drive folder via
a service account (no interactive OAuth -- a backend service can't do a
consent-screen login). Requires two real settings (see .env.example):

  GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON  -- path to a service account key file
  GOOGLE_DRIVE_FOLDER_ID             -- target folder's Drive ID, shared
                                         with that service account's email

Setup (one-time, ~5 minutes, no code):
  1. Google Cloud Console -> create a project (or reuse one) -> enable the
     Google Drive API.
  2. IAM & Admin -> Service Accounts -> create one -> Keys -> Add key ->
     JSON. Save that file somewhere the backend can read it and point
     GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON at its path.
  3. In Google Drive, create (or pick) a folder for master images, share
     it with the service account's email (looks like
     ...@<project>.iam.gserviceaccount.com) as an Editor, and copy the
     folder's ID from its URL into GOOGLE_DRIVE_FOLDER_ID.

Raises ProviderError with a clear message if either setting is missing,
following the same pattern as every other real-vendor adapter in this
codebase (see app/providers/web_search_market_intelligence.py) rather
than silently doing nothing.
"""

from __future__ import annotations

import asyncio
import io

from app.config import get_settings
from app.providers.base import DriveArchiveResult, ProviderError

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveArchiveProvider:
    name = "google_drive_archive"

    def __init__(self, *, service_account_json_path: str | None = None, folder_id: str | None = None):
        settings = get_settings()
        self._service_account_json_path = service_account_json_path or settings.google_drive_service_account_json
        self._folder_id = folder_id or settings.google_drive_folder_id
        self._service = None

    def _require_config(self) -> tuple[str, str]:
        if not self._service_account_json_path or not self._folder_id:
            raise ProviderError(
                "GoogleDriveArchiveProvider requires GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON and "
                "GOOGLE_DRIVE_FOLDER_ID to be set (see .env.example and this module's docstring "
                "for the one-time setup steps) -- this system never silently skips archiving to "
                "Drive without saying so."
            )
        return self._service_account_json_path, self._folder_id

    def _build_service(self):
        if self._service is not None:
            return self._service
        # Imported lazily so the google-api-python-client/google-auth
        # dependency is only required when this real adapter is actually
        # used, not for every test run in fake mode.
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        key_path, _ = self._require_config()
        credentials = service_account.Credentials.from_service_account_file(key_path, scopes=_DRIVE_SCOPES)
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def _upload_sync(self, *, filename: str, data: bytes, content_type: str) -> DriveArchiveResult:
        from googleapiclient.http import MediaIoBaseUpload

        _, folder_id = self._require_config()
        service = self._build_service()
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=content_type, resumable=False)
        file_metadata = {"name": filename, "parents": [folder_id]}
        try:
            created = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a provider-shaped error for retry/circuit-breaker
            raise ProviderError(f"Google Drive upload failed for '{filename}': {exc}") from exc
        return DriveArchiveResult(file_id=created["id"], file_url=created.get("webViewLink", ""))

    async def upload(self, *, filename: str, data: bytes, content_type: str = "image/png") -> DriveArchiveResult:
        self._require_config()
        return await asyncio.to_thread(self._upload_sync, filename=filename, data=data, content_type=content_type)
