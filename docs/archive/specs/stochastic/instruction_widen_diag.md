# Instruction: Widen DIAG Logging to Prediction Path

> **Status:** IMPLEMENTED — DIAG logging extended to predict.py path

**Context:** Phase 2 diagnostic logging currently lives inside `compute_order()` in `trade.py`. This only fires when a prediction passes all filters and reaches order submission (~41 times/day at best). When the market is quiet (conv=0 skips), zero DIAG lines are emitted and `validate_phase2.py` has nothing to analyze. We need data accumulating on every prediction cycle.

**Goal:** Move snapshot_age and conviction-vs-drift DIAG logging upstream into the prediction path so every prediction emits diagnostics, regardless of whether it becomes an order.

---

## What to Change

### 1. Add DIAG logging in `predict.py` (or wherever predictions are generated)

After the model produces a prediction and before any order/filter logic, emit two DIAG lines:

```python
# After prediction is generated, before any filtering
import time

# --- DIAG: snapshot age ---
# snapshot_age_ms = how old the price data is at prediction time
# Use the timestamp of the most recent candle vs now
candle_ts = <timestamp of the most recent candle used for this prediction, in ms>
snapshot_age_ms = (time.time() * 1000) - candle_ts
log.info(f"DIAG|snapshot_age_ms={snapshot_age_ms:.0f}|market={market_id}")

# --- DIAG: conviction vs drift ---
# conviction = model's conviction score (0-5)
# drift = absolute price change since the candle close used for prediction
#         i.e., |current_price - candle_close| / candle_close
drift = abs(current_price - candle_close) / candle_close if candle_close > 0 else 0.0
log.info(f"DIAG|conv={conviction}|drift={drift:.4f}|snapshot_age_ms={snapshot_age_ms:.0f}")
```

**Key details:**
- `market_id` = the Polymarket market/token being predicted on
- `conviction` = the integer conviction score the model assigned (0–5)
- `current_price` = live price at prediction time (from DB or API)
- `candle_close` = the close price of the candle the model used as input
- `candle_ts` = the timestamp (epoch ms) of that candle

### 2. Keep RTT logging in `compute_order()` (no change)

The RTT line requires a real order round-trip. Leave it where it is:

```python
log.info(f"DIAG|order_rtt_ms={rtt_ms:.0f}|status={response.status}")
```

This will naturally fire less often. That's fine — `validate_phase2.py` already handles sparse RTT data separately.

### 3. Do NOT remove the existing DIAG lines in `compute_order()`

The existing snapshot_age and drift lines in `compute_order()` can stay. Duplicate data is harmless — more samples is better. Or remove them if you prefer; the upstream ones will provide far more volume.

---

## Format Requirements (Critical)

The log lines MUST match these exact regex patterns used by `validate_phase2.py`:

```
DIAG|snapshot_age_ms=<number>|market=<string>
DIAG|conv=<integer>|drift=<decimal>|snapshot_age_ms=<number>
DIAG|order_rtt_ms=<number>|status=<string>
```

- No spaces around `|` or `=`
- `conv` must be an integer (0, 1, 2, 3, 4, 5)
- `drift` must be a decimal with 4 places (e.g., `0.0023`)
- `snapshot_age_ms` must be a number (integer or float, no negatives)
- `market` must be a non-whitespace string

If the format deviates at all, `validate_phase2.py` will count parse errors and the data is wasted.

---

## Expected Impact

| Metric | Before (order path only) | After (prediction path) |
|--------|--------------------------|------------------------|
| snapshot_age samples/day | 0–41 | ~275+ (every prediction cycle) |
| conv-vs-drift samples/day | 0–41 | ~275+ |
| RTT samples/day | 0–41 | 0–41 (unchanged, still needs real orders) |
| Time to 100 samples | Days to weeks | < 12 hours |

---

## Validation

After deploying, confirm within 1 hour:

```bash
grep "DIAG|" logs/loop.log | tail -20
grep "DIAG|" logs/loop.log | wc -l
```

You should see DIAG lines appearing every ~5 minutes (one snapshot + one conv/drift per prediction cycle). If you see zero, the logging isn't in the right code path.

Then run:

```bash
python validate_phase2.py --log-file logs/loop.log --min-samples 30
```

It should pass the "DIAG lines found" and "Snapshot age samples" quality checks within a few hours.
