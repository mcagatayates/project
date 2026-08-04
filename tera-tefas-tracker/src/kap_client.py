"""KAP (Kamuyu Aydınlatma Platformu) client — monthly per-stock fund holdings.

TEFAS only publishes asset-CLASS allocation (see tefas_client.py). Actual
per-security holdings ("Tera hangi hisseyi ne kadar tutuyor") are only
published by fund management companies through KAP's standardized
"Fon Portföy Dağılım Raporu" (Fund Portfolio Distribution Report), filed
monthly, within ~6 business days after each month closes.

IMPORTANT / KNOWN LIMITATION: this module could not be tested against
live KAP responses while it was written — the sandbox this was built in
has no network access to kap.org.tr. The disclosure-search endpoint and
the report-parsing logic below follow KAP's publicly documented
conventions as closely as possible, but treat this as a best-effort v1:
if it fails to find or parse a report, it degrades to sending a plain
link to the disclosure so you can check manually, rather than staying
silent or crashing the whole daily job. Expect to tighten this up after
seeing the first few real runs in the Actions logs.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

import requests

KAP_DISCLOSURE_QUERY_URL = "https://www.kap.org.tr/tr/api/memberDisclosureQuery"
KAP_DISCLOSURE_URL = "https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json; charset=UTF-8",
    "Referer": "https://www.kap.org.tr/tr/bist-sirketler",
}

REPORT_SUBJECT_HINT = "portföy dağılım raporu"

# Rows in the report table look like "GARAN  Garanti Bankası  8,42".
# A plausible BIST ticker is 3-6 uppercase Latin letters.
TICKER_ROW_RE = re.compile(
    r"\b([A-ZİÇŞĞÜÖ]{3,6})\b[^%\n]{0,80}?([0-9]{1,2}[.,][0-9]{1,4})\s*%?"
)


def search_fund_disclosures(fund_name: str, days_back: int = 40) -> list[dict[str, Any]]:
    """Search KAP for recent disclosures mentioning a fund by name.

    Returns raw disclosure summary dicts as given by KAP (at least a
    disclosure id, a title/subject, and a publish date) sorted newest
    first. Filtering down to "Fon Portföy Dağılım Raporu" specifically
    happens in `find_latest_portfolio_report`.
    """
    end = dt.date.today()
    start = end - dt.timedelta(days=days_back)
    body = {
        "fromDate": start.isoformat(),
        "toDate": end.isoformat(),
        "year": "",
        "prd": "",
        "term": "",
        "ruleType": "",
        "bdkReview": "",
        "disclosureClass": "FON",
        "index": "",
        "market": "",
        "isLate": "",
        "subjectList": [],
        "mkkMemberOidList": [],
        "inactiveMkkMemberOidList": [],
        "bdkMemberOidList": [],
        "mainSector": "",
        "sector": "",
        "subSector": "",
        "memberType": "IGS",
        "fromSrc": "N",
        "srcCategory": "",
        "text": fund_name,
    }
    resp = requests.post(KAP_DISCLOSURE_QUERY_URL, json=body, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    disclosures = data if isinstance(data, list) else data.get("data", data.get("result", []))
    return disclosures or []


def find_latest_portfolio_report(fund_name: str) -> dict[str, Any] | None:
    """Return the newest 'Fon Portföy Dağılım Raporu' disclosure for a fund, if any."""
    disclosures = search_fund_disclosures(fund_name)
    candidates = [
        d
        for d in disclosures
        if REPORT_SUBJECT_HINT in str(d.get("title") or d.get("subject") or "").lower()
    ]
    if not candidates:
        return None

    def _key(d: dict[str, Any]) -> str:
        return str(d.get("publishDate") or d.get("date") or "")

    candidates.sort(key=_key, reverse=True)
    return candidates[0]


def disclosure_url(disclosure_id: str) -> str:
    return KAP_DISCLOSURE_URL.format(disclosure_id=disclosure_id)


def parse_stock_weights(disclosure_id: str) -> dict[str, float]:
    """Best-effort extraction of {ticker: weight_percent} from a disclosure page.

    Tries the HTML disclosure page first (KAP often renders the standard
    "Fon Portföy Dağılım Raporu" form directly as an HTML table). Returns
    an empty dict if nothing recognizable is found — callers should treat
    that as "couldn't parse, fall back to sending the raw link" rather
    than as "fund holds no stocks".
    """
    url = disclosure_url(disclosure_id)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    weights: dict[str, float] = {}
    for match in TICKER_ROW_RE.finditer(html):
        ticker, pct_str = match.group(1), match.group(2)
        try:
            pct = float(pct_str.replace(",", "."))
        except ValueError:
            continue
        # Guard against picking up incidental uppercase words (headers,
        # currency codes) by requiring a plausible weight range.
        if 0 < pct <= 100:
            weights[ticker] = pct
    return weights
