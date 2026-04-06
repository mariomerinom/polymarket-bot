# TDD-First Refactoring: Golden-Path Tests → Extract → Unify

**Companion to `refactoring-plan.md` (kept as-is).**

## Context

Refactoring plan v2 (`docs/plans/refactoring-plan.md`) identified 28 untested modules (67%), god functions (211-line `execute_trades()`), and 5 copy-pasted pipelines. Three critique agents debated TDD-first vs extract-first. Verdict: **TDD-first wins** because:

1. Tests written BEFORE refactoring prove behavioral preservation. Tests written after cannot.
2. AI writes tests in minutes — the "weeks of testing" argument is invalid.
3. The refactoring is behavioral (extract functions, unify pipelines), not structural. Behavioral tests survive restructuring.
4. The `$2.18/$5` smoke test bug happened because code was changed without tests proving correct behavior.

## What We're Building

**Phase A: Golden-path behavioral tests** (~26 tests across 4 test files)
These test WHAT the system does, not HOW it's organized. They survive the refactoring in Phase B.

**Phase B: Refactoring** (Steps 1-5 from refactoring-plan.md)
Extract functions, unify pipelines, move misplaced code — with Phase A tests as the safety net.

---

## Phase A: Golden-Path Behavioral Tests

Write tests that assert WHAT the system does — these survive restructuring because they test contracts, not structure. Reuse existing patterns from `tests/test_pipeline_e2e.py` (mock fixture, in-memory DB, `_make_pipeline_db()`).

### A1. `tests/test_clob_resolution.py` — CLOB price resolution path (~6 tests)

Tests the behavior at `trade.py` lines 713-774 (inside `execute_trades()`). This is where the $2.18 bug lived.

| Test | Contract Being Verified |
|------|------------------------|
| `test_ws_hit_uses_live_price` | When WS cache has fresh price for both tokens, `execute_trades()` order uses WS price, not Gamma |
| `test_ws_miss_falls_back_to_rest` | When WS cache is None, REST orderbook is fetched and used |
| `test_both_miss_skips_trade` | When both WS and REST fail, order is skipped (not placed with Gamma price) |
| `test_stale_ws_cache_ignored` | WS cache older than 10s returns None, triggers REST fallback |
| `test_clob_verified_flag_propagates` | `market_row["_clob_verified"]` is set correctly and `compute_order()` reads it |
| `test_token_resolution_failure_skips` | When `_get_clob_tokens_safe()` throws, trade is skipped with DIAG log |

**Mock surface:** `predict._get_clob_tokens_safe`, `trade._get_live_token_mid`, `clob_depth.get_order_book`, `clob_depth.analyze_depth`. These are I/O boundaries that remain stable through refactoring.

**Calls:** `execute_trades(db, cycle)` end-to-end. Asserts on returned order list + DB state.

### A2. `tests/test_ci_run_lifecycle.py` — BTC 5m pipeline lifecycle (~8 tests)

Tests `ci_run.main()` — the live production pipeline, currently zero tests.

| Test | Contract Being Verified |
|------|------------------------|
| `test_happy_path_predict_and_trade` | Full cycle: fetch markets → predict → trade → score. Returns without error. |
| `test_no_active_markets_exits_clean` | Empty market list → clean exit, no crash |
| `test_candle_fetch_failure_exits` | When `fetch_btc_candles()` returns None, pipeline exits cleanly |
| `test_kill_switch_prevents_trades` | Kill switch active → no orders placed |
| `test_prediction_stored_in_db` | After cycle, predictions table has correct row |
| `test_dashboard_generated` | `generate()` is called after scoring |
| `test_candle_data_passthrough` | When `candle_data` kwarg is provided, no REST fetch happens |
| `test_indicators_passthrough` | When `indicators` kwarg is provided, TA engine not called |

**Mock surface:** `fetch_active_markets`, `fetch_btc_candles`, `_get_clob_tokens_safe`, `_get_live_token_mid`, `generate` (dashboard). Reuse `_make_pipeline_db()` pattern.

### A3. `tests/test_engine_dispatch.py` — Engine dispatch logic (~6 tests)

Tests `botsy_engine.py` dispatch (lines 474-538) — pure logic, no WebSocket needed.

