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

## Part 5: Zero-Cost Momentum Mode (ACTIVE)

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

### Validation criteria (in progress)
- [x] 500+ resolved predictions accumulated
- [x] Bet win rate ≥ 52% → **63.3% on 60 bets**
- [x] Mean-reverting regime correctly skipped
- [ ] 200+ bets with sustained WR ≥ 55%
- [ ] Positive ROI after simulated fees

### Success gate
If live data confirms backtest patterns → proceed to Part 6 (paper trading with real orders).
If live data does NOT confirm → the edge doesn't exist at this timeframe. Evaluate:
- Different Polymarket categories (sports, politics, events)
- Different timeframes (hourly, daily)
- Or shut down

---

## Part 6: Live Paper Trading (DEFERRED)

> Blocked until Part 5 validation criteria are met.

### Prerequisites
- Part 5 validation complete with positive results
- Polygon wallet with USDC
- `py-clob-client` SDK for CLOB order placement

### Plan
- `src/trade.py` — rule signal → order conversion
- Paper trading: log what we would have traded, track hypothetical P&L
- Regime filter active: skip mean-reverting markets
- Fixed $75 bet size (no Kelly until calibration proven)
- Daily loss limit: -$300 (4 consecutive losses → stop for 1 hour)
- Run 500 paper trades before any real capital

### After paper trading validates
- Micro-live: $5-10 bets for 200 trades
- Scale: $25 → $50 → $75 based on continued performance
- Full plan in `docs/DEPLOYMENT_PLAN.md`

---

## Part 7: Mac Mini Deployment (DEFERRED)

Move from GitHub Actions (unreliable cron, 1-30 min delays) to always-on Mac Mini.
Only worthwhile if Part 5/6 prove the edge is real.

- `scripts/mac-mini-loop.sh` — continuous loop with git push
- `scripts/com.polymarket.bot.plist` — launchd daemon
- Keep GitHub Pages dashboard (push HTML from Mini)
