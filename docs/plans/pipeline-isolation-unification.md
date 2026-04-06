# Pipeline Isolation + Unification

## Status: COMPLETE (2026-04-06)

Implemented in commit `1b3cddf8`. All 4 fixes landed, 3 ci_run files unified into `polymarket_pipeline.py`, deployed to VPS and verified. Tests pass. See `tests/test_pipeline_isolation.py` (10 tests) and `tests/test_ci_run_lifecycle.py` (updated for unified pipeline).

**Next step:** [Event-driven trade execution](event-driven-execution-plan.md) builds on the isolation foundation — reactive executor needs `pipeline_name` threading delivered by this work.

---

## Context

Incident on Apr 6 (#66): dual engine processes caused BTC 5m to silently run in paper mode, missing live trades. Root cause: `trade.TRADING_ENABLED` is a module-level global that every `ci_run_*.py` mutates via `trade.TRADING_ENABLED = is_pipeline_live("...")`. In a single-process async engine, the last pipeline to write wins — one pipeline's mode corrupts all others.

Three independent analyses (red-team, architectural risk, prevention design) converge: **as long as `trade.TRADING_ENABLED` exists as a writable global, this class of incident is inevitable**.

Meanwhile, `ci_run.py`, `ci_run_eth.py`, and `ci_run_15m.py` are 90% identical — same lifecycle with parameterizable differences. This duplication is what made the `TRADING_ENABLED` mutation spread to 3 files in the first place. **Fix the architecture (isolation) AND eliminate the duplication (unification) in one pass.**

### Current State (the bomb)

```
trade.py:37     → TRADING_ENABLED = _env("TRADING_ENABLED", "false")  # import-time, cached forever
ci_run.py:50    → trade.TRADING_ENABLED = is_pipeline_live("btc_5m")   # overwrites global
ci_run_eth.py:41 → trade.TRADING_ENABLED = is_pipeline_live("eth_5m")  # overwrites global
ci_run_15m.py:36 → trade.TRADING_ENABLED = is_pipeline_live("btc_15m") # overwrites global
```

8 call sites in `trade.py` read the global: lines 352, 376, 617, 1002, 1050, 1060, 1109, and startup check at 41.

---

## Part A: Pipeline Isolation (4 fixes, TDD-first)

### Fix 1: Pass `pipeline_name` to `execute_trades()` — resolve mode locally (CRITICAL)

**Makes corruption impossible by construction.**

Add `pipeline_name: str` parameter to `execute_trades()`. Inside, resolve trading mode from `pipeline_control.is_pipeline_live()` — never from the global. Thread `trading_enabled` as a local bool through to `place_order()` and `settle_orders()`.

**Changes in `src/trade.py`:**
- `execute_trades(db, cycle, pipeline_name="btc_5m")` — resolve `trading_enabled = is_pipeline_live(pipeline_name)` locally
- `place_order(db, ..., trading_enabled=None)` — new parameter, defaults to global for backward compat during transition
- All 8 internal readers of `TRADING_ENABLED` (lines 352, 376, 617, 1002, 1050, 1060, 1109) switch to the local `trading_enabled` parameter
- `get_trading_summary(db, pipeline_name=None)` — resolve mode from pipeline_name if provided

### Fix 2: PID lock file to prevent dual engine processes (QUICK)

Add PID lock file at top of `botsy_engine.main()`:
- Check `data/engine.pid` — if file exists and PID is alive, refuse to start
- Write current PID on startup, `atexit.register()` cleanup

**File:** `src/botsy_engine.py` — ~15 lines in `main()`

### Fix 3: Static analysis test (CI GUARD)

AST-walk `src/ci_run*.py` and `src/polymarket_pipeline.py` — fail if any assigns `trade.TRADING_ENABLED`.

**File:** `tests/test_pipeline_isolation.py`

### Fix 4: Runtime assertion in `place_order()` (DEFENSE-IN-DEPTH)

If the passed `trading_enabled` disagrees with the global, log CRITICAL warning. The passed value always wins.

**File:** `src/trade.py` in `place_order()` — 5 lines

---

## Part B: Pipeline Unification

### New file: `src/polymarket_pipeline.py`

Extract the shared lifecycle into `run_polymarket_pipeline()`. All 3 Polymarket ci_run files become thin config wrappers that call it.

```python
def run_polymarket_pipeline(
    pipeline_name: str,          # "btc_5m", "btc_15m", "eth_5m"
    db_init_fn,                  # init_db / init_db_15m / init_db_eth
    db_path,                     # DB_PATH / DB_PATH_15M / DB_PATH_ETH
    market_fetch_fn,             # fetch_active_markets / _15m / _eth
    candle_fetch_fn,             # fetch_btc_candles / fetch_eth_candles
    predict_fn,                  # run_predictions / run_predictions_eth
    predict_kwargs: dict = None, # extra kwargs: loose_mode, db_path
    post_predict_hook=None,      # e.g. 15m DOWN+NEUTRAL demotion
    shadow_pipeline_tag: str = None,  # "btc_5m" / "btc_15m" / "eth_5m"
    dashboard_fn=None,           # generate() or None
    price_fmt: str = ",.0f",     # ",.0f" for BTC, ",.2f" for ETH
    asset_label: str = "BTC",    # for log messages
    candle_data=None,            # engine-provided candle data
    indicators=None,             # engine-provided TA indicators
):
```

**Shared lifecycle (inside the function):**
1. Load pipeline config → check paused
2. Init DB
3. Fetch markets → store
4. Auto-resolve
5. Early exit if no markets and no unpredicted
6. Fetch candles (if not engine-provided) → log price
7. Predict (if unpredicted market exists)
8. Post-predict hook (optional)
9. Shadow indicators (optional)
10. Shadow conviction scorer (optional)
11. Trade execution → `execute_trades(db, cycle, pipeline_name=pipeline_name)` ← **Fix 1 wired in**
12. Scoring
13. Integrity checks
14. Dashboard generation

### Slim wrappers (ci_run files become ~30 lines each)

**`src/ci_run.py`** → calls `run_polymarket_pipeline("btc_5m", ...)` with BTC-specific config. Keeps `get_next_cycle()` and `has_unpredicted_market()` as they're imported from `pipeline_utils` already (or defined locally — ci_run.py has its own copies that we'll consolidate).

