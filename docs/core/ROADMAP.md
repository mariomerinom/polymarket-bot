# Polymarket Bot — Roadmap

## Status Key
- **DONE** — Completed and deployed
- **ACTIVE** — Currently in progress
- **NEXT** — Approved, ready to build
- **DEFERRED** — Documented, not started
- **FAILED** — Attempted, did not pass gate

---

## Part 1: Infrastructure (DONE)

Core pipeline running autonomously on GitHub Actions, dashboard on GitHub Pages.

- Polymarket Gamma API integration for BTC 5-min markets
- Auto-resolution and Brier scoring
- CI/CD: predict every 5 min, deploy dashboard
- Analytics dashboard with P&L simulation, streaks, calibration
- BTC candle data: Kraken primary, Coinbase fallback (replaced Binance)

---

## Part 2: Backtesting System (DONE)

Two backtesting engines built and validated.

### V1/V2 Backtest (`src/backtest.py`)
- Replay historical candles through LLM agent pipeline
- Synthetic market construction, no look-ahead bias
- Cost: ~$10 per 200-market run

### V3 Backtest (`src/v3/backtest.py`)
- Walk-forward with expanding window
- 14 days of Coinbase historical data (4,012 markets)
- Realistic friction: 1.5% round-trip + random slippage
- Regime-stratified reporting
- Cost: $0 (pure computation)

---

## Part 3: LLM Agent Ensemble (DONE → SUPERSEDED)

Three iterations of Claude-powered prediction agents.

| Version | Win Rate | ROI | Cost/day | Verdict |
|---------|----------|-----|----------|---------|
| V1 (3 agents) | 50.8% | -13% | ~$1.50 | Lost money |
| V2 (3 agents + conviction) | 55.2% | +19% | ~$1.50 | Conviction system worked |
| V2.1 (2 agents, no LOW bets) | 59.7% | +53% on MEDIUM | ~$1.50 | Best LLM version |

**Key finding:** Conviction-based bet sizing — not the agents — drove profitability.
The LLM agents are expensive ($1.50/day) and add marginal signal over simple rules.

See `docs/research/BACKTEST_FINDINGS.md` for full analysis.

---

## Part 4: ML Model Attempt (FAILED)

V3 XGBoost + Logistic Regression with 32 features.

- **Result:** 51.3% WR, +0.5% ROI — failed to beat contrarian rule baseline
- **Decision gate:** Required +3pp WR or +5pp ROI over baseline. Did not pass.
- **Calibration:** Failed on 6/8 bins. Kelly sizing would be dangerous.
- **Root cause:** Too many features (32) for too few samples (500). 5-min BTC is too noisy for ML to find patterns beyond simple rules.

---

## Part 5: Zero-Cost Momentum Mode (DONE)

**Goal:** Replace $1.50/day LLM agents with $0/day momentum rule + regime filter.

### What happened
- V3 contrarian (fade streaks) lost at 37% WR / -$962 on live Polymarket
- Polymarket already prices in BTC streak patterns — fading was redundant
- **Inverting to momentum (ride streaks) validated at 67% WR in paper trading**
- Regime filter correctly skips mean-reverting periods

### Validation criteria (ALL MET — 2026-03-30)
- [x] 500+ resolved predictions accumulated
- [x] Bet win rate ≥ 52% → **67.4% on 227 bets**
- [x] Mean-reverting regime correctly skipped
- [x] 200+ bets with sustained WR ≥ 55% → **227 bets at 67.4%**
- [x] Positive ROI after simulated fees → **+$8K simulated P&L**

### Success gate: PASSED
All criteria met. Proceeding to Part 6.

---

## Part 5.5: Continuous Optimization Validation (ACTIVE)

**Goal:** Every optimization gets automatically tracked, monitored, and flagged.

### Level 1: Auto-monitor with alerts (ACTIVE)
- Ship an optimization → register it with baseline stats and revert criteria
- Daily report computes post-change performance for each active optimization
- When sample size threshold is met, alert: "improved +6pp" or "REVERT CANDIDATE"
- Human decides, Claude executes

### Level 2: Auto-revert with PR (NEXT)
- When an optimization crosses its revert threshold, CI automatically creates a rollback PR
- Human merges or closes — the fix is already written and tested

### Level 3: A/B split testing (DEFERRED)
- Only viable when bet volume supports splitting (100+ bets/day)

---

## Part 6: Live Trading — Medium Grind (PAUSED → paper)

> Part 5 gate PASSED (227 bets, 67.4% WR). Live trading started 2026-03-31.
> **Reverted to paper 2026-04-09.** Signal quality is strong (63.4% WR on 484 bets) but adverse selection destroys edge: winning orders expire before filling, losing orders fill immediately. Execution fix needed before re-enabling live mode.

