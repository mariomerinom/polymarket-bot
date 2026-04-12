> **NOTE (2026-04-08):** GH Pages dashboards retired. Canonical view is local Streamlit (`streamlit run tools/diag.py`). Dashboard mentions below are historical.

# Testing & Pipeline Integrity

**Purpose:** Prevent production incidents. Nine incidents since March 15, 2026 cost $1,000+ in losses and 48+ hours of downtime. Every test exists because something broke. The integrity system exists because tests alone weren't enough.

**Current count: 760 tests across 48 files** (as of 2026-04-11). Runtime: ~100 seconds. Pre-existing failures: `test_ta_engine.py` (pandas_ta not on local), `test_fak_semantics.py` (py_clob_client not on local).

**Defense layers:** Tests gate commits (pre-push). Integrity checks run post-cycle (runtime on VPS). Together they cover what neither can alone.

**Methodology: TDD-first.** As of 2026-04-05, all development follows TDD: write behavioral tests BEFORE writing code. Before any implementation, evaluate existing tests for gaps and drift, review relevant plans, then determine both what to test and what to code. Tests assert WHAT the system does (contracts), not HOW it's organized. See `docs/plans/tdd-plan.md` for the full plan.

---

## Running Tests

```bash
# Full suite (~100 seconds)
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_pnl.py -v

# Single test
python -m pytest tests/test_regression.py::test_ci_workflow_no_deleted_paths -v
```

Tests run locally **before** every commit. If any test fails, the code does not get pushed — no broken code reaches the VPS engine.

---

## Test Architecture

### Test Gate Position

```
Local Dev: Edit → Run Tests → Commit → Push
                      │
                 FAIL = STOP
            (no push, no deploy)

VPS Engine: git pull → Predict → Trade → Score → Integrity Checks → git commit+push
                                                        │
                                                   Log to DB
                                             (surface in daily report)
```

Tests prevent broken code from reaching the VPS. Integrity checks catch runtime failures that tests can't simulate (API outages, stale tokens, DB corruption, expired orders).

### Test Patterns

| Pattern | Used By | Purpose |
|---------|---------|---------|
| In-memory SQLite | 8 files, 100+ tests | DB logic without file I/O or state leakage |
| `unittest.mock.patch` | 8 files, 80+ tests | Isolate external dependencies |
| Helper factories (`_make_candles`, `_make_db`) | 12 files | Generate synthetic candles, markets, predictions |
| Direct function tests | 10 files, 180+ tests | Pure functions, no setup needed |
| Class-based grouping | 10 files, 200+ tests | Logical test organization |
| `pytest.fixture` + `tmp_path` | 2 files | Per-test isolation with auto-cleanup |

No `conftest.py`, `pytest.ini`, or `pyproject.toml`. Each test file is self-contained with its own imports and setup.

---

## Test Layers (48 files, 760 tests)

### Layer 1: Smoke Tests — `test_smoke.py`, `test_smoke_bet.py` (~15 tests)

Catch broken imports and deleted modules before anything else runs.

Covers: `predict.py`, `btc_data.py`, `dashboard.py`, `fetch_markets.py`, `score.py`, `predict_eth.py` imports. Signal output structure. Empty data handling.

**When these fail:** Something fundamental is broken — fix before doing anything else.

### Layer 2: Signal Logic (3 files, ~30 tests)

The core trading brain.

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_momentum.py` | 10 | BTC streak detection, regime gating, direction (UP streak → predict UP), confidence, estimate bounds |
| `test_eth_signal.py` | 10 | ETH momentum matching BTC logic, conviction scoring, agent name `momentum_eth` |
| `test_regime.py` | 7 | Regime classification (trending/mean-reverting/neutral), volatility, autocorrelation, insufficient data |

**CRITICAL: Strategy is MOMENTUM for both BTC and ETH. Do not revert to contrarian.**

### Layer 3: Trade Execution — `test_trade.py`, `test_execution_fok.py`, `test_multi_pipeline_fok.py` (~55 tests)

Everything between a prediction and money moving.

Covers: flat $25 sizing, conviction gating (conv < 3 = no bet), daily loss limit ($300), consecutive loss breaker (5), kill switch (env + file), ETH agent detection, CLOB thin book guard, order construction, fill-priority spread, fill-size-based P&L, CLOB token import validation, FOK order semantics, multi-pipeline FOK execution.

### Layer 4: Data & Scoring (3 files, ~35 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_btc_data.py` | 8 | Candle parsing, summary stats, range bounds, volume ratios, trends |
| `test_pnl.py` | 16 | P&L math, conviction tiers, winning/losing bets, ROI — prevents Incident 2 (inverted conviction) |
| `test_asset_daily.py` | ~10 | Asset-level daily aggregations and stats |

