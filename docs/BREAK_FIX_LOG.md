# Break-Fix Log

Production incidents and their root causes. Review before making changes.

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

**Regression tests:** `test_cooldown_blocks_rapid_flip()`, `test_cooldown_allows_same_direction()`, `test_cooldown_allows_strong_streak_flip()`

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
