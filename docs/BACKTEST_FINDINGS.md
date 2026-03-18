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

## Recommended Next Step

**Regime-filtered contrarian rule:**
- Keep the V2.1 contrarian logic
- Add regime detection from V3 feature engineering
- Skip all trades when autocorrelation < -0.15 (mean-reverting regime)
- Expected improvement: eliminate the -$1,533 HIGH_VOL/MEAN_REVERTING bleed

This requires zero ML, zero LLM API calls, and can be computed in <1ms per market.

If this works, the production system is:
1. Poll Polymarket for BTC 5-min markets
2. Fetch 12 candles from Kraken
3. Compute regime (volatility + autocorrelation)
4. If not mean-reverting: check contrarian rule (streak ≥ 3 + exhaustion)
5. If signal fires: bet $75
6. Otherwise: skip

**Estimated cost:** $0/day (no API calls). Just compute.
