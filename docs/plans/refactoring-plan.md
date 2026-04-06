# BOTSY Refactoring Plan

## Why This Exists

A $5 smoke test on 2026-04-05 exposed pricing bugs that took 4 edits across 3 files to fix. Each edit required understanding 211 lines of `execute_trades()` and tracing data flow through JSON IPC, dynamic imports, and a 751-line untested async engine. The fix worked, but the effort-to-change ratio is unsustainable.

We want to add more markets and tokens. The current architecture makes that hard:
- 5 nearly-identical `ci_run_*.py` files (1,086 lines of 60% duplication)
- Every new pipeline copies the same boilerplate and introduces the same bugs
- `predict.py` is a hub with 8 dependents — any API change ripples everywhere
- 28 of 55 source files have zero test coverage, including `botsy_engine.py` (the core loop)

This plan restructures the codebase so adding a new market/token is a config change, not a new file.

---

## Current State

### What's Actually Fine
- **No circular imports** — dependency graph is clean (hub-and-spoke)
- **No module-level mutable state** — data flows through args, SQLite, JSON
- **WAL mode on SQLite** — concurrent access handled
- **`daily_report.py`** (1,677 lines) — it's big but it's output-only, low risk
- **Signal logic** — `momentum_signal()` is 48 lines, clean, well-tested

### What's Broken

| Problem | Evidence | Impact |
|---------|----------|--------|
| **God functions** | `execute_trades()` 211 lines, `run_predictions()` 186 lines, `format_report()` 345 lines | Every fix requires reading 200+ lines of context |
| **5 copy-pasted pipelines** | ci_run.py, ci_run_eth.py, ci_run_15m.py, ci_run_kalshi.py, ci_run_bybit.py share ~60% identical code | Bug fixed in one, forgotten in others |
| **Zero tests on core loop** | `botsy_engine.py` (751 lines) has no unit tests for dispatch, routing, WS handling | Can't refactor safely |
| **28 untested modules** | 67% of src/ has no test file | Refactoring is blind surgery |
| **JSON IPC with no contract** | 3 JSON files (`live_orderbook.json`, `ws_metrics.json`, `candle_buffer.json`) with implicit schemas | Schema drift causes silent failures |
| **7 dynamic imports in trade.py** | `from predict import ...`, `from clob_depth import ...`, `from shadow_indicators import ...` — all inside functions | Static analysis can't see them, they fail at runtime |
| **Hub dependency** | `predict.py` imported by 8 modules | API surface change = 8 files to update |

### Line Counts — Top 10

| File | Lines | Role |
|------|-------|------|
| `daily_report.py` | 1,677 | Output (low risk) |
| `trade.py` | 890 | Order execution (critical path) |
| `botsy_engine.py` | 751 | Async event loop (critical path, untested) |
| `backtest.py` | 613 | Offline analysis |
| `backtest_native.py` | 566 | Offline analysis |
| `predict.py` | 551 | Signal generation (hub) |
| `bybit_trade.py` | 530 | Bybit execution (untested) |
| `fetch_markets.py` | 420 | Market discovery |
| `predict_eth.py` | 390 | ETH signal variant |
| `activity_digest.py` | 339 | Output (low risk) |

---

## Target Architecture

### Principle: Pipeline = Composable Unit

A pipeline is a combination of 5 pluggable components:

```
Pipeline = DataSource + Signal + MarketSource + Executor + Scorer
```

| Component | Interface | Current Implementations |
|-----------|-----------|------------------------|
| **DataSource** | `fetch_candles(limit) -> CandleData` | btc_data, eth_data, bybit_data, kalshi_data |
| **Signal** | `generate(candles, config) -> Signal` | momentum_signal (shared), regime gate (shared) |
| **MarketSource** | `fetch_markets() -> list[Market]` | fetch_markets (Polymarket), kalshi_markets, bybit_markets |
| **Executor** | `execute(db, predictions, cycle) -> list[Order]` | trade.execute_trades (Polymarket), bybit_trade (Bybit) |
| **Scorer** | `resolve(db) + score(db)` | score.py + auto_resolve (Polymarket), kalshi_score, bybit_score |

### Adding a New Pipeline (Target State)

```python
# config/pipelines.json
{
  "sol_5m": {
    "mode": "paper",
    "data_source": "sol_data",
    "signal": "momentum",
    "market_source": "polymarket",
    "executor": "polymarket",
    "scorer": "polymarket",
    "asset": "SOL",
    "interval": "5m",
    "db_path": "data/predictions_sol.db",
    "bet_size": 25,
    "min_conviction": 3
  }
}
```

