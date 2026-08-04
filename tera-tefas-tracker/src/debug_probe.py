"""Temporary diagnostic script — see if TEFAS funds have their own KAP
member registration (separate from the management company), and check
whether fvt.com.tr exposes a usable per-stock fund holdings page/API.
Not part of the daily job; delete once kap_client.py is verified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

kap_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
session = requests.Session()
session.headers.update(kap_headers)
try:
    session.get("https://www.kap.org.tr/tr/bildirim-sorgu", timeout=15)
except Exception:
    pass

for query in ["tera portföy", "tera portföy hisse senedi", "THF"]:
    print(f"\n=== KAP member/filter probe for {query!r} ===", flush=True)
    try:
        resp = session.get(
            f"https://www.kap.org.tr/tr/api/member/filter/{query}", timeout=20
        )
        print("HTTP status:", resp.status_code, flush=True)
        print(resp.text[:3000], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("probe failed:", repr(exc), flush=True)

print("\n=== fvt.com.tr TLY page ===", flush=True)
try:
    resp = requests.get(
        "https://fvt.com.tr/fonlar/yatirim-fonlari/TLY",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=20,
    )
    print("HTTP status:", resp.status_code, flush=True)
    print("content length:", len(resp.text), flush=True)
    print(resp.text[:3000], flush=True)
except Exception as exc:  # noqa: BLE001
    print("fvt.com.tr probe failed:", repr(exc), flush=True)
