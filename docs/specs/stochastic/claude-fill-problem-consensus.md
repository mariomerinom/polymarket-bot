# BOTSY Fill Problem: Condensed Best Approach

**Date:** 2026-04-05
**Context:** 0% live fill rate, 8 expired orders that would have won, ~$165 missed profit
**Synthesized from:** Contrarian, Opportunity Scout, Veteran HFT Engineer, Return Optimizer

---

## Root Cause (All Four Agree)

The fill problem is not a pricing problem. It is an **infrastructure problem**. The order submission path uses a stale `market_price` snapshot from the database. By the time the order hits the book, the market has already repriced in the direction your model predicted. This creates textbook adverse selection: fills cluster on losers, expirations cluster on winners.

The static 7-cent cap (5c slippage + 2c fill priority) is a symptom, not the disease.

---

## What To Do (Priority Order)

### 1. Replace the Stale Price Feed (Week 1 -- Non-Negotiable)

Every proposed solution fails if the price anchor is stale. Before touching slippage logic, add a real-time market feed (websocket) to the order submission path. `compute_order()` must use a live mid/spread, not a database snapshot.

**Impact:** This alone likely recovers 30-50% of missed fills by anchoring limits to where the market actually is, not where it was.

### 2. Implement Cancel-Replace Cycle (Week 2)

Replace fire-and-forget limit orders with an iterative approach:

- Post limit order 1-2 ticks inside the market (post-only)
- If no fill in 200-500ms, cancel and resubmit closer to mid
- Cap at 2-3 cycles, then accept market price or walk away
- Total execution window: under 2 seconds

This is standard HFT execution. It captures price improvement when available and crosses the spread only when necessary.

### 3. Deploy Dynamic Price Cap by Microstructure (Week 3)

Once the price feed is live, layer in the dynamic cap from `spec_dynamic_price_cap.md`:

```
BASE = 3c, CEILING = 15c
dynamic_slippage = BASE + depth_bonus(0-6c) + spread_bonus(0-3c) + volume_bonus(0-3c)
```

This is the right structural fix. It tightens in thin markets (protects against slippage) and widens in thick markets (captures fills). The conviction-based approach (Solution A) is inferior because high conviction correlates with fast market moves, meaning you pay maximum slippage exactly when adverse selection is worst.

**Key change from the original spec:** Add the `volume` field to the `execute_trades()` SQL query. This is the only new data pipe required.

### 4. Kill the 15-Minute Pipeline (Immediate)

The 15-minute pipeline is negative EV: 46.7% WR, -$36.22 P&L, 3 consecutive losing days, declining from 71% to 48% over 7 days. Conv=5 is hitting 37.5% WR on this timeframe.

Reallocate its capital ($375/day wagered) to the BTC 5-minute pipeline, specifically conv=5 bets which are running at 54.5% ROI.

### 5. Adjust Bet Sizing by Sharpe (Week 3+)

Flat $25 across all tiers leaves money on the table. Recommended sizing:

- BTC 5m Conv=5: Increase to $35-40 (54.5% ROI, highest Sharpe)
- BTC 5m Conv=3-4: Hold at $25
- ETH 5m: Hold at $25 (wider spreads eat margin, 3.96% avg)
- 15m pipeline: $0

### 6. Exploit the 0.15-0.30 Price Bucket

Decision Alert #6 is ready: 90% WR over 20 bets in the 0.15-0.30 bucket. Allow wider caps (10-15c) specifically for this bucket where the model has extreme conviction. These are the highest-EV plays being left on the table.

---

## What NOT To Do

**Do not implement Stochastic Entry Timing yet.** All four analyses flagged concerns:

- The Contrarian notes it mixes timeframes (1-min oscillator on a 5-min signal) and could filter out best signals by waiting for contradictory conditions
- The HFT Engineer calls it "overthinking it" when execution infrastructure is broken at a lower level
- The Return Optimizer notes it's insufficient alone since 60s windows don't solve adverse selection if quotes are visible
- The Opportunity Scout ranks it lowest-leverage of the three proposals

Stochastic timing becomes relevant once the infrastructure fixes are in place and the bot is reliably filling orders. It is an optimization on top of a working system, not a fix for a broken one.

**Do not use conviction-based slippage (Solution A) as the primary mechanism.** It creates an inverted incentive: you pay the most slippage exactly when the market is moving fastest against your order. Use microstructure signals (Solution B) instead, which measure actual book conditions rather than model confidence.

---

## EV Math on Paying for Fills

The concern about paying more per share is overblown:

- 5-7c additional slippage on a $25 bet = $1.25-1.75 cost per order
- BTC 5m ROI is 28.2%, meaning $7.05 profit per bet on average
- Even at 15c max slippage ($3.75 cost), the bet remains +EV
- Currently: 0% fill rate = 0% of edge captured
- At 60% fill rate with modest slippage: ~38% of edge captured
- Recovering 8 expired winners = $165 immediate recapture

Paying for certainty is cheap insurance on positive-ROI pipelines. The only pipeline where slippage math doesn't work is the 15m pipeline, which should be killed anyway.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Fill rate | 0% (live) | >70% |
| Expired-would-win | 8/day | <2/day |
| Avg slippage per fill | N/A | <5c |
| 15m pipeline allocation | $375 | $0 |
| BTC 5m conv=5 bet size | $25 | $35-40 |

## Revert Criteria

- Fill rate drops below 50% over 50 bets
- Average slippage cost increases by more than 3c per bet
- Any order fills at >20c above market mid
- Daily P&L drops below -$100 for 2 consecutive days

---

*Signed: Claude*
*2026-04-05*