No new `ci_run_sol.py`. The pipeline runner reads config and composes components.

### Module Dependency Graph (Target)

```
config.py (pure data, no imports)
    ↑
pipeline_runner.py (orchestrator — replaces 5 ci_run_*.py files)
    ↑
    ├── data_sources/         (btc_data, eth_data, sol_data, ...)
    ├── signals/              (momentum, regime_gate)
    ├── market_sources/       (polymarket, kalshi, bybit)
    ├── executors/            (polymarket_executor, bybit_executor)
    ├── scorers/              (polymarket_scorer, kalshi_scorer, bybit_scorer)
    └── indicators/           (ta_engine, shadow_indicators, shadow_conviction)
         ↑
botsy_engine.py (event loop — dispatches to pipeline_runner)
```

Each box is independently testable. No box imports from a sibling.

---

## Execution Plan

### Phase 0: Test the Untested (prerequisite for everything else)

**Goal:** Get critical-path modules to testable state so we can refactor safely.

**Priority order by risk:**

| Module | Lines | Why First |
|--------|-------|-----------|
| `botsy_engine.py` | 751 | Core loop. Zero tests. Can't safely touch dispatch, routing, or WS handling. |
| `ci_run.py` | 141 | BTC 5m production pipeline. Template for all others. |
| `fetch_markets.py` | 420 | Market discovery. Untested Gamma API parsing. |
| `bybit_trade.py` | 530 | Bybit execution. Second venue, zero coverage. |

**Approach:**
- Extract pure functions from `botsy_engine.py` (dispatch logic, routing lookup, candle data building) into testable units
- `botsy_engine.py` async tests with `pytest-asyncio` for WS reconnect, fallback timer, dedup
- `ci_run.py` integration test with mocked dependencies (same pattern as `test_pipeline_e2e.py`)

**Exit criteria:** All 4 modules have tests. `pytest --cov` shows >80% line coverage on critical-path modules.

### Phase 1: Decompose God Functions

**Goal:** Break `execute_trades()` (211 lines) and `run_predictions()` (186 lines) into composable pieces.

#### 1a. `execute_trades()` → 4 functions

| Function | Lines | Responsibility |
|----------|-------|----------------|
| `resolve_clob_prices(pred, tokens)` | ~40 | WS cache → REST fallback → verified prices |
| `compute_order(pred, market_row, liquidity)` | ~50 | Already exists, stays as-is |
| `record_diagnostics(pred, market_row, order)` | ~30 | Staleness, drift, DIAG logging |
| `execute_trades(db, cycle)` | ~50 | Orchestrator: loop preds, call above, place_order |

The `resolve_clob_prices` extraction is the highest-value change — it's where the pricing bugs live, and it's currently buried 80 lines into a 211-line function.

#### 1b. `run_predictions()` → 3 functions

| Function | Lines | Responsibility |
|----------|-------|----------------|
| `filter_markets(markets, db)` | ~30 | Dead hour, price extreme, already-predicted gates |
| `predict_market(market, candles, regime, config)` | ~40 | Signal + consensus + store |
| `run_predictions(cycle, btc_data, indicators)` | ~40 | Orchestrator: fetch, filter, predict loop |

**Exit criteria:** No function over 60 lines in the critical path. Each new function has its own test.

### Phase 2: Pipeline Runner (eliminates ci_run_*.py duplication)

**Goal:** Replace 5 copy-pasted files with 1 parameterized runner.

#### 2a. Extract common pipeline lifecycle

All 5 ci_run files follow the same 15-step pattern. Extract into `pipeline_runner.py`:

```python
class PipelineRunner:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, candle_data=None, indicators=None):
        db = self._init_db()
        markets = self._fetch_and_store_markets(db)
        self._auto_resolve(db)
        cycle = self._next_cycle(db)
        candles = candle_data or self._fetch_candles()
        predictions = self._run_predictions(db, cycle, candles, indicators)
        orders = self._execute_trades(db, cycle, predictions)
        self._score(db)
        self._run_diagnostics(db, cycle)
        return orders
```

Each step is a method with a default implementation. Pipelines that need custom behavior (Kalshi caps conviction, Bybit creates synthetic markets) override just that method.

#### 2b. Pipeline registry

