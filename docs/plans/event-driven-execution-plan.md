# Plan: Event-Driven Trade Execution

## Context

The bot currently couples prediction and execution in the same 5-minute cycle. When `dispatch()` fires on a candle close, the pipeline predicts AND trades in one shot. But the Polymarket WS feed updates the orderbook cache continuously (~every second). If the orderbook improves 30 seconds after a cycle fires, we miss the edge entirely — we won't look again for another 5 minutes.

This is the primary fill-rate blocker: the bot sees the right direction (67.4% WR) but often can't execute because the orderbook at cycle time doesn't meet the FAK/IOC edge threshold (`edge >= spread + 0.02`). By the time the book moves in our favor, the cycle is over.

**Goal:** Decouple prediction (still 5m candle-driven) from execution (reactive to WS orderbook events). When a prediction is active and the live book shows sufficient edge, fire FAK immediately — take available liquidity now, kill the remainder, and don't wait for the next 5m cycle.

## Frozen File Check

🚫 FAIL — Requires changes to:
- `src/ci_run.py` — frozen, but only to pass through the new execution mode (minimal)

The core changes are in `src/botsy_engine.py` (not frozen), `src/trade.py` (not frozen), and a new `src/reactive_executor.py`.

**Mitigation:** ci_run.py changes are purely additive (one parameter passthrough). The reactive executor is a parallel path — existing 5m execution remains as fallback.

## Prerequisites

- [x] VPS deployment live with WS feeds (Bybit + Polymarket)
- [x] Orderbook cache (`data/live_orderbook.json`) updating per-token
- [x] Pipeline isolation landed (pipeline_name threaded to execute_trades) — see [pipeline-isolation-unification.md](pipeline-isolation-unification.md)
- [x] FAK/IOC logic validated in compute_order()
- [ ] BTC 5m fill rate baseline measured (current: estimate ~30-40% of qualifying predictions fill)

## Backward — What Breaks?

### Affected Pipelines
- **BTC 5m** (production) — primary beneficiary; reactive execution fires FAK between cycles
- **ETH 5m** (paper) — same reactive path, paper mode
- **BTC 15m** (paper) — same reactive path, paper mode
- **Kalshi** — NOT affected (no CLOB execution)

### Affected Tests
- `tests/test_ci_run_lifecycle.py` — needs mock for reactive executor
- `tests/test_pipeline_isolation.py` — needs reactive path isolation test
- `tests/test_multi_pipeline_fok.py` — needs reactive FAK variant; filename remains legacy-compatible

### Rollback Plan
1. Set `REACTIVE_EXECUTION=false` in env (kill switch — immediate disable)
2. Or: remove the `_reactive_check()` hook from `_update_orderbook_cache()` — one-line revert
3. Existing 5m execution remains fully functional as fallback — never removed

## Implementation Steps

### Step 1: Instrument fill-rate baseline
**Files:** `src/trade.py`, `tests/test_trade_fill_tracking.py`
**Change:** Add `fill_opportunity_window` column to orders table. When `compute_order()` produces a qualifying order but the cycle is over, log the missed window. Query: "How many 5m cycles had edge appear within 60s after cycle completion?"
**Commit:** `Add fill opportunity window tracking for baseline measurement`
**Tests:** Test that fill_opportunity_window is recorded on order creation

### Step 2: Create reactive executor module
**Files:** `src/reactive_executor.py` (NEW), `tests/test_reactive_executor.py` (NEW)
**Change:** New module with core logic:

```python
class ReactiveExecutor:
    """Monitors active predictions and fires FAK when orderbook shows edge."""

    def __init__(self, db_path, pipeline_name, min_edge_buffer=0.02):
        self.db_path = db_path
        self.pipeline_name = pipeline_name
        self.min_edge_buffer = min_edge_buffer
        self._pending_predictions = {}  # prediction_id → prediction_row
        self._fired = set()  # prediction_ids already executed
        self._cooldown_s = 30  # min seconds between attempts per prediction

    def register_prediction(self, prediction_row, market_row):
        """Called by pipeline after predict step. Registers for reactive monitoring."""

    def on_orderbook_update(self, asset_id, book_entry):
        """Called on every WS book event. Checks if any pending prediction has edge."""

    def _check_and_fire(self, prediction_id, book_entry):
        """Compute edge, fire FAK if threshold met. Deregister on fill."""

    def deregister(self, prediction_id):
        """Remove prediction from monitoring (filled, expired, or resolved)."""

    def cleanup_expired(self):
        """Remove predictions whose markets have resolved or expired."""
```

