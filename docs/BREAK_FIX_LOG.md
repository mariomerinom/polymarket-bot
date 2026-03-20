# Break-Fix Log

Production incidents and their root causes. Review before making changes.

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
