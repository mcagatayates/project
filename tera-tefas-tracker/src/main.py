"""Daily orchestrator: run once, send (at most) one Telegram message.

Checks:
  1. TEFAS daily asset-class allocation vs. the previous trading day, for
     every Tera Portföy fund (reliable, always runs).
  2. Whether KAP published a new "Pay Alım Satım Bildirimi" (shares
     transaction notification) for TERA PORTFÖY YÖNETİMİ A.Ş. since we
     last checked — each one names both the stock ticker and the Tera
     fund(s) that crossed an ownership threshold in it, which is the
     real per-stock "what are they buying" signal (there is no monthly
     portfolio-distribution report for these funds — checked live).

State (last-seen snapshots / disclosure index) is persisted to
state/state.json, which the GitHub Actions workflow commits back to the
repo after each run so the next day's comparison has something to diff
against.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kap_client
import tefas_client
import telegram_notify

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "state.json"

# Known Tera Portföy Yönetimi A.Ş. funds (TEFAS fon kodu -> tam adı).
# Update this list if Tera launches or closes a fund — cross-check against
# https://www.teraportfoy.com/fonlarimiz
TERA_FUNDS = {
    "THF": "TERA PORTFÖY HİSSE SENEDİ (TL) FONU",
    "FSU": "TERA PORTFÖY FON SEPETİ FONU",
    "TP2": "TERA PORTFÖY PARA PİYASASI (TL) FONU",
    "TLV": "TERA PORTFÖY PARA PİYASASI KATILIM (TL) FONU",
    "T3B": "TERA PORTFÖY ÜÇÜNCÜ HİSSE SENEDİ SERBEST (TL) FON",
    "TLY": "TERA PORTFÖY BİRİNCİ SERBEST FON",
    "TMV": "TERA PORTFÖY ALGORİTMİK STRATEJİLER SERBEST FON",
}

# Only alert on allocation moves at least this many percentage points,
# to avoid noise from rounding-level daily wobble.
MIN_DAILY_DELTA = 1.0


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"tefas_daily": {}, "kap_transactions": {"last_seen_index": 0}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))


def check_tefas_daily(state: dict, errors: list[str]) -> list[str]:
    lines = []
    today = dt.date.today()
    for code, name in TERA_FUNDS.items():
        try:
            prev, latest = tefas_client.latest_two_snapshots(code, today)
            if latest is None:
                errors.append(f"{code}: TEFAS'ta hiç veri bulunamadı.")
                continue

            latest_weights = tefas_client.allocation_weights(latest)
            state.setdefault("tefas_daily", {})

            if prev is not None:
                prev_weights = tefas_client.allocation_weights(prev)
            else:
                stored = state["tefas_daily"].get(code)
                prev_weights = stored["weights"] if stored else {}

            gains = []
            for col, new_val in latest_weights.items():
                old_val = prev_weights.get(col, 0.0)
                delta = new_val - old_val
                if delta >= MIN_DAILY_DELTA:
                    gains.append((col, old_val, new_val, delta))
            gains.sort(key=lambda g: g[3], reverse=True)

            if gains:
                parts = ", ".join(
                    f"{col} {old:.1f}%→{new:.1f}% (+{delta:.1f})"
                    for col, old, new, delta in gains
                )
                lines.append(f"📈 <b>{code}</b> ({name}): {parts}")

            state["tefas_daily"][code] = {
                "date": latest.get("tarih") or latest.get("TARIH"),
                "weights": latest_weights,
            }
        except Exception as exc:  # noqa: BLE001 - keep other funds running
            errors.append(f"{code}: TEFAS kontrolü başarısız — {exc}")
    return lines


def check_kap_transactions(state: dict, errors: list[str]) -> list[str]:
    lines = []
    state.setdefault("kap_transactions", {"last_seen_index": 0})
    last_seen = int(state["kap_transactions"].get("last_seen_index", 0))

    try:
        new_disclosures = kap_client.find_new_share_transactions(
            kap_client.TERA_PORTFOY_MEMBER_OID, last_seen
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"KAP pay alım/satım kontrolü başarısız — {exc}")
        return lines

    max_index = last_seen
    for disclosure in new_disclosures:
        idx = int(disclosure.get("disclosureIndex") or 0)
        max_index = max(max_index, idx)
        date = disclosure.get("publishDate", "")
        url = kap_client.disclosure_url(idx)

        try:
            parsed = kap_client.parse_transaction_notification(idx)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"KAP bildirimi {idx} ayrıştırılamadı — {exc}")
            continue

        companies = parsed.get("companies") or []
        funds = [f for f in (parsed.get("funds") or []) if f in TERA_FUNDS]
        if not companies or not funds:
            lines.append(
                f"🔔 Yeni bir Pay Alım Satım Bildirimi geldi ama otomatik "
                f"ayrıştırılamadı, manuel bakman gerekebilir ({date}): {url}"
            )
            continue

        # One line per fund, stacked, rather than joining multiple funds
        # into a single comma-separated line — easier to scan when a
        # disclosure covers several Tera funds at once.
        company_str = ", ".join(companies)
        for fund in funds:
            lines.append(
                f"🔔 <b>{fund}</b> → <b>{company_str}</b> hissesinde pay alım/satım "
                f"bildirimi ({date})\n{url}"
            )

    state["kap_transactions"]["last_seen_index"] = max_index
    return lines


def main() -> None:
    state = load_state()
    errors: list[str] = []

    daily_lines = check_tefas_daily(state, errors)
    transaction_lines = check_kap_transactions(state, errors)

    save_state(state)

    today_str = dt.date.today().strftime("%d.%m.%Y")
    sections = [f"<b>Tera Portföy TEFAS Takip — {today_str}</b>"]

    if daily_lines:
        sections.append("\n".join(["", "<u>Günlük varlık sınıfı değişimi:</u>", *daily_lines]))
    else:
        sections.append("\nGünlük: dikkate değer bir varlık sınıfı değişimi yok.")

    if transaction_lines:
        sections.append(
            "\n".join(["", "<u>KAP pay alım/satım bildirimleri:</u>", *transaction_lines])
        )

    if errors:
        sections.append("\n".join(["", "<u>⚠️ Kontrol edilemeyenler:</u>", *errors]))

    telegram_notify.send_message("\n".join(sections))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Last-resort: make sure a broken run is at least visible in Actions
        # logs with a full traceback, instead of failing silently.
        traceback.print_exc()
        raise
