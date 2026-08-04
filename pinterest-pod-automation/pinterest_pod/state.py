"""Paylaşım aralığı / günlük limit takibi için küçük JSON state dosyası."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_RETENTION_DAYS = 14


def load(path: Path) -> dict:
    if not path.exists():
        return {"last_post_at": None, "posts_by_day": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_post_at": None, "posts_by_day": {}}


def save(path: Path, state: dict) -> None:
    # Eski günleri temizle, dosya sonsuza kadar büyümesin.
    cutoff = datetime.now() - timedelta(days=STATE_RETENTION_DAYS)
    posts_by_day = {
        day: count
        for day, count in state.get("posts_by_day", {}).items()
        if _parse_day(day) >= cutoff
    }
    state = {**state, "posts_by_day": posts_by_day}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _parse_day(day: str) -> datetime:
    try:
        return datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return datetime.now()


def today_count(state: dict) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("posts_by_day", {}).get(today, 0)


def record_post(state: dict) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    posts_by_day = dict(state.get("posts_by_day", {}))
    posts_by_day[today] = posts_by_day.get(today, 0) + 1
    return {
        "last_post_at": datetime.now().isoformat(),
        "posts_by_day": posts_by_day,
    }


def minutes_since_last_post(state: dict) -> float | None:
    last = state.get("last_post_at")
    if not last:
        return None
    delta = datetime.now() - datetime.fromisoformat(last)
    return delta.total_seconds() / 60
