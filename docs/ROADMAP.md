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

See `docs/BACKTEST_FINDINGS.md` for full analysis.

---

## Part 4: ML Model Attempt (FAILED)

V3 XGBoost + Logistic Regression with 32 features.

- **Result:** 51.3% WR, +0.5% ROI — failed to beat contrarian rule baseline
- **Decision gate:** Required +3pp WR or +5pp ROI over baseline. Did not pass.
- **Calibration:** Failed on 6/8 bins. Kelly sizing would be dangerous.
- **Root cause:** Too many features (32) for too few samples (500). 5-min BTC is too noisy for ML to find patterns beyond simple exhaustion rules.

See `docs/BACKTEST_FINDINGS.md` and `src/v3/model.py` for details.

---

## Part 5: Zero-Cost Momentum Mode (DONE ✅)

**Goal:** Replace $1.50/day LLM agents with $0/day momentum rule + regime filter.
Keep the bot running, keep logging, keep the dashboard — stop paying for predictions.

### What happened
- V3 contrarian (fade streaks) lost at 37% WR / -$962 on live Polymarket
- Polymarket already prices in BTC streak patterns — fading was redundant
- **Inverting to momentum (ride streaks) validated at 63% WR in paper trading**
- Regime filter correctly skips mean-reverting periods (no bets placed)

### Implementation (DONE)
1. `predict.py` — momentum_signal() + regime computation, $0/day
2. Regime logging — volatility level + autocorrelation per prediction
3. Dashboard — P&L asymmetry visualization, regime breakdown
4. No LLM dependencies (no ANTHROPIC_API_KEY needed)

### Validation criteria (ALL MET — 2026-03-30)
- [x] 500+ resolved predictions accumulated
- [x] Bet win rate ≥ 52% → **67.4% on 227 bets**
- [x] Mean-reverting regime correctly skipped
- [x] 200+ bets with sustained WR ≥ 55% → **227 bets at 67.4%**
- [x] Positive ROI after simulated fees → **+$44K simulated P&L**

### Success gate: PASSED
All criteria met. Proceeding to Part 6.

---

## Part 5.5: Continuous Optimization Validation (ACTIVE)

**Goal:** Every optimization we ship gets automatically tracked, monitored, and flagged — no manual DB queries, no "did that change work?"

### Level 1: Auto-monitor with alerts (ACTIVE)
- Ship an optimization → register it with baseline stats and revert criteria
- Daily report computes post-change performance for each active optimization
- When sample size threshold is met, alert: "improved +6pp" or "REVERT CANDIDATE"
- Human decides, Claude executes

### Level 2: Auto-revert with PR (NEXT)
- When an optimization crosses its revert threshold, CI automatically:
  - Creates a rollback branch reverting the specific change
  - Opens a PR with the before/after stats in the description
  - Human merges or closes — the fix is already written and tested
- Jump from Level 1 is small: add `git revert` + `gh pr create` to the alert path

### Level 3: A/B split testing (DEFERRED)
- Split predictions into control/treatment groups (50/50)
- Same market, same cycle — one arm uses the new filter, one doesn't
- After N bets per arm, compare and auto-promote or auto-kill
- Requires schema changes (treatment group column) and dashboard changes
- Only viable when bet volume supports splitting (100+ bets/day)

### Implementation
- `src/optimization_tracker.py` — register, monitor, compare optimizations
- `docs/optimizations.json` — registry of all active/completed optimizations
- Daily report integration — reads registry, computes deltas, fires alerts
- Skill: `/validate-optimization` — registers new optimizations from any Claude session

---

## Part 6: Live Trading — Medium Grind (NEXT)

> Part 5 gate PASSED (227 bets, 67.4% WR). Moving to production.

### Sizing philosophy: grind, not gamble

Paper trading revealed concentration risk — tiered sizing ($75/$200/$300) produced 16 bets at $219 avg instead of 43 bets at $75. One bad day would hurt 3x as much. Production resets sizing to flat and earns its way up.

| Phase | Bet size | Trigger to advance | Trigger to stop |
|-------|----------|--------------------|-----------------|
| **Medium grind** | $25 flat | Bankroll +$500 from grind profits | WR < 52% over 50 bets, or -$300 daily loss |
| **Full grind** | $50 flat | Bankroll +$1,500 cumulative | WR < 52% over 50 bets, or -$500 daily loss |
| **Kelly on house money** | Kelly fractional, CLOB-capped | Bankroll +$3,000 cumulative | Drawdown > 30% of peak bankroll |

- **Conviction still gates which bets fire.** Only conv ≥ 3 places orders. But all bets are the same dollar amount within a phase.
- **Thin book constraint.** Max bet is whatever the CLOB can absorb at ≤2% slippage, regardless of phase. `clob_depth.py` already measures this.
- **Paper tiers keep running in parallel.** The current tiered system continues logging at conv 2 to collect counterfactual data.

### Prerequisites
- [ ] Polygon wallet funded with USDC
- [ ] `py-clob-client` SDK integrated
- [ ] `src/trade.py` — signal → order conversion
- [ ] Order fill tracking — log placed price vs fill price vs slippage
- [ ] Daily loss limit circuit breaker (-$300 → pause 1 hour)
- [ ] Kill switch — manual override to halt all trading

### Implementation plan
1. **`src/trade.py`** — Takes a prediction + conviction → places a CLOB limit order at $25. Logs order ID, fill status, actual price. No market orders (slippage risk on thin book).
2. **Order tracking table** — New `orders` table in DB: order_id, market_id, prediction_id, side, size, price_placed, price_filled, status, timestamp.
3. **CI integration** — After `run_predictions()`, if conviction ≥ 3 and trading enabled, call `trade.py`. Separate flag (`TRADING_ENABLED=true`) so we can kill it without touching code.
4. **Dashboard** — Add live P&L card showing real money: orders placed, filled, slippage, actual returns vs simulated.
5. **Circuit breakers** — Daily loss limit. Max concurrent open positions. CLOB depth check before every order.

---

## Part 7: Mac Mini Deployment (DEFERRED)

Move from GitHub Actions (unreliable cron, 1-30 min delays) to always-on Mac Mini.
Only worthwhile if Part 5/6 prove the edge is real.

- `scripts/mac-mini-loop.sh` — continuous loop with git push
- `scripts/com.polymarket.bot.plist` — launchd daemon
- Keep GitHub Pages dashboard (push HTML from Mini)

---

## Part 8: Multi-Asset Expansion (ACTIVE)

Expand from BTC-only to ETH, SOL, and beyond.

### ETH 5m Contrarian (ACTIVE — paper trading)
- Phase 1 outcome analysis + Phase 2 pattern mining validated **contrarian at 54.4% WR on 1,601 markets**
- Parallel pipeline shipped: `predict_eth.py`, `ci_run_eth.py`, `predict-eth-5m.yml`
- Separate DB (`predictions_eth.db`), separate dashboard (`docs/eth.html`)
- All predictions at conviction 2 (paper). Collecting 200+ resolved before calibration.
- Dashboard linked from nav bar: BTC 5m | BTC 15m | ETH 5m

### BTC 15m (ACTIVE — paper trading)
- Momentum signal with relaxed params (`min_streak=2`, `loose_mode=True`)
- 12 resolved bets at 67% WR — small sample, still collecting.

### SOL (DEFERRED)
- Phase 2 showed contrarian_exhaust_s3 at 53.8% on 186 bets — weaker signal, smaller sample.
- Not prioritized until ETH paper trading validates.

See [docs/multi-asset-plan.md](multi-asset-plan.md) for the original plan.
