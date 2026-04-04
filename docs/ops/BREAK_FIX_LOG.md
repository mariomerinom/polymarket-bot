# Break-Fix Log

Production incidents and their root causes. Review before making changes.

---

## Incident 9: Missing API_TIMEOUT_CLOB Import — ALL Live Orders Failing
**Date:** April 4, 2026 | **Duration:** ongoing since config refactor | **Severity:** P0 — every live order fails

**Symptom:** 5+ consecutive live orders failed with `missing_clob_token_id`. Incident 8 fix (import rename) was necessary but not sufficient — orders kept failing after deploy.

**Root cause:** `clob_depth.py` references `API_TIMEOUT_CLOB` in `get_clob_tokens()` but never imports it from `config.py`. The variable was added to config during the centralization refactor (f270b280) and used in the function, but the import was never added. `requests.get(..., timeout=API_TIMEOUT_CLOB)` throws `NameError`, caught by `except Exception: pass`, function returns `None`. **Same silent-swallow pattern as Incident 8.**

**Data:**
- 5 orders affected: markets 1847910, 1848236, 1848252, 1848446, 1849054
- All UP signals at $25, estimates 0.51–0.58
- No money lost (orders never reached CLOB), but opportunity cost from all 5

**Fix:** Added `from config import API_TIMEOUT_CLOB` to `clob_depth.py` (frozen file — user-approved exception).

**Lesson:** Two bugs, same root cause pattern: `except Exception: pass` hiding `NameError`/`ImportError` on the critical trade path. The config centralization refactor (f270b280) introduced both — it moved constants to config.py but missed consumers in frozen files that couldn't be touched during normal development. Frozen file protection prevented the fix AND prevented catching the bug in normal test runs.

**Regression test:** `TestClobTokenImport::test_clob_token_import_name_matches_predict` (from Incident 8). Additional: manual test bet script (`manual_test_bet.py`) proves end-to-end CLOB path.

---

## Incident 8: CLOB Token Import Name Mismatch — 3 Live Orders Failed
**Date:** April 4, 2026 | **Duration:** ~1 hour (3 orders) | **Severity:** P1 — live orders failing silently

**Symptom:** Three consecutive live orders failed with `missing_clob_token_id`. Dashboard showed UP predictions firing with conviction 3+ but all trades failed.

**Root cause:** `trade.py` line 668 imported `from predict import _get_clob_tokens`, but the function was renamed to `_get_clob_tokens_safe` in the April 3 refactor commit (f270b280). The `except Exception: pass` handler silently swallowed the `ImportError`, so `clob_token_id` stayed `None` and every live order hit the `missing_clob_token_id` guard.

**Data:**
- 3 orders affected: markets 1847910, 1848236, 1848252
- All were UP signals at $25, estimates 0.51–0.58
- No money lost (orders never reached CLOB), but opportunity cost unknown

**Fix:** Updated import to `_get_clob_tokens_safe`. Changed bare `except Exception: pass` to log the error (`print(f"CLOB token lookup failed: {e}")`).

**Lesson:** Silent exception swallowing (`except Exception: pass`) on critical execution paths turns bugs into ghosts. Always log what you catch, especially in trade execution. The function rename was safe in predict.py but the consumer in trade.py was never updated — a classic cross-file rename hazard.

**Regression test:** `TestClobTokenImport::test_clob_token_import_name_matches_predict` — verifies trade.py imports the correct function name.

---

## Incident 7: Drawdown Breaker Cold Start — 36 Hours of Dead Trading
**Date:** April 2–4, 2026 | **Duration:** ~36 hours | **Severity:** P0 — all live orders halted

**Symptom:** Zero orders placed since April 2 16:50 UTC. Dashboard showed predictions firing (72% WR) but Trade Execution section missing from daily report. 42 qualifying predictions produced zero orders across April 3–4.

**Root cause:** `max_drawdown_breaker` tripped at 78.5% drawdown, blocking all `should_trade()` calls. The drawdown was calculated against a peak cumulative P&L of **$17.36** (only 9 settled orders total). A single $25 loss after 2 wins created >100% percentage drawdown. The 15% threshold was designed for a mature book with hundreds in cumulative profit — not day 1 of live trading.

**Data:**
- Peak cumulative P&L: $17.36 (7 wins out of 9 orders)
- Current cumulative P&L at trip: $3.74
- Drawdown: 78.5% (threshold: 15%)
- Orders blocked: 42 qualifying predictions, $0 placed
- Counterfactual missed P&L: Apr 3 +$125 (76.5% WR), Apr 4 +$87 (68.0% WR) = **+$212 missed**

