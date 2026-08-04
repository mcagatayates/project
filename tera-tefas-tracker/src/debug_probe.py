"""Temporary diagnostic script — prints raw API responses to the Actions
log so field names can be confirmed without guessing. Not part of the
daily job; delete once tefas_client.py / kap_client.py are verified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime as dt

import requests

import tefas_client

print("=== TEFAS raw response for THF ===", flush=True)
try:
    today = dt.date.today()
    start = today - dt.timedelta(days=10)
    body = {
        "fonTipi": "YAT",
        "fonKodu": "THF",
        "basTarih": start.strftime("%Y%m%d"),
        "bitTarih": today.strftime("%Y%m%d"),
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
    }
    resp = requests.post(tefas_client.TEFAS_DIST_URL, json=body, headers=tefas_client.HEADERS, timeout=30)
    print("HTTP status:", resp.status_code, flush=True)
    payload = resp.json()
    dumped = json.dumps(payload, ensure_ascii=False, indent=2)
    print(dumped[:4000], flush=True)
except Exception as exc:  # noqa: BLE001
    print("TEFAS probe failed:", repr(exc), flush=True)

print("\n=== KAP roster probe for 'T' under YK ===", flush=True)
try:
    resp = requests.get(
        "https://www.kap.org.tr/tr/api/company/items/YK/T",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=20,
    )
    print("HTTP status:", resp.status_code, flush=True)
    payload = resp.json()
    dumped = json.dumps(payload, ensure_ascii=False, indent=2)
    print(dumped[:4000], flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP roster probe failed:", repr(exc), flush=True)
