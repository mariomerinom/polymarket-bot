# Polymarket Autoresearch Bot

An automated prediction market analysis system using Karpathy's autoresearch feedback loop pattern.

## How It Works

```
fetch_markets.py  →  Pulls active markets from Polymarket (fixed, never modified)
predict.py        →  Sends markets to agent prompts via Claude API
score.py          →  Calculates Brier scores on resolved markets
evolve.py         →  Identifies worst agent, generates prompt modification
prompts/*.md      →  The ONLY thing that gets modified (like train.py in autoresearch)
program.md        →  Strategy & rules (human-refined, read by agents)
```

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
cd src/

# Run a full cycle
python run_cycle.py --cycle 1 --markets 5

# Just fetch markets
python fetch_markets.py

# Just run predictions
python predict.py --cycle 1 --markets 5

# Mark a market as resolved and see scores
python score.py --resolve MARKET_ID 1   # 1=YES, 0=NO
python score.py                         # Print scorecard

# Evolve worst agent after enough resolutions
python run_cycle.py --evolve --cycle 2

# Full auto cycle (fetch → predict → score → evolve)
python run_cycle.py --full --cycle 2
```

## The Autoresearch Loop

1. **Fetch** active markets from Polymarket Gamma API
2. **Predict** — 3 agents (base_rate, news_momentum, contrarian) each estimate probabilities
3. **Wait** for markets to resolve
4. **Score** — Brier score each agent. Lower = better.
5. **Evolve** — Worst agent's prompt gets ONE modification suggested by Claude
6. **Repeat** — Run next cycle with modified prompt. Keep change if Brier improves, revert if not.

## Agents

| Agent | File | Strategy |
|-------|------|----------|
| Base Rate | `prompts/base_rate.md` | Historical frequencies, reference classes, statistical priors |
| News Momentum | `prompts/news_momentum.md` | Recent news flow, sentiment shifts, information lag |
| Contrarian | `prompts/contrarian.md` | Overconfidence detection, herding, mispriced consensus |

## Data

All predictions, scores, and evolution history stored in `data/predictions.db` (SQLite).
Evolution log also saved as `data/evolution_log.json` for easy review.

## Extending

- Add new agents: create a new `.md` file in `prompts/` — it's auto-discovered
- Change model: edit `MODEL` in `predict.py` and `evolve.py`
- Add trading: integrate `py-clob-client` SDK for live Polymarket orders (requires wallet auth)
