# Polymarket Bot — Roadmap

## Status Key
- **DONE** — Completed and deployed
- **ACTIVE** — Currently in progress
- **NEXT** — Approved, ready to build
- **DEFERRED** — Documented, not started

---

## Part 1: Infrastructure (DONE)

Core pipeline running autonomously on GitHub Actions, dashboard on GitHub Pages.

- Polymarket Gamma API integration for BTC 5-min markets
- Auto-resolution and Brier scoring
- Prompt self-evolution (evolve.py)
- CI/CD: predict every 5 min, evolve every 2 hours
- Analytics dashboard with P&L simulation, streaks, calibration
- Consolidated portfolio P&L banner

---

## Part 2: Backtesting System (DONE)

`src/backtest.py` — Replay historical BTC candles through agent pipeline.

- Downloads historical 5-min candles from Binance (paginated, free)
- Synthetic market construction with no look-ahead bias
- Resumable runs (safe to interrupt and continue)
- Cost controls: `--sample-rate`, `--max-candles`, `--dry-run`
- Summary report: per-agent accuracy, Brier, P&L, ROI, ensemble, vs coin flip

**V1 backtest (200 markets):** contrarian 58.6%, base_rate 49.5%, news_momentum 44.4%. Ensemble -13% ROI.

---

## Part 3: Prediction Engine v2 (DONE)

Rebuilt the prediction stack: 2-agent micro-TA ensemble, human macro bias layer, conviction-based bet sizing.

**Final config (v2.1):**
- **Agents:** contrarian (0.55) + volume_wick (0.45) — dropped pattern_reader after backtest showed it was noise
- **Conviction tiers:** NO_BET (score 0-1, $0), LOW (score 2, $0), MEDIUM (score 3, $75), HIGH (score 4+, $200)
- **Key insight:** LOW conviction loses money in every config — killed it. Only bet MEDIUM+.

**V2 backtest (200 markets):** 2-agent ensemble 59.4% accuracy, MEDIUM tier 78.3%, +$921 P&L, **+53.4% ROI**.

See `docs/BACKTEST_RESULTS.md` for full comparison across all versions.

---

## Part 5: Mac Mini Deployment (NEXT)

Move from GitHub Actions cron (unreliable, 1-30 min delays) to always-on Mac Mini.

- `scripts/mac-mini-loop.sh` — continuous loop with git push
- `scripts/com.polymarket.bot.plist` — launchd daemon (auto-start, auto-restart)
- `scripts/setup-mac-mini.md` — setup guide
- Keep GitHub Pages dashboard (push HTML from Mini)

---

## Part 6: Live Polymarket Trading (DEFERRED)

> Not starting until backtest proves consistent edge over 500+ predictions.

### Requirements
- Polygon wallet with USDC
- `py-clob-client` SDK for CLOB order placement
- `src/trade.py` — prediction → order conversion
- Risk management: Kelly sizing, daily loss limits, edge thresholds
- `orders` table in DB
- Paper trading phase → micro-live ($1-2 bets) → scale up

### Full plan in `docs/DEPLOYMENT_PLAN.md`
