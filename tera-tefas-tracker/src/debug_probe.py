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

kap_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json; charset=UTF-8",
}
kap_session = requests.Session()
kap_session.headers.update(kap_headers)
try:
    kap_session.get("https://www.kap.org.tr/tr/bildirim-sorgu", timeout=15)
except Exception:
    pass

print("\n=== KAP member/filter probe for 'tera' ===", flush=True)
try:
    resp = kap_session.get("https://www.kap.org.tr/tr/api/member/filter/tera", timeout=20)
    print("HTTP status:", resp.status_code, flush=True)
    print(resp.text[:3000], flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP member/filter probe failed:", repr(exc), flush=True)

print("\n=== KAP roster probes for letter 'T' across member types ===", flush=True)
for member_type in ["YK", "PYS", "ARK", "IGS"]:
    try:
        resp = kap_session.get(
            f"https://www.kap.org.tr/tr/api/company/items/{member_type}/T", timeout=20
        )
        print(f"--- type={member_type} status={resp.status_code} ---", flush=True)
        print(resp.text[:1500], flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"KAP roster probe failed for {member_type}:", repr(exc), flush=True)

print("\n=== KAP disclosure search filtered by subject (Portföy Dağılım Raporu) ===", flush=True)
try:
    body = {
        "fromDate": (dt.date.today() - dt.timedelta(days=15)).isoformat(),
        "toDate": dt.date.today().isoformat(),
        "mkkMemberOidList": [],
        "subjectList": ["Fon Portföy Dağılım Raporu"],
    }
    resp = kap_session.post(
        "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria", json=body, timeout=30
    )
    print("HTTP status:", resp.status_code, flush=True)
    data = resp.json()
    disclosures = data if isinstance(data, list) else data.get("data", data.get("result", []))
    print("count:", len(disclosures) if disclosures else 0, flush=True)
    if disclosures:
        print("first item keys:", list(disclosures[0].keys()), flush=True)
        print(json.dumps(disclosures[0], ensure_ascii=False, indent=2), flush=True)
        tera_hits = [
            d for d in disclosures
            if "tera" in json.dumps(d, ensure_ascii=False).lower()
        ]
        print(f"\nEntries mentioning 'tera': {len(tera_hits)}", flush=True)
        for d in tera_hits[:5]:
            print(json.dumps(d, ensure_ascii=False, indent=2), flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP disclosure search probe failed:", repr(exc), flush=True)
