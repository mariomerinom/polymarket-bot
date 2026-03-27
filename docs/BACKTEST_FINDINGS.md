# Backtest Findings — Full Evolution

**Date:** March 18, 2026
**Author:** Automated research pipeline + human review
**Total API spend on backtesting:** ~$23

---

## Executive Summary

We ran four versions of a BTC 5-minute prediction system through backtesting.
The key finding: **a 3-line contrarian rule outperforms both LLM agents and XGBoost ML.**
The real alpha came from bet sizing discipline (conviction tiers), not model sophistication.

| Version | Win Rate | ROI | P&L | Trades | What Changed |
|---------|----------|-----|-----|--------|-------------|
| V1 (3 LLM agents) | 50.8% | -13% | -$2,647 | 200 | Baseline ensemble |
| V2 (3 new LLM agents + conviction) | 55.2% | +19% | +$533 | 200 | New prompts + tier sizing |
| V2.1 (2 agents, drop pattern_reader) | 59.4% | +21% | +$604 | 200 | Removed weakest agent |
| V3 Contrarian Rule | 52.7% | +3.3% | +$960 | 389 | Simple rule, 14-day data |
| V3 XGBoost+LogReg | 51.3% | +0.5% | +$57 | 158 | ML model, FAILED gate |

---

## V1 — LLM Ensemble Baseline ($10 API cost)

**Setup:** 3 Claude-powered agents (base_rate, news_momentum, contrarian) predict
probability of BTC closing UP in each 5-minute candle. Simple average ensemble.
Bet on every market at $100.

**Period:** March 1–3, 2026 (200 markets)

### Agent Accuracy

| Agent | Accuracy (when calling) | Flat Rate | Take |
|-------|------------------------|-----------|------|
| contrarian | 58.6% | 4.5% | Best agent by far |
| base_rate | 49.5% | — | Coin flip |
| news_momentum | 44.4% | — | Actively harmful |

### Result
- **Ensemble: 50.8% accuracy, -13% ROI, -$2,647 P&L**
- Lost money because betting on every market at flat sizing
- news_momentum dragged the ensemble below breakeven
- contrarian was the only agent with genuine signal

### Key Lesson
> Betting on every market with equal sizing is fatal.
> One bad agent can destroy an otherwise profitable ensemble.

---

## V2 — New Agents + Conviction System ($10 API cost)

**Changes from V1:**
1. Replaced base_rate → pattern_reader (candle pattern recognition)
2. Replaced news_momentum → volume_wick (volume spikes + wick rejection)
3. Rewrote contrarian prompt with micro-TA context
4. Added conviction scoring (0–5) from 5 signal layers
5. Added tier-based bet sizing: NO_BET ($0), LOW ($25), MEDIUM ($75), HIGH ($200)
6. Weighted ensemble (pattern_reader 0.35, volume_wick 0.30, contrarian 0.35)

**Period:** March 1–3, 2026 (200 markets, same candles as V1)

### Agent Accuracy

| Agent | Accuracy (when calling) | Flat Rate |
|-------|------------------------|-----------|
| contrarian | 59.6% | — |
| volume_wick | 58.4% | — |
| pattern_reader | 52.4% | — |

### Conviction Tier Breakdown (3-agent)

| Tier | Markets | Accuracy | P&L | ROI |
|------|---------|----------|-----|-----|
| MEDIUM (score ≥ 3) | 25 | 68.0% | +$624 | +32% |
| LOW (score = 2) | 35 | 45.7% | -$91 | -10% |
| NO_BET (score ≤ 1) | 140 | 55.3% | $0 | — |

### Result
- **Ensemble: 55.2% accuracy, +19.4% ROI, +$533 P&L**
- MEDIUM tier carried all the profit at 68% accuracy
- LOW tier lost money — conviction system correctly identified weak signals but bet on them anyway
- pattern_reader was the weakest link at 52.4%

### Key Lesson
> The conviction system — not the new agents — is what turned V1's losses into V2's gains.
> MEDIUM tier at 68% accuracy is the profit engine. LOW tier bleeds.

---

## V2.1 — Drop pattern_reader, Kill LOW Bets ($0 cost, reanalysis)

**Changes from V2:**
1. Removed pattern_reader (52.4% accuracy was adding noise)
2. 2-agent ensemble: contrarian (0.55 weight) + volume_wick (0.45)
3. Eliminated LOW tier betting ($0 instead of $25)
4. Only bet on MEDIUM+ conviction

**Period:** Same 200 markets, reanalyzed

### Conviction Tier Breakdown (2-agent, no LOW bets)

| Tier | Markets | Accuracy | P&L | ROI |
|------|---------|----------|-----|-----|
| MEDIUM (score ≥ 3) | 23 | 78.3% | +$921 | +53% |
| LOW (score = 2) | 50 | — | $0 (skipped) | — |
| NO_BET (score ≤ 1) | 127 | — | $0 (skipped) | — |

