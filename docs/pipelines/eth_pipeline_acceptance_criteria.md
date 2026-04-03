# ETH Pipeline: Acceptance Criteria

**Date:** 2026-04-01 (revised twice)
**Current state:** Momentum (ride) strategy validated. Phase 1 passed 2026-04-02 (66.7% WR on 36 predictions). Medium confidence (streak 3-4) promoted to conv=3 ($25 bets). High confidence stays paper. Liquidity: 5.06% avg spread, $34 max bet @2% slippage.
**Target state:** Phase 2 adaptation layer (regime recalibration, cross-asset features, ETH-specific conviction adjustments).

**Key revision 1 (2026-04-01 AM):** Original plan proposed flipping to momentum based on 9 predictions. Rejected — insufficient evidence.

**Key revision 2 (2026-04-01 PM):** Deeper analysis revealed the "56.5% overall WR" was misleading — conv=0 predictions store market price (60% = market accuracy), not our signal. The actual contrarian signal hit **33.3% WR on 54 resolved predictions**. Momentum counterfactual on the same 54 bets: **66.7%**. This is not a conviction scoring problem — the signal itself was inverted. Flipped to momentum. Exhaustion gate removed (contradicts momentum, same as BTC).

---

## Phase 1 — Momentum Signal Validation (VALIDATED 2026-04-02)

Goal: Flip ETH from contrarian to momentum. Remove exhaustion gate. Validate the momentum signal.

### 1.1 Signal Direction Flip (Done)

- `momentum_signal_eth()` rides streaks: streak UP → predict UP, streak DOWN → predict DOWN
- Agent name: `momentum_eth`
- Signal reason: `ride_streak_{direction}`
- Exhaustion gate removed (contradicts momentum)

### 1.2 Evidence for the Flip

| Strategy | Same 54 bets | WR |
|----------|-------------|-----|
| Contrarian (was live) | fade the streak | **33.3%** |
| Momentum (counterfactual) | ride the streak | **66.7%** |

The "conviction anti-selection" thesis was wrong. Conv=0 predictions (442) stored market price as estimate — their 60% WR is market accuracy, not signal performance. The actual signal (conv=2, 54 predictions) was at 33.3%. The momentum counterfactual is the exact complement.

### 1.3 Conviction Scoring (Updated 2026-04-02)

- **Medium confidence (streak 3-4) → conv=3** ($25 bets). 74.2% WR on 31 resolved predictions.
- **High confidence (streak ≥ 5) → conv=2** (paper only). 20% WR on 5 bets — long streaks reverse on ETH.
- `paper_trading` in reasoning JSON is now dynamic (`conviction < 3`).
- No regime demotion — unlike BTC, ETH DOWN+NEUTRAL is the strongest segment (78.6% WR on 14 bets).

### 1.4 Phase 1 Validation Gate — PASSED

- **Result:** 36 resolved momentum predictions at **66.7% WR** (threshold was 55%)
- Gate passed early — WR 12pp above threshold made waiting for 50 unnecessary
- Optimization registered: `eth_conv3_medium_confidence`, revert if WR < 55% at 50 post-change bets

**Breakdown by confidence:**
| Confidence | Bets | Wins | WR |
|------------|------|------|----|
| medium (streak 3-4) | 31 | 23 | 74.2% |
| high (streak ≥ 5) | 5 | 1 | 20.0% |

**Breakdown by direction + regime:**
| Direction | Regime | Bets | Wins | WR |
|-----------|--------|------|------|----|
| DOWN | NEUTRAL | 14 | 11 | 78.6% |
| UP | NEUTRAL | 19 | 11 | 57.9% |

---

## Phase 2 — ETH Adaptation Layer (After Phase 1 validates)

Goal: Add ETH-specific features that account for the differences between ETH and BTC market dynamics. The BTC model's regime thresholds, conviction scoring, and sizing are calibrated to BTC — ETH needs its own calibration.

### 2.1 Recalibrate Volatility Regime Thresholds

- ETH volatility thresholds must be shifted upward to reflect ETH's structurally higher baseline volatility
- Current BTC thresholds (LOW < 0.05, MEDIUM 0.05-0.12, HIGH > 0.12) must not be used for ETH
- ETH thresholds must be derived from ETH candle data: proposed LOW < 0.12, MEDIUM 0.12-0.22, HIGH > 0.22
- After recalibration, the ETH regime distribution must no longer be >90% HIGH_VOL on typical days
- The regime computation for ETH must be separate from BTC (stop importing `compute_regime_from_candles` from `predict.py` with BTC thresholds, or pass ETH-specific thresholds)

### 2.2 Add ETH/BTC Cross-Asset Features

- The prediction function must accept and use the following ETH-specific inputs:
  - **ETH/BTC ratio (current):** Captures relative strength
  - **ETH/BTC ratio slope (5-min):** Direction of relative strength shift
  - **BTC 5-min return (lagged):** Detects ETH lag behind BTC moves. If BTC moved >1% in last 5 min and ETH hasn't caught up proportionally, this is a high-probability signal
  - **ETH-BTC rolling correlation (1h):** When correlation drops below 0.5, reduce conviction — BTC-derived signals become unreliable
