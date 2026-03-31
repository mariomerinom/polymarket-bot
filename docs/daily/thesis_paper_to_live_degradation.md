# Thesis: Paper-to-Live Win Rate Degradation

**Status:** Pre-production baseline
**Date:** 2026-03-31
**Pipeline:** BTC 5m (production candidate)

---

## Summary

Paper trading assumes perfect execution. Live trading does not get perfect execution. This document quantifies every factor that will erode win rate from paper to live, sets expectations, and defines revert criteria.

**Paper WR (7-day trailing, Mar 23-30):** 67-73%
**Expected live WR:** 60-66%
**Break-even WR at current spread/sizing:** ~54%
**Margin of safety:** 6-12pp above break-even

---

## Degradation Factors

### 1. Spread Cost (-2 to -3pp)

**Mechanism:** Paper predictions assume mid-price execution. The bot logs a prediction at estimate=0.62, and paper P&L calculates as if we bought YES at the market mid-price (~0.50). In reality, we pay the ask price, which is mid + half the spread.

**Data:** BTC Polymarket avg spread is 1.50% (from CLOB data, Mar 25-30). On a $25 bet at 0.50 mid-price:
- Paper buys at: $0.500
- Live buys at: ~$0.508 (ask side)
- Cost per trade: ~$0.38

Over 15 bets/day, that's $5.70/day of spread drag. At $25/bet, a winning trade profits ~$20. The spread cost turns approximately 1 marginal win per 5-6 bets into a loss, which on 15 daily bets is -2 to -3pp on WR.

**Why this is the biggest factor:** Every single trade pays the spread. There is no way around it. The spread is the market maker's edge — we're paying rent to trade.

### 2. Slippage (-0.5 to -1pp)

**Mechanism:** Our limit orders specify a price (e.g., buy YES at 0.52), but the actual fill may execute at a worse price if the book moves between order submission and matching.

**Mitigations already in place:**
- Thin book guard caps bets at 90% of CLOB max@2% slippage
- Limit orders (not market orders) — we set a ceiling
- $25 size is small relative to book depth ($910 avg max@2%)

**Residual risk:** Even with limit orders, in fast-moving 5-minute markets, the book can gap. Our limit might fill at the limit price but the "fair" price has already moved past us. This is slippage we can't see in the fill price.

**Estimate:** At $25 on BTC with tight spreads, slippage is minor. ~0.5-1% of trades get materially worse fills.

### 3. Timing / Latency (-1 to -2pp)

**Mechanism:** The prediction is generated based on candle data at time T. The order reaches the CLOB at time T + delta. In that delta, the market may have already moved.

**Measured delays:**
- CI pipeline: prediction → trade execution: ~5-15 seconds (same Python process)
- CLOB API: order submission → acknowledgment: ~1-3 seconds
- CLOB matching: order placed → filled: 0-30 seconds (depends on liquidity)
- **Total: ~10-45 seconds from signal to fill**

**In a 5-minute market, 10-45 seconds is 3-15% of the trading window.** If the signal is based on momentum (streak continuation), and the momentum is already pricing in during those 45 seconds, our entry is late. The edge decays with every second of delay.

**Paper doesn't have this problem:** Paper timestamps the prediction and evaluates at market close. The "order" is instant and free.

**Quantification:** If 10-15% of predictions are on markets where the edge evaporates in the first minute (fast momentum that already priced in), that's -1 to -2pp.

### 4. Fill Rate (-1 to -2pp)

**Mechanism:** Paper assumes 100% of qualifying predictions result in bets. Live GTC limit orders may not fill before the 5-minute market closes.

**Scenarios where orders don't fill:**
- Book is too thin at our price level
- Price moves away from our limit before matching
- Market closes before our order is reached in the queue
- CLOB API rejects the order (validation, balance, etc.)

**Selection bias:** The orders most likely to NOT fill are the marginal ones — where our limit price is close to the current market. These are also the ones closest to 50/50, so missing them has a moderate WR impact. But if we disproportionately miss winners (because winning bets are the ones where price is moving in our direction and away from our limit), the impact is worse.

