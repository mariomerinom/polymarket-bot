# Postmortem: Dual Engine Processes + BTC 5m Paper Mode

**Date:** 2026-04-06
**Duration:** ~24 hours (from engine migration on Apr 5 to fix on Apr 6)
**Impact:** BTC 5m pipeline ran as PAPER on VPS instead of LIVE. 89 paper orders created, 0 live orders placed. Duplicate predictions (2 per market) and 2-3 orders per market per cycle. No capital lost (fail-closed), but missed ~24h of live trading.

---

## Symptom

Dashboard showed PAPER badges on BTC 5m Recent Bets despite pipeline config set to `"mode": "live"`. Multiple duplicate orders appeared for the same 5-minute market window — 3 rows per market, some at different limit prices.

## Root Causes

### 1. Two systemd services running the same process

Two separate systemd unit files — `botsy.service` and `polymarket-bot.service` — both ran `botsy_engine.py`. Both created independently during VPS setup at different times. Neither service was aware of the other.

Each engine process subscribed to the same websocket feeds, received the same candle-close events, and triggered the same pipelines. Result: 2 predictions per market per cycle, 2-3 orders per market.

### 2. BTC 5m was the only pipeline without a `trade.TRADING_ENABLED` override

`trade.py` evaluates `TRADING_ENABLED` at module import time (line 37):
```python
TRADING_ENABLED = _env("TRADING_ENABLED", "false").lower() == "true"
```

`botsy_engine.py` loads `.env` in its `main()` function (line 770-783), which sets `os.environ["TRADING_ENABLED"] = "true"`. Python's module cache means `trade.TRADING_ENABLED` is evaluated once — if `trade` gets imported before `.env` is loaded, it locks to `False`.

Every other pipeline already had an explicit override:
- `ci_run_15m.py`: `trade.TRADING_ENABLED = is_pipeline_live("btc_15m")`
- `ci_run_eth.py`: `trade.TRADING_ENABLED = is_pipeline_live("eth_5m")`
- `ci_run_bybit.py`: `bybit_trade.BYBIT_TRADING_ENABLED = is_pipeline_live("bybit")`

`ci_run.py` was the only pipeline that relied solely on the env var being set before import.

### Why one engine showed LIVE and the other PAPER

The `.env` loading in `botsy_engine.py` happens in `main()`, before any pipeline imports. On a fresh start, this works — env is set, then `ci_run` is imported, and `trade.TRADING_ENABLED` evaluates to `True`.

But the older engine process (PID 19392, started Apr 5) likely imported `trade.py` before `.env` was loaded during a previous code path or restart race condition. Once `TRADING_ENABLED = False` was cached in the module, it never changed. The newer process (PID 30504) started clean and got `True`.

Both engines raced to create predictions and orders. The logs showed alternating `Mode: LIVE` / `Mode: PAPER` lines — the two processes taking turns.

## Fix

1. **Killed stale engine** (PID 19392) and **disabled `polymarket-bot.service`** — only `botsy.service` runs now
2. **Added explicit override to `ci_run.py`**:
   ```python
   import trade
   from pipeline_control import is_pipeline_live
   # ...
   def main():
       trade.TRADING_ENABLED = is_pipeline_live("btc_5m")
   ```
3. **Restarted engine** with clean code on VPS

## Prevention

- All five pipelines now use `pipeline_control.is_pipeline_live()` as the source of truth for trading mode — not env vars at import time
- `polymarket-bot.service` disabled and should be deleted from VPS
- Regression test should verify only one engine process runs at a time (or that duplicate processes produce identical mode decisions)

## Timeline

| Time (UTC) | Event |
|------------|-------|
| Apr 5 ~afternoon | botsy_engine.py deployed on VPS, both services started |
| Apr 5 – Apr 6 | Both engines ran, one LIVE and one PAPER, creating duplicate predictions |
| Apr 6 14:35 | User noticed duplicate PAPER orders on dashboard |
| Apr 6 14:50 | Root cause identified: dual services + missing TRADING_ENABLED override |
| Apr 6 14:55 | Fix pushed: ci_run.py override added, stale engine killed, polymarket-bot.service disabled |
| Apr 6 14:55 | Engine restarted with fix |

## Lessons

1. **Module-level constants evaluated at import time are a trap.** If the env var isn't set before the first import, the constant is wrong forever. Always override at runtime, not import time.
2. **Check for duplicate processes after deploying new services.** `ps aux | grep <name>` and `systemctl list-units | grep <name>` should be part of every deployment checklist.
3. **Fail-closed saved us.** The default `TRADING_ENABLED = false` meant the bug caused paper orders, not duplicate live orders. $0 lost.
