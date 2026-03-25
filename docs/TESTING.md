# Testing Strategy

**Purpose:** Prevent production incidents. Three breaks in one week (March 15–20, 2026) cost $1,021 in losses and 12+ hours of CI downtime. Every test exists because something broke.

---

## Running Tests

```bash
# Run all 44 tests (~0.2 seconds)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_pnl.py -v

# Run a specific test
python -m pytest tests/test_regression.py::test_ci_workflow_no_deleted_paths -v
```

Tests run automatically in CI **before** the prediction cycle. If any test fails, the workflow stops — no broken code gets committed to the database or dashboard.

---

## Test Layers

### 1. Smoke Tests (`test_smoke.py`) — 8 tests

**Purpose:** Catch broken imports and deleted modules before CI runs.

| Test | What it catches |
|------|----------------|
| `test_predict_imports` | predict.py imports without errors |
| `test_btc_data_imports` | btc_data.py imports without errors |
| `test_dashboard_imports` | dashboard.py imports without errors |
| `test_fetch_markets_imports` | fetch_markets.py imports without errors |
| `test_score_imports` | score.py imports without errors |
| `test_contrarian_signal_returns_valid_structure` | Signal output has required keys, estimate in [0,1] |
| `test_regime_returns_valid_structure` | Regime output has required keys, types correct |
| `test_dashboard_pnl_on_empty_data` | P&L functions handle empty input without crashing |

**When these fail:** Something fundamental is broken — a deleted file, bad import, or syntax error. Fix before doing anything else.

### 2. Momentum Signal Tests (`test_momentum.py`) — 7 tests

**Purpose:** Verify the core trading logic produces correct signals.

| Test | What it catches |
|------|----------------|
| `test_no_signal_short_streak` | Streak < 3 returns no trade signal |
| `test_no_signal_insufficient_data` | < 5 candles returns no trade signal |
| `test_streak_3_up_with_compression` | 3 UP candles + shrinking ranges → ride UP at 0.62 (momentum) |
| `test_streak_3_down_with_volume_spike` | 3 DOWN candles + volume spike → ride DOWN at 0.38 (momentum) |
| `test_streak_without_exhaustion_no_trade` | Streak ≥ 3 but no exhaustion signal → no trade |
| `test_high_confidence_streak_5` | Streak ≥ 5 → confidence upgrades to "high" |
| `test_estimate_always_in_range` | Estimate is always between 0 and 1, regardless of input |

**When these fail:** The trading logic changed. If intentional, update the test. If not, you just prevented a bad deploy. **CRITICAL: The strategy is MOMENTUM (ride). V3 contrarian (fade) lost at 37% WR. Do not revert.**

### 3. Regime Detection Tests (`test_regime.py`) — 6 tests

**Purpose:** Verify regime classification that gates all trades.

| Test | What it catches |
|------|----------------|
| `test_trending_regime` | Consistent UP candles → TRENDING, autocorr > 0.15 |
| `test_mean_reverting_regime` | Alternating UP/DOWN → MEAN_REVERTING, autocorr < -0.15 |
| `test_low_vol_detected` | Tiny moves → LOW_VOL label |
| `test_insufficient_data` | < 3 candles → UNKNOWN, autocorr 0.0 |
| `test_regime_keys` | Output has all required keys |
| `test_autocorrelation_bounded` | Autocorrelation stays in reasonable range |

**When these fail:** The regime filter changed. This filter prevents the system from trading in mean-reverting markets (which lost $1,533 in backtesting). Breaking it re-exposes that risk.

### 4. P&L Math Tests (`test_pnl.py`) — 10 tests

**Purpose:** Verify that profit/loss calculations are correct. Prevents the inverted conviction disaster (Incident 2).

| Test | What it catches |
|------|----------------|
| `test_winning_up_bet_positive_pnl` | Correct UP prediction → positive profit |
| `test_losing_up_bet_negative_pnl` | Wrong UP prediction → lose exactly $75 |
| `test_winning_down_bet_positive_pnl` | Correct DOWN prediction → positive profit |
| `test_losing_down_bet_negative_pnl` | Wrong DOWN prediction → lose exactly $75 |
| `test_conviction_0_no_bet` | Conviction 0 → $0 wagered, $0 P&L |
| `test_conviction_3_bets_75` | Conviction 3 → $75 bet |
| `test_conviction_4_bets_200` | Conviction 4 → $200 bet |
| `test_pnl_at_extreme_prices` | P&L correct at market prices 0.10 and 0.90 |
| `test_roi_calculation` | ROI = total_pnl / total_wagered × 100 |
| `test_ensemble_only_bets_medium_plus` | Ensemble skips conviction < 3 |

