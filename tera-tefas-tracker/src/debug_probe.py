"""Temporary diagnostic script — check the general monthly "Fon Bülteni"
PDF (covers all Tera funds) for a per-fund, per-stock holdings table.
Not part of the daily job; delete once a working approach is confirmed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pdfplumber
import requests

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
)

url = "https://www.teraportfoy.com/media/3tvhobgl/aral%C4%B1k_fon_bulteni_-1-20260123_101502.pdf"
print(f"=== Downloading {url} ===", flush=True)
resp = session.get(url, timeout=30)
print("HTTP status:", resp.status_code, "bytes:", len(resp.content), flush=True)

tmp_path = Path("/tmp/bulten.pdf")
tmp_path.write_bytes(resp.content)

with pdfplumber.open(tmp_path) as pdf:
    print(f"page count: {len(pdf.pages)}", flush=True)
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "TLY" in text or "TMV" in text or any(t in text for t in ["Hisse", "Pay Oranı", "OZATD", "ISVEA"]):
            print(f"\n--- page {i+1} (mentions TLY/TMV/hisse) ---", flush=True)
            print(text[:3000], flush=True)
        else:
            print(f"--- page {i+1}: no TLY/TMV/hisse keyword, first 150 chars: {text[:150]!r}", flush=True)
