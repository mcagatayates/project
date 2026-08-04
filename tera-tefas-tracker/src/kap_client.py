"""KAP (Kamuyu Aydınlatma Platformu) client — monthly per-stock fund holdings.

TEFAS only publishes asset-CLASS allocation (see tefas_client.py). Actual
per-security holdings ("Tera hangi hisseyi ne kadar tutuyor") are only
published by fund management companies through KAP's standardized
"Fon Portföy Dağılım Raporu" (Fund Portfolio Distribution Report), filed
monthly, within ~6 business days after each month closes.

Endpoints below follow KAP's actual (undocumented but observed) JSON API:
  - member roster lookup: /tr/api/company/items/{memberType}/{letter}
  - disclosure search:    POST /tr/api/disclosure/members/byCriteria
  - disclosure detail:    GET /tr/api/notification/attachment-detail/{id}

This was written and could not be live-tested against kap.org.tr from the
sandbox it was built in (no network access there) — treat it as
best-effort. If a fund's report can't be found or its table can't be
parsed, callers should fall back to sending a plain link rather than
staying silent or crashing the whole daily job.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

import requests

KAP_BASE = "https://www.kap.org.tr"
WARMUP_URL = f"{KAP_BASE}/tr/bildirim-sorgu"
SEARCH_URL = f"{KAP_BASE}/tr/api/disclosure/members/byCriteria"
DETAIL_URL = f"{KAP_BASE}/tr/api/notification/attachment-detail/{{disclosure_index}}"
ROSTER_URL = f"{KAP_BASE}/tr/api/company/items/{{member_type}}/{{letter}}"
DISCLOSURE_PAGE_URL = f"{KAP_BASE}/tr/Bildirim/{{disclosure_index}}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{KAP_BASE}/tr/bildirim-sorgu",
}

REPORT_SUBJECT_HINT = "portföy dağılım raporu"
ROW_RE = re.compile(r"<tr\b.*?>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<t[dh]\b.*?>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
# A plausible BIST ticker is 3-6 uppercase Latin/Turkish letters (as its
# own table cell, not just anywhere in text — avoids matching stray
# uppercase header words like "TARİH" or "ORAN").
TICKER_CELL_RE = re.compile(r"^[A-ZİÇŞĞÜÖ]{3,6}$")
PERCENT_CELL_RE = re.compile(r"([0-9]{1,3}[.,][0-9]{1,4})\s*%?$")

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    """A warmed-up session — KAP's WAF is reportedly more tolerant of
    requests that follow an initial page load rather than a cold POST."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
        try:
            _session.get(WARMUP_URL, timeout=15)
        except requests.RequestException:
            pass  # best-effort warmup; proceed regardless
    return _session


# KAP member-type codes worth trying when we don't know exactly how an
# entity is classified: "YK" covers brokerages/investment firms (e.g. a
# "Menkul Değerler A.Ş." that also runs fund management as a business
# line), "PYS" is dedicated portfolio management companies, "IGS" is
# BIST-listed companies.
DEFAULT_MEMBER_TYPES = ("YK", "PYS", "IGS")


def find_member_oid(name_contains: str, member_types: tuple[str, ...] = DEFAULT_MEMBER_TYPES) -> str | None:
    """Find a KAP member's mkkMemberOid by (partial, case-insensitive) name.

    Tries each member type in `member_types` in turn since KAP's
    classification of a given company (brokerage vs. dedicated portfolio
    manager vs. listed company) isn't something we can know for certain
    without querying.
    """
    letter = name_contains.strip()[0].upper()
    needle = name_contains.strip().lower()

    for member_type in member_types:
        url = ROSTER_URL.format(member_type=member_type, letter=letter)
        resp = _get_session().get(url, timeout=20)
        if not resp.ok:
            continue
        roster = resp.json()
        items = roster if isinstance(roster, list) else roster.get("data", roster.get("result", []))
        for item in items or []:
            title = str(item.get("title") or item.get("unvan") or "")
            if needle in title.lower():
                return item.get("mkkMemberOid") or item.get("memberOid")
    return None


def search_disclosures(member_oid: str, days_back: int = 40) -> list[dict[str, Any]]:
    """Search KAP for recent disclosures filed by a given member."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days_back)
    body = {
        "fromDate": start.isoformat(),
        "toDate": end.isoformat(),
        "mkkMemberOidList": [member_oid],
        "subjectList": [],
    }
    resp = _get_session().post(SEARCH_URL, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    disclosures = data if isinstance(data, list) else data.get("data", data.get("result", []))
    return disclosures or []


def find_latest_portfolio_report(member_oid: str, fund_name: str) -> dict[str, Any] | None:
    """Return the newest 'Fon Portföy Dağılım Raporu' disclosure for a fund, if any."""
    disclosures = search_disclosures(member_oid)
    fund_hint = fund_name.strip().lower()
    candidates = []
    for d in disclosures:
        subject = str(d.get("subject") or "").lower()
        if REPORT_SUBJECT_HINT not in subject:
            continue
        # A member files one report per fund; make sure this disclosure is
        # about *this* fund, not a sibling one, by requiring some overlap
        # between the fund's name and the disclosure subject.
        fund_words = [w for w in fund_hint.split() if len(w) > 3]
        if fund_words and not any(w in subject for w in fund_words):
            continue
        candidates.append(d)

    if not candidates:
        return None

    def _index(d: dict[str, Any]) -> int:
        try:
            return int(d.get("disclosureIndex") or 0)
        except (TypeError, ValueError):
            return 0

    candidates.sort(key=_index, reverse=True)
    return candidates[0]


def disclosure_url(disclosure_index: str) -> str:
    return DISCLOSURE_PAGE_URL.format(disclosure_index=disclosure_index)


def parse_stock_weights(disclosure_index: str) -> dict[str, float]:
    """Best-effort extraction of {ticker: weight_percent} from a disclosure.

    Returns an empty dict if nothing recognizable is found — callers
    should treat that as "couldn't parse, fall back to sending the raw
    link" rather than as "fund holds no stocks".
    """
    url = DETAIL_URL.format(disclosure_index=disclosure_index)
    resp = _get_session().get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    entries = payload if isinstance(payload, list) else [payload]
    html_parts: list[str] = []
    for entry in entries:
        body = entry.get("disclosureBody") if isinstance(entry, dict) else None
        if isinstance(body, list):
            html_parts.extend(str(b) for b in body)
        elif isinstance(body, str):
            html_parts.append(body)

    html = " ".join(html_parts)

    weights: dict[str, float] = {}
    for row_match in ROW_RE.finditer(html):
        cells = [
            HTML_TAG_RE.sub("", cell).strip()
            for cell in CELL_RE.findall(row_match.group(1))
        ]
        if len(cells) < 2:
            continue

        ticker = next((c for c in cells if TICKER_CELL_RE.match(c)), None)
        if ticker is None:
            continue

        pct = None
        for cell in cells:
            m = PERCENT_CELL_RE.search(cell)
            if m:
                try:
                    candidate = float(m.group(1).replace(",", "."))
                except ValueError:
                    continue
                if 0 < candidate <= 100:
                    pct = candidate
                    break
        if pct is not None:
            weights[ticker] = pct

    return weights
