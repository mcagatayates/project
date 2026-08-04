"""Temporary diagnostic script — check whether TERA PORTFÖY YÖNETİMİ A.Ş.
(mkkMemberOid 5553acdacf15471ba80c28eb45cdd9e7, distinct from the
brokerage entity) is the actual filer of Fon Portföy Dağılım Raporu for
Tera's TEFAS funds. Not part of the daily job; delete once kap_client.py
is verified end to end.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

TERA_PORTFOY_YONETIMI_OID = "5553acdacf15471ba80c28eb45cdd9e7"

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=UTF-8",
    }
)
try:
    session.get("https://www.kap.org.tr/tr/bildirim-sorgu", timeout=15)
except Exception:
    pass

print(f"=== All KAP disclosures for TERA PORTFÖY YÖNETİMİ A.Ş. (oid={TERA_PORTFOY_YONETIMI_OID}), last 180 days ===", flush=True)
try:
    body = {
        "fromDate": (dt.date.today() - dt.timedelta(days=180)).isoformat(),
        "toDate": dt.date.today().isoformat(),
        "mkkMemberOidList": [TERA_PORTFOY_YONETIMI_OID],
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
        print("\nfirst item raw:", json.dumps(disclosures[0], ensure_ascii=False, indent=2), flush=True)
        print("\n--- all subjects + disclosureIndex + date ---", flush=True)
        for d in disclosures:
            subj = d.get("subject") or d.get("title") or d.get("konu")
            idx = d.get("disclosureIndex") or d.get("id")
            date = d.get("publishDate") or d.get("date")
            print(f"idx={idx} date={date} subject={subj!r}", flush=True)
except Exception as exc:  # noqa: BLE001
    print("probe failed:", repr(exc), flush=True)
