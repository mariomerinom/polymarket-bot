# Trading Strategy — V4 Momentum System

Last updated: 2026-04-01

---

## Core Principle

**Ride streaks, don't fade them.** When BTC or ETH moves in one direction for 3+ candles, the next candle is more likely to continue than reverse. V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). V4 rides them and validates at 67%+ WR.

---

## BTC 5-Minute Pipeline (Production)

### Signal Logic
1. Fetch 20 most recent 5-minute BTC candles
2. Compute **regime** from candle data:
   - Volatility (stdev of returns): LOW / MEDIUM / HIGH
   - Autocorrelation (lag-1): TRENDING (>0.15) / NEUTRAL / MEAN_REVERTING (<-0.15)
3. If **mean-reverting** → skip (no edge; market already prices reversion correctly)
4. Count consecutive same-direction candles from most recent backward = **streak**
5. If streak >= 3 → **RIDE the streak**

No exhaustion gate. Removed 2026-03-31 after analysis showed exhaustion signals (compression, volume spike, shrinking range) were filtering out the best predictions (85% WR filtered vs 67% WR kept). These are contrarian indicators — they confirm a trend is ending, which is the opposite of what a momentum strategy needs.

### Conviction & Sizing (Production)
| Condition | Conviction | Bet Size |
|-----------|-----------|----------|
| Any qualifying signal | 3+ | $25 flat |
| DOWN + NEUTRAL regime | 2 | $0 (tracked) |
| No signal / low confidence | 0 | $0 |

Production uses flat $25 per bet. Paper trading retains tiered sizing for data collection.

### Active Filters (5m only)
- **Price gate**: Skip if market price > 0.85 or < 0.15 (breakeven WR exceeds signal capacity)
- **Dead hour gate**: Skip UTC hours 3 and 21 (41.7% and 37.5% WR respectively)
- **DOWN + NEUTRAL filter**: DOWN bets in NEUTRAL regime demoted to conv=2 (52% WR = no edge)

### Removed Filters
- **Exhaustion gate**: Removed 2026-03-31. Was filtering 85% WR predictions. See `docs/daily/analysis_exhaustion_gate.md`.
- **Cooldown flip gate**: Removed 2026-03-31. Was blocking 73% WR predictions. Regime gate handles chop.

### Performance
- Paper: 227+ bets at ~67% WR, +$8,141 P&L (tiered sizing)
- Live: Started 2026-03-31, flat $25 bets. First successful fills pending (SDK bug fixed 2026-04-01).

---

## BTC 15-Minute Pipeline (Paper)

### Signal Logic
Same momentum signal as 5m with two adjustments:
1. **min_streak = 2** (not 3) — a 2-candle streak on 15m is 30 minutes of directional movement
2. **autocorr_threshold = -0.20** (not -0.15) — relaxed mean-reversion detection

### Loose Mode
The 15m pipeline runs in `loose_mode` — all 5m-derived gates are **disabled**:
- No dead hour gate (derived from 5m data, unvalidated on 15m)
- No DOWN+NEUTRAL filter (52% WR finding is 5m-only)

### Active Filters (15m only)
- **Price gate**: Same as 5m (skip > 0.85 or < 0.15)
- **Mean-reversion regime gate**: Same logic, relaxed threshold (-0.20)

### Performance
- 12 resolved bets at 66.7% WR (small sample, still collecting)

---

## ETH 5-Minute Pipeline (Paper)

### Signal Logic
Same momentum signal as BTC: streak >= 3 in non-mean-reverting regime → ride the streak.

### History
- Phase 2 pattern mining validated contrarian at 54.4% WR on 1,601 historical markets
- Live contrarian signal hit **33.3% WR on 54 resolved predictions** — catastrophic
- Momentum counterfactual on same 54 bets: **66.7%** (exact complement)
- Flipped to momentum 2026-04-01. Same V3→V4 pattern as BTC.

### Current State
- All predictions at conviction 2 (paper trading, no money risked)
- Agent name: `momentum_eth`
- Collecting 200+ resolved predictions before evaluating for live trading
- Revert criteria: WR < 55% at 100+ momentum predictions

### Active Filters
- **Price gate**: Skip > 0.85 or < 0.15
- **Mean-reversion regime gate**: Same as BTC (uses BTC thresholds — recalibration planned for Phase 2)
- **Dead hours**: Empty set (will be calibrated from ETH data)

---

## What We Don't Do

- **No contrarian/fading.** V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). The signal direction is MOMENTUM for all assets. This is non-negotiable.
- **No mean-reversion trading.** 334 observations show the market already prices mean-reversion correctly. No independent signal found.
- **No LLM agents.** V1/V2 used GPT-4 for predictions at $15-50/day. V4 is pure computation from candle data. Cost: $0/day.
- **No agent bias.** The bot has no built-in directional bias. All bias comes from human macro config, not prompts or code.
- **No betting at extreme prices.** At price 0.95, you need 95% WR to break even. Our signal can't deliver that.

---

## Validation Rules

Every optimization follows these principles (enforced by `src/optimization_tracker.py`):

1. **Baseline before shipping.** Snapshot WR, P&L, bet count at registration time.
2. **Revert criteria before shipping.** Define failure while still objective.
3. **50-bet minimum.** Anything less is noise.
4. **Forward validation only.** The data that found the edge can't confirm it.
5. **Track the counterfactual.** Filtered predictions stored at conv=2 for comparison.
6. **One change at a time.** Can't attribute results to stacked changes.

---

## Decision Tracker

Pending decisions with automated triggers live in `docs/decisions.md`. The daily report checks these conditions and alerts when action is needed.