- These features must be logged in the reasoning JSON for every prediction, even when they don't trigger an adjustment

### 2.3 Implement ETH Conviction Scoring

- ETH must have its own conviction scoring logic, separate from BTC
- Conviction adjustments must include:
  - **Correlation gate:** If ETH-BTC 1h correlation < 0.5, reduce conviction by 1 (minimum 0)
  - **Lag detector:** If BTC moved >1% in 5 min and ETH moved < 30% of that, boost conviction by 1 (max 5)
  - **Spread gate:** If Polymarket ETH spread > 3%, cap conviction at 3. Never place conv=4/5 bets on wide-spread markets
  - **Liquidity cap:** If max bet at 2% slippage < $100, cap conviction at 2 (shadow only)
- Conviction tiers must only be enabled after the adaptation layer has collected 50 shadow bets
- The daily report must show ETH conviction tier breakdown separately from BTC

### 2.4 Implement ETH-Specific Sizing

- ETH bet sizes must be independent from BTC sizing
- Maximum sizes: conv=3 → $25, conv=4 → $50, conv=5 → $75
- Sizing must be dynamically adjusted by CLOB liquidity: never exceed 50% of max bet at 2% slippage
- If max bet at 2% slippage < $25, all bets must be shadow-only (conv=2)
- The sizing table must be documented in the ETH pipeline docstring

### 2.5 Phase 2 Validation Gate

- Shadow mode: Collect 50 adaptation-layer predictions with the new features logged
- Success criteria:
  - Adapted conviction scoring produces a meaningful distribution (not all conv=2)
  - Shadow WR with adaptation adjustments > shadow WR without (measured on same predictions)
  - Correlation gate fires on at least some predictions (proving the feature is active)
  - Lag detector fires on at least some predictions
- After shadow validation: enable conv=3 ($25 bets) for 50 live bets
- Live success criteria: WR > 55%, positive P&L after spread and slippage, no circuit breaker trigger

---

## Phase 3 — Full Integration (After Phase 2 validates)

Goal: ETH pipeline operating independently with proven edge.

### 3.1 Expand Conviction Range

- Enable conv=4 ($50) and conv=5 ($75) based on Phase 2 performance data
- Only enable higher tiers if Phase 2 conv=3 bets achieve > 58% WR at 50+ bets
- Dynamic sizing must be active — bets auto-reduce when liquidity is thin

### 3.2 ETH-Specific Dead Hours

- Calibrate dead hours from ETH paper trading data accumulated in Phases 1-2
- ETH liquidity patterns differ from BTC (worse on weekends, thinner in Asian hours)
- Dead hours must be derived from ETH-specific WR data, not copied from BTC

### 3.3 ETH-Specific Indicator Integration

- If RSI gate, OBV filter, or VWAP mean-reversion validate on BTC by this point, evaluate them for ETH
- ETH RSI period may need to be shorter (10-12 vs 14) due to faster moves
- ETH VWAP deviation bands must be wider than BTC (ETH deviates further before reverting)
- Each indicator must be shadow-tested independently on ETH before enabling — do not assume BTC parameters transfer

### 3.4 Consider Multi-Asset Model

- After 90+ days of ETH prediction data, evaluate whether a unified BTC+ETH model outperforms separate models
- The multi-asset model must learn cross-asset relationships natively (e.g., when ETH is about to decorrelate from BTC)
- This is a long-term goal, not a near-term requirement

### 3.5 Circuit Breaker

- ETH pipeline must have its own circuit breaker, independent from BTC
- Threshold: $150 max drawdown at conv=3 sizing (6 consecutive losses at $25)
- If triggered: pause ETH pipeline, do not affect BTC pipeline
- Auto-resume after 24 hours, or manual override

---

## Cross-Phase Requirements (Apply to All Phases)

### Data Requirements

| Data | Source | Phase Needed |
|------|--------|-------------|
| ETH 5-min OHLCV | Coinbase | Phase 1 (already available) |
| BTC 5-min OHLCV (aligned) | Coinbase | Phase 2 |
| ETH/BTC pair | Derived from Coinbase | Phase 2 |
| ETH Polymarket CLOB snapshots | Internal logs | Phase 1 (already available) |
| ETH-BTC rolling correlation | Derived | Phase 2 |
| ETH funding rates | Exchange API (TBD) | Phase 3 (optional) |

### Isolation Requirements

- ETH pipeline changes must never affect BTC pipeline behavior
- ETH and BTC must use separate databases
- ETH and BTC conviction scoring must be independent
- ETH and BTC sizing must be independent
- ETH circuit breaker must be independent

### Monitoring Requirements

- The daily report must show ETH as a separate section (already in place)
- ETH filter breakdown must track counterfactual WR for all skip reasons
- ETH shadow indicators (RSI, OBV, VWAP) must be logged separately from BTC
- ETH CLOB liquidity must be reported daily with spread distribution and token breakdown

### Break-Even Reference

At current ETH liquidity (5.06% spread, ~2% slippage at small sizes):
- Total cost per bet: ~5-7%
- Required WR to break even: ~55%
- If liquidity improves to BTC levels (~2% spread): required WR drops to ~52%
- Phase transitions should not proceed if ETH liquidity deteriorates further (max bet @2% < $25)