**Contributing factor:** `DEFAULT_CANDLE_LIMIT` NameError (Incident 6) was also crashing predictions April 3 00:00–15:27 UTC, but the drawdown breaker would have blocked trades regardless.

**Fix:** Removed `max_drawdown_breaker` entirely from `trade.py`, `bybit_trade.py`, `config.py`. Daily loss limit ($300) + consecutive loss breaker (5) remain as protection. Percentage drawdown is meaningless on a sub-$100 equity curve.

**Lesson:** Circuit breakers must account for cold start. Percentage-based thresholds (drawdown from peak) are pathological when the denominator (peak equity) is tiny. Either use absolute thresholds or add a minimum peak floor before activating percentage-based breakers. In our case, the simpler answer was that the breaker was redundant — daily loss limit and consecutive loss cap cover the same ground without the cold start trap.

**Regression test:** Removed `test_max_drawdown_breaker` and `test_drawdown_within_threshold_passes`.

---

## Incident 6: Missing Config Dependencies During CI Sequence 
**Date:** April 3, 2026 | **Duration:** < 1 hour | **Severity:** Degraded UI & CI Breaks

**Symptom:** 
1. The **Kalshi CI runner** threw fatal `NameError: name 'SETTLEMENT_DELAY_S' is not defined` crashes inside auto-resolve procedures. 
2. The core GitHub Actions effectively skipped rendering Realized P&L matrices on the dashboard with a soft warning block: `[DASHBOARD] Real P&L fetch: name 'API_TIMEOUT_GAMMA' is not defined`.

**Root cause:** 
During the massive `config.py` refactoring eliminating legacy `limit=` and `timeout=` magic variables globally, the execution logic properties were systematically swapped sequentially. However, actual `from config import ...` references were not identically piped to the top of all operational controllers. 

**Data (2026-04-03, 3 isolated crash locations):**
- **Test 1:** `ci_run.py`, `ci_run_eth.py`, `ci_run_15m.py`, and `ci_run_kalshi.py` all referenced `<CANDLE_LIMIT>` loops correctly but did not append the python pointer fetching it.
- **Test 2:** `kalshi_score.py` correctly abstracted logic waits to `SETTLEMENT_DELAY_S` but didn't import it.
- **Test 3:** The user's dashboard generator internally caught a `NameError` crash natively inside the `polymarket_pnl.py` request module due to `API_TIMEOUT_GAMMA` omitting dependencies, safely degrading instead of killing the entire pipeline script execution!

**Fix:** Appended missing explicit `from config import ...` dependencies respectively at the top of all affected script interfaces and forcibly ran CI cycle 1 loops to assert completely green outputs locally. Restored broken files mapping over database and tracking commits!

**Lesson:**
When substituting variable scopes comprehensively across a distributed environment (especially into files not natively triggered actively during localized testing phases), running global `grep` audits tracking string mapping definitions strictly against localized Python IDE import logs avoids these structural syntax `NameError` explosions. Always dry-run **EVERY** component (`ci_run.py`, `ci_run_eth.py`, etc.) not just the core.

---

## ETH Signal Flip: Contrarian → Momentum
**Date:** April 1, 2026 | **Approved by:** User | **Severity:** Planned

**Files touched:**
- `src/predict_eth.py` — Renamed `contrarian_signal_eth()` → `momentum_signal_eth()`. Flipped signal direction: streak UP → predict UP (was DOWN). Removed exhaustion gate. Agent name `contrarian_eth` → `momentum_eth`. Signal type `contrarian` → `momentum`.
- `tests/test_eth_signal.py` — Updated all tests for momentum direction.
- `tests/test_trade.py` — Updated agent name references.
- `src/trade.py` — Simplified ETH agent detection (removed stale `"contrarian"` check).
- `CLAUDE.md` — Updated ETH strategy documentation.

**Rationale:**
- Contrarian: 33.3% WR on 54 resolved live predictions (catastrophic)
- Momentum counterfactual: 66.7% on same 54 bets (exact complement)
- Pattern mining validated contrarian at 54.4% on historical data, but live data contradicts it
- Same V3→V4 pattern as BTC (contrarian lost, momentum wins)

**Tracking:** Paper trading at conv=2. Revert criteria: WR < 55% at 100+ resolved momentum predictions.

**Rollback:** Revert `predict_eth.py` from git history. Agent name change means new predictions won't conflict with old ones.

---