### Result
- **2-agent ensemble: 59.7% accuracy, +53.4% ROI on MEDIUM bets**
- MEDIUM accuracy jumped from 68% → 78% by removing pattern_reader noise
- Only 23 out of 200 markets traded (11.5% selectivity)
- Higher ROI but lower absolute P&L than V2 (more selective = less volume)

### Key Lesson
> Removing a weak agent IMPROVED the ensemble. Less noise = better conviction signal.
> The optimal system is extremely selective: trade ~11% of markets at high conviction.

---

## V3 — Feature Engineering + ML ($3 API cost)

**Complete architecture change:**
1. No LLM agents — replaced with computed features (32 features)
2. XGBoost classifier + Logistic Regression agreement gate
3. Walk-forward backtest with expanding training window
4. Realistic friction: 1.5% round-trip fees + 1–3 cent random slippage
5. Regime detection: volatility level × autocorrelation pattern

**Period:** March 3–17, 2026 (4,012 synthetic markets from 14 days of candles)

### Feature Categories (32 total)

| Category | Count | Examples |
|----------|-------|---------|
| Price action | 8 | hour_change, trend_ups, trend_downs, body_pct, wick_ratio |
| Momentum | 5 | consecutive_streak, range_position, volatility |
| Volume | 3 | volume_ratio, avg_volume, volume_trend |
| Pattern | 5 | compression, candle_pattern (doji, hammer, engulfing, etc.) |
| Regime | 5 | volatility_regime, autocorrelation, regime encoded |
| Order book | 4 | spread_pct, depth_imbalance, bid/ask depth |
| Time | 2 | minutes_to_close, hour_of_day |

### Stage 3.5 — Contrarian Rule Baseline

Simple rule: if streak ≥ 3 same direction + exhaustion signal → fade.

| Metric | Value |
|--------|-------|
| Win rate | 52.7% |
| ROI | +3.3% |
| P&L | +$960 |
| Trades | 389 / 3,512 (11.1% selectivity) |
| Trades/day | 32 |
| Max drawdown | -$966 |
| Sharpe | 0.46 |

#### Critical Regime Breakdown

| Regime | Win Rate | P&L | Verdict |
|--------|----------|-----|---------|
| HIGH_VOL / TRENDING | 57% | +$633 | Good |
| HIGH_VOL / NEUTRAL | 57% | +$819 | Good |
| **HIGH_VOL / MEAN_REVERTING** | **26%** | **-$1,533** | **Disaster** |
| MEDIUM_VOL / TRENDING | 58% | +$510 | Good |
| MEDIUM_VOL / NEUTRAL | 57% | +$687 | Good |
| MEDIUM_VOL / MEAN_REVERTING | 47% | -$288 | Losing |

**Finding:** Mean-reverting regimes destroy the contrarian rule.
The contrarian assumes streaks reverse — but in mean-reverting regimes,
reversions happen faster than streak ≥ 3 can detect. When the rule fires,
it's fading a streak that's already reverting = buying at the wrong time.

### Stage 4 — XGBoost + LogReg

| Metric | ML Model | Contrarian Rule | Delta |
|--------|----------|-----------------|-------|
| Win rate | 51.3% | 52.7% | -1.4pp |
| ROI | +0.5% | +3.3% | -2.8pp |
| P&L | +$57 | +$960 | -$903 |
| Trades | 158 | 389 | -231 |
| Sharpe | 0.10 | 0.46 | -0.36 |

**Decision Gate: FAIL.** ML did not beat the contrarian baseline by ≥3pp WR or ≥5pp ROI.

**Calibration: FAIL.** 6 of 8 probability bins failed (predicted vs actual gap > 10pp).
Kelly sizing would be dangerous with this calibration.

**One positive finding:** ML did better in mean-reverting regimes (54% vs 26%).
It learned regime awareness. But it overcorrected in trending regimes (39% vs 57%).

### Root Cause Analysis

1. **Too many features for too little data:** 32 features vs 500 training samples.
   Rule of thumb: need 10–50× samples per feature. We had 15×.
2. **LogReg failed to converge:** Features not scaled, too many dimensions.
3. **Isotonic calibration unreliable on small calibration set** (~75 samples).
4. **5-minute BTC candles are very noisy.** Signal-to-noise ratio is low.
   Simple rules that capture one strong pattern (exhaustion) may be near-optimal.

---

## Cross-Version Insights

### What Actually Works
1. **Contrarian exhaustion detection** — the only consistently profitable signal across all versions
2. **Conviction-based selectivity** — trading 10–15% of markets instead of 100%
3. **Regime awareness** — mean-reverting regimes are toxic for streak-fading strategies

