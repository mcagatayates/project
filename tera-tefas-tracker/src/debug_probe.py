"""Temporary diagnostic script — download a recent TLY 'Yatırımcı Bilgi
Formu' PDF from teraportfoy.com and extract its text to check whether it
contains a per-stock portfolio breakdown. Not part of the daily job;
delete once a working approach is confirmed.
"""
from __future__ import annotations

import re
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

PDF_LINK_RE = re.compile(r'href="([^"]*\.pdf[^"]*)"', re.IGNORECASE)

page_url = "https://www.teraportfoy.com/fonlarimiz/serbest-fonlarimiz/tera-portfoy-birinci-serbest-fon-tly"
print(f"=== Fetching {page_url} ===", flush=True)
resp = session.get(page_url, timeout=20)
print("HTTP status:", resp.status_code, flush=True)
pdfs = sorted(set(PDF_LINK_RE.findall(resp.text)))
print(f"unique PDF links: {len(pdfs)}", flush=True)
for p in pdfs:
    print(" -", p, flush=True)

# Find the most recent "ybf" (yatırımcı bilgi formu) link and the most
# recent "portfoy_dagilim" / "dagilim" link if one exists among them.
ybf_links = [p for p in pdfs if "ybf" in p.lower()]
dagilim_links = [p for p in pdfs if "dagilim" in p.lower() or "dağılım" in p.lower()]
print(f"\nybf_links: {ybf_links}", flush=True)
print(f"dagilim_links: {dagilim_links}", flush=True)

targets = []
if ybf_links:
    targets.append(("YBF", ybf_links[-1]))
if dagilim_links:
    targets.append(("DAGILIM", dagilim_links[-1]))

for label, rel_url in targets:
    full_url = "https://www.teraportfoy.com" + rel_url if rel_url.startswith("/") else rel_url
    print(f"\n=== Downloading {label}: {full_url} ===", flush=True)
    try:
        pdf_resp = session.get(full_url, timeout=30)
        print("HTTP status:", pdf_resp.status_code, "bytes:", len(pdf_resp.content), flush=True)
        tmp_path = Path(f"/tmp/{label}.pdf")
        tmp_path.write_bytes(pdf_resp.content)
        with pdfplumber.open(tmp_path) as pdf:
            print(f"page count: {len(pdf.pages)}", flush=True)
            for i, page in enumerate(pdf.pages[:6]):
                text = page.extract_text() or ""
                print(f"--- page {i+1} text ---", flush=True)
                print(text[:2500], flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{label} probe failed:", repr(exc), flush=True)