**Key design decisions:**
- **One executor per pipeline** — isolation by construction (matches pipeline_name threading)
- **Deregister on fill** — prevents double-execution
- **Cooldown** — 30s between attempts per prediction prevents order spam
- **Thread-safe** — uses `threading.Lock` since WS callbacks are on separate threads
- **Paper mode respected** — checks `is_pipeline_live(pipeline_name)` before submitting

**Commit:** `Add ReactiveExecutor: fire FAK on live orderbook edge`
**Tests:**
- `test_fires_fak_when_edge_appears` — register prediction, simulate book update with edge → FAK fired
- `test_no_fire_below_threshold` — book update with insufficient edge → no order
- `test_deregister_after_fill` — filled order removes prediction from monitoring
- `test_cooldown_prevents_spam` — two updates within 30s → only one order attempt
- `test_paper_mode_no_live_orders` — paper pipeline → orders logged but not submitted
- `test_expired_predictions_cleaned` — resolved market predictions auto-removed

### Step 3: Wire executor into botsy_engine
**Files:** `src/botsy_engine.py`
**Change:**
1. Create one `ReactiveExecutor` per pipeline in `__init__()`:
   ```python
   self._reactive_executors = {
       "btc_5m": ReactiveExecutor(DB_PATH, "btc_5m"),
       "eth_5m": ReactiveExecutor(DB_PATH_ETH, "eth_5m"),
       "btc_15m": ReactiveExecutor(DB_PATH_15M, "btc_15m"),
   }
   ```
2. Hook `_update_orderbook_cache()` — after updating cache, call each executor:
   ```python
   # At end of _update_orderbook_cache(), after cache write:
   for executor in self._reactive_executors.values():
       executor.on_orderbook_update(asset_id, entry)
   ```
3. After `dispatch()` runs a pipeline, register new predictions with the executor:
   ```python
   # In run_pipeline(), after pipeline.main() returns:
   if pipeline_name in self._reactive_executors:
       new_predictions = get_pending_predictions(db, cycle)
       for pred, market in new_predictions:
           self._reactive_executors[pipeline_name].register_prediction(pred, market)
   ```

**Commit:** `Wire ReactiveExecutor into engine orderbook feed`
**Tests:** Integration test with mock WS events → verify executor.on_orderbook_update called

### Step 4: Add kill switch and observability
**Files:** `src/reactive_executor.py`, `src/config.py`
**Change:**
- `REACTIVE_EXECUTION` env var (default: `false` — shadow mode first)
- Metrics logged per cycle: `reactive_checks`, `reactive_fires`, `reactive_fills`, `reactive_skips`
- Dashboard column: "Reactive" showing fills from reactive path vs cycle path
- Log format: `[REACTIVE] btc_5m pred_123: edge=0.04 spread=0.01 → FAK fired @ 0.52`

**Commit:** `Add reactive execution kill switch and observability`
**Tests:** Test kill switch disables all reactive firing

### Step 5: Shadow mode validation
**Files:** `src/reactive_executor.py`
**Change:** When `REACTIVE_EXECUTION=shadow`:
- Run full edge computation on every book update
- Log what WOULD have fired (with timestamp, edge, spread)
- Do NOT submit orders
- Store shadow reactive events in `data/reactive_shadow.jsonl` for analysis

This lets us measure: "How many additional fills would reactive execution capture?" without risk.

**Commit:** `Add reactive execution shadow mode for validation`
**Tests:** Shadow mode logs events but doesn't call place_order

### Step 6: Go live
**Files:** `src/reactive_executor.py`
**Change:** Set `REACTIVE_EXECUTION=true` on VPS. Monitor for 24h:
- Fill rate improvement
- No duplicate orders
- No mode corruption across pipelines
- Latency of reactive path (WS event → order submission)

**Commit:** `Enable reactive execution for BTC 5m`

## Architecture Diagram

