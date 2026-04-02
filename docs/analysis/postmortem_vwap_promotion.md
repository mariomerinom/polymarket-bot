# Postmortem: VWAP Mean-Reversion Promotion (Decision #23)

**Date:** 2026-04-02
**Severity:** Near-miss — production code deployed but **zero real orders fired** before catch.
**Status:** REVERTED. Code disabled in trade.py. Shadow continues collecting.

---

## What Happened

1. The daily report for 2026-04-01 showed: `shadow_vwap_meanrev: 42/50 bets collected (78.6% WR vs 67.4% baseline)`.
2. This was interpreted as "VWAP shadow has 42 resolved bets at 78.6% WR, nearly passing the 50-bet gate at >58%."
3. A production `vwap_strategy.py` was written, tested (6 tests), and deployed to `trade.py` to generate `vwap_rule` predictions at conviction=3 (real $25 bets).
4. Decision #23 was registered as ACTIONED.

**The stat was wrong.** The "42/50 at 78.6%" line in the daily report was the **RSI shadow gate** aggregated stat, not VWAP-specific performance. The daily report template reuses the same format for all shadow trackers. The actual VWAP line further down in the same report read: `VWAP Mean-Reversion (paper): 9 resolved, 33.3% WR (3W)`.

## The Real Numbers

### ETH VWAP Shadow: 17 resolved, 5W-12L, 29.4% WR

| Metric | Value |
|--------|-------|
| Total resolved | 17 |
| Wins | 5 |
| Losses | 12 |
| Win rate | **29.4%** |
| By direction: UP | 3W-5L (38%) |
| By direction: DOWN | 2W-7L (22%) |
| \|z\| ≥ 2.5 (extreme) | 1W-1L (50%) — 2 bets, meaningless |
| \|z\| 2.0–2.5 (moderate) | 4W-11L (27%) — this is where volume is |

### By Day

| Date | Record | WR |
|------|--------|----|
| 2026-03-31 | 2W-5L | 29% |
| 2026-04-01 | 3W-6L | 33% |
| 2026-04-02 | 0W-1L | 0% |

### BTC VWAP Shadow: Zero predictions

- BTC had 984 predictions in MEAN_REVERTING regime.
- Shadow logging (`shadow_log_indicators`) only ran on **1.8% of BTC cycles** (51 out of 2,814 predictions had shadow RSI attached).
- Zero VWAP shadow predictions were ever created for BTC.
- Root cause: shadow logging runs at the end of `execute_trades()`, which only fires when there are qualifying predictions (conv ≥ 3). During MEAN_REVERTING regime, momentum creates conv=0 skip predictions — so `execute_trades()` returns early at line 565 (`if not predictions: return []`), and shadow logging never runs.

## Why The Signal Fails

The VWAP mean-reversion thesis: "When price deviates >2σ from VWAP, it reverts to the mean."

On 5-minute Polymarket binary markets, this thesis has structural problems:

1. **VWAP is computed from 12 candles (1 hour).** That's a very short-term VWAP. The price can easily trend away from a 1-hour VWAP for the entire 5-minute window. Mean reversion over 1 hour is not the same as mean reversion within 5 minutes.

2. **The market's outcome is binary (up or down in 5 min), not magnitude.** VWAP measures how far price is from fair value, but the market only cares about direction. A 2σ deviation might slowly revert over 30 minutes — too late for a 5-minute bet.

3. **We're already in MEAN_REVERTING regime.** The autocorrelation is negative, meaning recent returns already show reversal patterns. But VWAP's signal (price far from average) doesn't add information about the *next* 5-minute candle's direction. It's descriptive, not predictive.

4. **DOWN direction is catastrophic at 22% WR.** When z > 2.0 (price above VWAP), predicting DOWN means betting the market will decline. But z > 2.0 often occurs during strong uptrends that continue — the VWAP hasn't caught up yet. This is trend-following disguised as mean-reversion.

5. **Market price contamination.** Several VWAP DOWN predictions occurred at market prices of 0.895 and 0.915 — well above the 0.85 price gate that momentum uses. These bets required 89-92% accuracy to break even. The VWAP strategy bypassed the price gate because it inserts predictions directly, not through the gated `run_predictions()` flow.

## What Went Wrong (Process)

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| **Misread stat** | Daily report conflates shadow tracker stats. Line 294 showed "78.6% WR" for all three shadow trackers with identical numbers. | Fix daily report template to show each shadow tracker's ACTUAL resolved WR, not shared aggregate stats. |
| **No independent verification** | Promotion relied on a single stat without querying the DB directly. | **Always query the source DB before promoting.** Never trust aggregated reports for go/no-go decisions. |
| **BTC shadow never collected data** | shadow_log_indicators only runs when execute_trades fires, which requires conv≥3 predictions. MEAN_REVERTING cycles produce conv=0 → execute_trades returns early → shadow logging skipped. | Fix the shadow logging call site so it runs every cycle, not only when there are qualifying trades. |
| **ETH data used for BTC decision** | VWAP shadow only had ETH data (17 bets). The promotion targeted BTC 5m. We promoted a BTC strategy based on zero BTC data. | **Never promote cross-asset.** Shadow data must come from the target pipeline. |
| **Gate passed "early"** | Applied the same early-pass precedent as Decision #18 (ETH Phase 1 at 36/50 at 66.7%). But that decision had 36 bets from the correct pipeline. VWAP had 0 bets from the correct pipeline. | Early-pass requires minimum 30 bets from the TARGET pipeline, not a sibling. |
| **No price gate in VWAP path** | vwap_strategy.py inserts predictions directly without the 0.15/0.85 price gate from predict.py. Several bets were at 0.89-0.97 market price. | Any new prediction path must inherit the same gates as the main pipeline. |

## Damage Assessment

**Zero real money lost.** The production code (`vwap_strategy.py`) was deployed and ran in `trade.py`, but:
- BTC: zero VWAP predictions generated (no shadow data, no production data)
- ETH: production code was not wired into `ci_run_eth.py` — only targeted BTC
- The code was disabled within hours of deployment

## Actions Taken

1. **Disabled** VWAP call in trade.py (replaced with explanatory comment)
2. **Reverted** Decision #23 to REVERTED status
3. **Shadow continues** — `shadow_log_indicators` still inserts `vwap_meanrev` (conv=2) for ongoing data collection
4. **This postmortem** documents the failure mode

## Actions Needed

1. **Fix daily report template** — shadow tracker stats should show per-tracker resolved WR, not shared aggregates
2. **Fix shadow logging call site** — must run every cycle regardless of whether execute_trades has qualifying predictions
3. **Add price gate to vwap_strategy.py** — if ever re-enabled, must filter extreme market prices
4. **Require source-pipeline data** — promotion gates must specify "50 bets from THIS pipeline", not any pipeline
5. **Add to ENGINEERING_LESSONS.md** — "Never promote based on aggregated stats. Always query the source DB."

## Lessons

1. **The daily report is a dashboard, not a decision gate.** When making GO/NO-GO decisions, query the database directly. Reports can conflate, aggregate, or lag.

2. **Cross-asset extrapolation is not validation.** ETH VWAP data (bad as it was) says nothing about BTC VWAP performance. Different assets, different volatility profiles, different market microstructure.

3. **Shadow logging architecture has a coverage gap.** If shadow indicators only run when `execute_trades()` fires, they systematically miss the regimes they're most needed in (MEAN_REVERTING, where momentum skips).

4. **Speed kills rigor.** The promotion was done same-day as the plan. The 6 unit tests all passed, the code was clean, the architecture was sound. But the input data was wrong. No amount of code quality fixes a bad premise.
