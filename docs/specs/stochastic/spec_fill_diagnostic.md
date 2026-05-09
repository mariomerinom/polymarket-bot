# Spec: Fill Diagnostic — Resolve Tension 1 & 2

> **Status:** PARTIALLY IMPLEMENTED — Logging present, validation framework incomplete

**Status:** Proposed
**Pipeline:** All live pipelines
**Duration:** 24-48 hours of logging, zero execution changes
**Goal:** Collect the two measurements that settle the conviction and infrastructure debates with data.

---

## Measurement A: Decision Delay And Orderbook Freshness (Resolves Tension 2)

**Question:** Is execution suffering from delayed prediction dispatch, stale orderbook reads, or both?

### Implementation

Log decision delay from candle close separately from true orderbook freshness:

```python
decision_delay_ms = now_ms - candle_ts_ms
log.info(f"DIAG|decision_delay_ms={decision_delay_ms:.0f}|market={market_id}")

orderbook_age_ms = now_ms - token_entry.updated_at_ms
log.info(f"DIAG|orderbook_age_ms={orderbook_age_ms:.0f}|market={market_id}")
```

Log every invocation, including skips and filters.

### Decision Rules

| Metric | Conclusion |
|---------------------|------------|
| Decision delay p95 < 30s | Dispatch delay is acceptable for paper promotion review. |
| Decision delay p95 >= 30s | Pipeline fanout or research work is delaying decisions. |
| Orderbook age p95 < 2s | CLOB cache freshness is acceptable. |
| Orderbook age p95 >= 2s | Polymarket cache coverage/freshness is a production blocker. |

### Bonus: API Latency

While logging, also capture round-trip time for order submission:

```python
t0 = time.monotonic()
response = submit_order(...)
rtt_ms = (time.monotonic() - t0) * 1000
log.info(f"DIAG|order_rtt_ms={rtt_ms:.0f}|status={response.status}")
```

This determines whether cancel-replace cycles are feasible on Polymarket's API. If RTT > 1s, cancel-replace is impractical.

---

## Measurement B: Conviction vs. Price Drift (Resolves Tension 1)

**Question:** Do high-conviction signals correlate with faster market moves (worse adverse selection)?

### Implementation

For every prediction that reaches `compute_order()`, log the price delta between the DB snapshot and a fresh API call:

```python
live_price = fetch_live_mid(market_row["market_id"])  # single REST call
price_drift = abs(live_price - market_price_yes)
conviction = prediction_row.get("conviction_score", 0)
log.info(f"DIAG|conv={conviction}|drift={price_drift:.4f}|market={market_row['market_id']}")
```

This is read-only. It does not change order pricing or execution.

### Decision Rules

| Finding | Conclusion |
|---------|------------|
| Conv=5 drift >> Conv=3 drift (statistically significant) | Conviction predicts adverse selection. Exclude from pricing formula (Claude is right). |
| No significant correlation | Conviction is safe to use. Apply as ceiling/governor (Gemini approach). |
| Conv=5 drift < Conv=3 drift | Conviction inversely correlates with adverse selection. Additive bonus is defensible (Grok approach). |

**Statistical bar:** Require p < 0.05 on a Mann-Whitney U test between conv=3 and conv=5 drift distributions. Minimum 20 samples per tier.

---

## What This Does NOT Change

- No modifications to order pricing, slippage caps, or execution logic
- No changes to bet sizing, pipeline allocation, or conviction thresholds
- All logging is additive — zero regression risk

## Files to Change

| File | Change |
|------|--------|
| `src/trade.py` | Add 4 log lines inside `compute_order()` |

That's it. One file, four log lines, 24 hours.

---

## After the Data Is In

Run this analysis script against the logs:

```
1. Histogram of decision_delay_ms (p50, p95, p99)
2. Histogram of orderbook_age_ms (p50, p95, p99)
3. Histogram of order_rtt_ms (feasibility of cancel-replace)
4. Box plot of price_drift grouped by conviction tier
5. Mann-Whitney U test: conv=3 drift vs conv=5 drift
```

The output is a one-page table that tells you exactly which of the three approaches (Grok/Gemini/Claude) is correct for your specific market conditions. Ship the formula change that the data supports.