```python
# pipeline_registry.py
PIPELINES = {
    "btc_5m":  PipelineConfig(asset="BTC", interval="5m", venue="polymarket", ...),
    "btc_15m": PipelineConfig(asset="BTC", interval="15m", venue="polymarket", ...),
    "eth_5m":  PipelineConfig(asset="ETH", interval="5m", venue="polymarket", ...),
    "kalshi":  PipelineConfig(asset="BTC", interval="5m", venue="kalshi", ...),
    "bybit":   PipelineConfig(asset="BTC", interval="5m", venue="bybit", ...),
}
```

`botsy_engine.py` routing table becomes: look up pipeline name → get PipelineConfig → call `PipelineRunner(config).run()`.

**Exit criteria:** All 5 ci_run files deleted. `pipeline_runner.py` handles all pipelines. Adding a new pipeline = 1 entry in `pipelines.json`.

### Phase 3: Typed IPC (replaces JSON file polling)

**Goal:** Replace 3 implicit JSON files with typed dataclasses and atomic read/write.

#### Current JSON IPC

| File | Writer | Reader | Schema |
|------|--------|--------|--------|
| `live_orderbook.json` | botsy_engine (WS) | trade.py | `{"tokens": {id: {mid, spread, ...}}}` |
| `ws_metrics.json` | botsy_engine (60s) | daily_report, dashboard | `{feed: {connected, last_msg, ...}}` |
| `candle_buffer.json` | botsy_engine + candle_buffer | botsy_engine (startup) | `{symbol: {interval: [candles]}}` |

#### Target

```python
# ipc.py
@dataclass
class TokenPrice:
    mid: float
    best_bid: float
    best_ask: float
    spread: float
    updated_at: str

@dataclass
class OrderbookCache:
    tokens: dict[str, TokenPrice]

    @classmethod
    def load(cls, path: Path, max_age_s: float = 10.0) -> "OrderbookCache | None":
        """Atomic read with staleness check."""
        ...

    def save(self, path: Path):
        """Atomic write via temp file."""
        ...

    def get_token_mid(self, token_id: str, max_age_s: float = 10.0) -> float | None:
        """Returns mid or None if stale/missing."""
        ...
```

Benefits:
- Schema is code — IDE autocomplete, type checking, no key typos
- Staleness logic in one place (not reimplemented in every reader)
- `mypy` catches drift at lint time, not at 3am in production
- Same dataclass used by both writer (engine) and reader (trade.py)

**Exit criteria:** All 3 JSON files use typed dataclasses. `_get_live_token_mid()` calls `OrderbookCache.load().get_token_mid()`.

### Phase 4: Reduce Hub Coupling

**Goal:** Shrink `predict.py` from 8 dependents to a stable, narrow API.

#### Current problem

`predict.py` exports 10 functions. 8 modules import it. Moving `_get_clob_tokens_safe` into `predict.py` was a mistake — it's a CLOB concern, not a prediction concern. Same for `compute_dead_hours` (a trade filtering concern).

#### Proposed splits

| Function | Current Home | Correct Home | Why |
|----------|-------------|-------------|-----|
| `_get_clob_tokens_safe()` | predict.py | clob_depth.py | It's a CLOB token resolution function |
| `compute_dead_hours()` | predict.py | trade.py or config.py | It's a trade gate, not a prediction |
| `compute_regime_from_candles()` | predict.py | signals/regime.py | It's a signal component |
| `momentum_signal()` | predict.py | signals/momentum.py | It's a signal component |

After this split, `predict.py` becomes a thin orchestrator that calls signal components and stores results. Its API surface drops from 10 functions to 3: `initialize_schema()`, `store_prediction()`, `run_predictions()`.

**Exit criteria:** `predict.py` has ≤4 public functions. No module imports `predict.py` just to get `_get_clob_tokens_safe`.

---

## What NOT to Refactor

| Module | Lines | Why Leave It |
|--------|-------|--------------|
| `daily_report.py` | 1,677 | Output-only. Ugly but harmless. Doesn't affect trading. |
| `backtest.py` | 613 | Offline analysis. Not on critical path. |
| `backtest_native.py` | 566 | Same. |
| `v3/` subpackage | ~1,800 | Archived experimental code. |
| `dashboard_v2/` | ~1,800 | Presentation layer. Refactor when needed. |

---

## Verification

Each phase has its own gate:

