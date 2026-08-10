"""Temporary diagnostic script — check whether broker-level (takas) net
buy/sell data for BIST stocks is reachable from a GitHub Actions runner,
and in what shape. Specifically looking for a source that can show how
many lots TERA YATIRIM MENKUL DEĞERLER A.Ş. (the brokerage, distinct from
TERA PORTFÖY YÖNETİMİ A.Ş. the fund manager already tracked by main.py)
cleared on a given stock on a given day — e.g. the ~3M lot HEDEF trade
reported for Friday 2026-08-07.

Not part of the daily job; delete once a working approach is confirmed.
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json",
    }
)


def show(url: str, **kwargs):
    print(f"\n=== {url} ===", flush=True)
    try:
        resp = session.get(url, timeout=20, **kwargs)
        print("HTTP status:", resp.status_code, flush=True)
        print("content-type:", resp.headers.get("Content-Type"), flush=True)
        print("content length:", len(resp.content), flush=True)
        text = resp.text
        print(text[:1500], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("probe failed:", repr(exc), flush=True)


# 1) isyatirim.com.tr "Takas Verileri" page (public, well-known among TR
#    retail traders) — HTML page + look for an underlying data endpoint.
show("https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Takas-Verileri.aspx?hisse=HEDEF")

# 2) Candidate JSON/ASMX data endpoints behind that page (guessed from
#    known isyatirim.com.tr API conventions; may 404).
show(
    "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/TakasEndeks",
    params={"hisse": "HEDEF"},
)
show(
    "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx/BrokerBazliVeri",
    params={"hisse": "HEDEF", "startdate": "07-08-2026", "enddate": "07-08-2026"},
)

# 3) fintables.com public takas page for the same stock, as a second
#    candidate source.
show("https://fintables.com/sirketler/HEDEF/takas")

# 4) KAP: did Friday's ~3M lot HEDEF trade already surface as a "Pay Alım
#    Satım Bildirimi" from TERA PORTFÖY YÖNETİMİ A.Ş.? (main.py already
#    tracks this — checking whether it would have caught this specific
#    trade, or whether it's below the ownership-threshold that triggers a
#    KAP filing.)
import kap_client  # noqa: E402

try:
    session.get(kap_client.WARMUP_URL, timeout=15)
except requests.RequestException:
    pass
print("\n=== KAP: recent Pay Alım Satım Bildirimi for Tera Portföy ===", flush=True)
try:
    disclosures = kap_client.search_disclosures(kap_client.TERA_PORTFOY_MEMBER_OID, days_back=10)
    matches = [d for d in disclosures if d.get("subject") == kap_client.SHARE_TRANSACTION_SUBJECT]
    print(f"{len(matches)} share-transaction disclosures in last 10 days", flush=True)
    for d in matches:
        print(json.dumps(d, ensure_ascii=False), flush=True)
except Exception as exc:  # noqa: BLE001
    print("KAP probe failed:", repr(exc), flush=True)
