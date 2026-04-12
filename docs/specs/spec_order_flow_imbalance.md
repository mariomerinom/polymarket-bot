# Spec: Order Flow Imbalance Strategy

> **Status:** STILL RELEVANT — CLOB data available but no imbalance detection built

**Status:** Proposed
**Pipeline:** BTC 5m (primary), ETH 5m (after liquidity improves)
**Category:** New strategy — leading indicator. Independent from momentum.
**Problem:** The momentum strategy is a lagging indicator: it waits for 3+ candles to confirm a streak before acting. By that point, 15+ minutes of the move have already happened. The CLOB order book contains information about where money is positioning *before* the price moves. This is a fundamentally different signal source — it's forward-looking, not backward-looking.
**Goal:** Use bid/ask imbalance in the Polymarket CLOB to predict short-term contract direction before the candle data confirms it.

---

## Why This Is Different from Momentum

| Aspect | Momentum (current) | Order Flow Imbalance |
|--------|-------------------|---------------------|
| Signal source | BTC exchange candles | Polymarket CLOB order book |
| Timing | Lagging — needs 3+ candles | Leading — sees positioning before the move |
| What it detects | Trend continuation | Informed money positioning |
| Overlap with existing | N/A — it *is* the existing strategy | Low — different data source entirely |
| Works in regimes | TRENDING, NEUTRAL | Any regime where the book is active |
| Edge source | BTC price momentum | Polymarket-specific microstructure |

The key insight: on traditional exchanges, order flow imbalance is a well-studied alpha source. On Polymarket, the CLOB is thinner and less efficient — imbalance signals are likely stronger and less arbitraged away.

---

## Signal Logic

### Core Metric: Book Imbalance Ratio

```
imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
```

Where `bid_depth` = total YES bid volume within N levels, `ask_depth` = total NO bid volume within N levels (or equivalently, YES ask volume).

| Imbalance | Interpretation | Signal |
|-----------|---------------|--------|
| > +0.3 | Strong buying pressure on YES | Predict UP |
| +0.1 to +0.3 | Moderate buying pressure | Weak UP signal |
| -0.1 to +0.1 | Balanced book | No signal |
| -0.3 to -0.1 | Moderate selling pressure | Weak DOWN signal |
| < -0.3 | Strong selling pressure on NO | Predict DOWN |

### Imbalance Velocity

Static imbalance is useful but imbalance *change* is more predictive. If the book flips from balanced to heavily bid-side in 2 minutes, someone is aggressively positioning.

```
imbalance_velocity = (imbalance_now - imbalance_2min_ago) / 2
```

| Velocity | Meaning |
|----------|---------|
| > +0.1/min | Rapid buying pressure building |
| < -0.1/min | Rapid selling pressure building |
| Near 0 | Stable positioning — no urgency |

### Combined Signal

```
if abs(imbalance) > 0.3 AND imbalance_velocity confirms direction:
    signal = direction with high confidence
elif abs(imbalance) > 0.3 OR abs(imbalance_velocity) > 0.1:
    signal = direction with medium confidence
else:
    no signal
```

---

## Depth Levels and Weighting

Not all levels are equal. Orders close to mid-price are more likely to execute and represent stronger commitment.

```
weighted_depth = Σ(volume_at_level × weight)
where weight = 1 / (1 + distance_from_mid)
```

| Level Distance | Weight | Rationale |
|---------------|--------|-----------|
| 0 (best bid/ask) | 1.00 | Highest commitment — will fill first |
| 1 tick away | 0.50 | Still close, likely fills |
| 2 ticks | 0.33 | Moderate commitment |
| 3+ ticks | 0.25 | Backstop liquidity — may be pulled |

Your CLOB data already captures 30-69 depth levels. Use the top 5-10 for signal generation; deeper levels are noise.

---

## Interaction with Momentum

Order flow imbalance and momentum can run as independent strategies or as confirmation layers:

### Mode A: Independent Signal (Recommended for v1)

Order flow generates its own predictions, separate from momentum. Both feed into the same conviction scorer and downstream filters. This captures edge that momentum misses (early moves, non-trending regimes).

```
candle data → momentum signal ──────────→ conviction scorer → filters → bet
CLOB data   → order flow signal ────────→ conviction scorer → filters → bet
```

### Mode B: Confirmation Layer (Future optimization)

Order flow confirms or downgrades momentum signals. A momentum signal with confirming order flow gets a conviction boost. A momentum signal with contradicting order flow (price streaking up but book is selling) gets a downgrade.

