# Epic: Separation of Down and Neutral Regimes

**Background:** 
Currently, the pipeline uses autocorrelation to classify markets as `TRENDING`, `NEUTRAL`, or `MEAN_REVERTING`. Because this relies only on correlation and volatility, it lacks directional bias (an upward grind and a downward bleed can both appear as `NEUTRAL` or `TRENDING`). To avoid taking bad `DOWN` bets in sideways markets, we currently rely on a hardcoded, hacky filter (`DOWN + NEUTRAL = conviction 2`).

By explicitly separating "Down" (bearish direction) from "Neutral" (sideways/chop) regimes, we can replace the hardcoded filter with clean, systemic rules. 

---

## Acceptance Criteria

### 1. Mathematical Definition of Directional Regimes
* **Given** the regime calculation function receives a standard batch of candles (e.g., 20)
* **When** it calculates the regime labels
* **Then** it must compute a directional bias metric (e.g., mean return, SMA slope, or linear regression slope over the window).
* **And** it must use this metric to separate `TRENDING` and `NEUTRAL` regimes into explicitly directional categories (e.g., `UP_TRENDING`, `DOWN_TRENDING`, `UP_NEUTRAL`, `DOWN_NEUTRAL`, or simply `BEARISH` / `BULLISH` / `SIDEWAYS`).

### 2. Clean Up Prediction Logic (Removing the Hack)
* **Given** a new 5-minute prediction cycle is running in `predict.py`
* **When** evaluating a `DOWN` momentum streak
* **Then** the bot must no longer use the hardcoded `DOWN + NEUTRAL` conviction downgrade rule.
* **And** the bot must instead use the new explicit regime labels to make sizing decisions (e.g., blocking `DOWN` bets when the regime is strictly `SIDEWAYS`, but allowing them when the regime is `DOWN_TRENDING` or `BEARISH`).

### 3. Database and Logging Compatibility
* **Given** a prediction is stored to the SQLite database
* **When** saving the `regime` column and `reasoning` JSON
* **Then** the new separated labels (e.g., `MEDIUM_VOL / DOWN_TRENDING`) must be saved correctly.
* **And** existing SQL schemas must not break (the `regime` column must remain a standard text string).

### 4. Daily Report Parsing
* **Given** the daily morning cron job runs `src/daily_report.py`
* **When** it generates the `Regime Breakdown` tables
* **Then** it must correctly group and display the new separated regimes without crashing on historical/legacy regime labels.
* **And** legacy regime labels in the database (from before this change) should cleanly default to their historical bucket or an `UNKNOWN` category.

### 5. Backtesting Engine Parity
* **Given** a data scientist runs `python3 src/backtest_native.py`
* **When** computing the regime from the provided PolyMarket historical series
* **Then** the `native_regime()` function must correctly mirror the live pipeline's split between Down and Neutral regimes.
* **And** the terminal output must break down simulated win-rates and P&L for "Down" vs "Neutral" environments independently.