### Sizing philosophy: grind, not gamble

| Phase | Bet size | Trigger to advance | Trigger to stop |
|-------|----------|--------------------|-----------------|
| **Medium grind** | $25 flat | Bankroll +$500 from grind profits | WR < 52% over 50 bets, or -$300 daily loss |
| **Full grind** | $50 flat | Bankroll +$1,500 cumulative | WR < 52% over 50 bets, or -$500 daily loss |
| **Kelly on house money** | Kelly fractional, CLOB-capped | Bankroll +$3,000 cumulative | Drawdown > 30% of peak bankroll |

### Implementation (DONE)
- [x] Polygon wallet funded with USDC
- [x] `py-clob-client` SDK integrated
- [x] `src/trade.py` — signal → order conversion, flat $25 bets
- [x] Order fill tracking — orders table in DB
- [x] Daily loss limit circuit breaker (-$300)
- [x] Kill switch — `KILL_SWITCH=true` env var or `data/KILL_SWITCH` file
- [x] Thin book guard — caps bets at 90% of CLOB max@2% slippage

### Blocker: Adverse Selection (Fill Problem)
Winners expire before filling; losers fill immediately. Multiple fix specs in `docs/specs/stochastic/`. Key approaches: dynamic price cap, stochastic entry timing, IOC orders.

---

## Part 7: DigitalOcean VPS Deployment (DONE — fully consolidated)

Move from GitHub Actions to a dedicated VPS in a non-US region. GitHub Actions runners are US-based and get 403 geoblocked by Polymarket's CLOB API — all live orders fail.

- **Droplet:** $6/mo, Amsterdam (non-US IP)
- **Engine:** `src/botsy_engine.py` — single async process, systemd-managed (`botsy.service`)
- **What runs on VPS:** All 5 pipelines, trading, scoring, git auto-commit every ~5min
- **What stays on GitHub:** Code hosting only (GH Pages dashboards retired 2026-04-08)
- **GitHub Actions:** Fully retired — no `.github/workflows/` directory exists
- **Diagnostic:** Local Streamlit app (`tools/diag.py`) for P&L, rolling WR, regime heatmaps
- **All 5 pipelines consolidated (2026-04-05).** Dispatched by Bybit WS candle-close events via `ROUTING` table.

---

## Part 8: Multi-Asset Expansion (ACTIVE)

### ETH 5m Momentum (ACTIVE — paper, Phase 2 conditional GO)
- Flipped from contrarian to momentum 2026-04-01 (contrarian: 33.3% WR, momentum counterfactual: 66.7%)
- **267 resolved bets at 57.7% WR** — clears 55% threshold and 200-bet minimum
- HIGH_VOL non-trending gate added 2026-04-09 (40.7% WR on 27 bets in that regime)
- Phase 2 priority: volatility regime recalibration (BTC thresholds misclassify ETH as HIGH_VOL)
- See `docs/pipelines/eth_pipeline_acceptance_criteria.md`

### BTC 15m (ACTIVE — paper trading)
- Momentum signal with relaxed params (`min_streak=2`, `loose_mode=True`)
- 106 resolved bets at 59.4% WR
- HIGH_VOL gate excluded (64.3% WR on 56 bets — different dynamics at 15m)

### Bybit BTC Perpetual (ACTIVE — paper trading)
- Same momentum signal as BTC 5m, applied to Bybit BTCUSDT perpetual futures
- **Rehabilitated 2026-04-09** (was 50.5% WR on 319 bets): conviction filters, dead hours, position management fixes, mock resolution removed. Issue #70.
- Expected post-fix WR: ~54.8% (without HIGH_VOL bets)
- Entry: `src/ci_run_bybit.py`, trade: `src/bybit_trade.py`, score: `src/bybit_score.py`

### Kalshi BTC (ACTIVE — Phase 0, resolution fixed)
- Momentum signal on Kalshi BTC strike-price markets
- **Mock resolution replaced with real candle-based resolution 2026-04-09** (was producing random 50/50 outcomes)
- Previous 3,871 hash-resolved predictions invalidated; fresh data accumulating
- Gate: 200+ resolved predictions. WR > 55% → Phase 0.5. WR < 50% → signal is venue-specific.
- See [docs/plans/KALSHI_INTEGRATION_PLAN.md](../plans/KALSHI_INTEGRATION_PLAN.md)

### SOL (DEFERRED)
- Phase 2 showed contrarian_exhaust_s3 at 53.8% on 186 bets — weaker signal, smaller sample.
- Not prioritized until ETH and Bybit validate.

See [docs/plans/multi-asset-plan.md](../plans/multi-asset-plan.md) for the original expansion plan.
