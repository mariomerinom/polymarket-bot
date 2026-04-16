# Spec: Bybit Perps Execution — Magnitude-Aware Trading

**Status:** DRAFT — requires backtest validation before live deployment  
**Author:** Mario + Claude  
**Date:** 2026-04-16  
**Pipeline:** Bybit BTC Perpetuals  
**Depends on:** Momentum strategy V4 (signal source), regime detection (vol × autocorrelation)  
**Problem:** Polymarket's binary resolution is forgiving (direction = win). Perps need price to move far enough to cover fees + slippage. A 55% directional WR can be unprofitable on perps if magnitude is insufficient.  
**EHR Baseline (2026-04-16):** Signal EHR = +0.003 on 376 predictions (~50th percentile Akey scale). The momentum signal's directional edge does not currently transfer to perps pricing — it identifies mispricings on Polymarket's binary structure but not on continuous price movement. This spec addresses the gap with magnitude-aware execution. The backtest (Section 8) will determine whether TP/SL structuring can extract positive EV from the directional signal despite near-zero raw EHR.

---

## 1. Problem Statement

BOTSY's momentum signal predicts *direction* of the next 5-minute candle. On Polymarket, this is sufficient — binary contracts resolve YES/NO based purely on direction. On Bybit perps, three additional costs exist that direction alone doesn't cover:

1. **Taker fees:** 0.055% per side → 0.11% round-trip
2. **Slippage:** estimated 0.03–0.05% per side at current sizing
3. **No automatic exit:** the signal says "next candle is UP" but doesn't say when to close

Minimum favorable price movement to break even: **~0.15–0.20%** (~$125–170 on BTC at $84K).

During MEDIUM_VOL/TRENDING regimes (4/3–4/5), 5-min candles routinely exceed this threshold. During HIGH_VOL/NEUTRAL (4/6) or LOW_VOL regimes, many candles do not. The signal was right about direction on 4/6 at 52.2% — but that's a losing rate on perps once fees are deducted.

### Evidence from dailies

| Date | Regime | WR | P&L (paper) | Notes |
|------|--------|----|-------------|-------|
| 2026-04-03 | MEDIUM_VOL/TRENDING | 57.6% | +$125 | Candles large, directional |
| 2026-04-04 | Mixed | 61.1% | +$200 | Transition day |
| 2026-04-05 | MEDIUM_VOL/TRENDING | 75.0% | +$400 | Best day — magnitude present |
| 2026-04-06 | HIGH_VOL/NEUTRAL | 52.2% | +$50 | Direction OK, magnitude absent |

---

## 2. Design Principle

**The signal predicts direction. The execution structure must handle magnitude.**

This means:
- Fixed take-profit and stop-loss to bound outcomes (synthetic binary payoff)
- Volatility-aware filters to skip trades where expected magnitude < fee floor
- Regime-conditional parameters so the strategy adapts to current market conditions
- Maximum hold time to prevent drift from the signal's 5-minute prediction horizon

---

## 3. Approach A: Fixed-Structure Trades (Ship First)

### 3.1 Trade Structure

Every perps trade has three exit conditions. Whichever triggers first closes the position.

### AC-BP-1 Entry
IF momentum signal fires with `conv >= 3` AND `magnitude_filter = PASS` (see AC-BP-5):
→ Market order (taker) in signal direction
→ Size: per conviction tier (see Section 6)

### AC-BP-2 Take-Profit
```
LONG:  take_profit = entry_price × (1 + tp_pct)
SHORT: take_profit = entry_price × (1 - tp_pct)
```

Default `tp_pct = 0.30%` ($252 on $84K BTC).

Rationale: 0.30% is ~2× the round-trip cost floor. This ensures wins meaningfully exceed costs. Backtestable against historical candle data.

### AC-BP-3 Stop-Loss
```
LONG:  stop_loss = entry_price × (1 - sl_pct)
SHORT: stop_loss = entry_price × (1 + sl_pct)
```

Default `sl_pct = 0.20%` ($168 on $84K BTC).

Reward-to-risk ratio: 1.5:1 (0.30% / 0.20%). Breakeven WR at this ratio: **~42%**. Any directional WR above 42% is profitable.

### AC-BP-4 Max Hold Time
IF position is still open after **5 minutes** from entry:
→ Close at market price regardless of P&L
→ Log as `max_hold_exit` with unrealized P&L at close

Rationale: The signal predicts the *next* 5-min candle. Beyond that horizon, the prediction has no informational value. Holding longer is a gamble, not a strategy.

### 3.2 Magnitude Filter

### AC-BP-5 ATR Gate
Before entering, compute:
```
atr_5 = average true range of the last 5 completed 5-min candles
fee_floor = 0.15%   (round-trip fees + estimated slippage)
```

