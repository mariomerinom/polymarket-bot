# Trading Strategy — V4 Momentum System

Last updated: 2026-03-29

---

## Core Principle

**Ride streaks, don't fade them.** When BTC moves in one direction for multiple candles and shows signs of exhaustion (compression, volume spike, or shrinking range), the next candle is more likely to continue than reverse. V3 faded streaks and lost at 37% WR. V4 rides them and validates at 66%+ WR.

---

## 5-Minute Pipeline

### Signal Logic
1. Fetch 20 most recent 5-minute BTC candles
2. Compute **regime** from candle data:
   - Volatility (stdev of returns): LOW / MEDIUM / HIGH
   - Autocorrelation (lag-1): TRENDING (>0.15) / NEUTRAL / MEAN_REVERTING (<-0.15)
3. If **mean-reverting** → skip (no edge; market already prices reversion correctly)
4. Count consecutive same-direction candles from most recent backward = **streak**
5. If streak >= 3 AND at least one **exhaustion** signal → **RIDE the streak**

### Exhaustion Signals (any one triggers)
- **Compression**: last 3 candle ranges are shrinking (ranges[0] > [1] > [2])
- **Volume spike**: last candle volume > 1.8x average
- **Shrinking range**: last candle range < 70% of average range

### Conviction & Sizing
| Condition | Conviction | Bet Size |
|-----------|-----------|----------|
| RIDE UP + price 20-70% | 4 | $200 |
| RIDE DOWN or UP outside sweet spot | 3 | $75 |
| DOWN + NEUTRAL regime | 2 | $0 (tracked) |
| No signal / low confidence | 0 | $0 |

### Active Filters (5m only)
- **Price gate**: Skip if market price > 0.85 or < 0.15 (breakeven WR exceeds signal capacity)
- **Dead hour gate**: Skip UTC hours 3 and 21 (41.7% and 37.5% WR respectively)
- **Cooldown gate**: If last bet was opposite direction, require streak > min_streak to flip (prevents whipsaw chop)
- **DOWN + NEUTRAL filter**: DOWN bets in NEUTRAL regime demoted to conv=2 (52% WR = no edge)

### Performance (as of March 29, 2026)
- 212+ resolved bets at ~67% WR
- Cumulative P&L: ~$5,000+
- Best regime: UP + MEDIUM_VOL/NEUTRAL (86.7% WR on 45 bets)
- Worst regime: DOWN + MEDIUM_VOL/NEUTRAL (52% WR — filtered out)

---

## 15-Minute Pipeline

### Signal Logic
Same momentum signal as 5m with two adjustments:
1. **min_streak = 2** (not 3) — a 2-candle streak on 15m is 30 minutes of directional movement, equivalent to a 6-candle streak on 5m
2. **autocorr_threshold = -0.20** (not -0.15) — relaxed mean-reversion detection because 15m candles produce noisier autocorrelation on fewer data points

### Loose Mode
The 15m pipeline runs in `loose_mode` — all 5m-derived gates are **disabled**:
- No dead hour gate (derived from 5m data, unvalidated on 15m)
- No cooldown gate (too aggressive for 15m's sparse signals)
- No DOWN+NEUTRAL filter (52% WR finding is 5m-only)

**Why:** The 15m signal has 72% directional accuracy across 75 predictions, but only 16% made it through the 5m filter stack. The filtered predictions had *higher* WR (73%) than the bets we placed (67%). We were strangling the signal.

### Cross-Timeframe Signal (5m → 15m)
When the 15m pipeline runs, it queries the 5m DB for recent activity:
- How many 5m bets in the last 60 minutes
- Direction majority (more UP or DOWN)
- Current 5m streak direction and length

This context is stored in the reasoning JSON for every 15m prediction. **Not used for filtering yet** — gathering data to analyze whether 5m agreement predicts higher 15m WR. Early data (8 bets) showed 87.5% WR when they agree, but sample is too small.

### Active Filters (15m only)
- **Price gate**: Same as 5m (skip > 0.85 or < 0.15)
- **Mean-reversion regime gate**: Same logic, relaxed threshold (-0.20)

### Performance (as of March 29, 2026)
- 12 resolved bets at 66.7% WR
- Raw signal accuracy: 72% on 75 predictions (most were filtered out pre-loose_mode)
- Tracking optimization `15m_loose_mode` — revert if WR < 55% at 50+ bets

---

## What We Don't Do

- **No contrarian/fading.** V3 faded streaks and lost at 37% WR. The signal direction is MOMENTUM. This is non-negotiable.
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

## Active Optimizations

Tracked in `docs/optimizations.json`, monitored daily at 06:00 CST:

| Name | Pipeline | Baseline WR | Post WR | Bets | Status |
|------|----------|-------------|---------|------|--------|
| direction_regime_filter | 5m | 66.3% | 90.0% | 10/50 | Collecting |
| dead_hour_gate | 5m | 66.3% | 90.0% | 10/50 | Collecting |
| 15m_loose_mode | 15m | 66.7% | — | 0/50 | Just shipped |

---

## Decision Tracker

Pending decisions with automated triggers live in `docs/decisions.md`. The daily report checks these conditions and alerts when action is needed.