| Phase | Gate | Metric |
|-------|------|--------|
| 0 | Test coverage | `pytest --cov` >80% on botsy_engine, ci_run, fetch_markets, bybit_trade |
| 1 | Function size | No function >60 lines in trade.py or predict.py |
| 2 | File count | 5 ci_run_*.py deleted, replaced by pipeline_runner.py + config |
| 3 | Type safety | All JSON IPC uses dataclasses; `mypy src/ipc.py` passes |
| 4 | Coupling | `predict.py` has ≤4 public functions; no module imports it for CLOB tokens |

**End-to-end:** After each phase, run the full lifecycle:
1. `pytest tests/ -v` — all pass
2. `python src/smoke_bet.py --dry-run` — pipeline works end-to-end
3. Deploy to VPS, verify engine starts and places orders
4. Check dashboard shows correct data

---

## Priority & Dependencies

```
Phase 0 (tests)
    ↓
Phase 1 (decompose) ←── requires Phase 0 tests to refactor safely
    ↓
Phase 2 (pipeline runner) ←── requires Phase 1 clean functions to compose
    ↓
Phase 3 (typed IPC) ←── independent, can run parallel with Phase 2
    ↓
Phase 4 (reduce coupling) ←── requires Phase 2 to know final import graph
```

Phase 0 is the prerequisite. Without tests on `botsy_engine.py`, we can't safely touch the dispatch loop that all pipelines depend on.

---

## Test Coverage Map (Current)

### Tested (27 modules)

| Module | Test File | Tests |
|--------|-----------|-------|
| trade.py | test_trade.py | 44 |
| predict.py | test_momentum.py, test_regime.py, test_consensus.py, test_pipeline_e2e.py | 48+ |
| btc_data.py | test_btc_data.py, test_15m.py | 25 |
| candle_buffer.py | test_candle_buffer.py | 13 |
| clob_depth.py | test_clob_depth.py | 12 |
| config.py | test_config.py | 19 |
| shadow_conviction_scorer.py | test_shadow_conviction.py | 23 |
| shadow_indicators.py | test_shadow_indicators.py | 20 |
| ta_engine.py | test_ta_engine.py | 14 |
| pipeline_control.py | test_pipeline_control.py | 18 |
| pipeline_integrity.py | test_pipeline_integrity.py | 25 |
| activity_digest.py | test_activity_digest.py | 6 |
| daily_report.py | test_daily_report.py | 21 |
| optimization_tracker.py | test_optimization_tracker.py | 10 |
| polymarket_pnl.py | test_pnl.py | 16 |
| smoke_bet.py | test_smoke_bet.py | 5 |
| vwap_strategy.py | test_vwap_strategy.py | 5 |
| bybit_*.py | test_bybit.py | 47 |
| kalshi_*.py | test_kalshi.py | 12 |
| (integration) | test_pipeline_e2e.py | 21 |
| (regression) | test_regression.py | 17 |

### Untested (28 modules) — by risk tier

**Tier 1 — Critical Path (must test before refactoring)**

| Module | Lines | Risk |
|--------|-------|------|
| botsy_engine.py | 751 | Core async loop, dispatch, WS feeds |
| ci_run.py | 141 | BTC 5m production pipeline |
| fetch_markets.py | 420 | Gamma API market discovery |
| bybit_trade.py | 530 | Bybit order execution |

**Tier 2 — Important (test during relevant phase)**

| Module | Lines | Risk |
|--------|-------|------|
| ci_run_eth.py | 173 | ETH pipeline (paper) |
| ci_run_15m.py | 164 | BTC 15m pipeline (paper) |
| ci_run_kalshi.py | 312 | Kalshi pipeline (paper) |
| ci_run_bybit.py | 296 | Bybit pipeline (paper) |
| predict_eth.py | 390 | ETH prediction variant |
| eth_data.py | 343 | ETH candle fetching |
| anomaly.py | 290 | Real-time anomaly detection |
| score.py | 160 | Brier score calculation |

**Tier 3 — Low Priority (test when touched)**

| Module | Lines | Risk |
|--------|-------|------|
| backtest.py | 613 | Offline analysis |
| backtest_native.py | 566 | Offline analysis |
| fill_diagnostic.py | 205 | Post-hoc analysis |
| kalshi_data.py | 46 | Tiny module |
| run_cycle.py | 65 | Manual trigger |
| dashboard_server.py | 135 | Presentation |
| generate_dashboard.py | 32 | Presentation |
| v3/* | ~1,800 | Archived |
