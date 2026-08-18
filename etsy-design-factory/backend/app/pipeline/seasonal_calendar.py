"""Calendar-aware trend research: an occasion (Halloween, Christmas, ...)
should start showing up in research queries `lead_weeks` before it
happens, not the week of -- by the time a buyer is searching "Halloween
wall art," a seller who only just started listing has already missed most
of that search volume. See config/seasonal_calendar.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_CALENDAR_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "seasonal_calendar.yaml"


@dataclass(frozen=True)
class Occasion:
    name: str
    month: int
    day: int
    lead_weeks: int
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class ActiveOccasion:
    occasion: Occasion
    occasion_date: date
    weeks_until: float


@lru_cache
def load_occasions(path: str | None = None) -> tuple[Occasion, ...]:
    p = Path(path) if path else DEFAULT_CALENDAR_PATH
    raw = yaml.safe_load(p.read_text())["occasions"]
    return tuple(
        Occasion(
            name=o["name"],
            month=o["month"],
            day=o["day"],
            lead_weeks=o["lead_weeks"],
            keywords=tuple(o["keywords"]),
        )
        for o in raw
    )


def next_occurrence(today: date, *, month: int, day: int) -> date:
    """The next date (today or in the future) matching month/day. Rolls to
    next year if this year's occurrence already passed."""
    candidate = date(today.year, month, day)
    if candidate < today:
        candidate = date(today.year + 1, month, day)
    return candidate


def previous_occurrence(today: date, *, month: int, day: int) -> date:
    """The most recent past occurrence (strictly before today) of
    month/day -- the mirror of next_occurrence, used by
    app/pipeline/trend_signal.py to look at *last* year's real search
    interest for an occasion, not the upcoming one."""
    candidate = date(today.year, month, day)
    if candidate >= today:
        candidate = date(today.year - 1, month, day)
    return candidate


def active_occasions(today: date, *, occasions: tuple[Occasion, ...] | None = None) -> list[ActiveOccasion]:
    """Occasions whose lead-time window has started: 0 <= weeks_until <=
    lead_weeks. An occasion that already passed rolls to next year's date
    (see next_occurrence), so it naturally drops out of the window."""
    occasions = occasions if occasions is not None else load_occasions()
    active: list[ActiveOccasion] = []
    for occ in occasions:
        occ_date = next_occurrence(today, month=occ.month, day=occ.day)
        weeks_until = (occ_date - today).days / 7.0
        if weeks_until <= occ.lead_weeks:
            active.append(ActiveOccasion(occasion=occ, occasion_date=occ_date, weeks_until=round(weeks_until, 1)))
    active.sort(key=lambda a: a.weeks_until)
    return active
