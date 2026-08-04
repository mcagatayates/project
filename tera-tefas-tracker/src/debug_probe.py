"""Temporary diagnostic script — prints raw API responses to the Actions
log so the KAP disclosure search can be verified against real data
instead of guessing. Not part of the daily job; delete once kap_client.py
is verified end to end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime as dt

import requests

import kap_client

TERA_OID = kap_client.TERA_MENKUL_MEMBER_OID

kap_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json; charset=UTF-8",
}
session = requests.Session()
session.headers.update(kap_headers)
try:
    session.get("https://www.kap.org.tr/tr/bildirim-sorgu", timeout=15)
except Exception:
    pass

print(f"=== All KAP disclosures for TERA YATIRIM MENKUL DEĞERLER (oid={TERA_OID}), last 180 days ===", flush=True)
try:
    body = {
        "fromDate": (dt.date.today() - dt.timedelta(days=180)).isoformat(),
        "toDate": dt.date.today().isoformat(),
        "mkkMemberOidList": [TERA_OID],
        "subjectList": [],
    }
    resp = session.post(
        "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria", json=body, timeout=30
    )
    print("HTTP status:", resp.status_code, flush=True)
    data = resp.json()
    disclosures = data if isinstance(data, list) else data.get("data", data.get("result", []))
    print("total count:", len(disclosures) if disclosures else 0, flush=True)
    if disclosures:
        print("first item raw:", json.dumps(disclosures[0], ensure_ascii=False, indent=2), flush=True)
        print("\n--- all subjects + disclosureIndex + date ---", flush=True)
        for d in disclosures:
            subj = d.get("subject") or d.get("title") or d.get("konu")
            idx = d.get("disclosureIndex") or d.get("id")
            date = d.get("publishDate") or d.get("date")
            print(f"idx={idx} date={date} subject={subj!r}", flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP disclosure search failed:", repr(exc), flush=True)

print("\n=== Same search but with a 400-day window (in case nothing recent) ===", flush=True)
try:
    body = {
        "fromDate": (dt.date.today() - dt.timedelta(days=400)).isoformat(),
        "toDate": dt.date.today().isoformat(),
        "mkkMemberOidList": [TERA_OID],
        "subjectList": [],
    }
    resp = session.post(
        "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria", json=body, timeout=30
    )
    print("HTTP status:", resp.status_code, flush=True)
    data = resp.json()
    disclosures = data if isinstance(data, list) else data.get("data", data.get("result", []))
    print("total count:", len(disclosures) if disclosures else 0, flush=True)
    for d in (disclosures or [])[:40]:
        subj = d.get("subject") or d.get("title") or d.get("konu")
        idx = d.get("disclosureIndex") or d.get("id")
        date = d.get("publishDate") or d.get("date")
        print(f"idx={idx} date={date} subject={subj!r}", flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP disclosure search (400d) failed:", repr(exc), flush=True)
