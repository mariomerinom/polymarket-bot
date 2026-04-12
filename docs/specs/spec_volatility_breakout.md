# Spec: Volatility Breakout Strategy

> **Status:** STILL RELEVANT — In Strategy Lab as always-fire; spec has full threshold logic for production

**Status:** Proposed
**Pipeline:** BTC 5m (primary), ETH 5m (after Phase 1 validates)
**Category:** New strategy — regime transition. Independent from momentum.
**Problem:** The momentum strategy performs best in TRENDING regimes and poorly in MEAN_REVERTING. But it completely ignores the *transition* between regimes — specifically, the moment volatility expands from LOW_VOL to MEDIUM_VOL or MEDIUM_VOL to HIGH_VOL. These transitions are the highest-conviction moments in crypto markets: compressed price action breaks out, and the first directional candle after a compression period tends to be reliable.
**Goal:** Detect volatility compression → expansion transitions and bet on the direction of the breakout candle.

---

## Why This Is Different from Momentum

| Aspect | Momentum | Volatility Breakout |
|--------|----------|-------------------|
| Signal source | Streak of same-direction candles | Regime transition + first directional move |
| Requires streak | Yes (3+ candles) | No — fires on 1 candle after compression |
| Timing | After trend is established | At the very start of a new trend |
| Regime dependency | Best in TRENDING | Fires specifically at LOW→MEDIUM or MEDIUM→HIGH transitions |
| Duration of signal | Rides existing streak | One-shot — bet on the breakout direction persisting |

Momentum says "a trend is happening." Volatility breakout says "a trend is about to start." These are temporally adjacent — breakout fires first, momentum confirms later.

---

## Signal Logic

### Step 1: Detect Volatility Compression

Compression = volatility is abnormally low relative to its recent history. This is the coiled spring before the breakout.

```
realized_vol = std_dev of 5-min returns over last N candles
vol_sma = simple moving average of realized_vol over M periods
vol_ratio = realized_vol / vol_sma

Compression detected when: vol_ratio < compression_threshold (e.g., 0.6)
```

Translation: current volatility is less than 60% of its recent average. The market is coiling.

### Step 2: Detect Expansion (Breakout Trigger)

```
For each new candle:
  candle_range = abs(high - low) / open
  avg_range = SMA of candle_range over last N candles

  expansion = candle_range / avg_range

  Breakout triggered when:
    - Currently in compression (vol_ratio < 0.6)
    - New candle has expansion > expansion_threshold (e.g., 2.0)
    - i.e., the candle's range is 2x the recent average
```

### Step 3: Determine Direction

The breakout candle's close relative to its open determines direction:

```
if breakout_candle.close > breakout_candle.open:
    direction = UP
else:
    direction = DOWN
```

Additional confirmation: compare close to the compression range's midpoint. If the breakout candle closes above the high of the compression range, it's a stronger UP signal (and vice versa).

```
compression_high = max(highs over compression period)
compression_low = min(lows over compression period)
compression_mid = (compression_high + compression_low) / 2

if breakout_candle.close > compression_high:
    strength = "strong"  # broke above the range
elif breakout_candle.close > compression_mid:
    strength = "moderate"  # above midpoint but within range
else:
    strength = "weak"  # breakout candle direction contradicted by position
```

### Step 4: Signal Generation

| Condition | Signal | Conviction |
|-----------|--------|-----------|
| Strong breakout UP (close > compression_high) | Predict UP | High — clean breakout above range |
| Moderate breakout UP (close > compression_mid) | Predict UP | Medium — directional but not decisive |
| Weak breakout (direction vs position mismatch) | No signal | Ambiguous — stay out |
| Strong breakout DOWN (close < compression_low) | Predict DOWN | High — clean breakout below range |
| Moderate breakout DOWN (close < compression_mid) | Predict DOWN | Medium |

---

## Compression Detection Refinements

### Bollinger Band Width

An alternative compression metric using Bollinger Bands:

```
bb_width = (upper_band - lower_band) / middle_band
bb_width_percentile = percentile_rank(bb_width, lookback=100 candles)

Compression when: bb_width_percentile < 20  (narrowest 20% of recent history)
```

This is more adaptive than a fixed threshold because it adjusts to the asset's own volatility history.

### Consecutive Narrow Candles

A simpler heuristic that doesn't require rolling calculations:

```
narrow_count = count of last N candles where candle_range < avg_range × 0.5
if narrow_count >= 4 out of last 6:
    compression = True
```

Four out of six candles with less than half the average range = clear compression.

### Recommended: Use Both

```
compression = (vol_ratio < 0.6) OR (bb_width_percentile < 20) OR (narrow_count >= 4/6)
```

Any of the three detecting compression is sufficient. Using OR increases sensitivity (more signals). If too many false signals, switch to AND (require 2 of 3).

---

## Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Vol lookback (N) | 20 candles (100 min) | Period for realized vol calculation |
| Vol SMA period (M) | 50 candles (~4 hours) | Longer-term vol baseline |
| Compression threshold | 0.6 | vol_ratio below this = compressed |
| Expansion threshold | 2.0 | Candle range must be 2x average to trigger breakout |
| BB width percentile | 20th | Bottom quintile = compressed |
| Narrow candle threshold | 4 of 6 | Four narrow candles in last six |
| Min compression duration | 4 candles (20 min) | Must be compressed for at least 20 min — prevents noise |
| Max time after breakout | 1 candle (5 min) | Must bet within the breakout candle or next candle |
| Cooldown | 30 minutes | After a breakout signal, don't fire again for 30 min |

