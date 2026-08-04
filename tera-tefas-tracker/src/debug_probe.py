"""Temporary diagnostic script — inspect the detail of a 'Pay Alım Satım
Bildirimi' disclosure to see its actual body content (buy/sell, amount,
resulting stake %, etc). Not part of the daily job; delete once
kap_client.py is verified end to end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }
)
try:
    session.get("https://www.kap.org.tr/tr/bildirim-sorgu", timeout=15)
except Exception:
    pass

for idx in [1642343, 1642293, 1639782]:
    print(f"\n=== Disclosure detail for idx={idx} ===", flush=True)
    try:
        resp = session.get(
            f"https://www.kap.org.tr/tr/api/notification/attachment-detail/{idx}", timeout=20
        )
        print("HTTP status:", resp.status_code, flush=True)
        payload = resp.json()
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:5000], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("probe failed:", repr(exc), flush=True)