Decision:
```
IF atr_5 >= fee_floor × 2:   → PASS (magnitude likely sufficient)
IF atr_5 < fee_floor × 2:    → SKIP (candles too small to clear costs)
```

The `× 2` multiplier requires that the average candle is at least 2× the cost floor. This filters out low-volatility periods where even correct directional calls lose money.

### AC-BP-6 ATR Logging
System MUST log `atr_5` for every signal (traded or skipped) to enable post-hoc analysis of the filter's effectiveness.

---

## 4. Approach B: Regime-Conditional Parameters (Phase 2)

After Approach A validates on 100+ trades, layer on regime-specific TP/SL/sizing.

### AC-BP-7 Regime Table

| Regime | TP | SL | Sizing | ATR Gate |
|--------|----|----|--------|----------|
| MEDIUM_VOL / TRENDING | 0.40% | 0.20% | Full | atr_5 ≥ 0.20% |
| MEDIUM_VOL / NEUTRAL | 0.25% | 0.15% | Full | atr_5 ≥ 0.20% |
| HIGH_VOL / TRENDING | 0.50% | 0.30% | 75% | atr_5 ≥ 0.30% |
| HIGH_VOL / NEUTRAL | 0.20% | 0.15% | 50% | atr_5 ≥ 0.25% |
| LOW_VOL / any | — | — | SKIP | — |

Rationale:
- **MEDIUM_VOL/TRENDING** is the sweet spot — directional moves with sufficient magnitude. Widest TP to capture full move.
- **HIGH_VOL/TRENDING** has magnitude but noise. Wider TP and SL to accommodate, reduced size to limit risk.
- **HIGH_VOL/NEUTRAL** is the worst case for momentum. Tight TP to grab small moves, tight SL to cap losses, half size. This is the regime that killed 4/6.
- **LOW_VOL** skips entirely — candles don't clear the fee floor regardless of direction.

### AC-BP-8 Regime Override
The regime table values are starting points. After 50 trades per regime cell, system SHOULD recompute optimal TP/SL from realized trade data using:
```
optimal_tp = percentile_75 of (max favorable excursion) on winning trades
optimal_sl = percentile_75 of (max adverse excursion) on losing trades
```

This calibrates to actual market behavior rather than theoretical assumptions.

---

## 5. Approach C: ATR-Scaled Dynamic Targets (Phase 3)

Replace fixed TP/SL with volatility-responsive targets.

### AC-BP-9 Dynamic TP/SL
```
atr_5 = average true range of last 5 candles

take_profit = entry ± (1.5 × atr_5)    # 1.5 ATR in signal direction
stop_loss   = entry ∓ (1.0 × atr_5)    # 1.0 ATR against signal direction
```

Reward-to-risk ratio remains 1.5:1, but absolute levels scale with current volatility.

### AC-BP-10 ATR Floor
IF `atr_5 < 0.15%`:
→ Skip trade regardless of signal strength
→ Log as `atr_below_floor`

### AC-BP-11 ATR Cap
IF `atr_5 > 1.0%`:
→ Cap TP at `entry ± 1.0%` and SL at `entry ∓ 0.67%`
→ Prevents runaway targets during flash moves where the signal's 5-min horizon doesn't apply

### AC-BP-12 Max Hold
5-minute max hold remains in effect regardless of ATR scaling.

---

## 6. Position Sizing

### AC-BP-13 Conviction-Based Sizing
```
conv=3:  0.5× leverage  ($12.50 notional per $25 margin)
conv=4:  1.0× leverage  ($25 notional per $25 margin)
conv=5:  1.5× leverage  ($37.50 notional per $25 margin)
```

### AC-BP-14 Max Leverage
System MUST NOT exceed **3× leverage** under any circumstance. At current sizing ($25 base), this is not binding, but the constraint prevents future misconfiguration.

### AC-BP-15 Max Concurrent Positions
System MUST NOT hold more than **2 concurrent open positions**. If a second signal fires while the first is still open, the second is skipped.

Rationale: Two concurrent positions in the same direction doubles exposure to a single regime. Two in opposite directions is a hedge that nets to zero minus fees.

### AC-BP-16 Daily Loss Limit
IF realized perps P&L for the day < **-$75**:
→ Pause all perps trading until next UTC day
→ Alert: "Bybit daily loss limit hit"

Separate from Polymarket circuit breaker.

---

## 7. Fee Optimization

### AC-BP-17 Maker Entry (Future)
Phase 1 uses market orders (taker). After establishing a fill-rate baseline, explore limit-order entry at `best_bid + tick` (for longs) to earn maker rebate (0.02% on Bybit).

