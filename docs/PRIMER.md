# Polymarket Bot — Primer

**What this is:** A bot that bets on 5-minute and 15-minute "Bitcoin/Ethereum Up or Down" markets on [Polymarket](https://polymarket.com). It uses price momentum to predict whether BTC/ETH will be higher or lower at the end of each window. No AI agents, no LLMs at runtime. Pure math from candlestick data. Cost: $0/day.

**Current performance:**
- **BTC 5m:** 67% WR on 227+ bets, ~$8K cumulative P&L (paper). Live trading started 2026-03-31 at $25/bet.
- **BTC 15m:** 67% WR on 12 bets (small sample, paper).
- **ETH 5m:** Momentum signal deployed 2026-04-01 (paper, conv=2). Collecting data.

---

## How It Works (One Paragraph)

Every 5 minutes, GitHub Actions triggers the bot. The bot fetches 20 BTC candles from Kraken and Coinbase, checks if BTC has been moving in one direction for 3+ candles (a "streak"). If yes, it **rides the streak** — bets that BTC will continue in the same direction. It skips when the market is mean-reverting (autocorrelation < -0.15), the price is at extremes (>85% or <15%), or it's a dead trading hour (UTC 3 or 21). Production uses flat $25 bets via `py-clob-client` on Polygon. ETH runs the same momentum logic on a parallel pipeline.

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
│  Yes → RIDE the streak                       │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─ Gate Filters ──────────────────────────────┐
│  • Price gate: skip > 0.85 or < 0.15       │
│  • Dead hours: skip UTC 3 and 21            │
│  • DOWN+NEUTRAL: demote to conv=2 (tracked) │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─ Conviction & Sizing ──────────────────────┐
│  Conv ≥ 3 → $25 flat bet (live)            │
│  Conv 2 → $0 (paper, tracked)              │
│  Conv 0 → skip                             │
└─────────────────────────────────────────────┘
```

**Key principle:** This is a **momentum** system — we ride streaks, we don't fade them. An earlier version (V3) faded streaks and lost at 37% WR. Inverting to momentum validated at 67% WR. This is non-negotiable.

---

## Repository Map

### Core Pipeline (src/)

| File | What It Does |
|------|-------------|
| `ci_run.py` | Entry point for BTC 5-min pipeline. Called by GitHub Actions every 5 minutes. |
| `ci_run_15m.py` | Entry point for BTC 15-min pipeline. Separate DB, separate dashboard. |
| `ci_run_eth.py` | Entry point for ETH 5-min pipeline. Separate DB, separate dashboard. |
| `predict.py` | BTC brain. Computes regime, detects streaks, applies gates, stores predictions. |
| `predict_eth.py` | ETH brain. Same momentum signal, separate DB. Paper trading at conv=2. |
| `btc_data.py` | Fetches BTC candles from Kraken (primary) and Coinbase (secondary + consensus). |
| `eth_data.py` | Fetches ETH candles from Coinbase. |
| `fetch_markets.py` | Fetches active Polymarket markets via Gamma API. |
| `score.py` | Auto-resolves markets and computes Brier scores. |
| `trade.py` | Live order execution via `py-clob-client` on Polygon. Flat $25 bets. |
| `dashboard.py` | Generates the static HTML dashboard (GitHub Pages). |
| `daily_report.py` | Daily performance report with alerts and optimization monitoring. |
| `optimization_tracker.py` | Registers, monitors, and flags active optimizations. |
| `clob_depth.py` | Queries Polymarket CLOB for liquidity/spread data. |

### Kalshi Pipeline (src/)

| File | What It Does |
|------|-------------|
| `ci_run_kalshi.py` | Entry point for Kalshi BTC pipeline. Paper trading, 15-min cycles. |
| `kalshi_markets.py` | Fetches active Kalshi BTC markets via REST API. HMAC auth + mock mode. |
| `kalshi_data.py` | BTC candle wrapper (delegates to `btc_data.py` — BTC is BTC). |
| `kalshi_score.py` | Resolves Kalshi predictions via settlement API. |

### Data (data/)

| File | What It Holds |
|------|-------------|
| `predictions.db` | Live BTC 5-min predictions — the source of truth. CI auto-commits this. |
| `predictions_15m.db` | Live BTC 15-min predictions. Fully isolated from 5m. |
| `predictions_eth.db` | Live ETH 5-min predictions. Fully isolated from BTC. |
| `predictions_kalshi.db` | Kalshi BTC predictions. Phase 0 signal transfer test. |

### CI/CD (.github/workflows/)

| Workflow | Schedule | What It Does |
|----------|----------|-------------|
| `predict-and-score.yml` | Every 5 min | Fetch markets → predict → resolve → trade → dashboard → commit |
| `predict-15m.yml` | Every 15 min | Same, but for 15-min BTC markets with relaxed thresholds |
| `predict-eth-5m.yml` | Every 5 min | ETH pipeline: fetch → predict → resolve → dashboard → commit |
| `predict-kalshi.yml` | Every 15 min | Kalshi BTC pipeline: fetch → predict → resolve → dashboard → commit |
| `daily-report.yml` | 06:00 CST daily | Performance report, optimization alerts, decision monitoring |

**Important:** CI auto-commits constantly. Always `git pull --rebase` before pushing. If the DB conflicts, your code changes win — CI regenerates the DB.

### Docs (docs/)

| File | Purpose |
|------|---------|
| `strategy.md` | Human-readable strategy for all pipelines |
| `decisions.md` | Tracked decisions with automated trigger conditions |
| `ROADMAP.md` | Project phases and current status |
| `BREAK_FIX_LOG.md` | Production incident log |
| `daily/` | One markdown file per day with WR, P&L, alerts |
| `daily/eth_pipeline_acceptance_criteria.md` | ETH pipeline phased rollout plan |

### Tests (tests/)

~178 tests. Run with `pytest tests/ -v`. Must pass before every commit.

---

## The Three Pipelines

### BTC 5-Minute (Production)
- Runs every 5 min via `predict-and-score.yml`
- `min_streak=3`, `autocorr_threshold=-0.15`
- Gates: price, dead hour, DOWN+NEUTRAL filter
- 227+ bets at 67% WR (paper). Live trading at $25/bet started 2026-03-31.

### BTC 15-Minute (Paper)
- Runs every 15 min via `predict-15m.yml`
- `min_streak=2` (30 min of movement ≈ 5m streak of 6)
- `autocorr_threshold=-0.20` (relaxed — noisier on fewer data points)
- `loose_mode=True` — 5m-derived gates disabled to gather unfiltered data
- 12 resolved bets at 67% WR (small sample)

### ETH 5-Minute (Paper)
- Runs every 5 min via `predict-eth-5m.yml`
- Same momentum signal as BTC: ride streaks >= 3 in non-mean-reverting regime
- All predictions at conviction 2 (no money risked)
- Flipped from contrarian to momentum 2026-04-01 (contrarian lost at 33.3% WR on 54 bets; momentum counterfactual: 66.7%)
- Collecting 200+ resolved predictions before evaluating for live trading

The pipelines are **fully isolated**: separate databases, separate dashboards, separate CI workflows. If one crashes, the others are unaffected.

---

## Live Trading

Production uses `src/trade.py` with `py-clob-client` SDK on Polygon.

| Setting | Value |
|---------|-------|
| Bet size | $25 flat |
| Min conviction | 3 (conv < 3 = paper only) |
| Daily loss limit | $300 (circuit breaker) |
| Kill switch | `KILL_SWITCH=true` env var or `data/KILL_SWITCH` file |
| Slippage guard | Max bet capped at 90% of CLOB max@2% slippage |
| Order type | GTC limit orders (no market orders) |

Trading is controlled by `TRADING_ENABLED=true` in CI. Can be killed without code changes.

---

## Cross-Exchange Consensus

Every BTC cycle fetches candles from both Kraken and Coinbase. The consensus score compares their streak signals:

| Score | Meaning | Effect |
|-------|---------|--------|
| 2 | Both see same streak (length ≥ 2) | Tracked for analysis |
| 1 | One source only, or direction matches but streaks differ | No change |
| -1 | Exchanges disagree on direction | Tracked for analysis |

Stored in the reasoning JSON for every prediction.

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
- **ETH Prices:** Coinbase REST API (free, no auth)
- **Markets:** Polymarket Gamma API (free, no auth)
- **Trading:** `py-clob-client` SDK on Polygon (USDC)
- **Dashboard:** Static HTML on GitHub Pages
- **Dependencies:** `requests`, `pytest`, `python-dotenv`, `py-clob-client`
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

- **Don't revert to contrarian/fading.** V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). Momentum is the signal for both assets.
- **Don't add LLM agents at runtime.** V1/V2 cost $15-50/day for marginal signal. The current system runs for $0.
- **Don't ship without registering the optimization.** Use `python3 src/optimization_tracker.py register`.
- **Don't trust samples under 50 bets.** A 10-bet winning streak means nothing.
- **Don't push without pulling first.** CI commits every 5 minutes. You will conflict.
- **Don't commit `.env` or API keys.** Trading keys are in GitHub Secrets.