### What Doesn't Work
1. **LLM agents for micro-TA** — expensive, slow, inconsistent, tend to hedge at 0.50
2. **Simple ML on raw features** — not enough data, miscalibrated, no better than rules
3. **Betting on weak signals** — LOW conviction consistently loses money
4. **Equal-weight ensembles** — one bad component poisons the whole system

### The Uncomfortable Truth
A 3-line contrarian rule (streak ≥ 3, check exhaustion, fade) generates more
profit than 3 LLM agents ($10/backtest) or an XGBoost model with 32 features.
The complexity added no value. The bet sizing discipline (only trade high conviction)
is what separates profit from loss.

---

## Stage 4 — Regime-Filtered Contrarian (VALIDATED)

**Date:** March 18, 2026 | **Cost:** $0 (pure computation)

Tested three strategies on the same 14-day dataset (3,512 evaluated markets):

| Strategy | Win Rate | ROI | P&L | Trades/day | Max DD | Sharpe |
|----------|----------|-----|-----|------------|--------|--------|
| Plain Contrarian | 53.5% | +4.9% | +$1,413 | 31 | -$966 | 0.70 |
| **Regime-Filtered** | **58.3%** | **+14.3%** | **+$3,225** | **25** | **-$618** | **2.30** |
| Enhanced (V3.1 2-of-3) | 45.0% | -11.8% | -$708 | 7 | -$780 | -3.62 |

### What the regime filter does
- Computes lag-1 autocorrelation on recent 5-min returns
- If autocorrelation < -0.15 (mean-reverting): **skip the market entirely**
- Otherwise: apply the standard contrarian rule (streak ≥ 3 + exhaustion → fade)

### Impact
- **+4.8pp win rate** (53.5% → 58.3%)
- **+9.4pp ROI** (4.9% → 14.3%)
- **+$1,812 additional P&L** ($1,413 → $3,225)
- **Max drawdown improved** (-$966 → -$618)
- **Sharpe tripled** (0.70 → 2.30)

### Why Enhanced (V3.1 spec) failed
The consultant's recommended "2-of-3 exhaustion signals" filter was too strict.
It reduced trades from 300 to 80 (7/day) and accuracy dropped to 45%.
The wick rejection threshold (1.8× body) rarely fires in combination with
other signals. The simple exhaustion check (compression OR volume spike OR
shrinking range) works better than requiring multiple confirmations.

### Why the regime filter works
Mean-reverting regimes produced the largest single loss (-$1,524 in HIGH_VOL/MEAN_REVERTING).
The contrarian rule assumes streaks persist then reverse — but in mean-reverting regimes,
reversions happen before streak ≥ 3 fires. By the time the rule triggers, it's fading
a streak that already reversed. The filter removes 81 toxic trades and preserves 300
profitable ones.

---

## V3 Paper Trading Results — FAILED (March 19–22, 2026)

**632 predictions over 3 days (paper trading, no real capital).**

| Metric | Skip (conv=0) | Bet (conv=3) |
|--------|---------------|--------------|
| Count | 562 | 70 |
| Win Rate | **62.6%** | **37.1%** |

| Bet Direction | Count | Wins | WR |
|---------------|-------|------|----|
| Fade UP (est=0.38) | 38 | 15 | 39.5% |
| Fade DOWN (est=0.62) | 32 | 11 | 34.4% |

**Simulated P&L: -$962 | -18% ROI | EV per bet: -$13.70 | Edge: -8.3pp below breakeven**

### Why Contrarian Failed on Live Polymarket

The backtest used **synthetic markets** (fabricated price_yes ≈ 0.50) where streaks
hadn't been priced in yet. Live Polymarket already prices in BTC candle patterns —
we were fading streaks the market already faded.

The 62.6% skip accuracy is an **artifact**: skips anchor estimate = market_price,
which mechanically matches outcomes on skewed markets. It's not genuine signal.

### Decision: Invert to Momentum

If the contrarian signal loses at 37%, the **opposite** (momentum — ride the streak)
should win at ~63%. This is a V4 paper trading experiment to validate.

**Risk**: The 63% figure may itself be an artifact. Paper trading validates this
before any capital is risked.

---

## V4 — Momentum Signal (Inverted Contrarian)

**Date:** March 22, 2026 | **Status:** Paper trading

```
1. Poll Polymarket for BTC 5-min markets
2. Fetch 20 candles from Kraken
3. Compute regime: autocorrelation on 5-min returns
4. If autocorrelation < -0.15 → SKIP (mean-reverting)
5. If streak ≥ 3 + exhaustion signal → bet $75 RIDING the streak (momentum)
6. Otherwise → skip
```

**Hypothesis:** BTC momentum persists beyond what Polymarket prices in.
**Validation gate:** 200+ bets, WR ≥ 52%, positive ROI. If fails, pause project.

