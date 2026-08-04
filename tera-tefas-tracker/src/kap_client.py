"""KAP (Kamuyu Aydınlatma Platformu) client — per-stock signal for Tera's funds.

TEFAS only publishes asset-CLASS allocation (see tefas_client.py), never
individual stock holdings. A KAP monthly "Fon Portföy Dağılım Raporu"
does not appear to exist for Tera's funds (checked live: zero matches
across 90 disclosures / 180 days for the fund manager). Instead, the real
usable per-stock signal is KAP's "Pay Alım Satım Bildirimi" (Shares
Transaction Notification) — filed by TERA PORTFÖY YÖNETİMİ A.Ş. whenever
one of its funds crosses an ownership threshold in a listed company's
stock. Each notification's body names both the traded company ticker(s)
("İlgili Şirketler") and the Tera fund code(s) involved ("İlgili
Fonlar") — this is a near-real-time signal of what Tera's funds are
accumulating, confirmed live via a debug probe (see git history for
tera-debug-probe.yml).

Endpoints (confirmed live via a one-off debug probe run in GitHub
Actions):
  - member text search: GET /tr/api/member/filter/{query}
  - disclosure search:  POST /tr/api/disclosure/members/byCriteria
  - disclosure detail:  GET /tr/api/notification/attachment-detail/{id}

Note: there are two distinct Tera entities in KAP — "TERA PORTFÖY
YÖNETİMİ A.Ş." (the fund manager, files fund-related disclosures) and
"TERA YATIRIM MENKUL DEĞERLER A.Ş." (the brokerage, files its own
corporate disclosures only). This module uses the former.
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
MEMBER_FILTER_URL = f"{KAP_BASE}/tr/api/member/filter/{{query}}"
DISCLOSURE_PAGE_URL = f"{KAP_BASE}/tr/Bildirim/{{disclosure_index}}"

# TERA PORTFÖY YÖNETİMİ A.Ş. — the fund manager, confirmed via
# /tr/api/member/filter/tera and by finding its "Pay Alım Satım
# Bildirimi" filings naming Tera's own fund codes (TLY, TMV, THF, T3B...).
TERA_PORTFOY_MEMBER_OID = "5553acdacf15471ba80c28eb45cdd9e7"

SHARE_TRANSACTION_SUBJECT = "Pay Alım Satım Bildirimi"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{KAP_BASE}/tr/bildirim-sorgu",
}

# The disclosure body lists related companies/funds as e.g.
# "İlgili Şirketler ... [ISVEA]" / "İlgili Fonlar ... [TLY, TMV]".
RELATED_COMPANIES_RE = re.compile(r"İlgili Şirketler.*?\[([^\]]*)\]", re.DOTALL)
RELATED_FUNDS_RE = re.compile(r"İlgili Fonlar.*?\[([^\]]*)\]", re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")

# The explanation prose always reads like: "...toplam pay oranı
# 8.533441%'den 2.430599%'a düşmüştür." (or "...yükselmiştir" /
# "...ulaşmıştır" for increases) — capture the before/after ownership
# percentages regardless of which verb follows.
OWNERSHIP_CHANGE_RE = re.compile(r"toplam pay oranı\s+([\d.]+)%'\w+\s+([\d.]+)%'\w+")

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


def find_member_oid(name_contains: str) -> str | None:
    """Find a KAP member's mkkMemberOid by (partial, case-insensitive) name
    via KAP's free-text member search."""
    query = name_contains.strip()
    resp = _get_session().get(MEMBER_FILTER_URL.format(query=query), timeout=20)
    resp.raise_for_status()
    items = resp.json()

    needle = query.lower()
    for item in items or []:
        title = str(item.get("title") or "")
        if needle in title.lower():
            return item.get("mkkMemberOid")
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


def find_new_share_transactions(
    member_oid: str, since_index: int, days_back: int = 15
) -> list[dict[str, Any]]:
    """Return 'Pay Alım Satım Bildirimi' disclosures newer than `since_index`.

    Sorted oldest-first so callers can process in publish order and track
    the new high-water mark as they go.
    """
    disclosures = search_disclosures(member_oid, days_back)
    matches = [
        d
        for d in disclosures
        if str(d.get("subject") or "") == SHARE_TRANSACTION_SUBJECT
        and int(d.get("disclosureIndex") or 0) > since_index
    ]
    matches.sort(key=lambda d: int(d.get("disclosureIndex") or 0))
    return matches


def disclosure_url(disclosure_index: int | str) -> str:
    return DISCLOSURE_PAGE_URL.format(disclosure_index=disclosure_index)


def parse_transaction_notification(disclosure_index: int | str) -> dict[str, Any]:
    """Extract company/fund codes and the before/after ownership % from a
    'Pay Alım Satım Bildirimi' notification's body.

    Returns {"companies": [...], "funds": [...], "old_pct": float | None,
    "new_pct": float | None}. Missing pieces come back empty/None — callers
    should treat that as "couldn't parse" rather than "no data".
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

    companies_match = RELATED_COMPANIES_RE.search(html)
    funds_match = RELATED_FUNDS_RE.search(html)
    companies = (
        [c.strip() for c in companies_match.group(1).split(",") if c.strip()]
        if companies_match
        else []
    )
    funds = (
        [f.strip() for f in funds_match.group(1).split(",") if f.strip()]
        if funds_match
        else []
    )

    # The ownership-change sentence is prose split across table cells in
    # the raw HTML; strip tags and collapse whitespace/entities so it
    # reads as one continuous sentence before matching.
    plain_text = HTML_TAG_RE.sub(" ", html).replace("&#160;", " ")
    plain_text = re.sub(r"\s+", " ", plain_text)

    old_pct = new_pct = None
    change_match = OWNERSHIP_CHANGE_RE.search(plain_text)
    if change_match:
        try:
            old_pct = float(change_match.group(1))
            new_pct = float(change_match.group(2))
        except ValueError:
            old_pct = new_pct = None

    return {"companies": companies, "funds": funds, "old_pct": old_pct, "new_pct": new_pct}
