# Kelly Criterion Analysis

> Generated: 2026-03-29 23:01 UTC
> Dataset: 221 resolved bets from `predictions.db`
> Starting bankroll: $5,000

## Overall Kelly Fractions

| Metric | Value |
|--------|-------|
| Win Rate | 67.0% |
| Avg Net Odds | 0.994 |
| Full Kelly (f*) | 33.7% of bankroll |
| Half Kelly | 16.9% |
| Quarter Kelly | 8.4% |

## Kelly by Conviction Tier

| Tier | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |
|------|------|----|----------|------------|-------------------|
| Conv=3 | 178 | 66.9% | 0.998 | 33.6% | $421 (=8.4%) |
| Conv=4 | 40 | 67.5% | 0.970 | 34.0% | $425 (=8.5%) |
| Conv=5 | 3 | 66.7% | 1.086 | 36.0% | $450 (=9.0%) |

## Kelly by Regime

| Regime | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |
|--------|------|----|----------|------------|-------------------|
| NEUTRAL | 146 | 69.9% | 1.052 | 41.2% | $515 (=10.3%) |
| TRENDING | 75 | 61.3% | 0.882 | 17.5% | $218 (=4.4%) |

## Kelly by Direction

| Direction | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |
|-----------|------|----|----------|------------|-------------------|
| DOWN | 92 | 63.0% | 1.097 | 29.4% | $367 (=7.3%) |
| UP | 129 | 69.8% | 0.921 | 36.9% | $462 (=9.2%) |

## Strategy Comparison

Starting bankroll: **$5,000** · 221 bets replayed in chronological order

| Strategy | Final | P&L | ROI | Max DD | DD% | Sharpe |
|----------|-------|-----|-----|--------|-----|--------|
| Current fixed tiers | $8,735 | $+3,735 | +74.7% | $333 | 4.5% | 0.272 |
| Full Kelly | $12,841,158 | $+12,836,158 | +256723.2% | $12,649,278 | 88.4% | 0.272 |
| Half Kelly | $5,294,752 | $+5,289,752 | +105795.0% | $1,969,640 | 55.5% | 0.272 |
| Quarter Kelly | $349,076 | $+344,076 | +6881.5% | $61,117 | 30.2% | 0.272 |
| Flat $50 | $7,991 | $+2,991 | +59.8% | $200 | 3.2% | 0.272 |
| Flat $100 | $10,981 | $+5,981 | +119.6% | $400 | 6.2% | 0.272 |
| Conv-aware ¼ Kelly | $349,649 | $+344,649 | +6893.0% | $63,758 | 30.1% | 0.272 |
| Regime-aware ¼ Kelly | $528,936 | $+523,936 | +10478.7% | $83,352 | 30.8% | 0.272 |

## Interpretation

- **Full Kelly** maximizes long-run growth but has extreme drawdowns. Never use full Kelly in practice.
- **Quarter Kelly** is the standard conservative approach — captures ~75% of the growth rate with ~25% of the variance.
- **Conv-aware Kelly** sizes each bet based on that conviction tier's edge. Higher conviction = bigger bet, but only if the tier has proven edge.
- **Regime-aware Kelly** reduces or skips bets in NEUTRAL regime (where our edge is weakest) and sizes up in TRENDING.
- **Max drawdown %** is the peak-to-trough decline — this is what determines whether you can psychologically stay in the game.

## Recommendation

**Flat $50** offers the best risk/reward tradeoff:
- P&L: $+2,991 (+59.8% ROI)
- Max drawdown: 3.2% ($200)
- Sharpe: 0.272

### Current vs Recommended Bet Sizes

| Conviction | Current | Quarter Kelly | Change |
|------------|---------|---------------|--------|
| 3 | $50 | $421 | ↑ |
| 4 | $100 | $425 | ↑ |
| 5 | $200 | $450 | ↑ |

---
*Analysis only. No production code was changed.*
