"""Ortam değişkenlerini (.env) okuyup tek bir yerden sunan modül."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Config:
    # Pinterest OAuth kimlik bilgileri
    app_id: str
    app_secret: str
    redirect_uri: str
    refresh_token: str

    # Marka / görsel şablonu
    brand_name: str
    logo_path: str
    font_path: str

    # Zamanlama / hız sınırlama
    daily_pin_limit: int
    min_minutes_between_pins: int

    # Dosya yolları
    csv_path: Path
    output_dir: Path
    log_path: Path
    state_dir: Path

    @property
    def token_cache_path(self) -> Path:
        return self.state_dir / "token_cache.json"

    @property
    def posting_state_path(self) -> Path:
        return self.state_dir / "posting_state.json"


def load_config() -> Config:
    return Config(
        app_id=os.getenv("PINTEREST_APP_ID", ""),
        app_secret=os.getenv("PINTEREST_APP_SECRET", ""),
        redirect_uri=os.getenv("PINTEREST_REDIRECT_URI", "https://localhost/callback"),
        refresh_token=os.getenv("PINTEREST_REFRESH_TOKEN", ""),
        brand_name=os.getenv("BRAND_NAME", ""),
        logo_path=os.getenv("LOGO_PATH", ""),
        font_path=os.getenv("FONT_PATH", ""),
        daily_pin_limit=_get_int("DAILY_PIN_LIMIT", 4),
        min_minutes_between_pins=_get_int("MIN_MINUTES_BETWEEN_PINS", 180),
        csv_path=BASE_DIR / os.getenv("CSV_PATH", "urunler.csv"),
        output_dir=BASE_DIR / os.getenv("OUTPUT_DIR", "pinler"),
        log_path=BASE_DIR / os.getenv("LOG_PATH", "log.txt"),
        state_dir=BASE_DIR / "state",
    )
