"""Temporary diagnostic script — dump the FULL body of a share transaction
notification (untruncated) to find the buy/sell direction and
before/after ownership percentage fields. Not part of the daily job;
delete once kap_client.py captures this correctly.
"""
from __future__ import annotations

import re
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

TAG_RE = re.compile(r"<[^>]+>")

for idx in [1642343, 1642293]:
    print(f"\n=== FULL body for idx={idx} (tags stripped) ===", flush=True)
    try:
        resp = session.get(
            f"https://www.kap.org.tr/tr/api/notification/attachment-detail/{idx}", timeout=20
        )
        payload = resp.json()
        entries = payload if isinstance(payload, list) else [payload]
        html_parts = []
        for entry in entries:
            body = entry.get("disclosureBody")
            if isinstance(body, list):
                html_parts.extend(str(b) for b in body)
            elif isinstance(body, str):
                html_parts.append(body)
        html = " ".join(html_parts)
        text = TAG_RE.sub(" | ", html)
        text = re.sub(r"\s+", " ", text)
        text = text.replace("| | |", "|").replace("| |", "|")
        print(text, flush=True)
    except Exception as exc:  # noqa: BLE001
        print("probe failed:", repr(exc), flush=True)
