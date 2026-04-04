# Trading Strategy — V4 Momentum System

Last updated: 2026-04-04

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
- **Exhaustion gate**: Removed 2026-03-31. Was filtering 85% WR predictions. See `docs/analysis/analysis_exhaustion_gate.md`.
- **Cooldown flip gate**: Removed 2026-03-31. Was blocking 73% WR predictions. Regime gate handles chop.

### Performance
- Paper: 227+ bets at ~67% WR, +$8,141 P&L (tiered sizing)
- Live: Started 2026-03-31, flat $25 bets. First successful fills pending (SDK bug fixed 2026-04-01).

---

## BTC 15-Minute Pipeline (Paper)

### Signal Logic — 5m as Atomic Unit
The 15m pipeline does **not** use 15m candles. It uses the same 5m candles as the BTC 5m pipeline — same `min_streak=3`, same `autocorr_threshold=-0.15`, same regime classification. The 5m candle is the atomic signal unit across both pipelines.

**Why:** A streak visible in 5m candles (3+ candles = 15 min of momentum) may not register in coarser 15m candles until the move is nearly over. 15m candles aggregate 3× the data, masking micro-trends. Using 5m candles gives the 15m pipeline the same resolution advantage as production.

### 5m Confirmation Boost
When the 5m pipeline has 2+ recent predictions in the same direction as the 15m signal, conviction gets a +1 boost (capped at 5). This is a cross-pipeline confirmation — if two independent pipelines agree, confidence is higher. Tracked in reasoning JSON as `sibling_5m_boost`.

### Loose Mode
The 15m pipeline runs in `loose_mode`:
- No dead hour gate (derived from 5m data, unvalidated on 15m)
- DOWN+NEUTRAL demotion applied **post-hoc** in `ci_run_15m.py` (not inline in predict.py)

### Active Filters (15m only)
- **Price gate**: Same as 5m (skip > 0.85 or < 0.15)
- **Mean-reversion regime gate**: Same threshold as 5m (-0.15, since we use 5m candles)
- **DOWN+NEUTRAL demotion**: Post-prediction demotion to conv=2 (symmetric with 5m). HIGH_VOL/NEUTRAL+DOWN allowed through (64% WR on 50 bets on 5m).

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

## Kalshi BTC Pipeline (Paper — Phase 0)

Same momentum signal as BTC production, running against Kalshi BTC 15-min/1h markets. Uses Kraken/Coinbase candles. All predictions at conviction 2 (paper only). Goal: determine whether the momentum edge transfers to a different venue.

- **Signal**: `momentum_signal(candles, min_streak=2)`
- **Regime gate**: `autocorr_threshold=-0.20` — skip mean-reverting regimes
- **Entry point**: `src/ci_run_kalshi.py` → `data/predictions_kalshi.db` → `docs/kalshi.html`
- **Phase 0 gate**: 200+ resolved predictions. WR > 55% → Phase 0.5. WR < 50% → signal is venue-specific.

See [docs/plans/KALSHI_INTEGRATION_PLAN.md](../plans/KALSHI_INTEGRATION_PLAN.md) for cross-market arbitrage strategy (Phase 1+).

---

## Shadow Conviction Scorer (All Pipelines)

Runs alongside all 4 pipelines. Computes a continuous strength signal (0.0–1.0) from two components:

- **Length**: `min(log(streak) / log(baseline), 1.0)` — longer streaks score higher, log curve prevents over-weighting
- **Magnitude**: `min(|net_return| / (realized_vol × multiplier), 1.0)` — bigger moves relative to volatility score higher

`strength = length × magnitude` → mapped to estimate (0.50 ± max_edge × strength) → conviction tier (2/3/4/5).

Always on, zero production impact. Shadow scores stored in reasoning JSON as `shadow_generic_scorer`. Daily report surfaces tier-by-tier WR comparison and divergence analysis (when shadow ≠ production, who was right?).

Phase A analysis triggers after BTC live gate passes (Decision #17, currently 33/50 bets).

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

Pending decisions with automated triggers live in `docs/core/decisions.md`. The daily report checks these conditions and alerts when action is needed.
