# Spec: Dead Regime Harvesting Strategy

> **Status:** STILL RELEVANT — Mean-reverting regime still skipped, not harvested

**Status:** Proposed
**Pipeline:** BTC 5m (primary), ETH 5m (secondary)
**Category:** New strategy — mean reversion in unfavorable regimes. Independent from momentum.
**Problem:** The pipeline currently discards predictions in two "dead" conditions: MEAN_REVERTING regime (~200+/day predictions skipped) and DEAD_HOURS_UTC {3, 21} (~40+/day skipped). These are dead zones for the *momentum* strategy — but they're not dead zones for all strategies. In MEAN_REVERTING conditions, price oscillates around a mean. In dead hours, the CLOB is thinner and contract prices drift. Both conditions contain exploitable patterns that momentum ignores.
**Goal:** Extract edge from the predictions the pipeline currently throws away by using strategies suited to range-bound and low-activity conditions.

---

## Why This Is Different from Momentum and VWAP

| Aspect | Momentum | VWAP Mean Reversion | Dead Regime Harvesting |
|--------|----------|-------------------|----------------------|
| Signal source | BTC candle streaks | Price vs VWAP ± 2σ | Contract price oscillation + range boundaries |
| Regime | TRENDING/NEUTRAL | MEAN_REVERTING | MEAN_REVERTING + DEAD_HOURS |
| Requires | Streak ≥ 3 | VWAP deviation | Identified range + contract price near boundary |
| Data dependency | Exchange candles | Exchange candles + volume profile | Polymarket contract prices (primary) |
| Edge source | Trend continuation | Statistical mean reversion on spot | Contract-specific microstructure patterns |

VWAP mean reversion trades the spot price reverting to VWAP. Dead regime harvesting trades the *contract price* oscillating within a range. These are different instruments — the contract has its own microstructure (CLOB dynamics, position limits, expiry mechanics) that creates patterns independent of the spot price.

---

## Two Sub-Strategies

### Sub-Strategy A: Contract Range Trading (MEAN_REVERTING Regime)

In MEAN_REVERTING conditions, BTC oscillates and so does the contract price. The contract price tends to bounce between support and resistance levels within its 0-1 range.

#### Signal Logic

```
# Track contract price range over rolling window
contract_high = max(contract_prices, last N snapshots)
contract_low = min(contract_prices, last N snapshots)
contract_range = contract_high - contract_low
contract_mid = (contract_high + contract_low) / 2

# Current position within range
position = (contract_price_now - contract_low) / contract_range

# Signal
if position > 0.85:    # near top of range
    signal = DOWN (predict price reverts toward mid)
elif position < 0.15:  # near bottom of range
    signal = UP (predict price reverts toward mid)
else:
    no signal  # middle of range, no edge
```

#### Why This Works on Contracts

Binary contracts have natural boundaries. A contract at 0.90 has limited upside (max 1.00) but significant downside. A contract at 0.10 has limited downside (min 0.00) but significant upside. In a MEAN_REVERTING regime where the outcome is uncertain, prices near the extremes tend to revert because:

1. **Asymmetric payoff:** Buying YES at 0.90 risks 0.90 to gain 0.10. Selling YES at 0.90 risks 0.10 to gain 0.90. The asymmetry attracts sellers near extremes.
2. **Bayesian updating:** In MEAN_REVERTING conditions, each new candle partially contradicts the previous one. A contract at 0.90 (implying 90% probability of UP) is overconfident if the regime is mean-reverting.
3. **CLOB thin at extremes:** Near 0.90 or 0.10, one side of the book is very thin. Small flow can push the price, creating overshoot.

### Sub-Strategy B: Dead Hour Fade (DEAD_HOURS_UTC)

During dead hours (UTC 3 and 21), volume drops and the CLOB becomes thinner. Contract prices can drift due to small orders with no countervailing flow. These drifts tend to be noise and revert when normal trading resumes.

#### Signal Logic

```
# At the start of a dead hour, snapshot the contract price
dead_hour_start_price = contract_price at hour start

# During the dead hour, monitor drift
drift = contract_price_now - dead_hour_start_price

# If contract has drifted significantly, bet on reversion
if abs(drift) > drift_threshold:
    if drift > 0:
        signal = DOWN  # price drifted up on no volume, will revert
    else:
        signal = UP    # price drifted down on no volume, will revert
```

#### Why This Works

