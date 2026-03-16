# Polymarket BTC 5-Min Prediction Bot

An autonomous prediction system for Polymarket's "Bitcoin Up or Down" 5-minute candle markets, using Karpathy's autoresearch feedback loop pattern. Three AI agents predict each candle, get scored, and the worst agent's prompt self-evolves.

**[Live Dashboard](https://mariomerinom.github.io/polymarket-bot/)**

## How It Works

```
fetch_markets.py  →  Pulls live BTC 5-min markets from Polymarket Gamma API
predict.py        →  3 agents estimate probability via Claude API (sonnet)
score.py          →  Auto-resolves markets, calculates Brier scores
evolve.py         →  Identifies worst agent, generates ONE prompt modification
prompts/*.md      →  The ONLY thing that gets modified (the "weights")
program.md        →  Strategy & rules (human-refined, read by agents)
```

## Architecture

The bot runs autonomously on **GitHub Actions**:

| Workflow | Schedule | What it does |
|----------|----------|-------------|
| `predict-and-score` | Every 5 minutes | Fetch → Predict → Score → Update dashboard |
| `evolve` | Every 2 hours | Evaluate agents → Evolve worst performer (if 10+ new resolutions) |

Results are published to **GitHub Pages** as a static dashboard with:
- Win/loss rates and streaks per agent
- Simulated P&L with confidence-based position sizing
- Rolling accuracy time series
- Confidence calibration analysis
- Agent vs coin-flip comparison
- Evolution history

## Agents

| Agent | Prompt | Strategy |
|-------|--------|----------|
| Base Rate | `prompts/base_rate.md` | Statistical priors: time-of-day, autocorrelation, mean reversion. Max ±10pp from 50% |
| News Momentum | `prompts/news_momentum.md` | Short-term momentum + macro catalysts. Up to ±15pp from 50% with strong catalyst |
| Contrarian | `prompts/contrarian.md` | Mean-reversion when market is mispriced. Fades stretched moves up to 12pp |

Each agent outputs structured JSON with `estimate`, `edge`, `confidence` (low/medium/high), and reasoning fields.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Required environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### Run a single cycle locally
```bash
cd src/
python ci_run.py
```

### Run continuously (local)
```bash
cd src/
python run_loop.py
```

### Manual CLI
```bash
cd src/

# Fetch markets
python fetch_markets.py

# Run predictions for a cycle
python predict.py --cycle 1 --markets 5

# Score resolved markets
python score.py

# Evolve worst agent
python evolve.py

# Full manual cycle
python run_cycle.py --full --cycle 2
```

### Local dashboard
```bash
cd src/
python dashboard.py  # http://localhost:5050
```

## Data

- **Database**: `data/predictions.db` (SQLite) — markets, predictions, evolution log
- **Evolution log**: `data/evolution_log.json` — human-readable change history
- **Dashboard**: `docs/index.html` — auto-generated static HTML

## Tech Stack

- **Model**: Claude Sonnet (claude-sonnet-4-6) via Anthropic API
- **Market data**: Polymarket Gamma API (read-only, no auth required)
- **CI/CD**: GitHub Actions (cron workflows)
- **Dashboard**: GitHub Pages (static HTML from `docs/`)
- **Database**: SQLite
- **Language**: Python 3.14

## P&L Simulation

The dashboard simulates financial returns using confidence-based position sizing:

| Confidence | Bet Size |
|-----------|----------|
| Low | $50 |
| Medium | $100 |
| High | $200 |

Profit on correct prediction: `bet_size × (1/market_price - 1)`
Loss on incorrect prediction: `-bet_size`

## Extending

- **Add agents**: Create a new `.md` file in `prompts/` — auto-discovered by `predict.py`
- **Change model**: Edit `MODEL` constant in `predict.py` and `evolve.py`
- **Live trading**: See `docs/DEPLOYMENT_PLAN.md` for what's needed to place real bets
