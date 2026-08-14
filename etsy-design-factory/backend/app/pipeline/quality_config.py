from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "quality_thresholds.yaml"


@lru_cache
def get_quality_config(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_PATH
    return yaml.safe_load(p.read_text())
