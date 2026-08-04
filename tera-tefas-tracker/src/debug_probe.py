"""Temporary diagnostic script — check whether teraportfoy.com's fund
bulletin pages are reachable from GitHub Actions and find the current
month's "Portföy Dağılım Raporu" PDF link for TLY/TMV. Not part of the
daily job; delete once a working approach is confirmed.
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
)

PDF_LINK_RE = re.compile(r'href="([^"]*\.pdf[^"]*)"', re.IGNORECASE)

urls = [
    "https://www.teraportfoy.com/fon-bulteni",
    "https://www.teraportfoy.com/fonlarimiz/serbest-fonlarimiz/tera-portfoy-birinci-serbest-fon-tly",
    "https://www.teraportfoy.com/fonlarimiz/serbest-fonlarimiz",
]

for url in urls:
    print(f"\n=== {url} ===", flush=True)
    try:
        resp = session.get(url, timeout=20)
        print("HTTP status:", resp.status_code, flush=True)
        print("content length:", len(resp.text), flush=True)
        pdfs = PDF_LINK_RE.findall(resp.text)
        print("PDF links found:", len(pdfs), flush=True)
        for p in pdfs[:20]:
            print(" -", p, flush=True)
        if resp.status_code != 200:
            print(resp.text[:1000], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("probe failed:", repr(exc), flush=True)
