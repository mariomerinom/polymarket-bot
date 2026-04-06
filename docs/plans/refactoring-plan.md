# BOTSY Refactoring Plan v2

*Revised after pragmatic, architectural, and risk critiques.*

## Why This Exists

A $5 smoke test on 2026-04-05 exposed pricing bugs that took 4 edits across 3 files to fix. Each edit required understanding 211 lines of `execute_trades()`. The effort-to-change ratio is unsustainable, and we want to add more markets and tokens.

---

## Current State

### What's Fine
- No circular imports — clean hub-and-spoke graph
- No module-level mutable state — data flows through args, SQLite, JSON
- WAL mode on SQLite — concurrent access handled
- `daily_report.py` (1,677 lines) — big but output-only, low risk
- Signal logic — `momentum_signal()` is 48 lines, clean, well-tested

### What's Broken

| Problem | Evidence | Impact |
|---------|----------|--------|
| **God functions** | `execute_trades()` 211 lines, `run_predictions()` 186 lines | Every fix requires reading 200+ lines of context |
| **5 copy-pasted pipelines** | ci_run*.py files share ~60% identical code | Bug fixed in one, forgotten in others |
| **28 untested modules** | 67% of src/ has no test file | Refactoring is blind surgery |
| **JSON IPC with no contract** | 3 JSON files with implicit schemas | Schema drift = silent failures |
| **7 dynamic imports in trade.py** | All inside functions, invisible to static analysis | Runtime failures only |

---

## Guiding Principles (from critique)

1. **Ship value in days, not weeks.** No multi-week prerequisite phases. Test what you touch, when you touch it.
2. **BTC 5m is always last to move.** Paper pipelines are canaries. The live money path changes only after validation elsewhere.
3. **Strangler fig, not big bang.** New code runs in parallel with old code. Delete old code only after 200+ cycles of identical outputs.
4. **Functions, not frameworks.** A shared `run_polymarket_pipeline()` function is the right abstraction for 3 similar Polymarket pipelines. A class hierarchy is premature for 5 pipelines with 3 genuinely different venues.
5. **Freeze the money path.** `place_order()`, `_submit_clob_order()`, `compute_order()`, `should_trade()`, `is_kill_switched()` — do not modify during refactoring unless the change has been validated on paper pipelines first.

---

## Execution Plan

### Step 1: Extract `resolve_clob_prices()` from `execute_trades()` (1-2 days)

**The highest-value single change.** This is the exact code block (trade.py lines 713-774) that caused the pricing bug and required 4 edits to fix. It's self-contained with clear inputs and outputs.

**What to do:**
1. Create `resolve_clob_prices(pred, tokens) -> dict` as a standalone function that returns `market_row` with `_clob_verified` flag.
2. Call it FROM the existing `execute_trades()` at the exact insertion point — sprout method, not move.
3. Write 4 tests: WS hit, WS miss + REST fallback, both miss (returns unverified), stale cache.
4. Assert new function produces identical `market_row` to inline code.
5. Once tests pass, delete the inline code.

**Files:** `src/trade.py`, `tests/test_trade.py`

**Risk:** Variable scope leakage — the `tokens` dict is used both for pricing AND for CLOB token ID selection downstream (line 784). The extraction must return `tokens` alongside `market_row`, or accept `tokens` as a parameter.

**Frozen:** `compute_order()`, `place_order()`, `_submit_clob_order()`, `should_trade()`.

### Step 2: Extract `record_diagnostics()` (1 day)

**What to do:**
1. Extract lines 787-815 (snapshot staleness, conviction drift tension) into `record_diagnostics(pred, market_row, order_params)`.
2. Also explicitly handle shadow indicators (lines 671-689) — they write to DB and must not be silently dropped. Move them to a named function `run_shadow_logging(db, cycle)` called at the top of `execute_trades()`.
3. Write 2 tests for diagnostics, 1 test for shadow logging.

**Files:** `src/trade.py`, `tests/test_trade.py`

After Steps 1-2, `execute_trades()` drops from 211 lines to ~80 — an orchestrator that calls named functions.

### Step 3: Unify Polymarket pipelines (3-4 days)

**Why not a class:** Kalshi has its own `store_prediction_kalshi()` with conviction capping. Bybit has `create_synthetic_market()`, position management, and `execute_bybit_trades()`. These are genuinely different execution models — not parameter variations. Wrapping them in a class hierarchy moves complexity into inheritance, which is harder to read than 2 standalone files.