**`src/ci_run_eth.py`** → calls `run_polymarket_pipeline("eth_5m", ...)` with ETH-specific config.

**`src/ci_run_15m.py`** → calls `run_polymarket_pipeline("btc_15m", ...)` with 15m-specific config + `post_predict_hook` for DOWN+NEUTRAL demotion.

### Key differences parameterized

| Parameter | BTC 5m | BTC 15m | ETH 5m |
|-----------|--------|---------|--------|
| `db_init_fn` | `init_db` | `init_db_15m` | `init_db_eth` |
| `db_path` | `DB_PATH` | `DB_PATH_15M` | `DB_PATH_ETH` |
| `market_fetch_fn` | `fetch_active_markets` | `fetch_active_markets_15m` | `fetch_active_markets_eth` |
| `candle_fetch_fn` | `fetch_btc_candles` | `fetch_btc_candles` | `fetch_eth_candles` |
| `predict_fn` | `run_predictions` | `run_predictions` | `run_predictions_eth` |
| `predict_kwargs` | `{}` | `{loose_mode: True, db_path: DB_PATH_15M}` | `{db_path: DB_PATH_ETH}` |
| `post_predict_hook` | None | DOWN+NEUTRAL demotion | None |
| `dashboard_fn` | `generate_dashboard.generate` | None (dynamic) | None (dynamic) |
| `price_fmt` | `",.0f"` | `",.0f"` | `",.2f"` |
| `asset_label` | `"BTC"` | `"BTC 15m"` | `"ETH"` |

### NOT unified: Kalshi

`ci_run_kalshi.py` has custom prediction logic, no trade execution, custom auto_resolve, and a fundamentally different market structure. It stays separate.

### Helper consolidation

`ci_run.py` defines `get_next_cycle()` and `has_unpredicted_market()` locally. `ci_run_eth.py` and `ci_run_15m.py` import them from `pipeline_utils.py`. The unified function imports from `pipeline_utils` — remove the local copies from `ci_run.py`.

---

## Step 0: Tests first → `tests/test_pipeline_isolation.py`

~10 behavioral tests across 4 classes:

