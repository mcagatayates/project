"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) client.

Uses TEFAS's current, publicly-reachable JSON API (the site was rewritten
at some point; the old `/api/DB/BindHistoryAllocation` endpoint is
retired and now 404s — this targets the replacement under `/api/funds/`,
confirmed against the mirzazad/pytefas client).

This returns, per fund per date, the fund's portfolio broken down by
asset CLASS (e.g. "hisse senedi", "kamu borçlanma", "ters repo" ...) as
percentages of the total portfolio. It does NOT return individual stock
tickers — TEFAS does not publish per-security holdings; that only comes
from KAP's monthly fund reports (see kap_client.py).

The exact response field/column names aren't officially documented, so
this client treats every numeric field in the 0-100 range as a
percentage-allocation column rather than hardcoding names — that keeps
it working even if TEFAS renames or adds columns, and avoids
accidentally treating a date/id field as an allocation weight.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import requests

TEFAS_DIST_URL = "https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tefas.gov.tr/FonKarsilastirma.aspx",
}

# Fields that are metadata, not allocation percentages — matched
# case-insensitively so we don't care whether TEFAS returns "FONKODU",
# "fonKodu", or similar variants.
METADATA_FIELD_NAMES = {
    "tarih",
    "fonkodu",
    "fonunvan",
    "fontipi",
    "fonturkod",
    "fongrubu",
    "fiyat",
    "price",
    "code",
    "date",
    "kind",
    "id",
}


def _to_yyyymmdd(date: dt.date) -> str:
    return date.strftime("%Y%m%d")


def fetch_allocation_history(
    fund_code: str, start_date: dt.date, end_date: dt.date
) -> list[dict[str, Any]]:
    """Return TEFAS's daily allocation records for a fund between two dates."""
    body = {
        "fonTipi": "YAT",
        "fonKodu": fund_code,
        "basTarih": _to_yyyymmdd(start_date),
        "bitTarih": _to_yyyymmdd(end_date),
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
    }
    resp = requests.post(TEFAS_DIST_URL, json=body, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    # The exact wrapper key isn't documented; try the ones known to be
    # used by TEFAS's `/api/funds/*` family.
    records = None
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("data", "resultList", "result", "Data"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
    if records is None:
        raise ValueError(f"Unrecognized TEFAS response shape: {list(payload)[:5] if isinstance(payload, dict) else type(payload)}")

    def _date_key(rec: dict[str, Any]) -> str:
        for key in ("tarih", "TARIH", "date", "Date"):
            if key in rec:
                return str(rec[key])
        return ""

    records.sort(key=_date_key)
    return records


def allocation_weights(record: dict[str, Any]) -> dict[str, float]:
    """Extract {column_name: weight} for numeric, plausible-percentage fields."""
    weights: dict[str, float] = {}
    for key, value in record.items():
        if key.lower() in METADATA_FIELD_NAMES:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            weights[key] = float(value)
    return weights


def latest_two_snapshots(
    fund_code: str, as_of: dt.date, lookback_days: int = 10
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (previous, latest) allocation records for a fund.

    Looks back `lookback_days` calendar days from `as_of` to comfortably
    cover weekends/holidays, and returns the two most recent distinct
    snapshots found (previous may be None if there's only one, latest may
    be None if there's none at all).
    """
    start = as_of - dt.timedelta(days=lookback_days)
    records = fetch_allocation_history(fund_code, start, as_of)
    if not records:
        return None, None
    if len(records) == 1:
        return None, records[-1]
    return records[-2], records[-1]