**When these fail:** The P&L calculation changed. This directly affects the dashboard numbers and any future real-money decisions. Do not deploy until fixed.

### 5. BTC Data Tests (`test_btc_data.py`) — 8 tests

**Purpose:** Verify candle data parsing and summary statistics.

| Test | What it catches |
|------|----------------|
| `test_compute_summary_keys` | Summary has all 20 required keys |
| `test_range_position_bounded` | Range position stays in [0, 1] |
| `test_volume_ratio_positive` | Volume ratio and average are positive |
| `test_format_for_prompt_none` | Handles missing data gracefully |
| `test_format_for_prompt_valid` | Produces readable output with table |
| `test_up_down_counts_sum` | up_count + down_count = total candles |
| `test_trend_labels_valid` | Trend is one of up/down/neutral |
| `test_candle_pattern_valid` | Pattern is a known value (doji, hammer, etc.) |

**When these fail:** Candle parsing or micro-TA computation is broken. Agents receive bad data and make bad predictions.

### 6. Regression Tests (`test_regression.py`) — 5 tests

**Purpose:** One test per past production incident. These exist solely to prevent known bugs from recurring.

| Test | Incident | What it catches |
|------|----------|----------------|
| `test_kraken_response_parsing` | #1: Binance 451 | Data provider must return volume > 0 |
| `test_winning_bets_always_profit` | #2: Inverted conviction | Correct prediction at ANY market price must produce positive P&L |
| `test_losing_bets_always_lose_exactly_bet_size` | #2: Inverted conviction | Wrong prediction always loses exactly the bet size |
| `test_ci_workflow_no_deleted_paths` | #3: CI broken 12h | CI workflows must not reference deleted directories |
| `test_no_evolve_imports` | #3: CI broken 12h | Production code must not import deleted modules |

**When these fail:** You are about to reintroduce a bug that already cost money or downtime. Stop and investigate.

---

## CI Pipeline Order

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌─────────────┐     ┌──────────────┐
│  Checkout    │────▶│  Install     │────▶│  Run Tests    │────▶│  Predict    │────▶│  Commit +    │
│  repo        │     │  deps        │     │  (44 tests)   │     │  cycle      │     │  push        │
└─────────────┘     └──────────────┘     └───────────────┘     └───────────────┘     └──────────────┘
                                               │
                                          FAIL = STOP
                                          (no commit,
                                           no push)
```

If tests fail, the workflow stops. No predictions are made, no data is committed, no dashboard is updated. This prevents broken code from corrupting the production database.

---

## Pre-Change Checklist

Before pushing any change to `main`:

```bash
# 1. Run full test suite
python -m pytest tests/ -v

# 2. Check for references to deleted files in CI
grep -rn "prompts/\|evolve" .github/workflows/

# 3. Run prediction cycle locally
cd src && python ci_run.py

# 4. If changing P&L logic: verify on known inputs
python -m pytest tests/test_pnl.py tests/test_regression.py -v
```

---

## Adding New Tests

**When to add a test:**
- A production incident occurs → add a regression test
- A new feature is added → add unit tests for the new logic
- A function's behavior is changed → update existing tests first

**Regression test template:**
```python
def test_incident_N_description():
    """Brief description of what broke.
    Incident N: What happened and what it cost.
    """
    # Reproduce the exact conditions that caused the failure
    # Assert the correct behavior
```

**Test file locations:**
```
tests/
  test_smoke.py        # imports, connectivity, basic sanity
  test_contrarian.py   # contrarian_signal() logic
  test_regime.py       # compute_regime_from_candles() logic
  test_pnl.py          # P&L math, conviction tiers
  test_btc_data.py     # candle parsing, summary stats
  test_regression.py   # one test per past incident
```