Dead hours are dead for momentum because trends don't sustain without volume. But the *absence* of volume is itself a signal: any contract price movement during dead hours is disproportionately likely to be noise rather than information. Fading these moves captures the reversion when volume returns.

Key requirement: the contract must have enough time remaining to resolve after the dead hour ends. Don't bet on a contract that expires during the dead hour — there's no volume to correct the price.

---

## Parameters

### Sub-Strategy A: Contract Range Trading

| Parameter | Value | Notes |
|-----------|-------|-------|
| Range lookback | 12 snapshots (1 hour at 5-min intervals) | Window for computing contract price range |
| Min range width | 0.05 (5 percentage points) | If range < 5pp, market is too flat to trade |
| Position threshold (high) | 0.85 | Contract price in top 15% of range |
| Position threshold (low) | 0.15 | Contract price in bottom 15% of range |
| Required regime | MEAN_REVERTING | Only fire in confirmed MR regime |
| Cooldown | 15 minutes | One signal per contract per 15 min |
| Max conviction | conv=3 | Cap conviction — this is a low-confidence strategy |

### Sub-Strategy B: Dead Hour Fade

| Parameter | Value | Notes |
|-----------|-------|-------|
| Dead hours | {3, 21} UTC (BTC). TBD for ETH | Hours with sub-50% momentum WR |
| Drift threshold | 0.04 (4 percentage points) | Contract must drift > 4pp to trigger |
| Min time remaining | 30 minutes | Contract must not expire during dead hour |
| Max conviction | conv=3 | Low-confidence strategy |
| Cooldown | 30 minutes | Conservative for thin markets |

---

## Data Requirements

| Data | Source | Currently Available? |
|------|--------|---------------------|
| Contract prices over time | Polymarket CLOB snapshots | Partially — per-prediction snapshots exist. Higher frequency preferred |
| Contract price range history | Derived from CLOB snapshots | No — need to compute and store |
| Regime classification | `compute_regime_from_candles()` | Yes |
| Dead hour identification | Config (DEAD_HOURS_UTC) | Yes |
| Time to contract expiry | Polymarket API (Gamma) | Yes |
| CLOB volume/depth during dead hours | Polymarket CLOB | Partially — need dead-hour-specific logging |

### New Infrastructure Needed

1. **Contract price time series:** If the CLOB polling loop (from order flow spec) is deployed, this is already available. Otherwise, need per-prediction contract price logging (already partially happening).
2. **Range tracker:** Rolling high/low/mid of contract prices per market. Lightweight — a sliding window over the contract price series.
3. **Dead hour drift monitor:** Snapshot contract price at dead hour start, track drift throughout. Trigger signal if drift exceeds threshold.

Infrastructure overlap with order flow and dislocation specs is significant. The CLOB polling loop benefits all three strategies.

---

## Interaction with Other Strategies

| Strategy | Relationship |
|----------|-------------|
| Momentum | **Regime complement.** Momentum works in TRENDING/NEUTRAL. Dead regime harvesting works in MEAN_REVERTING and DEAD_HOURS. Zero overlap by design — they cover different conditions |
| VWAP Mean Reversion | **Partial overlap in MEAN_REVERTING.** Both trade MR regimes. VWAP trades spot price vs VWAP. Contract range trades contract price vs range. Different instruments, but may signal same direction. If both fire: higher conviction. If they disagree: stay out |
| Dislocation | **Can co-occur.** A dead hour drift in the contract without a corresponding spot move IS a dislocation. Dead regime harvesting and dislocation may fire on the same event. Confirm both → high conviction |
| Order Flow | **Confirmation.** In dead hours, a single large order can cause drift. If order flow shows the drift was one-sided (a single large buy with no follow-through), that confirms the fade signal |
| Volatility Breakout | **Mutually exclusive.** Breakout fires on regime expansion (LOW→MEDIUM). Dead regime harvesting fires during stable MR. If a breakout is detected, dead regime harvesting should stop immediately — the regime is changing |

---

## Expected Impact

### Sub-Strategy A: Contract Range Trading

```
Predictions in MEAN_REVERTING regime: ~200/day
Signals near range boundaries: ~15-20% of those = 30-40 per day
After filtering for min range width and cooldown: ~8-12 signals/day
At conv=3 ($75) × 58% WR = ~$9/day
Monthly: ~$270
```

