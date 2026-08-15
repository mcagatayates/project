"""Builds a ProviderRegistry from config/providers.yaml + app settings.

This is the one place allowed to know about every concrete adapter class,
including vendor adapters once they exist (see docs/PROVIDER_ARCHITECTURE.md,
"Provider-independence rule").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings
from app.providers.base import ProviderError
from app.providers.fake.drive_archive import FakeDriveArchiveProvider
from app.providers.fake.image_gen import FakeImageGenProvider
from app.providers.fake.llm import FakeLLMProvider
from app.providers.fake.upscale import FakeUpscaleProvider
from app.providers.fake.vision import FakeVisionProvider
from app.providers.google_drive import GoogleDriveArchiveProvider
from app.providers.local_storage import LocalStorageProvider
from app.providers.registry import AdapterSpec, HealthEventHook, ProviderRegistry

_ADAPTER_BUILDERS: dict[str, Any] = {
    "fake_llm": FakeLLMProvider,
    "fake_image_gen": FakeImageGenProvider,
    "fake_vision": FakeVisionProvider,
    "fake_upscale": FakeUpscaleProvider,
    "local": LocalStorageProvider,
    "google_drive": GoogleDriveArchiveProvider,
}


def _build_adapter(kind: str, role: str):
    settings = get_settings()
    force_fake = settings.provider_mode == "fake" or settings.is_test
    if force_fake:
        if "vision" in role:
            return FakeVisionProvider()
        if "llm" in role:
            return FakeLLMProvider()
        if "upscale" in role:
            return FakeUpscaleProvider()
        if "storage" in role:
            return LocalStorageProvider()
        if "drive" in role or "archive" in role:
            return FakeDriveArchiveProvider()
        return FakeImageGenProvider()

    if kind == "local":
        return LocalStorageProvider()
    if kind in _ADAPTER_BUILDERS:
        return _ADAPTER_BUILDERS[kind]()

    raise ProviderError(
        f"adapter '{kind}' for role '{role}' is not implemented in this repository "
        "(see docs/ROADMAP.md 'Explicit non-goals'). Implement app/providers/<vendor>.py "
        "against the Protocol in app/providers/base.py and register it in "
        "app/providers/factory.py."
    )


def build_registry(on_health_event: HealthEventHook | None = None, config_path: str | None = None) -> ProviderRegistry:
    settings = get_settings()
    path = Path(config_path or settings.providers_config_path)
    raw = yaml.safe_load(path.read_text()) if path.exists() else {"roles": {}}

    force_fake = settings.provider_mode == "fake" or settings.is_test

    registry = ProviderRegistry(on_health_event=on_health_event)
    for role, cfg in raw.get("roles", {}).items():
        adapter_kind = cfg.get("adapter", "fake")
        instance = _build_adapter(adapter_kind, role)
        # Rate limits in providers.yaml model REAL vendor limits. A fake
        # adapter has no such constraint -- honoring the configured limit
        # anyway would make a 30-design simulation take minutes waiting on
        # a token bucket sized for a paid API that was never called.
        rate_per_minute = 1_000_000.0 if force_fake else float(cfg.get("rate_per_minute", 120.0))
        spec = AdapterSpec(
            name=f"{adapter_kind}:{role}",
            instance=instance,
            rate_per_minute=rate_per_minute,
            max_retries=int(cfg.get("max_retries", 3)),
        )
        registry.register_role(role, primary=spec)
    return registry