**Estimate:** Based on Polymarket 5-minute market liquidity (avg $910 max bet@2%), at $25 bets, fill rate should be >90%. But the 5-10% that don't fill could be biased toward winners or losers unpredictably. Assuming random: -1pp. Assuming adverse selection in fills: -2pp.

### 5. Adverse Selection (-0.5 to -1pp)

**Mechanism:** When our limit order fills, it means someone on the other side chose to sell to us (or buy from us). In efficient markets, the counterparty may have information we don't.

**In Polymarket 5-minute markets:** The counterparties are:
- Market makers (automated, edge from spread)
- Other bots (may have faster/better signals)
- Retail (less informed, our best counterparty)

**At $25 size:** We're too small to attract sophisticated counterparty attention. Most fills will come from standing market maker liquidity. Adverse selection is minor.

**Estimate:** 0.5-1pp. The market maker's edge is built into the spread (already counted in factor 1), so this is the residual adverse selection beyond the spread.

### 6. Market Impact (-0 to -0.5pp)

**Mechanism:** Our order changes the order book. Buying $25 of YES shares at 0.52 removes liquidity at that level, potentially pushing the price up. If many similar bots are trading the same signal, the collective impact is larger.

**At $25 on BTC (avg book: $910@2%):** Our order is 2.7% of the book. Negligible impact.

**At $50+ (future scaling):** Starts to matter. At $75, we're 8.2% of the book.

**Estimate:** At current $25 sizing, effectively zero. Flag for future if we scale.

---

## Aggregate Estimate

| Scenario | Spread | Slippage | Timing | Fill Rate | Adverse Sel. | Impact | Total | Live WR |
|----------|--------|----------|--------|-----------|-------------|--------|-------|---------|
| **Best case** | -2pp | -0.5pp | -1pp | -1pp | -0.5pp | 0pp | **-5pp** | **~68%** |
| **Expected** | -2.5pp | -0.75pp | -1.5pp | -1.5pp | -0.75pp | 0pp | **-7pp** | **~66%** |
| **Worst case** | -3pp | -1pp | -2pp | -2pp | -1pp | -0.5pp | **-9.5pp** | **~63%** |

Using paper trailing WR of 73% (Mar 28-30 avg):
- Best case: 68% live → very profitable, ~$90/day at $25 flat
- Expected: 66% live → solidly profitable, ~$65/day
- Worst case: 63% live → marginally profitable, ~$30/day

All scenarios remain above break-even (54%).

---

## Revert Criteria

Defined now, before we're watching the numbers and bias creeps in.

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Live WR < 55% after 50 bets | Pause trading, diagnose | Within 1pp of break-even. Edge may not survive execution costs. |
| Live WR < 50% after 30 bets | Kill switch, full review | Below coin flip. Something is fundamentally broken in execution. |
| Circuit breaker trips 2x in 7 days | Reduce bet size to $10 | Variance is too high for current sizing. Grind smaller. |
| Avg slippage > 3% over 20 fills | Review limit price logic | Entry pricing is too aggressive or book is thinner than expected. |
| Fill rate < 80% over 50 orders | Review order timing/pricing | Too many orders expiring unfilled. May need to cross the spread. |

---

## What We'll Measure

Track from day 1 of live trading:

1. **Live WR vs paper WR** (same-period comparison, not historical paper)
2. **Actual spread paid** (price_filled vs mid-price at prediction time)
3. **Fill rate** (filled orders / submitted orders)
4. **Time to fill** (order placed → order filled)
5. **Slippage** (price_limit vs price_filled)
6. **Unfilled order analysis** (would the unfilled bets have won or lost?)

All of these surface in the dashboard and daily report automatically via the orders table.

---

## Decision Gate

After 50 live bets:
- Compare live WR to this thesis
- If degradation is within the -5 to -9pp range → thesis validated, continue
- If degradation is worse → investigate which factor is larger than expected
- If degradation is better → thesis was conservative, consider scaling to $50

Register as Decision #17 in `docs/decisions.md`.
