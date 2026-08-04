"""Daily orchestrator: run once, send (at most) one Telegram message.

Checks, for every Tera Portföy fund:
  1. TEFAS daily asset-class allocation vs. the previous trading day
     (reliable, always runs).
  2. Whether KAP published a new monthly per-stock "Fon Portföy Dağılım
     Raporu" since we last checked, and if so, which stocks gained weight
     vs. the prior report (best-effort, see kap_client.py).

State (last-seen snapshots) is persisted to state/state.json, which the
GitHub Actions workflow commits back to the repo after each run so the
next day's comparison has something to diff against.
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

# Known Tera Portföy Yönetimi A.Ş. funds (TEFAS fon kodu -> KAP arama adı).
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
MIN_MONTHLY_DELTA = 0.5


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"tefas_daily": {}, "kap_monthly": {}}


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
                "date": latest.get("TARIH"),
                "weights": latest_weights,
            }
        except Exception as exc:  # noqa: BLE001 - keep other funds running
            errors.append(f"{code}: TEFAS kontrolü başarısız — {exc}")
    return lines


def check_kap_monthly(state: dict, errors: list[str]) -> list[str]:
    lines = []
    for code, name in TERA_FUNDS.items():
        try:
            report = kap_client.find_latest_portfolio_report(name)
            if report is None:
                continue

            disclosure_id = str(report.get("disclosureIndex") or report.get("id") or "")
            if not disclosure_id:
                continue

            state.setdefault("kap_monthly", {})
            stored = state["kap_monthly"].get(code)
            if stored and stored.get("disclosure_id") == disclosure_id:
                continue  # already processed this report

            new_weights = kap_client.parse_stock_weights(disclosure_id)
            url = kap_client.disclosure_url(disclosure_id)

            if not new_weights:
                lines.append(
                    f"📄 <b>{code}</b> ({name}): yeni bir KAP Portföy Dağılım Raporu "
                    f"yayınlandı ama otomatik ayrıştırılamadı, manuel bakman gerekebilir: {url}"
                )
                state["kap_monthly"][code] = {
                    "disclosure_id": disclosure_id,
                    "weights": stored.get("weights", {}) if stored else {},
                }
                continue

            old_weights = stored.get("weights", {}) if stored else {}
            gains = []
            for ticker, new_val in new_weights.items():
                old_val = old_weights.get(ticker, 0.0)
                delta = new_val - old_val
                if delta >= MIN_MONTHLY_DELTA:
                    gains.append((ticker, old_val, new_val, delta))
            gains.sort(key=lambda g: g[3], reverse=True)

            if gains:
                # Mirrors the "Ağırlık / Önceki / Fark" layout fund-tracking
                # apps show: one stock per line, weight, previous weight,
                # and the delta — brand-new positions show "yeni pozisyon"
                # instead of a 0.0% "Önceki".
                rows = []
                for ticker, old, new, delta in gains:
                    onceki = "yeni pozisyon" if old == 0.0 else f"Önceki %{old:.2f}"
                    rows.append(f"• {ticker}: %{new:.2f} ({onceki}, Fark +{delta:.2f})")
                lines.append(
                    f"🏦 <b>{code}</b> ({name}) — hisse ağırlığı artanlar:\n"
                    + "\n".join(rows)
                    + f"\n{url}"
                )
            elif old_weights:
                lines.append(
                    f"🏦 <b>{code}</b> ({name}): yeni KAP raporu geldi, "
                    f"belirgin bir ağırlık artışı yok.\n{url}"
                )

            state["kap_monthly"][code] = {
                "disclosure_id": disclosure_id,
                "weights": new_weights,
            }
        except Exception as exc:  # noqa: BLE001 - keep other funds running
            errors.append(f"{code}: KAP kontrolü başarısız — {exc}")
    return lines


def main() -> None:
    state = load_state()
    errors: list[str] = []

    daily_lines = check_tefas_daily(state, errors)
    monthly_lines = check_kap_monthly(state, errors)

    save_state(state)

    today_str = dt.date.today().strftime("%d.%m.%Y")
    sections = [f"<b>Tera Portföy TEFAS Takip — {today_str}</b>"]

    if daily_lines:
        sections.append("\n".join(["", "<u>Günlük varlık sınıfı değişimi:</u>", *daily_lines]))
    else:
        sections.append("\nGünlük: dikkate değer bir varlık sınıfı değişimi yok.")

    if monthly_lines:
        sections.append("\n".join(["", "<u>Aylık KAP hisse raporu:</u>", *monthly_lines]))

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