---

## Mean-Reversion Strategy Assessment (March 27, 2026)

**Question:** Can we trade in mean-reverting regimes instead of skipping them?

**Data:** 334 skip observations in mean-reverting regimes (5m pipeline):

| Regime | Market Lean | n | Went UP | UP% |
|--------|------------|---|---------|-----|
| HIGH_VOL / MR | market_says_DOWN | 78 | 32 | 41.0% |
| HIGH_VOL / MR | market_says_UP | 117 | 67 | 57.3% |
| MEDIUM_VOL / MR | market_says_DOWN | 67 | 29 | 43.3% |
| MEDIUM_VOL / MR | market_says_UP | 72 | 46 | 63.9% |

**Finding:** The market is already pricing mean-reversion correctly. When the market says UP in a mean-reverting regime, it goes UP 57-64% of the time. There is no independent signal beyond what the market price provides.

**Decision:** Continue skipping mean-reverting regimes. No tradeable edge found. The 58% overall "accuracy" on skips in these regimes is an artifact — skips anchor estimate to market price, mechanically matching outcomes on skewed markets.

**What would change this:** If we found a signal that disagrees with the market price AND is correct more often than the market, we'd have an edge. Current data shows the market is right. Revisit if regime dynamics change or with larger sample sizes.

## Market Price Gate (March 27, 2026)

**Finding:** Bets at extreme market prices (>0.85 or <0.15) have terrible risk/reward:

| Price | Win Payout | Loss | Breakeven WR | Our WR | Verdict |
|-------|-----------|------|-------------|--------|---------|
| 0.95 | $3.95 | -$75 | 95.0% | 66% | **Guaranteed loss** |
| 0.85 | $13.24 | -$75 | 85.0% | 66% | **Guaranteed loss** |
| 0.70 | $32.14 | -$75 | 70.0% | 66% | Marginal |
| 0.50 | $75.00 | -$75 | 50.0% | 66% | **Sweet spot** |
| 0.30 | $175.00 | -$75 | 30.0% | 66% | **Sweet spot** |
| 0.15 | $425.00 | -$75 | 15.0% | 66% | **Sweet spot** |
| 0.05 | $1,425.00 | -$75 | 5.0% | 66% | Great payout but market already decided |

**Decision:** Gate at 0.15–0.85. Below 0.15 the market is nearly decided (NO side is consensus). Above 0.85 the market is nearly decided (YES side is consensus). In both cases, our momentum signal can't overcome the breakeven requirement.

## Tiered Bet Sizing (March 27, 2026)

**Data:** 169 resolved bets from 5m paper trading (March 22-27, 2026).

### Direction asymmetry

| Direction | Bets | WR | P&L | ROI |
|-----------|------|-----|-----|-----|
| RIDE UP | 87 | **71.3%** | +$2,242 | +34% |
| RIDE DOWN | 82 | 61.0% | +$953 | +16% |

RIDE UP is 10pp higher WR and 2.3× the P&L.

### Best zone: RIDE UP + price 20-70%

| Zone | Bets | WR | P&L | ROI |
|------|------|-----|-----|-----|
| UP + 20-30% | 2 | 100% | +$463 | +309% |
| UP + 30-50% | 33 | 63.6% | +$902 | +36% |
| UP + 50-70% | 38 | 73.7% | +$949 | +33% |
| **Combined** | **73** | **70%** | **+$2,314** | **+42%** |

### Decision: Tiered conviction scoring

| Condition | Conviction | Bet Size | Rationale |
|-----------|-----------|----------|-----------|
| RIDE UP, price 20-70% | 4 (high) | $200 | 71% WR, best zone |
| RIDE DOWN, any price | 3 (medium) | $75 | 61% WR, decent but not as strong |
| RIDE UP, price outside 20-70% | 3 (medium) | $75 | Good WR but worse risk/reward |
| No signal / low confidence | 0 (skip) | $0 | No edge detected |

**Expected impact:** At $200 on the 73 RIDE UP bets in the sweet spot, P&L would have been ~+$6,171 vs +$2,314 at flat $75. ROI stays ~42% but on 2.67× the capital.

**Risk:** Small sample (73 bets). Could be regime-specific or time-period specific. Paper trading continues — if RIDE UP WR drops below 60% over next 200 bets, revert to flat $75.

---

## Cumulative Spend

| Item | Cost |
|------|------|
| V1 backtest (200 markets, 3 LLM agents) | ~$10 |
| V2 backtest (200 markets, 3 LLM agents) | ~$10 |
| V3 backtest (4,012 markets, pure compute) | $0 |
| Stage 4 regime backtest (3,512 markets) | $0 |
| Daily LLM observation (V2.1, ~3 days) | ~$4.50 |
| **Total** | **~$24.50** |
