# Polymarket Autoresearch Program

## Objective
Maximize prediction accuracy (minimize Brier score) across resolved Polymarket markets using a multi-agent feedback loop.

## Architecture
This follows Karpathy's autoresearch pattern adapted for prediction markets:

```
prepare.py  →  Fixed. Fetches markets, calculates scores. Never modified by agents.
prompts/*   →  The ONLY thing that gets modified. Each agent has a prompt file.
program.md  →  This file. Human-refined strategy. Agents read but don't modify.
```

## The Loop
1. `fetch_markets.py` pulls active markets from Polymarket Gamma API
2. `predict.py` sends each market + agent prompt to Claude API → structured prediction
3. Predictions stored in `data/predictions.db` (SQLite)
4. On market resolution: `score.py` calculates Brier scores per agent
5. `evolve.py` identifies worst agent → uses Claude to suggest ONE prompt modification
6. If Brier improves after next batch: commit change. If not: git revert.

## Agent Roster
- `prompts/base_rate.md` — Historical base rates and reference classes
- `prompts/news_momentum.md` — Recent news flow and sentiment
- `prompts/contrarian.md` — Overconfidence detection and mispricing

## Market Selection Criteria
- Volume > $50,000 (enough liquidity to trust the price signal)
- Resolves within 30 days (faster feedback loop)
- Clear binary outcome (YES/NO, not multi-outcome)
- Skip markets with < 48 hours to resolution (too noisy)

## Scoring
- Primary metric: Brier score = (prediction - outcome)^2
- Lower is better. Perfect = 0.0, worst = 1.0
- Market itself is the benchmark — agents must beat market price accuracy

## Evolution Rules
- Evaluate after every 5 resolved markets per agent
- Modify ONE thing in the worst agent's prompt per cycle
- Run for 5 more resolutions before evaluating the change
- Keep change if Brier improved by > 0.01, revert otherwise
- Log all changes in data/evolution_log.json
