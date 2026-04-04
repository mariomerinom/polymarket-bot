# Testing Strategy

**Purpose:** Prevent production incidents. Seven incidents since March 15, 2026 cost $1,021+ in losses and 48+ hours of downtime. Every test exists because something broke.

**Current count: 322 tests** (as of 2026-04-04). Runtime: ~12 seconds.

---

## Running Tests

```bash
# Run all tests (~12 seconds)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_pnl.py -v

# Run a specific test
python -m pytest tests/test_regression.py::test_ci_workflow_no_deleted_paths -v
```

Tests run automatically in CI **before** the prediction cycle. If any test fails, the workflow stops — no broken code gets committed to the database or dashboard.

---

## Test Layers

### 1. Smoke Tests (`test_smoke.py`)

**Purpose:** Catch broken imports and deleted modules before CI runs.

Covers: `predict.py`, `btc_data.py`, `dashboard.py`, `fetch_markets.py`, `score.py`, `predict_eth.py` imports. Signal output structure validation. Empty data handling.

**When these fail:** Something fundamental is broken — a deleted file, bad import, or syntax error. Fix before doing anything else.

### 2. Momentum Signal Tests (`test_momentum.py`)

**Purpose:** Verify the core BTC trading logic produces correct signals.

Covers: streak detection, regime gating, direction (UP streak → predict UP), confidence levels, estimate bounds.

**CRITICAL: The strategy is MOMENTUM (ride). V3 contrarian (fade) lost at 37% WR. Do not revert.**

### 3. ETH Signal Tests (`test_eth_signal.py`)

**Purpose:** Verify the ETH momentum signal matches BTC direction logic.

Covers: ride UP/DOWN streaks, no exhaustion gate, agent name `momentum_eth`, conviction scoring (medium → conv=3, high → conv=2), signal matches BTC momentum on same data.

**CRITICAL: ETH is MOMENTUM, not contrarian. Contrarian lost at 33.3% WR on 54 live bets. Do not revert.**

### 4. Regime Detection Tests (`test_regime.py`)

**Purpose:** Verify regime classification that gates all trades.

Covers: trending/mean-reverting/neutral detection, volatility levels, autocorrelation bounds, insufficient data handling.

**When these fail:** The regime filter changed. This filter prevents trading in mean-reverting markets (which lost $1,533 in backtesting).

### 5. P&L Math Tests (`test_pnl.py`)

**Purpose:** Verify profit/loss calculations. Prevents the inverted conviction disaster (Incident 2).

Covers: winning/losing UP/DOWN bets, conviction-to-bet-size mapping, extreme prices, ROI calculation.

### 6. Trade Execution Tests (`test_trade.py`)

**Purpose:** Verify live order placement, sizing, circuit breakers, and kill switch.

Covers: flat $25 sizing, conviction gating (conv < 3 = no bet), daily loss limit, consecutive loss breaker, kill switch, ETH agent detection, CLOB thin book guard, order construction, fill-priority spread, fill-size-based P&L.

### 7. BTC Data Tests (`test_btc_data.py`)

**Purpose:** Verify candle data parsing and summary statistics.

Covers: summary keys, range position bounds, volume ratios, null handling, trend labels, candle patterns.

### 8. 15-Minute Pipeline Tests (`test_15m.py`)

**Purpose:** Verify the 15m pipeline's relaxed parameters and loose mode.

Covers: `min_streak=2`, `autocorr_threshold=-0.20`, `loose_mode=True` disables 5m gates, cross-timeframe context.

### 9. Regression Tests (`test_regression.py`)

**Purpose:** One test per past production incident or optimization. Prevent known bugs from recurring.

| Test | Incident / Optimization |
|------|--------------------------|
| `test_kraken_response_parsing` | #1: Binance 451 — data provider must return volume > 0 |
| `test_winning_bets_always_profit` | #2: Inverted conviction |
| `test_losing_bets_always_lose_exactly_bet_size` | #2: Inverted conviction |
| `test_ci_workflow_no_deleted_paths` | #3: CI broken 12h |
| `test_no_evolve_imports` | #3: CI broken 12h |
| `test_price_gate_prevents_extreme_bets` | #4: Extreme price bets — bad risk/reward |
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

### 10. Shadow Conviction Tests (`test_shadow_conviction.py`)

**Purpose:** Verify the parameterized shadow conviction scorer (generic engine).

Covers: 23 tests — tier mapping, edge calculation, log-curve scoring, production isolation (shadow never overrides live conv), per-pipeline config validation, VWAP mean-reversion scoring.

### 11. VWAP Strategy Tests (`test_vwap_strategy.py`)

**Purpose:** Verify VWAP mean-reversion shadow indicator.

Covers: only fires in mean-reverting regime, z-score conviction mapping, direction logic (above VWAP → SHORT, below → LONG), no duplicate predictions, no frozen file modifications.

### 12. Shadow Indicator Tests (`test_shadow_indicators.py`)

**Purpose:** Verify shadow indicator logging and integration.

Covers: RSI/OBV/VWAP shadow log format, candle parameter passing, no duplicate VWAP predictions.

### 13. Activity Digest Tests (`test_activity_digest.py`)

**Purpose:** Verify automated session log generation.

Covers: session existence detection, skip-when-exists, digest generation, index update, empty data formatting, pipeline health queries.

---

## CI Pipeline Order

```
Checkout → Install deps → Run Tests → Predict → Trade (if enabled) → Score → Dashboard → Commit + Push
                                │
                           FAIL = STOP
                           (no commit, no push)
```

If tests fail, the workflow stops. No predictions are made, no orders placed, no data committed.

---

## Adding New Tests

**When to add a test:**
- A production incident occurs → add a regression test
- A new optimization ships → add a regression test with revert criteria
- A new feature is added → add unit tests
- A function's behavior changes → update existing tests first

**Test file locations:**
```
tests/
  test_smoke.py              # imports, connectivity, basic sanity
  test_momentum.py           # BTC momentum_signal() logic
  test_eth_signal.py         # ETH momentum_signal_eth() logic
  test_regime.py             # compute_regime_from_candles() logic
  test_pnl.py                # P&L math, conviction tiers
  test_trade.py              # live order execution, sizing, circuit breakers
  test_btc_data.py           # candle parsing, summary stats
  test_15m.py                # 15-minute pipeline specifics
  test_regression.py         # one test per past incident/optimization
  test_shadow_conviction.py  # shadow scorer logic, tier mapping, production isolation
  test_shadow_indicators.py  # RSI/OBV/VWAP shadow indicator integration
  test_vwap_strategy.py      # VWAP mean-reversion shadow strategy
  test_activity_digest.py    # automated session log generation
```