```
                    ┌──────────────────────────────────────────────┐
                    │              botsy_engine.py                  │
                    │                                              │
  Bybit WS ──────► │  candle_buffer  ──5m close──►  dispatch()    │
  (kline events)   │       │                           │           │
                    │       │                      run_pipeline()   │
                    │       │                           │           │
                    │       │                    ┌──────▼───────┐   │
                    │       │                    │ predict +     │   │
                    │       │                    │ cycle trade   │   │
                    │       │                    │ (existing)    │   │
                    │       │                    └──────┬───────┘   │
                    │       │                           │           │
                    │       │              register_prediction()    │
                    │       │                           │           │
  Polymarket WS ──►│  _update_orderbook_cache()        ▼           │
  (book events)    │       │              ┌─────────────────────┐  │
                    │       └─────────────►│ ReactiveExecutor    │  │
                    │                      │ (per pipeline)      │  │
                    │                      │                     │  │
                    │                      │ on_orderbook_update │  │
                    │                      │   → check edge     │  │
                    │                      │   → fire FAK        │  │
                    │                      │   → deregister      │  │
                    │                      └─────────────────────┘  │
                    └──────────────────────────────────────────────┘
```

## Interaction with Existing FAK Logic

The reactive executor reuses `compute_order()` from `trade.py` — same edge threshold, same FAK/IOC parameters, same risk gates. The only difference is **when** it's called:

| | Cycle Execution (existing) | Reactive Execution (new) |
|---|---|---|
| **Trigger** | 5m candle close | Any WS book update |
| **Prediction** | Just computed | Previously registered |
| **Edge check** | Once per cycle | Every ~1s (book update rate) |
| **Order type** | FAK (if WS data) or GTC | FAK only (always has WS data) |
| **Dedup** | One order per prediction per cycle | Deregister on fill, 30s cooldown |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Double execution (cycle + reactive) | Medium | High ($25 extra) | Deregister on fill; check order exists before cycle execution |
| Order spam from rapid book updates | Medium | Medium (API rate limit) | 30s cooldown per prediction; max 1 outstanding order per prediction |
| Stale prediction acted on | Low | Medium (wrong direction) | Cleanup expired predictions; max TTL = market end_date |
| Mode corruption (paper/live) | Low | High | Pipeline isolation already landed; each executor has its own pipeline_name |
| WS disconnection → no reactive events | Medium | Low (fallback to cycle) | Cycle execution remains; reactive is additive, not replacement |
| Latency spike in _update_orderbook_cache | Low | Medium (blocks WS loop) | Executor.on_orderbook_update is sync but fast (<1ms); fire order async if needed |

## Test Plan

- [ ] Unit tests for ReactiveExecutor (6 tests in Step 2)
- [ ] Integration test: mock WS → executor → place_order path
- [ ] Pipeline isolation: reactive executors don't cross-contaminate
- [ ] Kill switch: REACTIVE_EXECUTION=false → no reactive orders
- [ ] Shadow mode: logs events without submitting
- [ ] Existing tests still pass: `pytest tests/ -v`
- [ ] No regression in cycle execution path

## Validation Plan

### Shadow Phase (Steps 1-5)
- `REACTIVE_EXECUTION=shadow` for 48h minimum
- Measure: how many reactive events would have fired per day?
- Measure: of those, how many would have filled? (check market resolution)
- Measure: latency from WS event to would-fire decision

### Live Phase (Step 6)
- Register optimization:
  ```bash
  python3 src/optimization_tracker.py register \
    --name reactive_execution \
    --description "Event-driven FAK on WS book updates between 5m cycles" \
    --revert-if "reactive_fill_rate < 0.3 or reactive_wr < 0.55" \
    --min-sample 50
  ```
- Baseline: current fill rate, current P&L per day, current expired-would-win count
- Success: fill rate +20pp, expired-would-win from ~8/day to <3/day
- Timeline: ~5-7 days to 50 reactive fills at current prediction volume

## Estimated Timeline

- **Step 1 (baseline):** 1 hour
- **Step 2 (executor module):** 3 hours
- **Step 3 (engine wiring):** 2 hours
- **Step 4 (kill switch + observability):** 1 hour
- **Step 5 (shadow validation):** 1 hour + 48h shadow data collection
- **Step 6 (go live):** 30 min + 7 days monitoring to 50 fills
- **Total implementation:** ~8 hours
- **Total validation:** ~9 days

## What This Does NOT Do

- Does NOT change prediction logic — still 5m candle-driven with momentum/regime
- Does NOT change bet sizing — still $25 flat
- Does NOT implement cancel-replace cycles — that's a future optimization on top of reactive execution
- Does NOT change conviction scoring — still conv >= 3 to trade
- Does NOT touch Kalshi pipeline
- Does NOT remove cycle execution — reactive is additive, cycle remains as fallback