### Layer 5: Pipeline-Specific (6 files, ~120 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_15m.py` | 18 | 15m relaxed params (`min_streak=2`), `loose_mode`, cross-timeframe context, 5m atomic unit |
| `test_bybit.py` | 45 | Bybit perps: config, schema, synthetic markets, position lifecycle, ATR, P&L, scoring, perps-vs-spot consensus |
| `test_kalshi.py` | 12 | Kalshi API integration, market fetching, order sizing |
| `test_hl.py` | ~20 | Hyperliquid pipeline: config, schema, position lifecycle, P&L |
| `test_perp_pipeline.py` | ~20 | Unified perp pipeline: multi-asset dispatch, ETH/SOL/DOGE lifecycle |
| `test_alpha_cushion.py` | ~10 | Alpha cushion edge calculation, threshold gating |

### Layer 6: Shadow & Experimental (4 files, ~82 tests)

Paper-trading signals that run alongside production but never place orders. Includes Strategy Lab for multi-strategy shadow testing.

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_shadow_conviction.py` | 23 | Parameterized shadow scorer, tier mapping, edge calculation, production isolation (shadow never overrides live conv) |
| `test_shadow_indicators.py` | 20 | RSI/OBV/VWAP shadow logging, candle parameter passing, no duplicates |
| `test_vwap_strategy.py` | 5 | VWAP mean-reversion: only fires in MR regime, z-score conviction, direction logic |
| `test_strategy_lab.py` | 34 | Strategy Lab: base types, indicator snapshots, always-fire strategies, DB operations, dispatch, auto-resolution, config loading, engine integration |

### Layer 7: Infrastructure (7 files, ~115 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_config.py` | 19 | Config constant coupling, shadow_configs structure, sane value bounds |
| `test_pipeline_control.py` | 18 | `pipelines.json` loading: live/paper/paused modes, bet sizes, pipeline status |
| `test_pipeline_integrity.py` | 25 | All 6 integrity checks (see Integrity System below), table creation, summary computation |
| `test_consensus.py` | 10 | Dual-source consensus scoring, tie-breaking, agent weighting |
| `test_daily_report.py` | 21 | Report generation, P&L rollups, agent breakdowns, empty data, integrity alerts |
| `test_activity_digest.py` | 6 | Session log generation, skip-when-exists, health queries |
| `test_orderbook_cache.py` | ~10 | Orderbook caching, staleness, eviction |

### Layer 8: Golden-Path Behavioral (TDD Phase A) — 4 files, ~26 tests