---

## Data Requirements

| Data | Source | Currently Available? |
|------|--------|---------------------|
| BTC 5-min OHLCV | Coinbase | Yes |
| ETH 5-min OHLCV | Coinbase | Yes |
| Historical candle ranges | Derived from OHLCV | Yes — compute on the fly |
| Realized volatility | Already computed in `compute_regime_from_candles()` | Yes |
| Bollinger Bands | Derived from close prices | No — need to compute (trivial) |

### New Infrastructure Needed

1. **Compression state tracker:** At each prediction cycle, compute and store whether the market is in compression. This is a boolean state that persists across cycles.
2. **Compression duration counter:** Track how many consecutive cycles the market has been compressed. Minimum duration prevents spurious triggers.
3. **Breakout event log:** When a breakout fires, log the compression metrics, breakout candle details, and eventual outcome.

Minimal new infrastructure — this strategy mostly reuses existing candle data with new derived metrics.

---

## Interaction with Other Strategies

| Strategy | Relationship |
|----------|-------------|
| Momentum | **Sequential.** Breakout fires on candle 1 of a new move. If the move becomes a streak, momentum fires on candle 3+. Breakout is earlier entry on what may become a momentum signal. No conflict — breakout is a faster version of momentum's edge |
| VWAP Mean Reversion | **Opposite regimes.** VWAP reversion works in MEAN_REVERTING. Breakout works at the transition *out* of compression into trending. They don't overlap temporally |
| Order Flow | **Complementary.** Order flow may show positioning building during compression (informed traders accumulating before the breakout). Order flow signal during compression + breakout trigger = very high conviction |
| Dislocation | **Complementary.** A breakout on spot may create a dislocation on Polymarket if the contract hasn't repriced. Breakout + dislocation = different confirmation of the same event |
| Lead-Lag | **Complementary.** One exchange may break out before the other. Lead-lag detects this. Breakout on the leader exchange + lag on the other = bet on the lagger catching up |

---

## Expected Impact

Volatility compression → breakout is one of the most reliable patterns in crypto. The edge comes from the first candle being highly predictive of the next 2-3 candles' direction.

```
Estimated breakout signals: 2-4 per day (BTC), 3-6 per day (ETH — more volatile, more compression cycles)
Average: ~3 signals/day
At conv=3 ($75) × 65% WR = ~$22/day
Monthly: ~$660
```

Plus conviction boost when breakout aligns with other signals:

```
Breakout + order flow confirmation: estimated 1-2 per day
Conviction bump to conv=4 ($200) × 70% WR = ~$80/day on those
Additional monthly: ~$480

Total estimated: ~$1,140/month
```

---

## Risks

| Risk | Mitigation |
|------|-----------|
| False breakouts (price breaks out then reverses) | Require strong breakout (close beyond compression range). Track false breakout rate. If > 40%, tighten expansion threshold |
| Compression detected but no breakout for hours | Not a risk — no signal fires until the expansion candle appears. The strategy is patient by design |
| Multiple breakout signals in rapid succession | 30-minute cooldown prevents rapid-fire bets |
| Works on backtests but not live | Breakout patterns are well-documented across all markets. Start with shadow mode. Success threshold is conservative (>58% WR) |
| Expansion candle is a news-driven spike that instantly reverses | Add a confirmation: if the candle after the breakout candle reverses > 50% of the breakout move, don't enter. This adds 5 min of delay but filters news spikes |
| Overlap with momentum — betting on the same move twice | Track overlap rate. If breakout and momentum fire on the same contract > 50% of the time, the strategies aren't independent. In that case, use breakout as a conviction boost for momentum rather than an independent signal |

---

## Validation Plan

```
name: volatility_breakout
type: data collection → shadow → small stakes

Phase 1 — Calibration (1 week):
  - Compute compression metrics retroactively on last 30 days of BTC 5-min data
  - Identify historical breakout events
  - Measure: breakout direction accuracy, false breakout rate, overlap with momentum
  - Determine: optimal compression/expansion thresholds
  - Target: identify 50+ historical breakout events with >60% directional accuracy

Phase 2 — Shadow (50 signals):
  - Generate shadow predictions from breakout detection
  - Track: WR, P&L, timing advantage vs momentum, false breakout rate
  - Success: WR > 58%, false breakout rate < 35%

Phase 3 — Small Stakes (50 bets):
  - Enable at conv=3 ($75)
  - Circuit breaker: $300 max drawdown
  - Success: positive P&L, timing advantage of 1+ candle vs pure momentum
```

---

## Relationship to Regime Detection

The current `compute_regime_from_candles()` already classifies volatility into LOW/MEDIUM/HIGH. This strategy adds a new dimension: detecting the *transition* between regimes, not just the current state.

Consider adding a `regime_transition` field to the prediction metadata:

```
regime_transition = {
    "from": previous_regime,
    "to": current_regime,
    "transition_candle": candle_index,
    "compression_duration": N candles,
    "breakout_strength": "strong" | "moderate" | "weak"
}
```

This metadata is useful for all strategies, not just breakout. Momentum could use it to adjust conviction (a momentum signal during a regime transition is higher conviction than one during steady-state).

---

## Decision

This strategy requires no new data sources — only new derived metrics from existing candle data. Implementation priority is high because:
1. Minimal infrastructure cost
2. Fires before momentum (earlier entry)
3. Well-studied pattern with strong theoretical backing
4. Provides signal during regime transitions where current strategies are silent

Begin calibration immediately using historical candle data. Deploy shadow mode after threshold optimization.
