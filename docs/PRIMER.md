# Polymarket Bot — Primer

**What this is:** A bot that bets on 5-minute and 15-minute "Bitcoin Up or Down" markets on [Polymarket](https://polymarket.com). It uses BTC price momentum to predict whether BTC will be higher or lower at the end of each window. No AI agents, no LLMs at runtime. Pure math from candlestick data. Cost: $0/day.

**Current performance:** 67.3% win rate on 217 resolved bets, ~$6,000 cumulative P&L (paper trading, simulated bets).

---

## How It Works (One Paragraph)

Every 5 minutes, GitHub Actions triggers the bot. The bot fetches 20 BTC candles from Kraken and Coinbase, checks if BTC has been moving in one direction for 3+ candles and shows signs of exhaustion (shrinking range, volume spike, or compression). If yes, it **rides the streak** — bets that BTC will continue in the same direction. It skips when the market is mean-reverting (autocorrelation < -0.15), the price is at extremes (>85% or <15%), or it's a dead trading hour. Bet sizes scale with conviction ($75 base, $200 for UP bets in the sweet spot, $300 when both exchanges agree).

---

## The Signal

```
20 BTC candles (Kraken + Coinbase)
        │
        ▼
┌─ Regime Filter ─────────────────────────────┐
│  Mean-reverting (autocorr < -0.15)? → SKIP  │
│  Trending / Neutral? → Continue              │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─ Streak Detection ──────────────────────────┐
│  3+ consecutive same-direction candles?      │
│  No → SKIP                                   │
│  Yes → Check exhaustion                      │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─ Exhaustion Signals (any one) ──────────────┐
│  • Compression: last 3 ranges shrinking     │
│  • Volume spike: last candle > 1.8x avg     │
│  • Shrinking range: last < 70% of avg       │
│  None? → SKIP                                │
│  Found? → RIDE the streak                    │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─ Conviction Scoring ────────────────────────┐
│  Base: conv 3 ($75)                         │
│  UP + price 20-70%: conv 4 ($200)           │
│  + Kraken/Coinbase agree: conv +1 (max 5)   │
│  Conv 5 = $300                              │
│  DOWN + NEUTRAL regime: conv 2 ($0, tracked)│
└─────────────────────────────────────────────┘
```

**Key principle:** This is a **momentum** system — we ride streaks, we don't fade them. An earlier version (V3) faded streaks and lost at 37% WR. Inverting to momentum validated at 67% WR. This is non-negotiable.

---

## Repository Map

### Core Pipeline (src/)

| File | What It Does |
|------|-------------|
| `ci_run.py` | Entry point for 5-min pipeline. Called by GitHub Actions every 5 minutes. |
| `ci_run_15m.py` | Entry point for 15-min pipeline. Separate DB, separate dashboard. |
| `predict.py` | The brain. Computes regime, detects streaks, applies gates, stores predictions. |
| `btc_data.py` | Fetches BTC candles from Kraken (primary) and Coinbase (secondary + consensus). |
| `fetch_markets.py` | Fetches active Polymarket markets via Gamma API. |
| `score.py` | Auto-resolves markets and computes Brier scores. |
| `dashboard.py` | Generates the static HTML dashboard (GitHub Pages). |
| `daily_report.py` | Daily performance report with alerts and optimization monitoring. |
| `optimization_tracker.py` | Registers, monitors, and flags active optimizations. |
| `backtest_native.py` | Backtests using historical Polymarket resolved markets (no external data). |

### Data (data/)

| File | What It Holds |
|------|-------------|
| `predictions.db` | Live 5-min predictions — the source of truth. CI auto-commits this. |
| `predictions_15m.db` | Live 15-min predictions. Fully isolated from 5m. |
| `backtest.db` | Historical Polymarket markets for backtesting. |

### CI/CD (.github/workflows/)

| Workflow | Schedule | What It Does |
|----------|----------|-------------|
| `predict-and-score.yml` | Every 5 min | Fetch markets → predict → resolve → dashboard → commit |
| `predict-15m.yml` | Every 15 min | Same, but for 15-min markets with relaxed thresholds |
| `daily-report.yml` | 06:00 CST daily | Performance report, optimization alerts, decision monitoring |

**Important:** CI auto-commits constantly. Always `git pull --rebase` before pushing. If the DB conflicts, your code changes win — CI regenerates the DB.

### Docs (docs/)

| File | Purpose |
|------|---------|
| `strategy.md` | Human-readable strategy for both pipelines |
| `signal-infrastructure-plan.md` | Multi-exchange data roadmap and NEUTRAL regime analysis |
| `decisions.md` | Tracked decisions with automated trigger conditions |
| `optimizations.json` | Active optimization registry (managed by `optimization_tracker.py`) |
| `ROADMAP.md` | Project phases and current status |
| `daily/` | One markdown file per day with WR, P&L, alerts |

### Tests (tests/)

105 tests. Run with `pytest tests/ -v`. Must pass before every commit.

---

## The Two Pipelines

### 5-Minute (Primary)
- Runs every 5 min via `predict-and-score.yml`
- `min_streak=3`, `autocorr_threshold=-0.15`
- All gates active: price, dead hour, cooldown, DOWN+NEUTRAL filter
- 217 bets at 67.3% WR

### 15-Minute (Experimental)
- Runs every 15 min via `predict-15m.yml`
- `min_streak=2` (30 min of movement ≈ 5m streak of 6)
- `autocorr_threshold=-0.20` (relaxed — noisier on fewer data points)
- `loose_mode=True` — 5m-derived gates disabled to gather unfiltered data
- Cross-timeframe: queries the 5m DB for recent streak context
- 12 resolved bets at 67% WR (small sample)

The pipelines are **fully isolated**: separate databases, separate dashboards, separate CI workflows. If 15m crashes, 5m is unaffected.

---

## Cross-Exchange Consensus

Every cycle fetches BTC candles from both Kraken and Coinbase. The consensus score compares their streak signals:

| Score | Meaning | Effect |
|-------|---------|--------|
| 2 | Both see same streak (length ≥ 2) | Conviction +1 (bigger bet) |
| 1 | One source only, or direction matches but streaks differ | No change |
| -1 | Exchanges disagree on direction | No change (tracked for analysis) |

Stored in the reasoning JSON for every prediction. Just shipped — collecting data.

---

## Active Optimizations

Every code change to the signal gets registered with a baseline and revert criteria. The daily report monitors progress automatically.

| Name | What | Baseline | Status |
|------|------|----------|--------|
| `direction_regime_filter` | Skip DOWN bets in NEUTRAL regime | 66.3% WR | 10/50 bets, 90% WR |
| `dead_hour_gate` | Skip UTC hours 3 and 21 | 66.3% WR | 10/50 bets, 90% WR |
| `15m_loose_mode` | Disable 5m gates on 15m pipeline | 66.7% WR | Collecting |
| `cross_exchange_consensus` | Conviction boost when Kraken+Coinbase agree | 67.4% WR | Just shipped |

**Rule:** 50 bets minimum before deciding anything. Anything less is noise.

---

## Validation Principles

These are enforced, not aspirational:

1. **Baseline before shipping.** Snapshot WR, P&L, bet count before every change.
2. **Revert criteria before shipping.** Decide what "failure" looks like while you're still objective.
3. **50-bet minimum.** Anything less is noise.
4. **Forward validation only.** The data that found the edge can't confirm it.
5. **Track the counterfactual.** Filtered predictions stored at conv=2 ($0) for comparison.
6. **One change at a time.** Can't attribute results to stacked changes.

---

## Tech Stack

- **Language:** Python 3.11+
- **Runtime:** GitHub Actions (cron every 5 min)
- **Data:** SQLite (predictions.db, committed to repo)
- **BTC Prices:** Kraken + Coinbase REST APIs (free, no auth)
- **Markets:** Polymarket Gamma API (free, no auth)
- **Dashboard:** Static HTML on GitHub Pages
- **Dependencies:** `requests`, `pytest`, `python-dotenv`, `flask` (4 packages)
- **LLM cost at runtime:** $0

---

## Quick Commands

```bash
# Run tests (always do this before committing)
pytest tests/ -v

# Check optimization status
python3 src/optimization_tracker.py summary

# Run a quick backtest (7 days)
python3 src/backtest_native.py --days 7

# Generate dashboard locally
python3 src/generate_dashboard.py

# Check project health
git pull
cat docs/daily/$(ls -t docs/daily/ | head -1)
python3 src/optimization_tracker.py summary
pytest tests/ -v
```

---

## What NOT to Do

- **Don't revert to contrarian/fading.** V3 faded streaks and lost at 37% WR. Momentum is the signal.
- **Don't add LLM agents at runtime.** V1/V2 cost $15-50/day for marginal signal. The current system runs for $0.
- **Don't ship without registering the optimization.** Use `python3 src/optimization_tracker.py register`.
- **Don't trust samples under 50 bets.** A 10-bet winning streak means nothing.
- **Don't push without pulling first.** CI commits every 5 minutes. You will conflict.
- **Don't commit `.env` or API keys.** The bot doesn't need any keys to run.