Written BEFORE refactoring as behavioral contracts. These test WHAT the system does, not HOW it's organized — they survive restructuring.

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_clob_resolution.py` | 6 | CLOB price resolution: WS hit, REST fallback, both-miss skip, stale cache, `_clob_verified` propagation, token resolution failure |
| `test_ci_run_lifecycle.py` | 8 | BTC 5m pipeline lifecycle: happy path, no markets, candle fail, kill switch, passthrough, dashboard, exception handling |
| `test_engine_dispatch.py` | 6 | Engine dispatch: routing, dedup, pruning, candle data building |
| `test_ci_run_bybit_lifecycle.py` | 6 | Bybit pipeline lifecycle: synthetic market, regime skip, dead hours, consensus boost, position sync |

**Why these exist:** The $2.18 smoke test bug (2026-04-05) happened because code was changed without tests proving correct behavior. These tests are the safety net for Phase B refactoring (extract functions, unify pipelines). See `docs/plans/tdd-plan.md`.

### Layer 9: End-to-End — `test_pipeline_e2e.py` (~21 tests, 5 classes)

Full predict → trade → settle → score lifecycle on in-memory DB. Created after the cold-start drawdown breaker incident.

| Class | Tests | What It Proves |
|-------|-------|----------------|
| `TestFullPipelineLifecycle` | 3 | Single cycle happy path, 5-cycle accumulation (3W-2L), cold start |
| `TestCircuitBreakers` | 7 | Daily loss trips/resets, consecutive loss at/below threshold, cross-cycle |
| `TestOrderConstruction` | 3 | Shadow prediction no order, no duplicates same cycle |
| `TestPnLComputation` | 5 | Winning/losing UP/DOWN, only filled+resolved get P&L |
| `TestMultiCycleIntegration` | 3 | Full 5-cycle pipeline, breaker trips, daily loss accumulates |

### Layer 10: Regression — `test_regression.py` (~17 tests)

One test per past production incident or optimization. The incident log in code form.

| Test | Incident / Optimization |
|------|--------------------------|
| `test_kraken_response_parsing` | #1: Binance 451 — data provider must return volume > 0 |
| `test_winning_bets_always_profit` | #2: Inverted conviction |
| `test_losing_bets_always_lose_exactly_bet_size` | #2: Inverted conviction |
| `test_tiered_conviction_ride_up_sweet_spot` | Conviction tier calibration |
| `test_down_neutral_demoted_to_no_bet` | DOWN+NEUTRAL → conv=2 (52% WR) |
| `test_up_neutral_still_bets` | UP+NEUTRAL stays conv≥3 (86.7% WR) |
| `test_dead_hour_gate_is_data_driven` | Dead hour gate computed from DB, not hardcoded |
| `test_dead_hour_fallback` | Fallback to config when DB has no data |
| `test_dead_hour_min_bets_enforced` | Min sample size for dead hour gating |
| `test_workflows_have_git_stash` | CI must stash before pull (concurrent push fix) |
| `test_fill_priority_spread_widens_limit_price` | #6: 53% fill rate — $165 missed profit |
| `test_pnl_uses_actual_fill_size` | #6: P&L from actual fill size, not intended |
| `test_down_neutral_demoted_even_in_loose_mode` | DOWN+NEUTRAL vol-split (HIGH_VOL allowed) |
| `test_mr_shadow_extreme_estimate` | MR shadow: extreme estimates tracked at conv=2 |
| `test_extreme_estimate_shadow_dead_hour` | Extreme estimates shadow even in dead hours |
| `test_extreme_estimate_shadow_price_gate` | Extreme estimates shadow at extreme prices |
| `test_eth_mr_shadow_extreme_estimate` | ETH MR shadow mirrors BTC pattern |

### Layer 11: Manual & Operational (2 files, ~18 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_manual_test_bet.py` | 8 | $5 smoke test: trading-disabled guard, audit trail (`agent=manual_test_user`), $5 size, UP/DOWN routing, abort on non-YES |
| `test_optimization_tracker.py` | 10 | Experiment registration, stats computation, closure checks |

### Layer 12: State & Invariants (5 files, ~50 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_state_invariants.py` | ~10 | Cross-pipeline state invariants, no global mutation |
| `test_state_transitions.py` | ~10 | Prediction state machine transitions (pending → resolved) |
| `test_pipeline_isolation.py` | ~10 | Pipeline isolation: no cross-contamination, mode independence |
| `test_system_state.py` | ~10 | System-wide state assertions |
| `test_paper_settlement.py` | ~10 | Paper trading settlement logic, outcome resolution |

### Layer 13: Engine (3 files, ~30 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_engine.py` | ~10 | Engine core: startup, shutdown, pipeline orchestration |
| `test_engine_resilience.py` | ~10 | Engine resilience: crash recovery, reconnection, error handling |
| `test_candle_buffer.py` | ~10 | Ring buffer: capacity, eviction, out-of-order handling |

### Layer 14: Specialist (3 files, ~25 tests)

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_judge.py` | ~10 | Judge evaluation: prediction grading, accuracy scoring |
| `test_pure_ta.py` | ~10 | Pure technical analysis: indicator computation without side effects |
| `test_fill_diagnostic.py` | ~5 | Fill diagnostic instrumentation: expired orders, would-win tracking |

---

## Pipeline Integrity System

### Why Tests Aren't Enough

Tests run pre-deploy and mock external dependencies. They can't catch:
- API outages at runtime (Gamma API returns 500 during a cycle)
- CLOB token resolution failures (tokens exist but API is slow)
- Orders that submit but never fill (expired on the book)
- Orphaned predictions (conv≥3 signal that never became an order)
- DB configuration drift (WAL mode disabled, foreign keys off)
- Kill switch activation

Incidents 8 and 9 proved this: tests passed, CI deployed, and every live order failed because `clob_depth.py` had a `NameError` hidden by `except Exception: pass`. Tests mocked the import chain and never caught it.

### Architecture

```
CI Cycle
  ├── predict()
  ├── execute_trades()
  ├── score()
  ├── run_integrity_checks()  ← catches what tests can't
  │     ├── failed_orders
  │     ├── orphaned_predictions
  │     ├── api_health
  │     ├── db_health
  │     ├── expired_would_win
  │     └── kill_switch
  ├── generate_dashboard()    ← shows integrity status
  └── commit + push