```
candle data → momentum signal ─┐
                                ├─→ combined scorer → filters → bet
CLOB data   → order flow signal ┘
```

Mode A is cleaner to validate because the signals are independent. Mode B requires careful interaction design and more data to calibrate.

---

## Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Depth levels used | 5 | Top 5 levels, weighted by distance |
| Imbalance threshold | ±0.3 | Below this = balanced, no signal |
| Velocity window | 2 minutes | Rate of change of imbalance |
| Velocity threshold | ±0.1/min | Below this = stable |
| Snapshot frequency | Every 30 seconds | Needs higher frequency than current per-prediction snapshots |
| Cooldown | 2 minutes between signals | Prevent rapid-fire bets on the same imbalance shift |
| Min book depth | 3 levels with orders | If fewer, book is too thin to read reliably |

---

## Data Requirements

| Data | Source | Currently Available? |
|------|--------|---------------------|
| Polymarket CLOB snapshots | `clob_depth.py` via Polymarket API | Partially — current snapshots are per-prediction. Need higher frequency (every 30s) |
| Historical CLOB snapshots | Internal logging | No — need to start storing snapshots for backtesting |
| YES/NO bid volumes by level | Polymarket CLOB | Yes — already parsed in `get_liquidity_summary()` |
| Mid-price | Derived from best bid/ask | Yes |
| Timestamp per snapshot | System clock | Yes |

### New Infrastructure Needed

1. **CLOB polling loop:** Currently `clob_depth.py` is called once per prediction. Need a background process that snapshots the order book every 30 seconds for active markets and stores them in the DB.
2. **Imbalance time series table:** New DB table storing `(market_id, timestamp, imbalance, bid_depth, ask_depth, levels)` for rolling analysis.
3. **Backfill:** Once the polling loop is running, accumulate 3-5 days of snapshots before activating the strategy. This provides enough data to calibrate thresholds.

---

## ETH Considerations

ETH CLOB data shows 50% of spreads are wide (>3%) and max bet at 2% slippage is $34. The order book is thinner, which means:

- Imbalance signals may be stronger (small orders move the ratio more)
- But also noisier (a single large order can create false imbalance)
- Min book depth requirement must be stricter (5+ levels with orders)
- Do not enable on ETH until book depth consistently exceeds 10 active levels

---

## Expected Impact

The strategy's value comes from *timing*. Momentum waits 15+ minutes (3 candles × 5 min). Order flow can signal within 1-2 minutes of informed positioning.

If order flow captures even 5 signals per day that momentum misses (early moves, non-streak setups):

```
5 bets/day × $75 (conv=3) × 60% WR = ~$37.50/day
Monthly: ~$1,125
```

Conservative estimate. The real upside is if order flow can frontrun momentum signals — betting before the streak reaches 3 candles.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Spoofing — fake orders placed to mislead then pulled | Use imbalance velocity, not static imbalance. Spoofed orders are typically placed and pulled quickly. Require imbalance to persist for 60+ seconds |
| Thin books create noisy imbalance | Min depth requirement (3+ levels). Weight by distance from mid. Wider thresholds for thin markets |
| CLOB polling adds API load | 30-second intervals are conservative. Polymarket API rate limits are generous for read-only CLOB queries |
| Strategy is front-runnable | Polymarket is on Polygon — MEV is minimal compared to Ethereum mainnet. Transaction ordering is less gameable |
| Correlation with momentum | Track correlation between order flow and momentum signals. If >0.7 correlated, the strategy isn't adding new information |

---

## Validation Plan

```
name: order_flow_imbalance
type: shadow (Phase 1), then small stakes (Phase 2)

Phase 1 — Data Collection (1 week):
  - Deploy CLOB polling loop
  - Accumulate snapshots every 30s for all active BTC markets
  - Compute imbalance and velocity retroactively
  - Correlate with actual outcomes
  - Calibrate thresholds

Phase 2 — Shadow (50 bets):
  - Generate shadow predictions from order flow signals
  - Log alongside momentum predictions
  - Track: WR, P&L, correlation with momentum, timing advantage
  - Success: WR > 55%, correlation with momentum < 0.5

Phase 3 — Small Stakes (50 bets):
  - Enable at conv=3 ($75)
  - Independent circuit breaker: $300 max drawdown
  - Success: positive P&L after spread/slippage
```

---

## Decision

This strategy requires new infrastructure (CLOB polling loop, imbalance time series). It cannot be shipped as a config change. Prioritize the polling loop — it provides data for both this strategy and future CLOB-based improvements. Start data collection immediately; activate shadow mode after 3-5 days of accumulated snapshots.