| Test | Contract Being Verified |
|------|------------------------|
| `test_routing_btc_5m` | `("bybit_spot", "BTCUSDT", "5")` dispatches to `["btc_5m", "kalshi"]` |
| `test_routing_unknown_key` | Unknown (source, symbol, interval) → no dispatch |
| `test_dedup_prevents_double_dispatch` | Same `(source, symbol, candle_ts)` dispatches exactly once |
| `test_dedup_allows_new_timestamp` | Different `candle_ts` for same symbol dispatches again |
| `test_dedup_pruning_preserves_recent` | After 100+ entries, recent keys are not evicted |
| `test_candle_data_building` | Buffer candles → `candle_data` dict with correct `current_price`, `1h_change_pct`, `trend` |

**Approach:** Test `dispatch()` method directly with mocked `run_pipeline()`.

### A4. `tests/test_ci_run_bybit_lifecycle.py` — Bybit pipeline lifecycle (~6 tests)

Tests `ci_run_bybit.main()` — the most structurally different pipeline.

| Test | Contract Being Verified |
|------|------------------------|
| `test_happy_path_with_synthetic_market` | Synthetic market created, prediction stored, trade executed |
| `test_no_candle_data_fetches_from_api` | When `candle_data` is None, `fetch_bybit_candles()` called |
| `test_dead_hours_skip` | Dead hour → no prediction |
| `test_mean_reverting_regime_skip` | Mean-reverting regime → skip |
| `test_consensus_boost` | Consensus score == 2 and conviction >= 3 → conviction boosted |
| `test_position_sync` | Open position synced before prediction |

**Mock surface:** `init_db_bybit`, `fetch_bybit_candles`, `get_open_position`, `execute_bybit_trades`.

---

## Phase B: Refactoring (with Phase A tests as safety net)

After Phase A tests pass on CURRENT code, proceed with Steps 1-5 from `docs/plans/refactoring-plan.md`:

1. ~~Extract `resolve_clob_prices()` from `execute_trades()`~~ DONE (ce0d2d30)
2. ~~Extract `record_diagnostics()` + `run_shadow_logging()`~~ DONE (ce0d2d30)
3. ~~Extract shared pipeline utils (`get_next_cycle`, `has_unpredicted_market`)~~ DONE (de06d65a)
4. ~~Move `_get_clob_tokens_safe()` to `clob_depth.py`~~ DONE (ed7d9f89)
5. ~~Typed `OrderbookCache` dataclass for `live_orderbook.json`~~ DONE (ae09a723)

Each step: make the change -> run `pytest tests/` -> all green -> commit -> next step.

**Phase B complete.** All 5 steps shipped. 463 tests passing (1 pre-existing failure in test_engine.py unrelated to refactoring).

---

## Files to Create (Phase A)

| File | Tests |
|------|-------|
| `tests/test_clob_resolution.py` | 6 |
| `tests/test_ci_run_lifecycle.py` | 8 |
| `tests/test_engine_dispatch.py` | 6 |
| `tests/test_ci_run_bybit_lifecycle.py` | 6 |

## Files to Modify (Phase B only, after Phase A passes)

| File | Change |
|------|--------|
| `src/trade.py` | Extract `resolve_clob_prices()`, `record_diagnostics()`, `run_shadow_logging()` |
| `src/pipeline_utils.py` (new) | `get_next_cycle()`, `has_unpredicted_market()` |
| `src/run_polymarket_pipeline.py` (new) | Common Polymarket lifecycle function |
| `src/ci_run_eth.py` | Calls `run_polymarket_pipeline()` |
| `src/ci_run_15m.py` | Calls `run_polymarket_pipeline()` |
| `src/ci_run.py` | Calls `run_polymarket_pipeline()` (last to move, after 200+ cycle validation) |
| `src/clob_depth.py` | Receives `_get_clob_tokens_safe()` from predict.py |
| `src/orderbook_cache.py` (new) | Typed dataclass for `live_orderbook.json` |

## Verification

After each phase:
1. `pytest tests/ -v` — all pass (including new Phase A tests)
2. `python src/smoke_bet.py --dry-run` — pipeline works end-to-end
3. Deploy to VPS, verify engine starts
4. For Phase B Step 3: parallel run BTC 5m (old + new) for 200+ cycles before switchover
