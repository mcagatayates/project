# Example commands

Paper trading with a virtual $100 balance (real market data, no real money, no API keys, no `pm-hl-conservative-plus-repo` needed):

```bash
python3 scripts/btc5m_paper.py --profile conservative --start-balance 100 --minutes 120
```

Check accumulated virtual PnL any time by re-running with the same `--ledger` path (default `runtime/paper_ledger.json`); add `--reset` to start a fresh $100.

Dry-run (safe validation):

```bash
.venv/bin/python scripts/test_btc_5m_session_exit_sl.py --profile conservative
```

Real execution (conservative):

```bash
.venv/bin/python scripts/test_btc_5m_session_exit_sl.py --profile conservative --execute
```

Real execution (aggressive):

```bash
.venv/bin/python scripts/test_btc_5m_session_exit_sl.py --profile aggressive --execute
```
