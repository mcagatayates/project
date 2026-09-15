#!/usr/bin/env python3
"""Paper-trading simulator for the BTC 5m momentum skill.

Uses the SAME live market data as the real runner (Polymarket Gamma API for
market resolution, public/unauthenticated CLOB order books for entry and
exit prices), but never places an order and never touches
pm_live_trade_runner.py, PM_PRIVATE_KEY, or any API credential. All money is
virtual: a JSON ledger file tracks a starting balance (default $100) and
every simulated trade's PnL. There is no --execute flag here on purpose --
this script is incapable of sending a real order.
"""
import argparse
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from test_btc_5m_session_exit_sl import (
    PROFILES,
    clob_best_bid,
    clob_side_prices,
    market_side_prices,
    resolve_active_current_5m_market,
    ts_utc,
)


def default_ledger_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "runtime" / "paper_ledger.json")


def load_ledger(path: str, start_balance: float) -> dict[str, Any]:
    p = Path(path)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "balance" in data:
                return data
        except Exception:
            pass
    return {
        "created_at": ts_utc(),
        "start_balance": start_balance,
        "balance": start_balance,
        "trades": [],
    }


def save_ledger(path: str, ledger: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_profile_defaults(args: argparse.Namespace) -> argparse.Namespace:
    prof = PROFILES.get(args.profile or "conservative", PROFILES["conservative"])
    if args.threshold is None:
        args.threshold = float(prof["threshold"])
    if args.stop_loss_pct is None:
        args.stop_loss_pct = float(prof["stop_loss_pct"])
    if args.exit_before_sec is None:
        args.exit_before_sec = int(prof["exit_before_sec"])
    if args.min_entry_seconds_left is None:
        args.min_entry_seconds_left = int(prof["min_entry_seconds_left"])
    if args.poll_sec is None:
        args.poll_sec = float(prof["poll_sec"])
    return args


def simulate_one_trade(args: argparse.Namespace, ledger: dict[str, Any], deadline: float) -> bool:
    """Wait for one entry signal and simulate it through to close.

    Returns True if a trade was recorded, False if the deadline passed
    with no entry (caller should stop the outer loop).
    """
    while time.time() < deadline:
        m = resolve_active_current_5m_market()
        if not m:
            time.sleep(args.poll_sec)
            continue

        try:
            g_up, g_dn, up_t, dn_t, slug, end_iso = market_side_prices(m)
        except Exception:
            time.sleep(args.poll_sec)
            continue

        try:
            end_ts = dt.datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp()
        except Exception:
            time.sleep(args.poll_sec)
            continue
        sec_left = max(0.0, end_ts - time.time())

        if sec_left < args.min_entry_seconds_left:
            time.sleep(args.poll_sec)
            continue

        try:
            up_ask, dn_ask, _min_spread = clob_side_prices(up_t, dn_t)
        except Exception:
            time.sleep(args.poll_sec)
            continue

        candidates: list[tuple[str, float, str]] = []
        if up_ask is not None and float(up_ask) >= args.threshold:
            candidates.append(("UP", float(up_ask), up_t))
        if dn_ask is not None and float(dn_ask) >= args.threshold:
            candidates.append(("DOWN", float(dn_ask), dn_t))

        if not candidates:
            time.sleep(args.poll_sec)
            continue

        side, entry_price, token_id = sorted(candidates, key=lambda x: x[1], reverse=True)[0]

        stake = min(args.stake_usd, ledger["balance"])
        if stake < 0.01:
            print(f"[{ts_utc()}] balance too low to open a position ({ledger['balance']:.4f})")
            return False

        shares = stake / entry_price
        sl_price = entry_price * (1.0 - args.stop_loss_pct)
        print(
            f"[{ts_utc()}] PAPER OPEN {side} slug={slug} entry={entry_price:.3f} "
            f"stake=${stake:.2f} shares={shares:.4f} sl_price={sl_price:.3f}"
        )

        close_reason = None
        exit_price = entry_price
        while True:
            now = time.time()
            if now >= (end_ts - args.exit_before_sec):
                close_reason = f"time_exit_{args.exit_before_sec}s_before_end"
                px = clob_best_bid(token_id)
                exit_price = px if px is not None else entry_price
                break
            try:
                px = clob_best_bid(token_id)
            except Exception:
                px = None
            if px is not None and px <= sl_price:
                close_reason = f"stop_loss_{int(args.stop_loss_pct * 100)}pct"
                exit_price = px
                break
            time.sleep(args.poll_sec)

        exit_price = max(0.0, min(1.0, float(exit_price)))
        proceeds = shares * exit_price
        pnl = round(proceeds - stake, 6)
        ledger["balance"] = round(ledger["balance"] - stake + proceeds, 6)

        trade = {
            "opened_at": ts_utc(),
            "market_slug": slug,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": round(shares, 6),
            "stake_usd": round(stake, 6),
            "proceeds_usd": round(proceeds, 6),
            "pnl_usd": pnl,
            "close_reason": close_reason,
            "balance_after": ledger["balance"],
        }
        ledger["trades"].append(trade)
        print(
            f"[{ts_utc()}] PAPER CLOSE {side} exit={exit_price:.3f} reason={close_reason} "
            f"pnl=${pnl:+.4f} balance=${ledger['balance']:.4f}"
        )
        return True

    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=["conservative", "aggressive"], default="conservative")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--stake-usd", type=float, default=5.0, help="Virtual stake per trade")
    ap.add_argument("--stop-loss-pct", type=float, default=None)
    ap.add_argument("--exit-before-sec", type=int, default=None)
    ap.add_argument("--min-entry-seconds-left", type=int, default=None)
    ap.add_argument("--poll-sec", type=float, default=None)
    ap.add_argument("--start-balance", type=float, default=100.0, help="Virtual starting balance in USD")
    ap.add_argument("--minutes", type=float, default=60.0, help="Total wall-clock minutes to simulate")
    ap.add_argument("--max-trades", type=int, default=None, help="Stop after this many simulated trades")
    ap.add_argument("--ledger", default=default_ledger_path(), help="Path to the JSON paper-trading ledger")
    ap.add_argument("--reset", action="store_true", help="Reset the ledger back to --start-balance")
    args = apply_profile_defaults(ap.parse_args())

    ledger = load_ledger(args.ledger, args.start_balance)
    if args.reset:
        ledger = {
            "created_at": ts_utc(),
            "start_balance": args.start_balance,
            "balance": args.start_balance,
            "trades": [],
        }

    print(
        f"[{ts_utc()}] paper trading start: balance=${ledger['balance']:.2f} "
        f"profile={args.profile} threshold={args.threshold} stake=${args.stake_usd:.2f} "
        f"(SIMULATION ONLY - no real orders, no API keys used)"
    )

    deadline = time.time() + args.minutes * 60
    trades_done = len(ledger["trades"])
    start_trades = trades_done

    try:
        while time.time() < deadline:
            if args.max_trades is not None and (trades_done - start_trades) >= args.max_trades:
                break
            if ledger["balance"] < 0.01:
                print(f"[{ts_utc()}] virtual balance depleted, stopping")
                break
            got_trade = simulate_one_trade(args, ledger, deadline)
            save_ledger(args.ledger, ledger)
            if not got_trade:
                break
            trades_done = len(ledger["trades"])
    except KeyboardInterrupt:
        print(f"[{ts_utc()}] interrupted by user")
    finally:
        save_ledger(args.ledger, ledger)

    total_trades = len(ledger["trades"]) - start_trades
    total_pnl = round(ledger["balance"] - ledger["start_balance"], 6) if start_trades == 0 else None
    print(f"[{ts_utc()}] paper trading summary: trades_this_run={total_trades} balance=${ledger['balance']:.4f}")
    if total_pnl is not None:
        print(f"[{ts_utc()}] total pnl since ledger start: ${total_pnl:+.4f} (started ${ledger['start_balance']:.2f})")
    print(f"ledger: {args.ledger}")


if __name__ == "__main__":
    main()
