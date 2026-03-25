# Polymarket BTC 5-Min Prediction Bot

A zero-cost prediction system for Polymarket's "Bitcoin Up or Down" 5-minute candle markets. Uses regime-filtered momentum signals from BTC price data — no LLM, no API keys, pure computation.

**[Live Dashboard](https://mariomerinom.github.io/polymarket-bot/)**

## How It Works

```
fetch_markets.py  →  Pulls live BTC 5-min markets from Polymarket Gamma API
btc_data.py       →  Fetches 20 × 5-min candles from Kraken (Coinbase fallback)
predict.py        →  Regime filter + momentum signal → conviction score
score.py          →  Auto-resolves markets, calculates Brier scores
dashboard.py      →  Generates static HTML dashboard with P&L analytics
```

## Strategy (V4 Momentum)

1. Fetch 20 recent 5-min BTC/USD candles
2. Compute regime: volatility level × autocorrelation pattern
3. If mean-reverting (autocorr < -0.15) → **skip** (no edge)
4. If streak ≥ 3 same direction + exhaustion signal → **ride the streak** (momentum)
5. Otherwise → skip

**Exhaustion signals:** compression (shrinking ranges), volume spike (>1.8× avg), shrinking last candle (<70% of avg range).

### History

| Version | Strategy | Win Rate | ROI | Cost/day |
|---------|----------|----------|-----|----------|
| V1-V2 | 3 LLM agents (Claude) | 50-55% | -13% to +19% | $1.50 |
| V3 | Contrarian (fade streaks) | 37% | -18% | $0 |
| **V4** | **Momentum (ride streaks)** | **63%** | **Validating** | **$0** |

V3 contrarian faded streaks and lost — Polymarket already prices in BTC patterns. Inverting to momentum (ride) captures the pricing lag.

## Architecture

Runs autonomously on **GitHub Actions** with self-rescheduling (every ~5 min via `repository_dispatch`).

- **Data**: Kraken public REST (primary), Coinbase Exchange (fallback)
- **Database**: `data/predictions.db` (SQLite, auto-committed by CI)
- **Dashboard**: GitHub Pages (`docs/index.html`, auto-generated)
- **Tests**: 44+ tests gate every CI commit

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

No API keys required — all data sources are free and public.

## Usage

```bash
cd src/

# Run a single prediction cycle
python run_cycle.py --cycle 1

# Score resolved markets only
python run_cycle.py --score-only

# Run tests
python -m pytest tests/ -v
```

## P&L Simulation

Binary options P&L is asymmetric:
- **Win**: `bet_size × (1/market_price - 1)` — variable, depends on entry price
- **Loss**: `-bet_size` — fixed ($75 for medium conviction, $200 for high)

| Conviction | Bet Size | When |
|-----------|----------|------|
| 0 (skip) | $0 | No streak or no exhaustion |
| 2 (low) | $0 | Signal fires but low confidence |
| 3 (medium) | $75 | Streak + exhaustion + medium/high confidence |
| 4+ (high) | $200 | Streak ≥ 5 or multiple exhaustion signals |

## Key Documents

- [`docs/BACKTEST_FINDINGS.md`](docs/BACKTEST_FINDINGS.md) — V1→V4 results with regime analysis
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Execution plan and validation gates
- [`docs/TESTING.md`](docs/TESTING.md) — Test strategy and CI pipeline
- [`docs/BREAK_FIX_LOG.md`](docs/BREAK_FIX_LOG.md) — Production incident log