Conservative — 58% WR is only slightly above breakeven. The edge is small per bet but the volume is high (many more signals than other strategies).

### Sub-Strategy B: Dead Hour Fade

```
Predictions in dead hours: ~40/day
Contracts with > 4pp drift: ~10-15% = 4-6 per day
After filtering for time-to-expiry and cooldown: ~2-3 signals/day
At conv=3 ($75) × 60% WR = ~$15/day
Monthly: ~$450
```

### Combined

```
Total estimated: ~$720/month
```

Lower per-signal edge than other strategies, but addresses a currently unmonetized segment of predictions. The real value is that it adds revenue during periods when all other strategies are silent.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| MEAN_REVERTING regime misclassified → actually trending | The regime detector's autocorrelation threshold must be reliable. If a MR signal fires and the next 3 candles trend strongly, the regime detector was wrong. Track this rate. If > 20%, tighten autocorrelation thresholds |
| Contract range is too narrow to trade | Min range width of 0.05 (5pp) filters out flat markets. If the contract is at 0.48-0.52, there's no tradeable range |
| Dead hour volume is so low that bets don't fill | Use limit orders only. If the bid-ask spread is > 5% during dead hours, skip the signal. The thin CLOB is both the opportunity (drift) and the risk (execution) |
| Fading a drift that's actually informed trading | In dead hours, this is unlikely — informed traders tend to act during liquid hours. But add a check: if the drift is accompanied by a large spot move (BTC > 0.5%), it's not noise — skip the fade |
| Low WR makes this a grind | Cap at conv=3 to limit downside. Circuit breaker at $200 drawdown. This is additive edge, not core — if it doesn't work, sunset it without impacting the main pipeline |
| Strategy conflicts with VWAP mean reversion | Track agreement rate. If they disagree > 30% of the time on direction, run only the one with better WR. If they agree > 70%, keep only the better-performing one (they're redundant) |

---

## Validation Plan

```
name: dead_regime_harvesting
type: data collection → shadow → small stakes

Phase 1 — Analysis (1 week):
  - Retroactively analyze contract price behavior during MEAN_REVERTING periods
  - Compute: range width distribution, boundary touch rate, reversion rate after boundary touch
  - Analyze dead hour drifts: frequency, magnitude, reversion rate
  - Determine: is there a tradeable pattern? What thresholds optimize WR?
  - Target: identify 100+ historical range boundary events, 50+ dead hour drift events

Phase 2 — Shadow (50 signals per sub-strategy):
  - Generate shadow predictions from range boundary and dead hour drift signals
  - Track: WR, P&L, overlap with VWAP strategy, regime accuracy
  - Success criteria:
    - Contract range trading: WR > 55%, range reversion rate > 60%
    - Dead hour fade: WR > 57%, drift reversion rate > 65%

Phase 3 — Small Stakes (50 bets per sub-strategy):
  - Enable at conv=3 ($75)
  - Separate circuit breakers: $200 max drawdown each
  - Success: positive P&L after spread/slippage
  - If one sub-strategy fails but the other passes, keep only the winner
```

---

## Relationship to VWAP Mean Reversion Spec

The VWAP spec addresses the same problem (MEAN_REVERTING regime is wasted) but from a different angle. Comparison:

| Dimension | VWAP Mean Reversion | Dead Regime Harvesting |
|-----------|-------------------|----------------------|
| Instrument | BTC spot price vs VWAP | Polymarket contract price vs range |
| Signal | Statistical deviation (2σ) | Range boundary proximity |
| Data source | Exchange candles + volume | Polymarket CLOB |
| Complexity | Medium (requires VWAP + bands) | Low (requires contract price tracking) |
| Dead hours | Not specifically addressed | Explicitly targeted |

Recommendation: implement both, track overlap and correlation. After 100 signals each, decide:
- If overlap < 30%: keep both (independent signals)
- If overlap 30-70% and both profitable: keep both but don't compound conviction when they agree
- If overlap > 70%: keep only the higher-WR strategy

---

## Decision

This strategy has the lowest per-signal edge of the five new strategies but addresses the largest untapped prediction volume (~200+ MR predictions + ~40 dead hour predictions daily). It requires minimal new infrastructure beyond what the CLOB polling loop provides. Begin Phase 1 analysis immediately using existing prediction logs and CLOB snapshots. Deploy shadow mode after confirming that contract price range-boundary reversion and dead hour drift reversion are statistically significant.