**Class: `TestPipelineModeIsolation`** (3 tests)
- `test_eth_paper_does_not_corrupt_btc_live` — run ETH (paper) then BTC (live) in sequence; BTC orders are mode=live
- `test_execute_trades_uses_pipeline_name_not_global` — flip the global to wrong value; `execute_trades(pipeline_name="btc_5m")` still uses the correct mode
- `test_place_order_uses_passed_mode_not_global` — directly test that `place_order()` respects its `trading_enabled` parameter

**Class: `TestStaticAnalysisGuards`** (2 tests)
- `test_no_direct_trading_enabled_mutation` — AST scan: no pipeline file writes `trade.TRADING_ENABLED`
- `test_all_execute_trades_calls_pass_pipeline_name` — AST scan: every `execute_trades()` call includes `pipeline_name=`

**Class: `TestPIDLock`** (2 tests)
- `test_pid_lock_prevents_dual_start` — write PID file with current PID → engine refuses to start
- `test_stale_pid_lock_allows_start` — write PID file with dead PID → engine starts fine

**Class: `TestRuntimeAssertion`** (1 test)
- `test_place_order_logs_warning_on_global_mismatch` — set global to False, pass trading_enabled=True → warning logged, order placed as live

**Class: `TestUnifiedPipeline`** (2 tests)
- `test_unified_pipeline_calls_lifecycle_steps` — mock all fns, call `run_polymarket_pipeline()`, verify all lifecycle steps called in order
- `test_unified_pipeline_passes_pipeline_name_to_execute_trades` — verify `execute_trades` receives `pipeline_name=` argument

---

## Execution Order

1. **Write tests** (`tests/test_pipeline_isolation.py`) — all fail
2. **Fix 1**: Modify `trade.py` — add `pipeline_name` to `execute_trades()`, `trading_enabled` to `place_order()`, update all 8 reader sites
3. **Part B**: Create `src/polymarket_pipeline.py` with `run_polymarket_pipeline()`
4. **Slim down ci_run files**: Each becomes a thin wrapper calling `run_polymarket_pipeline()`
5. **Fix 2**: PID lock in `botsy_engine.py`
6. **Fix 3+4**: Static analysis test passes, runtime assertion added
7. **Run full test suite**, verify 0 regressions

## Files Modified

| File | Change |
|------|--------|
| `tests/test_pipeline_isolation.py` | **NEW** — ~10 behavioral tests |
| `src/trade.py` | `execute_trades(pipeline_name=)`, `place_order(trading_enabled=)`, all 8 reader sites, runtime assertion |
| `src/polymarket_pipeline.py` | **NEW** — `run_polymarket_pipeline()` unified lifecycle |
| `src/ci_run.py` | Slim wrapper → calls `run_polymarket_pipeline("btc_5m", ...)`. Remove `get_next_cycle`, `has_unpredicted_market`, global mutation |
| `src/ci_run_eth.py` | Slim wrapper → calls `run_polymarket_pipeline("eth_5m", ...)`. Remove global mutation |
| `src/ci_run_15m.py` | Slim wrapper → calls `run_polymarket_pipeline("btc_15m", ...)`. Remove global mutation |
| `src/botsy_engine.py` | PID lock file in `main()` |

## What This Does NOT Do

- Does NOT change signal logic, conviction scoring, or bet sizing
- Does NOT change pipeline modes (all stay as-is in `pipelines.json`)
- Does NOT unify Kalshi (too different)
- Does NOT add concurrency locks (pipelines run sequentially via `for` loop in `dispatch()`)
- Does NOT remove `TRADING_ENABLED` from `trade.py` — it remains as a legacy fallback and startup guard. It just stops being the source of truth.

## Verification

1. `pytest tests/test_pipeline_isolation.py -v` — all new tests pass
2. `pytest tests/ -v --ignore=tests/test_ta_engine.py` — full suite, 0 regressions
3. Deploy to VPS → verify in `logs/loop.log`:
   - BTC 5m orders show `mode=live` (not paper)
   - ETH 5m and BTC 15m show `mode=paper`
   - No CRITICAL warnings about mode mismatch
4. Kill the engine, restart → verify PID lock works (no dual process)
5. Monitor 24h → confirm zero mode corruption incidents
