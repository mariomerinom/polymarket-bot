# Spec: Fill Diagnostic — Resolve Tension 1 & 2

> **Status:** PARTIALLY IMPLEMENTED — Logging present, validation framework incomplete

**Status:** Proposed
**Pipeline:** All live pipelines
**Duration:** 24-48 hours of logging, zero execution changes
**Goal:** Collect the two measurements that settle the conviction and infrastructure debates with data.

---

## Measurement A: Snapshot Staleness (Resolves Tension 2)

**Question:** How old is the `market_price` when `compute_order()` uses it?

### Implementation

Add one timestamp comparison at the top of `compute_order()`:

```python
snapshot_age_ms = (datetime.utcnow() - market_row["updated_at"]).total_seconds() * 1000
log.info(f"DIAG|snapshot_age_ms={snapshot_age_ms:.0f}|market={market_row['market_id']}")
```

Log every invocation, including skips and filters.

### Decision Rules

| Snapshot Age (p95) | Conclusion |
|---------------------|------------|
| < 500ms | Staleness is not the bottleneck. Deploy formula change directly (Grok/Gemini are right). |
| 500ms - 2s | Gray zone. Deploy formula change now, plan real-time feed as follow-up. |
| > 2s | Infrastructure is the root cause. Real-time feed must come first (Claude is right). |

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
1. Histogram of snapshot_age_ms (p50, p95, p99)
2. Histogram of order_rtt_ms (feasibility of cancel-replace)
3. Box plot of price_drift grouped by conviction tier
4. Mann-Whitney U test: conv=3 drift vs conv=5 drift
```

The output is a one-page table that tells you exactly which of the three approaches (Grok/Gemini/Claude) is correct for your specific market conditions. Ship the formula change that the data supports.
