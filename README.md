# Polymarket Crypto Prediction Bot

A zero-cost prediction system for Polymarket's "Up or Down" 5-minute and 15-minute candle markets. Uses regime-filtered momentum signals from price data — no LLM, no API keys at runtime, pure computation.

**[Live Dashboard](https://mariomerinom.github.io/polymarket-bot/)**

## How It Works

```
btc_data.py / eth_data.py  →  Fetches candles from Kraken + Coinbase
predict.py / predict_eth.py →  Regime filter + momentum signal → conviction score
trade.py                    →  Places $25 limit orders via py-clob-client (Polygon)
score.py                    →  Auto-resolves markets, calculates Brier scores
dashboard.py                →  Generates static HTML dashboards with P&L analytics
```

## Strategy (V4 Momentum)

1. Fetch 20 recent 5-min candles
2. Compute regime: volatility level × autocorrelation pattern
3. If mean-reverting (autocorr < -0.15) → **skip** (no edge)
4. If streak ≥ 3 same direction → **ride the streak** (momentum)
5. Apply gates: price extremes, dead hours, DOWN+NEUTRAL filter
6. Conviction ≥ 3 → $25 live bet. Conviction < 3 → paper only.

### Pipelines

| Pipeline | Signal | Status |
|----------|--------|--------|
| BTC 5m | Momentum (ride streaks) | **Production** — $25/bet |
| BTC 15m | Momentum (relaxed params) | Paper |
| ETH 5m | Momentum (ride streaks) | Paper |

### History

| Version | Strategy | Win Rate | Cost/day |
|---------|----------|----------|----------|
| V1-V2 | 3 LLM agents (Claude) | 50-55% | $1.50 |
| V3 | Contrarian (fade streaks) | 37% BTC, 33% ETH | $0 |
| **V4** | **Momentum (ride streaks)** | **67% BTC** | **$0** |

## Architecture

Runs autonomously on **GitHub Actions** (every ~5 min via `repository_dispatch`).

- **Data**: Kraken + Coinbase REST APIs (free, no auth)
- **Trading**: `py-clob-client` SDK on Polygon (USDC)
- **Database**: SQLite (auto-committed by CI)
- **Dashboard**: GitHub Pages (3 dashboards: BTC 5m, BTC 15m, ETH 5m)
- **Tests**: ~178 tests gate every CI commit

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

No API keys required for paper trading. Live trading requires Polygon wallet keys in GitHub Secrets.

## Usage

```bash
# Run tests (always before committing)
pytest tests/ -v

# Run a single BTC prediction cycle
python src/ci_run.py --cycle 1

# Run ETH prediction cycle
python src/ci_run_eth.py --cycle 1

# Check optimization status
python src/optimization_tracker.py summary
```

## Key Documents

- [`docs/strategy.md`](docs/strategy.md) — Current trading strategy for all pipelines
- [`docs/PRIMER.md`](docs/PRIMER.md) — Full system overview and repository map
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Project phases and validation gates
- [`docs/decisions.md`](docs/decisions.md) — Tracked decisions with automated triggers
- [`docs/BREAK_FIX_LOG.md`](docs/BREAK_FIX_LOG.md) — Production incident log