**What to do:**
1. Extract `get_next_cycle()` and `has_unpredicted_market()` from all 5 ci_run files into `pipeline_utils.py`. These are copy-pasted identically.
2. Create `run_polymarket_pipeline(config)` as a plain function handling the common lifecycle: init_db → fetch_markets → auto_resolve → predict → trade → score → dashboard.
3. Convert `ci_run_eth.py` first (paper, safest). The delta is: which `fetch_candles`, which `run_predictions`, and the pipeline_control pause/resume check.
4. Convert `ci_run_15m.py` next (paper). Delta: loose_mode=True, conviction demotion for DOWN+NEUTRAL.
5. Convert `ci_run.py` LAST (live money). Run both old `ci_run.py` and new `run_polymarket_pipeline("btc_5m")` in parallel for 200+ cycles, comparing outputs. Suppress orders from new path.
6. Leave `ci_run_kalshi.py` and `ci_run_bybit.py` as separate files — they're different venues, not parameters.

**Config:** `pipelines.json` stores parameters (bet_size, mode, interval, asset, db_path). The pipeline *type* (polymarket vs bybit vs kalshi) maps to a Python function/file, not just a config key. Adding a new asset on Polymarket = config entry. Adding a new venue = new file.

**Files:** New `src/pipeline_utils.py`, new `src/run_polymarket_pipeline.py`, modified ci_run_eth.py, ci_run_15m.py, ci_run.py.

**Estimated savings:** ~300 lines of duplicated code eliminated. 3 files → 1 function + config.

### Step 4: Move `_get_clob_tokens_safe()` to `clob_depth.py` (half day)

**Why:** It's in `predict.py` but it's a CLOB concern. `trade.py` does `from predict import _get_clob_tokens_safe` — a dynamic import that creates hidden coupling between the prediction module and the execution module.

**What to do:** Move the function. Grep-and-replace the import in `trade.py`. Update `smoke_bet.py`. Run tests.

**Files:** `src/predict.py`, `src/clob_depth.py`, `src/trade.py`, `src/smoke_bet.py`

### Step 5: Typed IPC for orderbook cache (half day)

**Scope:** Only `live_orderbook.json` — the one that matters for money. `ws_metrics.json` and `candle_buffer.json` are low risk and can wait.

**What to do:**
1. Create `OrderbookCache` dataclass with `load(path, max_age_s)` and `save(path)`.
2. Add `"version": 2` field to the JSON. Reader handles both v1 and v2.
3. Deploy new reader to `trade.py` first (backward compatible).
4. Deploy new writer to `botsy_engine.py` after reader is live.
5. After 1 week, remove v1 support.

**Why not a message bus / in-process singleton:** We have 1 writer and 1 reader. A dataclass with atomic file I/O is the right tool. If we scale to 15+ pipelines, revisit.

**Files:** New `src/orderbook_cache.py`, modified `src/trade.py`, `src/botsy_engine.py`

### Step 6 (Optional): Engine dispatch improvements

**Only if we feel pain.** The current sequential dispatch with no backpressure works for 5 pipelines on 5-minute intervals. If we add faster intervals or more pipelines:

1. `asyncio.gather()` for pipelines triggered by the same event (currently sequential `for` loop)
2. `asyncio.Semaphore(3)` to cap concurrent pipeline threads
3. `asyncio.wait_for(timeout=120)` to prevent hung pipelines from blocking the engine

**Also:** The dedup set pruning at botsy_engine.py line 484 (`set → list → slice`) is not order-preserving. A `collections.OrderedDict` would be correct. Fix when writing dispatch tests.

---

## What NOT to Do

| Proposed in v1 | Why Dropped |
|----------------|-------------|
| Phase 0: "Test the untested" as blocking prerequisite | Multi-week upfront investment with zero visible improvement. Test what you touch instead. |
| `PipelineRunner` class with method overrides | Moves complexity into inheritance. A plain function is simpler for 3 Polymarket pipelines. Kalshi and Bybit stay as separate files. |
| `Pipeline = DataSource + Signal + MarketSource + Executor + Scorer` | Over-abstracted for 5 pipelines. Missing axes: position management (Bybit), market lifecycle (synthetic vs discovered), risk gates. Wait for a 6th pipeline to reveal the real pattern. |
| JSON config registry for all pipelines | Adding a new venue requires a new Python file regardless. Config works for parameters, not for control flow. |
| Phase 4: Reduce hub coupling (move 4 functions out of predict.py) | Only `_get_clob_tokens_safe` is clearly misplaced. The others (`momentum_signal`, `compute_regime_from_candles`) are prediction concerns. Wait for pain. |
| >80% coverage target on botsy_engine.py | Arbitrary threshold. A single contract test asserting "no duplicate orders" is worth more than 100 line-coverage tests. |

---

## Frozen Files (Do Not Modify During Refactoring)

