# Polymarket BTC 5-Min Candle — Program Rules

## Objective
Maximize prediction accuracy (minimize Brier score) on Polymarket's "Bitcoin Up or Down" 5-minute candle markets using a multi-agent feedback loop.

## Architecture
This follows Karpathy's autoresearch pattern adapted for prediction markets:

```
fetch_markets.py  →  Fixed. Fetches live BTC 5-min markets. Never modified.
predict.py        →  Fixed. Sends markets to agents via Claude API. Never modified.
score.py          →  Fixed. Auto-resolves from API, calculates Brier scores. Never modified.
evolve.py         →  Fixed. Identifies worst agent, suggests ONE prompt change. Never modified.
prompts/*.md      →  The ONLY thing that gets modified. Each agent has a prompt file.
program.md        →  This file. Human-refined strategy. Agents read but don't modify.
```

## The Loop
1. `fetch_markets.py` polls Polymarket Gamma API for active BTC 5-min "Up or Down" markets
2. `predict.py` sends each market + agent prompt to Claude → structured JSON prediction
3. Predictions stored in `data/predictions.db` (SQLite)
4. `score.py` checks for resolved markets via API, calculates Brier score per agent
5. `evolve.py` (every ~10 resolved markets) identifies worst agent → Claude suggests ONE prompt modification
6. If Brier improves by > 0.01 after next batch: keep change. Otherwise: revert.

## Market Selection
- **Market type**: "Bitcoin Up or Down" 5-minute candle markets only
- **Source**: Polymarket Gamma API with `end_date_min` filter for currently active markets
- **Filter**: Title must match "Bitcoin" + 5-minute time window regex
- **Resolution**: Automatic — candle closes, market resolves YES (close ≥ open) or NO

## Agent Roster
- `prompts/base_rate.md` — Statistical priors: base rate (~50%), time-of-day, autocorrelation, mean reversion
- `prompts/news_momentum.md` — Short-term momentum, trending vs ranging regime, macro catalysts
- `prompts/contrarian.md` — Mean-reversion, exhaustion signals, fading overcrowded moves

## Prediction Output
Each agent returns structured JSON:
```json
{
  "market": "BTC Up or Down 5min",
  "market_price": 0.XX,
  "estimate": 0.XX,
  "edge": 0.XX,
  "confidence": "low|medium|high",
  "wrong_if": "..."
}
```

## Confidence Calibration
Agents must rate confidence honestly:
- **low**: Near 50%, no real edge. Most predictions should be low confidence.
- **medium**: Multiple signals align, estimate deviates 4-8pp from 50%.
- **high**: Strong multi-signal convergence. Rare (~10-15% of predictions).

Confidence drives simulated position sizing: low=$50, medium=$100, high=$200.

## Scoring
- **Primary metric**: Brier score = (prediction - outcome)²
- **Lower is better**: Perfect = 0.0, worst = 1.0, coin flip = 0.25
- **Benchmark**: Market price accuracy — agents must beat the market's own implied probability
- **P&L simulation**: Tracks simulated profit/loss using confidence-based bet sizing at market odds

## Evolution Rules
- Evaluate after every ~10 resolved markets (tracked by evolution count vs total resolutions)
- Modify ONE thing in the worst agent's prompt per evolution
- Keep change if Brier improves by > 0.01, revert otherwise
- All changes logged in `data/evolution_log.json`
- Prompt backups saved as `.md.backup` before modification

## Deployment
- **CI**: GitHub Actions — predictions every 5 minutes, evolution every 2 hours
- **Dashboard**: Static HTML generated to `docs/index.html`, served via GitHub Pages
- **Concurrency**: Single workflow group prevents parallel runs
- **Timeouts**: 4 minutes for predict-and-score, 5 minutes for evolve