## Frozen File Change: Fix CLOB SDK API Change (order_type removed)
**Date:** April 1, 2026 | **Approved by:** User | **Severity:** P0 — all live orders failing

**Files touched:**
- `src/trade.py` — Removed `OrderType` import and `order_type=OrderType.GTC` kwarg from `_submit_clob_order()`. `py-clob-client` v0.34.6 removed this parameter; GTC is now the default.
- `.github/workflows/daily-report.yml` — Reordered git operations: stash+pull before commit+push. Previous order caused `cannot pull with rebase: unstaged changes` errors (Mar 29, 30 failures).

**Impact:** 13+ live orders failed between 04:27–10:52 UTC on April 1. All showed `ClobClient.create_and_post_order() got an unexpected keyword argument 'order_type'`. Zero orders placed on the first full day of live trading post-exhaustion-gate removal.

**Rollback:** N/A — the old code is broken against the current SDK version.

---

## Frozen File Change: Remove Exhaustion Gate + Cooldown Flip Gate
**Date:** March 31, 2026 | **Approved by:** User | **Severity:** Planned

**Files touched:**
- `src/predict.py` — Removed exhaustion gate (compression, volume spike, shrinking range checks) and cooldown_flip gate. Momentum signal now fires on streak >= 3 alone.

**Rationale:**
- **Exhaustion gate:** Filtered predictions hit 85% WR (n=100, 9 days, no day below 70%) vs 67% WR for kept predictions. -18pp delta. The gate was a contrarian filter (selects for dying trends) on a momentum strategy (needs healthy trends). Pass rate dropped from 77% to 54% over one week as BTC candle sizes became more uniform, pushing range_ratio below the 0.7 threshold. Full analysis: `docs/analysis/analysis_exhaustion_gate.md`.
- **Cooldown flip:** Blocked 3/3 winning trades. Regime gate already handles chop.

**Tracking:** Daily report filter breakdown section. Revert if WR drops below 60% at 100+ bets.

**Rollback:** Re-add gates from git history (commit prior to this change).

---

## Frozen File Change: Production Trading Env Vars
**Date:** March 31, 2026 | **Approved by:** User | **Severity:** Planned

**Files touched:**
- `.github/workflows/predict-and-score.yml` — Added env vars (TRADING_ENABLED, POLYMARKET_PRIVATE_KEY, BET_SIZE, DAILY_LOSS_LIMIT, KILL_SWITCH) to the prediction cycle step. Required for live trading.

**Rationale:** Cannot go live without passing secrets to the workflow. Using `vars.*` for non-sensitive config (visible in Actions UI), `secrets.*` for private key only.

**Rollback:** Remove the `env:` block from the prediction cycle step. Trading falls back to paper mode (TRADING_ENABLED defaults to false).

---

## Incident 5: Whipsaw Chop — 52% Flip Rate in Flat Market
**Date:** March 27, 2026 | **Duration:** ~4 hours | **Severity:** Capital erosion

**Symptom:** BTC range-bound for 4+ hours. Bot placed 30 bets with 15 direction flips (52% flip rate). Between 05:01–05:45 UTC: 4 flips in 44 minutes (DOWN→UP→DOWN→UP). Momentum signal fires on short-lived streaks that immediately reverse in a flat market.

**Root cause:** The momentum signal only needs `min_streak` consecutive candles + exhaustion to fire. In a choppy/flat market, short streaks form in both directions as noise. The signal has no awareness that it just bet the opposite direction — it treats each cycle independently. Momentum needs follow-through to win; flat markets have none.

**Data (2026-03-27, last 30 bets):**
- 15 direction flips out of 29 transitions (52%)
- Regimes: 34% MEAN_REVERTING (correctly skipped), but 42% NEUTRAL where chop still fires
- The signal was technically correct each time (streak existed, exhaustion confirmed) but the streaks were noise

**Fix:** Added cooldown gate in `run_predictions()`: if the last bet (conv≥3) for the same market was in the *opposite* direction, require `min_streak + 1` to flip. Same-direction bets are unaffected. This is surgical — only activates during chop. When BTC is trending, consecutive bets go the same direction and the cooldown never triggers.

**Lesson:** A momentum signal in a range-bound market is a random number generator. The signal itself can't distinguish "genuine trend reversal" from "noise oscillation." Adding state (what did we bet last?) is cheap and filters the worst whipsaw cycles.

