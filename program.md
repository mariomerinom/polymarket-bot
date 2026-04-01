# Polymarket BTC 5-Min Candle — Program Rules (LEGACY)

> **This document is from the V1/V2 LLM agent era and is no longer active.**
> The multi-agent Claude prediction system was superseded by V4 zero-cost momentum
> (Part 5, `src/predict.py`). LLM agents cost $15-50/day and added marginal signal.
> V4 runs for $0/day with 67% WR.
>
> See `docs/strategy.md` for the current system.
> See `docs/ROADMAP.md` Part 3 for the history.

---

## Original Architecture (V1/V2, no longer running)

```
fetch_markets.py  →  Fixed. Fetches live BTC 5-min markets.
predict.py        →  Was: sends markets to agents via Claude API. Now: pure momentum signal.
score.py          →  Fixed. Auto-resolves from API, calculates Brier scores.
evolve.py         →  Was: identifies worst agent, suggests prompt changes. Now: removed.
prompts/*.md      →  Agent prompt files. No longer used.
program.md        →  This file.
```

## The Old Loop (no longer active)
1. `fetch_markets.py` polls Polymarket Gamma API for active BTC 5-min markets
2. `predict.py` sent each market + agent prompt to Claude → structured JSON prediction
3. Predictions stored in `data/predictions.db`
4. `score.py` checks for resolved markets, calculates Brier score per agent
5. `evolve.py` identifies worst agent → Claude suggests ONE prompt modification
6. If Brier improves by > 0.01: keep. Otherwise: revert.

## Agent Roster (retired)
- `prompts/base_rate.md` — Statistical priors
- `prompts/news_momentum.md` — Short-term momentum, regime
- `prompts/contrarian.md` — Mean-reversion, exhaustion signals

## Why We Moved On
- Best LLM version (V2.1) achieved 59.7% WR at ~$1.50/day
- V4 momentum rule achieves 67% WR at $0/day
- Conviction-based sizing was the real driver, not agent intelligence
- See `docs/BACKTEST_FINDINGS.md` for the full analysis
