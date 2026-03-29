---
name: backtest
description: >
  Run native Polymarket backtests against historical resolved markets.
  Use this skill when: the user says "backtest", "run backtest", "overnight backtest",
  "kick off backtest", "backtest results", "how did the backtest do", or "/backtest".
  Supports 5m and 15m pipelines. Can fetch historical data, replay signals, or both.
---

# Native Polymarket Backtest

Run the V4 momentum signal against historical resolved "Bitcoin Up or Down" markets using **only Polymarket data** — no external candle sources.

## Quick Reference

| Command | What it does |
|---------|-------------|
| `/backtest run` | Fetch + replay (default: 7 days, 5m) |
| `/backtest overnight` | Kick off 30-day fetch for both 5m and 15m in background |
| `/backtest results` | Show results from the last completed run |
| `/backtest replay` | Re-run signal replay on cached data (instant) |

## Commands

### 1. Run (fetch + replay)

```bash
git pull

# 7-day 5m (quick, ~20 min)
python3 src/backtest_native.py --days 7 --window 5m

# 7-day 15m
python3 src/backtest_native.py --days 7 --window 15m --db data/backtest_15m.db

# Custom date range
python3 src/backtest_native.py --start 2026-03-01 --end 2026-03-28 --window 5m
```

The Gamma API is slow (~5 min per day of history). For runs > 7 days, use the **overnight** command.

### 2. Overnight (background 30-day run)

Kick off both pipelines in background. User can close the terminal — logs are saved:

```bash
# 5m — runs in background
python3 src/backtest_native.py --days 30 --window 5m 2>&1 | tee data/backtest_30d_5m.log &

# 15m — runs in background
python3 src/backtest_native.py --days 30 --window 15m --db data/backtest_15m.db 2>&1 | tee data/backtest_30d_15m.log &
```

**Estimated runtime:** 2-3 hours per pipeline.

**Next morning, check results:**
```bash
tail -30 data/backtest_30d_5m.log
tail -30 data/backtest_30d_15m.log
```

### 3. Results (read last run)

If logs exist, read them:
```bash
tail -30 data/backtest_30d_5m.log   # 5m overnight results
tail -30 data/backtest_30d_15m.log  # 15m overnight results
```

For a fresh analysis from the cached DB (no API calls):
```bash
python3 src/backtest_native.py --replay-only
python3 src/backtest_native.py --replay-only --window 15m --db data/backtest_15m.db
```

Also query the DB directly for custom breakdowns:
```python
import sqlite3
db = sqlite3.connect('data/backtest.db')

# Overall
db.execute("""
    SELECT COUNT(*), SUM(correct), SUM(pnl)
    FROM backtest_results WHERE conviction >= 3
""").fetchone()

# By regime
db.execute("""
    SELECT regime, COUNT(*), SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END), SUM(pnl)
    FROM backtest_results WHERE conviction >= 3
    GROUP BY regime ORDER BY COUNT(*) DESC
""").fetchall()

# By direction + regime (most granular)
db.execute("""
    SELECT predicted_direction, regime, COUNT(*),
           SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END), SUM(pnl)
    FROM backtest_results WHERE conviction >= 3
    GROUP BY predicted_direction, regime ORDER BY COUNT(*) DESC
""").fetchall()
```

### 4. Replay (instant, no API calls)

Re-run the signal against already-fetched data. Useful for testing parameter changes:

```bash
# Default parameters
python3 src/backtest_native.py --replay-only

# Test with min-streak=2 (15m-style)
python3 src/backtest_native.py --replay-only --min-streak 2

# Test 15m
python3 src/backtest_native.py --replay-only --window 15m --db data/backtest_15m.db
```

## Key Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | 7 | Days of history to fetch |
| `--window` | 5m | Market window: `5m` or `15m` |
| `--min-streak` | 3 (5m) / 2 (15m) | Minimum consecutive same-direction outcomes |
| `--db` | `data/backtest.db` | Override DB path |
| `--fetch-only` | false | Only fetch, don't replay |
| `--replay-only` | false | Only replay cached data |
| `--start` / `--end` | — | Custom date range (YYYY-MM-DD) |

## What to Look For

When reviewing results, compare against live performance:

| Metric | Live (5m) | Backtest target |
|--------|-----------|-----------------|
| Win rate | 67% | > 60% |
| TRENDING WR | 86% | > 75% |
| NEUTRAL WR | 52% | < 55% (confirms filter) |
| Best streak | 3 | 3 |

**Red flags:**
- WR < 55% = signal may not generalize
- NEUTRAL WR > 60% = our `direction_regime_filter` may be wrong
- Streak=3 underperforms longer streaks = our min_streak threshold may be wrong

## Data Limitations

- **No pre-resolution prices.** The Gamma API only exposes `lastTradePrice` (post-resolution: 0.01 or 0.99). We use 0.50 as a fair-value assumption. **Win rate is the primary metric, not P&L.**
- **No server-side text filter.** Every market on Polymarket must be paginated through to find BTC 5m/15m markets. This is why fetches are slow.
- **Exhaustion signals are native.** Volume spike, price compression, and volume decline are computed from Polymarket market data — no Kraken/Coinbase.
