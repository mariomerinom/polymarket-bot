# Testing Strategy

**Purpose:** Prevent production incidents. Three breaks in one week (March 15–20, 2026) cost $1,021 in losses and 12+ hours of CI downtime. Every test exists because something broke.

---

## Running Tests

```bash
# Run all tests (~0.3 seconds)
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

Covers: ride UP/DOWN streaks, no exhaustion gate, agent name `momentum_eth`, conviction always 2 (paper trading), signal matches BTC momentum on same data.

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

Covers: flat $25 sizing, conviction gating (conv < 3 = no bet), daily loss limit, kill switch, ETH agent detection, CLOB thin book guard, order construction.

### 7. BTC Data Tests (`test_btc_data.py`)

**Purpose:** Verify candle data parsing and summary statistics.

Covers: summary keys, range position bounds, volume ratios, null handling, trend labels, candle patterns.

### 8. 15-Minute Pipeline Tests (`test_15m.py`)

**Purpose:** Verify the 15m pipeline's relaxed parameters and loose mode.

Covers: `min_streak=2`, `autocorr_threshold=-0.20`, `loose_mode=True` disables 5m gates, cross-timeframe context.

### 9. Regression Tests (`test_regression.py`)

**Purpose:** One test per past production incident. Prevent known bugs from recurring.

| Test | Incident |
|------|----------|
| `test_kraken_response_parsing` | #1: Binance 451 — data provider must return volume > 0 |
| `test_winning_bets_always_profit` | #2: Inverted conviction |
| `test_losing_bets_always_lose_exactly_bet_size` | #2: Inverted conviction |
| `test_ci_workflow_no_deleted_paths` | #3: CI broken 12h |
| `test_no_evolve_imports` | #3: CI broken 12h |

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
- A new feature is added → add unit tests
- A function's behavior changes → update existing tests first

**Test file locations:**
```
tests/
  test_smoke.py        # imports, connectivity, basic sanity
  test_momentum.py     # BTC momentum_signal() logic
  test_eth_signal.py   # ETH momentum_signal_eth() logic
  test_regime.py       # compute_regime_from_candles() logic
  test_pnl.py          # P&L math, conviction tiers
  test_trade.py        # live order execution, sizing, circuit breakers
  test_btc_data.py     # candle parsing, summary stats
  test_15m.py          # 15-minute pipeline specifics
  test_regression.py   # one test per past incident
  test_shadow_conviction.py  # 23 tests: shadow scorer logic, tier mapping, production isolation
```