| File / Lines | Reason |
|---|---|
| `trade.py` lines 289-369 (`place_order`, `_store_order`, `_submit_clob_order`) | Actual money-moving code. On-chain order submission. |
| `trade.py` lines 216-286 (`compute_order`) | Price limits and sizing. 1-cent error = overpaying every order. |
| `trade.py` lines 82-119 (`should_trade`) | Trade gates. If weakened, bot places orders it shouldn't. |
| `trade.py` line 37 (`TRADING_ENABLED`) | Paper/live toggle. |
| `trade.py` lines 848-853 (`is_kill_switched`) | Kill switch. Must remain functional at all times. |
| `botsy_engine.py` lines 400-443 (`_update_orderbook_cache`) | JSON IPC writer. Format change breaks trade.py reader. |
| `.github/workflows/predict-and-score.yml` | Live CI pipeline. Broken workflow = bot stops trading. |
| `config/pipelines.json` (btc_5m entry) | Live pipeline config. |

**Rule:** If a refactoring step touches a frozen file, it must run in paper mode for 50+ cycles and produce identical outputs before merging to production.

---

## Migration Safety

### For each step:
1. **New code runs alongside old code first** (strangler fig)
2. **Paper pipelines are canaries** — ETH 5m and BTC 15m validate before BTC 5m moves
3. **Each commit is independently revertible** — one extraction per commit, not batched
4. **Schema changes are backward compatible** — deploy reader first, then writer, then remove old format

### BTC 5m migration specifically:
- `ci_run.py` is not deleted until `run_polymarket_pipeline("btc_5m")` has run 200+ cycles with zero divergence
- During parallel run: both paths execute, but new path's orders are suppressed (TRADING_ENABLED=false for new path)
- Only after comparison passes: switch BTC 5m, delete ci_run.py

---

## Sequencing

```
Step 1: Extract resolve_clob_prices()     [1-2 days, ship immediately]
Step 2: Extract record_diagnostics()      [1 day, ship immediately]
Step 3: Unify Polymarket pipelines        [3-4 days, ETH first, BTC last]
Step 4: Move _get_clob_tokens_safe        [half day]
Step 5: Typed IPC for orderbook cache     [half day, reader first]
Step 6: Engine dispatch (optional)        [when needed]
```

Steps 1-2 are independent and deliver immediate value.
Steps 3-5 can run in any order.
Step 6 is optional until we add more pipelines.

**Total: 6-8 working days for Steps 1-5.** Not 7-9 weeks.

---

## Verification (per step)

1. `pytest tests/ -v` — all pass
2. `python src/smoke_bet.py --dry-run` — pipeline works end-to-end
3. Deploy to VPS, verify engine starts and places orders
4. For Step 3: parallel run comparison (200+ cycles) before BTC 5m switchover

---

## Test Coverage Map

### Currently Tested (27 modules, 414 tests)

| Module | Test File | Tests |
|--------|-----------|-------|
| trade.py | test_trade.py | 49 |
| predict.py | test_momentum, test_regime, test_consensus, test_pipeline_e2e | 48+ |
| btc_data.py | test_btc_data, test_15m | 25 |
| candle_buffer.py | test_candle_buffer | 13 |
| clob_depth.py | test_clob_depth | 12 |
| config.py | test_config | 19 |
| shadow_*.py | test_shadow_conviction, test_shadow_indicators | 43 |
| ta_engine.py | test_ta_engine | 14 |
| pipeline_*.py | test_pipeline_control, test_pipeline_integrity | 43 |
| bybit_*.py | test_bybit | 47 |
| kalshi_*.py | test_kalshi | 12 |
| (integration) | test_pipeline_e2e, test_regression | 38 |
| (others) | test_daily_report, test_pnl, test_smoke_bet, etc. | 58 |

### Untested Critical Path

| Module | Lines | When to Test |
|--------|-------|-------------|
| botsy_engine.py | 751 | When Step 6 is needed (dispatch tests) |
| ci_run.py | 141 | During Step 3 (integration test for polymarket pipeline) |
| fetch_markets.py | 420 | During Step 3 (market discovery is part of pipeline) |
| bybit_trade.py | 530 | When Bybit goes live (not blocking any current step) |

### Tests Added by This Plan

| Step | New Tests |
|------|-----------|
| Step 1 | 4 tests for `resolve_clob_prices()` |
| Step 2 | 3 tests for `record_diagnostics()` + `run_shadow_logging()` |
| Step 3 | Integration test for `run_polymarket_pipeline()` |
| Step 4 | Update import paths in existing tests |
| Step 5 | 3 tests for `OrderbookCache` load/save/staleness |
