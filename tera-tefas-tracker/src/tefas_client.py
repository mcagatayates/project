"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) client.

Uses TEFAS's public, unauthenticated JSON endpoint that backs the
"Tarihsel Veriler" / "Portföy Dağılımı" pages on tefas.gov.tr. This
returns, per fund per date, the fund's portfolio broken down by asset
CLASS (e.g. "hisse senedi", "kamu borçlanma", "ters repo" ...) as
percentages of the total portfolio. It does NOT return individual stock
tickers — TEFAS does not publish per-security holdings; that only comes
from KAP's monthly fund reports (see kap_client.py).

The exact set of allocation-column names returned by TEFAS has varied
across sources we could find documented, so this client treats every
non-metadata field in a record as a numeric allocation column rather
than hardcoding names — that keeps it working even if TEFAS renames or
adds columns.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import requests

TEFAS_ALLOCATION_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
    "X-Requested-With": "XMLHttpRequest",
}

# Fields TEFAS returns alongside the allocation percentages that are not
# themselves allocation weights.
METADATA_FIELDS = {"TARIH", "FONKODU", "FONUNVAN", "FONTURACIKLAMA", "FIYAT"}


def _to_epoch_ms(date: dt.date) -> int:
    return int(dt.datetime(date.year, date.month, date.day).timestamp() * 1000)


def fetch_allocation_history(
    fund_code: str, start_date: dt.date, end_date: dt.date
) -> list[dict[str, Any]]:
    """Return TEFAS's daily allocation records for a fund between two dates.

    TEFAS dates are given as "DD.MM.YYYY" in the request; the response is
    a JSON object with a "data" list, one entry per trading day the fund
    published a snapshot for (weekends/holidays are simply absent).
    """
    payload = {
        "fontip": "YAT",
        "sfontur": "",
        "fonkod": fund_code,
        "bastarih": start_date.strftime("%d.%m.%Y"),
        "bittarih": end_date.strftime("%d.%m.%Y"),
    }
    resp = requests.post(TEFAS_ALLOCATION_URL, data=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    records = body.get("data", [])
    # TARIH comes back as a "/Date(epoch_ms)/" style string on some TEFAS
    # endpoints; normalize to an ISO date string when that's the case.
    for rec in records:
        tarih = rec.get("TARIH")
        if isinstance(tarih, str) and tarih.startswith("/Date("):
            epoch_ms = int(tarih.strip("/Date()"))
            rec["TARIH"] = dt.datetime.utcfromtimestamp(epoch_ms / 1000).date().isoformat()
    records.sort(key=lambda r: r.get("TARIH", ""))
    return records


def allocation_weights(record: dict[str, Any]) -> dict[str, float]:
    """Extract {column_name: weight} for the non-metadata numeric fields."""
    weights: dict[str, float] = {}
    for key, value in record.items():
        if key in METADATA_FIELDS:
            continue
        if isinstance(value, (int, float)):
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