**Regression tests:** ~~`test_cooldown_blocks_rapid_flip()`, `test_cooldown_allows_same_direction()`, `test_cooldown_allows_strong_streak_flip()`~~ Removed 2026-03-31 — cooldown gate removed after blocking 3/3 winning trades. Regime gate handles chop. See "Frozen File Change: Remove Cooldown Flip Gate" above.

---

## Incident 4: Extreme Price Bets — Bad Risk/Reward
**Date:** March 27, 2026 | **Duration:** Ongoing until fix | **Severity:** Capital risk

**Symptom:** 15m bot bet #7: market price 0.005 (99.5% NO). Risked $75 to win $0.38 if correct. Breakeven WR at that price: 99.5%. Our signal hits ~66%. Mathematically guaranteed loss.

**Root cause:** No gate on market price in `run_predictions()`. The momentum signal and regime filter only look at BTC candle data, not the Polymarket price itself. Markets priced >0.85 or <0.15 have already priced in the outcome — our 66% WR signal can't overcome the breakeven requirement at those extremes.

**Data:**
- At price 0.95: win = $3.95, loss = -$75. Need 95% WR to break even.
- At price 0.50: win = $75, loss = -$75. Need 50% WR to break even.
- At price 0.30: win = $175, loss = -$75. Need 30% WR to break even.
- Sweet spot for our 66% signal: prices between 0.15–0.85.

**Fix:** Added price gate in `run_predictions()`: skip markets where `price_yes > 0.85 or price_yes < 0.15`. Stores as conviction=0 (no bet). Follows same pattern as regime gate.

**Lesson:** Binary option risk/reward depends entirely on entry price. Even a high-accuracy signal is mathematically guaranteed to lose at extreme prices. Gate on price before applying any signal logic.

**Regression test:** `test_price_gate_prevents_extreme_bets()`

---

## Incident 3: CI Failing After Evolution Cleanup
**Date:** March 19–20, 2026 | **Duration:** ~12 hours | **Severity:** CI down

**Symptom:** All Predict and Score runs failing with `fatal: pathspec 'prompts/' did not match any files`

**Root cause:** Deleted `prompts/` directory (legacy LLM agent prompts) without updating `.github/workflows/predict-and-score.yml` which had `git add data/ docs/ prompts/`.

**Fix:** Remove `prompts/` from git add line in workflow.

**Lesson:** When deleting directories, grep for references in CI workflows BEFORE pushing. Checklist:
```
grep -rn "prompts/" .github/
grep -rn "evolve" .github/
```

---

## Incident 2: Inverted Conviction — Lost $1,021
**Date:** March 18–19, 2026 | **Duration:** ~24 hours | **Severity:** Financial loss

**Symptom:** Dashboard showing -50% ROI. Conv=3 bets hitting 26% accuracy while Conv=0 skips hitting 69%.

**Root cause:** Contrarian rule backtested on synthetic markets where `price_yes ≈ 0.50` (we fabricated the market price from recent UP%). On live Polymarket, the market already prices in the streak — fading an already-faded streak arrives late. The rule overrides a good signal (market price) with a bad one.

**Fix:** Switched to paper trading mode. No real capital at risk.

**Lesson:** Backtests on synthetic data do not validate live edge. The market price IS the signal on Polymarket — you must test against real market pricing. Any future backtest must use actual Polymarket `price_yes` values, not fabricated ones.

---

## Incident 1: Binance 451 — Agents Flying Blind
**Date:** March 15–17, 2026 | **Duration:** ~48 hours | **Severity:** Degraded predictions

**Symptom:** Binance returning HTTP 451 from GitHub Actions (US IP). Fallback to CoinGecko provided 30-minute candles with zero volume. Agents had no usable price action data.

**Root cause:** Binance geo-blocks US IPs. CoinGecko OHLC endpoint minimum granularity is 30 minutes, and it doesn't include volume data. The "fallback" was effectively no data.

**Fix:** Replaced Binance → Kraken (US-regulated, no auth, 5-min OHLCV). Replaced CoinGecko → Coinbase (US-based, no auth, 5-min OHLCV).

**Lesson:** Test data providers from the actual deployment environment (GitHub Actions = US IP). Verify fallback actually returns usable data, not just "something."

---

## Pre-Change Checklist

Before pushing to main, verify:

- [ ] `grep -rn` for any references to deleted files/directories in `.github/workflows/`
- [ ] Run prediction cycle locally: `cd src && python ci_run.py`
- [ ] Check dashboard generates: `python dashboard.py --output ../docs/index.html`
- [ ] If changing bet logic: verify on live DB that conviction scores and P&L math are correct
- [ ] If changing data providers: test from a clean environment (not just local)