```

### Core Module: `src/pipeline_integrity.py`

Single entry point: `run_integrity_checks(db, pipeline, cycle, api_ok, data_fetched)`

Runs 6 checks, logs results to `integrity_log` table, returns list of `{check_name, status, detail}`. No external dependencies — pure DB queries.

### The 6 Checks

| Check | Detects | Status |
|-------|---------|--------|
| `failed_orders` | Orders with `status='failed'` this cycle | WARN — execution path broken |
| `orphaned_predictions` | Conv≥3 predictions with no matching order | WARN — high-conviction trade didn't execute |
| `api_health` | API call failed or returned empty data | FAIL if down, WARN if empty |
| `db_health` | WAL mode, busy_timeout, foreign_keys misconfigured | WARN — concurrency/data integrity risk |
| `expired_would_win` | Expired orders that would have won | WARN — missed profit (liquidity/fill issue) |
| `kill_switch` | Kill switch active (env var or file) | WARN — trading intentionally halted |

### Status Levels

- **OK** — No issues
- **WARN** — Anomaly detected, non-blocking (logged, surfaced in dashboard + daily report)
- **FAIL** — Critical failure (API down, check threw exception)

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS integrity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,     -- ISO 8601 UTC
    pipeline TEXT NOT NULL,      -- btc_5m, eth_5m, btc_15m, bybit, kalshi
    cycle INTEGER,               -- Current cycle number
    check_name TEXT NOT NULL,    -- Which check ran
    status TEXT NOT NULL,        -- OK, WARN, FAIL
    detail TEXT                  -- Human-readable explanation
)
```

### Where Checks Run

| Pipeline | File | Hook Point |
|----------|------|------------|
| BTC 5m | `generate_dashboard.py` | Before `build_html()` (ci_run.py calls this) |
| BTC 15m | `ci_run_15m.py` | Before `db.close()` |
| ETH 5m | `ci_run_eth.py` | Before `db.close()` |
| Bybit | `ci_run_bybit.py` | Before `db.close()` |
| Kalshi | `ci_run_kalshi.py` | Before `db.close()` |

Each uses the same pattern:
```python
try:
    from pipeline_integrity import run_integrity_checks
    results = run_integrity_checks(db, pipeline="...", cycle=cycle,
                                    api_ok=data is not None,
                                    data_fetched=bool(data))
    for r in results:
        if r["status"] != "OK":
            print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
except Exception as e:
    print(f"  [INTEGRITY] check failed: {e}")
```

### How Issues Surface

**Dashboard:** `src/dashboard.py` calls `get_integrity_summary(db)` → renders a green/yellow/red indicator with tooltip showing recent issues.

**Daily Report:** `src/daily_report.py` queries `integrity_log` for the day's WARN/FAIL entries. High-value alerts (`orphaned_predictions`, `expired_would_win`, `failed_orders`) bubble to the top of the alerts section.

**Summary logic:**
- Any FAIL in 24h → **red**
- Any WARN in 24h → **yellow**
- All OK → **green**

### Query Functions

```python
# Get WARN/FAIL entries from the last 24 hours
issues = get_recent_integrity(db, hours=24)

# Get dashboard summary: {status, checks_24h, warnings_24h, failures_24h, recent_issues}
summary = get_integrity_summary(db)
```

---

## Test Execution

> **Note (2026-04-08):** GitHub Actions workflows are fully retired. All pipelines run on a DigitalOcean VPS via `botsy_engine.py` managed by systemd (`botsy.service`). There is no `.github/workflows/` directory.

Tests run **locally before every commit** as part of the development workflow. The pre-commit discipline is: `pytest tests/ -v` must pass before pushing. A broken push stops the engine from pulling clean code.

```bash
# Full suite (~100 seconds)
python -m pytest tests/ -v --tb=short
```

The VPS engine does not re-run the test suite on every cycle — it trusts that pushed code has been tested locally. This makes local test discipline critical.

---

## Manual Smoke Test: `src/manual_test_bet.py`

Places a real $5 bet through the production CLOB execution path. Bypasses signal/conviction logic entirely. Proves the wallet, SDK, token resolution, and order submission work end-to-end.

```bash
cd src/
TRADING_ENABLED=true python3 manual_test_bet.py --direction UP
```

- Direction is **required** (no default — no agent bias)
- Requires `POLYMARKET_PRIVATE_KEY` and `POLYMARKET_PROXY_ADDRESS`
- Asks for `YES` confirmation before submitting
- Records as `agent="manual_test_user"`, `conviction_score=0` in `predictions.db`
- $5 hardcoded — smoke test, not a position

---

## Adding New Tests

**When to add a test:**
- A production incident occurs → regression test in `test_regression.py`
- A new optimization ships → regression test with revert criteria
- A new feature is added → unit tests in appropriate file
- A function's behavior changes → update existing tests first

**Test file map (48 files):**