This mirrors the Polymarket maker-mode spec — but perps limit orders face less adverse selection than prediction market limits because perps don't have binary resolution creating discontinuous payoff cliffs.

### AC-BP-18 Fee Tracking
System MUST log per trade:
```
entry_fee:    actual fee paid on entry
exit_fee:     actual fee paid on exit
total_cost:   entry_fee + exit_fee + slippage
gross_pnl:    raw price movement × size
net_pnl:      gross_pnl - total_cost
cost_ratio:   total_cost / gross_pnl  (what % of the move went to fees)
```

IF rolling 20-trade average `cost_ratio > 0.50` → alert. More than half the edge is going to fees.

---

## 8. Backtest Requirements (Before Any Live Deployment)

### AC-BP-19 Historical Candle Backtest
Using existing 5-min BTC candle data, simulate Approach A on every historical momentum signal:

For each signal where momentum fires:
1. Record entry price (open of next candle as proxy)
2. Check if TP (0.30%) or SL (0.20%) is hit within the next 5 candles (25 minutes max, 5-min forced exit)
3. If neither hit within 1 candle (5 min), mark as `max_hold_exit` at close of that candle
4. Record outcome: `tp_hit`, `sl_hit`, `max_hold_win`, `max_hold_loss`

### AC-BP-20 Backtest Output
```
total_signals:          int
atr_filtered:           int (skipped by magnitude filter)
trades_entered:         int
tp_hit_rate:            float (% of trades that reached TP)
sl_hit_rate:            float (% of trades that hit SL)
max_hold_exit_rate:     float (% closed at time limit)
net_pnl:                float (after simulated fees)
sharpe:                 float (annualized on 5-min returns)
max_drawdown:           float
best_regime:            string
worst_regime:           string
```

### AC-BP-21 Backtest Gate
Proceed to paper trading ONLY IF:
1. Net P&L after fees is positive over full backtest period
2. TP hit rate > SL hit rate (more trades reach profit target than stop)
3. Sharpe ratio > 0.5 (modest but positive risk-adjusted returns)
4. The ATR filter removes < 50% of signals (if it removes more, the strategy is only viable in rare conditions)

### AC-BP-22 Regime Segmentation
Backtest MUST be segmented by regime. If Approach A is only profitable in MEDIUM_VOL/TRENDING, that's fine — it means the regime gate is doing its job and the strategy should only trade that regime.

---

## 9. Paper → Live Transition

### AC-BP-23 Paper Trading Phase
Minimum **14 days or 200 trades** on Bybit testnet, whichever is longer.

### AC-BP-24 Paper Success Criteria
1. Net P&L positive after simulated fees
2. Max drawdown < $150
3. Cost ratio < 0.40 (fees consume < 40% of gross edge)
4. No single day loss > $50

### AC-BP-25 Live Entry
Begin with **$100 max daily notional** (4 trades at $25). Scale to full allocation after 50 live trades IF paper criteria hold.

---

## 10. EHR Analog for Perps

Polymarket EHR measures `outcome - trade_price` (did you buy below fair value?). For perps, the analog is:

### AC-BP-26 Edge Capture Ratio
```
ECR = mean(net_pnl per trade) / mean(atr_5 at entry)
```

This measures what fraction of available price movement you actually capture after costs. An ECR of 0.10 means you're capturing 10% of the candle's range as net profit — reasonable for a short-horizon momentum strategy.

IF rolling 50-trade ECR < 0.0 → the strategy is not capturing any magnitude, regardless of directional accuracy.

---

## 11. What This Spec Does NOT Cover

- **Funding rate harvesting.** Perps have periodic funding payments. A delta-neutral funding rate strategy is a different product from directional momentum. Potentially additive but separate.
- **Multi-asset perps.** This spec is BTC-only. ETH perps face the same magnitude problem with worse liquidity. Defer until BTC perps validate.
- **Hedging Polymarket positions with Bybit.** Conceptually interesting (long binary + short perp = bounded risk), but adds execution complexity. Backlog item.

---

## 12. Implementation Order

```
Week 1:   Backtest Approach A on historical candle data (AC-BP-19 through AC-BP-22)
Week 1:   If backtest passes → deploy Approach A on Bybit testnet (paper)
Week 2-3: Paper trade 200+ signals, measure TP/SL hit rates and cost ratio
Week 3:   If paper passes → begin live with $100/day cap
Week 4:   Assess. If profitable → layer on Approach B (regime-conditional params)
Week 6+:  Approach C (ATR-scaled dynamic targets) after regime table calibrates
```

---

*The core insight: direction is a necessary but insufficient condition for perps profitability. This spec bridges the gap between "is it going up?" (what the signal answers) and "will it go up enough?" (what perps require).*