```
tests/
├── test_15m.py                    # 15-minute pipeline specifics
├── test_activity_digest.py        # Session log generation
├── test_alpha_cushion.py          # Alpha cushion edge calculation
├── test_asset_daily.py            # Asset-level daily aggregations
├── test_btc_data.py               # Candle parsing, summary stats
├── test_bybit.py                  # Bybit perps pipeline
├── test_candle_buffer.py          # Ring buffer capacity, eviction
├── test_ci_run_bybit_lifecycle.py # Bybit pipeline lifecycle (TDD Phase A)
├── test_ci_run_lifecycle.py       # BTC 5m pipeline lifecycle (TDD Phase A)
├── test_clob_depth.py             # CLOB book depth, spread, thin book
├── test_clob_resolution.py        # CLOB price resolution (TDD Phase A)
├── test_config.py                 # Config constants, shadow configs
├── test_consensus.py              # Dual-source consensus scoring
├── test_daily_report.py           # Report generation, P&L, alerts
├── test_engine.py                 # Engine core orchestration
├── test_engine_dispatch.py        # Engine dispatch routing/dedup (TDD Phase A)
├── test_engine_resilience.py      # Engine crash recovery, reconnection
├── test_eth_signal.py             # ETH momentum_signal_eth() logic
├── test_execution_fok.py          # FOK order execution semantics
├── test_fak_semantics.py          # FAK order semantics (needs py_clob_client)
├── test_fill_diagnostic.py        # Fill diagnostic instrumentation
├── test_hl.py                     # Hyperliquid pipeline
├── test_judge.py                  # Judge evaluation, prediction grading
├── test_kalshi.py                 # Kalshi integration
├── test_momentum.py               # BTC momentum_signal() logic
├── test_multi_pipeline_fok.py     # Multi-pipeline FOK execution
├── test_optimization_tracker.py   # Experiment tracking
├── test_orderbook_cache.py        # Orderbook caching, staleness
├── test_paper_settlement.py       # Paper trading settlement logic
├── test_perp_pipeline.py          # Unified perp pipeline (multi-asset)
├── test_pipeline_control.py       # pipelines.json loading, mode management
├── test_pipeline_e2e.py           # Full predict→trade→settle→score lifecycle
├── test_pipeline_integrity.py     # All 6 integrity checks
├── test_pipeline_isolation.py     # Pipeline isolation, no cross-contamination
├── test_pnl.py                    # P&L math, conviction tiers
├── test_pure_ta.py                # Pure technical analysis indicators
├── test_regime.py                 # compute_regime_from_candles() logic
├── test_regression.py             # One test per past incident
├── test_shadow_conviction.py      # Shadow scorer, tier mapping
├── test_shadow_indicators.py      # RSI/OBV/VWAP shadow logging
├── test_smoke.py                  # Imports, connectivity, basic sanity
├── test_smoke_bet.py              # Smoke bet integration tests
├── test_state_invariants.py       # Cross-pipeline state invariants
├── test_state_transitions.py      # Prediction state machine transitions
├── test_strategy_lab.py           # Strategy Lab: multi-strategy shadow testing
├── test_system_state.py           # System-wide state assertions
├── test_trade.py                  # Order execution, sizing, circuit breakers
├── test_vwap_strategy.py          # VWAP mean-reversion shadow
└── test_manual_test_bet.py        # $5 manual smoke test
```

---

## Lessons Learned

1. **Tests that mock imports don't catch missing imports.** Incidents 8 and 9: `except Exception: pass` hid `ImportError` and `NameError` in the real import chain. Tests passed because they mocked the chain. The integrity system and manual smoke test exist because of this gap.

2. **`except Exception: pass` on trade paths is a production incident waiting to happen.** Every instance has been replaced with error logging. If you add a new try/except on any trade-adjacent code, log what you catch.

3. **One test per incident, written before the fix.** Write the failing test first, then fix. The test is proof the fix works and prevents regression. 17 regression tests and counting.

4. **Circuit breakers need cold-start awareness.** Percentage-based thresholds (drawdown from peak) are pathological when the denominator is tiny. Prefer absolute thresholds or add minimum floor.

5. **Runtime checks complement deploy-time tests.** Tests prove code is correct. Integrity checks prove the environment is correct (APIs up, tokens resolvable, DB healthy). Both are required.

6. **TDD-first for everything.** Write behavioral tests BEFORE writing code. Before implementation, evaluate existing tests for gaps and drift, review relevant plans, then determine both what to test and what to code. Tests written before prove behavioral preservation — tests written after cannot. The $2.18 pricing bug proved that changing code without tests proving correct behavior is gambling with real money.
