# Polymarket BTC 5-Min Prediction Bot — Project Evolution

> Produced March 17, 2026 for external review. All numbers pulled directly from SQLite databases.
> 100 commits over 3 days. ~$20 in Claude API costs for backtesting. System is live.

---

## 1. What This Is

An autonomous prediction system for Polymarket's "Bitcoin Up or Down" 5-minute candle markets. Two AI agents (Claude Sonnet 4.6) read BTC candlestick data, predict the next candle direction, and a conviction scoring system decides whether to bet and how much.

Runs on GitHub Actions every ~30 minutes. Auto-resolves markets, scores agents, evolves the worst agent's prompt every 2 hours. Dashboard auto-deploys to GitHub Pages.

**Current deployed config (V2.1):**
- 2 agents: contrarian (weight 0.55) + volume_wick (weight 0.45)
- Only bets on MEDIUM+ conviction (score >= 3 out of 5)
- Backtest result: 78.3% accuracy on bet markets, +53.4% ROI
- Live result (first 21 resolved markets): contrarian 61.9%, volume_wick 57.1%

---

## 2. V1: Original 3-Agent System

### Agents

| Agent | Strategy | Weight |
|-------|----------|--------|
| **base_rate** | Time-of-day effects, day-of-week patterns, mean reversion at 5-min scale | 1/3 |
| **news_momentum** | Short-term momentum, trending vs ranging regimes, macro catalyst reasoning | 1/3 |
| **contrarian** | Fade exhaustion after consecutive candles, compression detection | 1/3 |

Simple average ensemble. Flat $100 bet on every market. No conviction filtering.

### V1 Backtest (200 markets, March 1-15 2026)

**Individual agent accuracy (excluding 0.500 flat calls):**

| Agent | Correct | Called | Accuracy | Flat Calls | Total Predictions |
|-------|---------|--------|----------|------------|-------------------|
| contrarian | 112 | 191 | **58.6%** | 76/267 (28%) | 267 |
| base_rate | 105 | 212 | 49.5% | 53/265 (20%) | 265 |
| news_momentum | 108 | 243 | **44.4%** | 26/269 (10%) | 269 |

**V1 Ensemble result:**
- 94 correct, 91 wrong, 15 flat
- Accuracy: **50.8%**
- P&L: **-$76** on $18,500 wagered = **-0.4% ROI**

The ensemble was essentially a coin flip because it averaged one good agent (58.6%) with one coin flip (49.5%) and one anti-predictive agent (44.4%).

### V1 Post-Mortem

1. **news_momentum was actively destructive at 44.4%.** It reasoned about "macro catalysts" and "momentum" — meaningless at 5-minute scale where price moves faster than any reasoning chain. It also had the lowest flat rate (10%), meaning it confidently called the wrong direction.

2. **base_rate was a coin flip at 49.5%.** Day-of-week and time-of-day effects don't exist at 5-minute granularity. The agent was pattern-matching on noise.

3. **contrarian was the only real signal at 58.6%.** Fading exhaustion after consecutive candles is a genuine micro-TA signal. But equal-weight ensemble diluted its edge by averaging in the two bad agents.

4. **No bet sizing discipline.** Flat $100 on everything meant the system bled equally on high-conviction and low-conviction calls.

---

## 3. V2: Micro-TA Redesign

### Design Philosophy

Replace macro-reasoning agents with micro-TA specialists that read candle patterns, volume, and wicks. Add a conviction scoring system to filter bets.

### New Agents

| Agent | Replaces | Strategy |
|-------|----------|----------|
| **contrarian** | (kept) | Fade exhaustion after 3+ consecutive candles, check body sizes shrinking, wick confirmation |
| **volume_wick** | news_momentum | Read volume spikes (ratio > 2x average) and wick rejection patterns (wick > 2x body) |
| **pattern_reader** | base_rate | Candle formations (doji, hammer, engulfing, inside bar), range position (0=bottom, 1=top) |

### Micro-TA Data Added to Agent Context

Agents now receive pre-computed signals from the last 12 five-minute candles:

- **Range position:** Where current price sits in 12-candle range (0.0 = bottom, 1.0 = top)
- **Volume ratio:** Last candle volume / average volume (spike detection)
- **Range ratio:** Last candle range / average range (expansion detection)
- **Compression:** Are last 3 candle ranges shrinking? (breakout setup)
- **Candle pattern:** doji, hammer, inv_hammer, engulfing_bull, engulfing_bear, inside_bar
- **Wick ratios:** Upper and lower wick size relative to body

### Conviction Scoring System

5 independent binary layers, each worth 1 point (max score = 5):

| Layer | Condition | Points |
|-------|-----------|--------|
| Agent Agreement | All agents predict same direction | +1 |
| Magnitude | Average estimate > 4pp from 0.50 | +1 |
| Confidence | 2+ agents report medium or high confidence | +1 |
| Macro Alignment | Agent direction matches human macro bias | +1 |
| Computed Bias | Rolling UP% (7d/24h/1h blend) confirms direction | +1 |

**Tier mapping:**

| Score | Tier | Bet Size |
|-------|------|----------|
| 0-1 | NO_BET | $0 |
| 2 | LOW | $25 |
| 3 | MEDIUM | $75 |
| 4-5 | HIGH | $200 |

### V2 Backtest (200 markets, same period)

**Individual agent accuracy (excluding flat calls):**

| Agent | Correct | Called | Accuracy | Flat Rate | vs V1 Counterpart |
|-------|---------|--------|----------|-----------|-------------------|
| contrarian | 90 | 151 | **59.6%** | 49/200 (25%) | +1.0pp |
| volume_wick | 87 | 149 | **58.4%** | 51/200 (26%) | +14.0pp (vs news_momentum) |
| pattern_reader | 76 | 145 | 52.4% | 55/200 (28%) | +2.9pp (vs base_rate) |

**3-agent ensemble with conviction tiers (LOW = $25):**

| Tier | Markets | Called | Correct | Accuracy | P&L |
|------|---------|--------|---------|----------|-----|
| MEDIUM (3) | 26 | 26 | 18 | **69.2%** | **+$696** |
| LOW (2) | 55 | 53 | 25 | 47.2% | -$100 |
| NO_BET (0-1) | 119 | 104 | 58 | 55.8% | $0 |
| **Total** | **200** | **183** | **101** | **55.2%** | **+$596** |

Wagered: $3,275. ROI: **+18.2%**

The conviction system correctly identified that MEDIUM tier had real signal (69.2%) while LOW tier was below coin flip (47.2%).

---

## 4. V2.1: Drop Pattern Reader

### Analysis

We tested every possible ensemble configuration against the same 200-market backtest:

| Configuration | Ensemble Acc | MEDIUM Acc | P&L | Wagered | ROI |
|---------------|-------------|------------|-----|---------|-----|
| 3-agent, LOW=$25 | 55.2% | 69.2% | +$596 | $3,275 | +18.2% |
| 3-agent, LOW=$0 | 55.2% | 69.2% | +$696 | $1,950 | +35.7% |
| **2-agent, LOW=$0** | **59.4%** | **78.3%** | **+$921** | **$1,725** | **+53.4%** |
| 2-agent, LOW=$25 | 59.4% | 78.3% | +$647 | $3,175 | +20.4% |
| contrarian solo | 59.6% | n/a | +$417 | $1,200 | +34.8% |

### Key finding: dropping pattern_reader improved MEDIUM tier accuracy from 69.2% to 78.3%

Pattern_reader was adding noise that diluted the conviction signal. Its 52.4% accuracy meant it frequently disagreed with the two better agents, reducing the agreement score and preventing MEDIUM conviction from firing on good calls. When it did agree, it was often wrong.

### Second finding: LOW tier always loses money

Across every configuration tested, LOW conviction (score = 2) accuracy was below 50%. The system correctly identified weak signals — and then bet on them anyway. Eliminating LOW tier bets was the second-largest improvement.

### V2.1 Final Config

- **Agents:** contrarian (0.55 weight) + volume_wick (0.45 weight)
- **Bet only on MEDIUM (score 3, $75) and HIGH (score 4+, $200)**
- **Skip LOW and NO_BET entirely**
- Result: 23 markets bet on out of 200 (11.5% selectivity), 18 correct (78.3%), +$921 profit

---

## 5. The Evolution System

### How It Works

Every 2 hours, `evolve.py` runs:

1. Check if 10+ new market resolutions since last evolution
2. Find worst V2 agent by average Brier score
3. Extract that agent's 5 worst predictions (highest Brier)
4. Send to Claude: "Here's the agent's prompt, here are its mistakes. Diagnose the pattern and generate ONE targeted text substitution to fix it."
5. Claude returns: `{diagnosis, old_text, new_text, expected_effect}`
6. Apply the substitution. Back up original prompt.
7. Log to `data/evolution_log.json`

### Evolution Stats

- **17 total evolutions** over 3 days (March 15-17, 2026)
- **Agents evolved:** news_momentum (8), base_rate (5), volume_wick (4)
- **Zero manual reversions needed**
- Contrarian was never the worst agent — it was never evolved

### Recurring Error Patterns Found by Evolution

**1. Defaulting to 0.50 instead of market_price (most common)**
Agents naturally output 0.50 ("coin flip") when uncertain. This ignores the market_price signal entirely. The evolution system caught this repeatedly and added explicit rules: "When no signal, return market_price exactly, NEVER 0.50."

**2. news_momentum over-anchoring to market price**
The opposite problem: after fixing the 0.50 default, news_momentum started just mirroring market_price without adding any independent signal. Evolution added: "Form estimate independently FIRST, then check market_price."

**3. Extreme divergence from market**
Agents sometimes output estimates 30-40pp away from market_price. Evolution added mandatory adjustment rules: "If gap > 20pp from market, adjust 75% of the way toward market."

---

## 6. Data Provider Migration

### The Problem

The system was designed to use Binance for BTC candle data. But:
- **Binance returns HTTP 451** from US IP addresses (GitHub Actions runs in US)
- **CoinGecko fallback** only provides **30-minute candles with zero volume data**
- Agents were receiving degraded data — no volume spikes, no 5-minute granularity
- The volume_wick agent was effectively blind (all volume values = 0)

### The Fix

| Role | Old | New |
|------|-----|-----|
| Primary | Binance (geo-blocked from US) | **Kraken** (US-regulated, no auth, native 5-min OHLCV) |
| Fallback | CoinGecko (30-min, no volume) | **Coinbase** (US-based, no auth, 5-min OHLCV) |

Both Kraken and Coinbase provide real volume data, enabling the volume_wick agent to actually detect spikes and the contrarian agent to confirm exhaustion with volume.

---

## 7. Human-in-the-Loop: Macro Bias

### Design

`config/macro_bias.md` is the one human-edited file:

```
Regime: CHOPPY
Direction Bias: NEUTRAL
Prior: 0.50
```

Agents read this to understand the macro context. It feeds into conviction layer 4 (macro alignment).

### Current Setting: NEUTRAL

With NEUTRAL bias, conviction layer 4 never fires. This means max practical conviction score is 3 (MEDIUM), not 5 (HIGH). This is intentional:
- Avoids confirmation bias in the evolution system
- Keeps agents signal-driven rather than prior-driven
- When the human sets a directional bias (UP/DOWN), conviction can reach 4-5 on aligned calls

### Backtest Limitation

The backtest uses the CURRENT macro_bias.md for ALL historical candles. Since the backtest period (March 1-15) is within the same regime as when the bias was set (March 16), this is approximately correct. For backtests spanning different regimes, we'd need time-indexed bias configs.

---

## 8. Architecture

### Pipeline

```
Polymarket API → fetch_markets.py → predict.py → conviction.py → score.py
                                        ↑                            ↓
                                   Kraken/Coinbase            evolve.py (every 2h)
                                   (BTC candles)                    ↓
                                                            prompts/*.md (modified)
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Model | Claude Sonnet 4.6 (Anthropic API) |
| Market Data | Polymarket Gamma API (public, no auth) |
| BTC Prices | Kraken primary + Coinbase fallback (no auth) |
| Database | SQLite (data/predictions.db) |
| CI/CD | GitHub Actions (cron every 5 min) |
| Dashboard | Static HTML on GitHub Pages |
| Language | Python 3.14 |

### Database Schema

```sql
CREATE TABLE markets (
    id TEXT PRIMARY KEY,
    question TEXT, category TEXT, end_date TEXT,
    volume REAL, price_yes REAL, price_no REAL,
    fetched_at TEXT, resolved INTEGER DEFAULT 0,
    outcome INTEGER DEFAULT NULL  -- 1=UP, 0=DOWN
);

CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT, agent TEXT,
    estimate REAL, edge REAL, confidence TEXT,
    reasoning TEXT, predicted_at TEXT, cycle INTEGER,
    conviction_score INTEGER  -- 0-5 (v2)
);
```

### GitHub Actions Workflows

- **predict-and-score.yml:** Every 5 minutes. Fetch markets, predict, score, generate dashboard, commit.
- **evolve.yml:** Every 2 hours. Identify worst agent, generate prompt modification, apply, commit.

---

## 9. What Worked

1. **Contrarian agent consistency.** 58.6% in V1, 59.6% in V2. The only agent that reliably beat coin flip across both versions. Fading exhaustion after consecutive candles is a genuine micro-TA signal.

2. **Conviction tier system.** 5 independent layers correctly separated signal (78.3% MEDIUM) from noise (47.2% LOW). The key insight: selectivity beats volume. Betting on 11.5% of opportunities at 78% accuracy beats betting on 100% at 55%.

3. **Killing LOW tier bets.** LOW conviction was consistently unprofitable across every configuration. Eliminating it was the difference between +18% ROI and +53% ROI.

4. **Autoresearch on prompts.** 17 evolution iterations over 3 days with zero manual reversions. The system identified real failure patterns (0.50 anchoring) and fixed them automatically.

5. **Data provider upgrade.** Switching from CoinGecko (30-min, no volume) to Kraken (5-min, real volume) gave agents actual signals to work with.

---

## 10. What Failed

1. **V1 equal-weight ensemble.** Averaging one good agent with two bad ones destroyed the signal. Equal weighting is the worst possible approach when agent quality varies.

2. **news_momentum agent.** 44.4% accuracy — actively destructive. Macro reasoning doesn't work at 5-minute scale. Information moves faster than any reasoning chain at this granularity.

3. **pattern_reader agent.** 52.4% accuracy — marginal. Candle pattern recognition (doji, hammer, engulfing) doesn't reliably predict the next candle at 5-minute scale. Worse, it added noise that diluted the conviction signal.

4. **LLM default to 0.50.** The single most common agent error in the evolution log. When uncertain, Claude outputs 0.50 rather than using market_price as anchor. Required explicit, repeated prompt engineering to fix.

5. **CoinGecko as fallback.** Was providing 30-minute candles with zero volume, making the volume_wick agent useless on GitHub Actions. This went undetected for days.

6. **GitHub Actions cron reliability.** Scheduled for every 5 minutes, but actually fires every 20-60 minutes due to GitHub's throttling. Planned fix: Mac Mini daemon for always-on operation.

---

## 11. Open Questions for External Review

1. **Is 200 markets enough sample size?** Our backtest used 200 markets (March 1-15). The 78.3% MEDIUM accuracy is based on only 23 markets. Is this statistically significant, or could we be overfitting to a 2-week window?

2. **Conviction scoring independence assumption.** We treat the 5 layers as independent binary signals. But agent agreement and magnitude are clearly correlated (if agents agree, the average is further from 0.50). Should we use a different scoring model?

3. **Are we overfitting through evolution?** 17 prompt modifications in 3 days on the same market type. Are we tuning to the noise of March 2026 BTC, or finding generalizable patterns?

4. **Is contrarian just market reversion?** Contrarian's 59% edge could be explained by simple mean reversion at 5-minute scale (after 3+ consecutive candles, reversion is statistically favored). If so, a simple rule-based system might outperform the LLM agent.

5. **Cost-effectiveness.** We're paying ~$1.50/day in Claude API costs for ~$0 in real bets (simulation only). At what point does the signal justify the cost? And would a cheaper model (Haiku) lose meaningful accuracy?

6. **Macro bias paradox.** With NEUTRAL macro bias, conviction layer 4 never fires and max score is 3. This means we're leaving the HIGH tier ($200 bets) permanently unused. Is the safety of NEUTRAL worth the missed upside?

7. **Volume data quality.** Kraken's BTC/USD volume on 5-minute candles ranges from 0.1 to 50 BTC. Is this thin enough that volume spikes are noise rather than signal? Should we use BTC/USDT on a higher-volume pair?

8. **Two-agent fragility.** With only 2 agents, "agreement" means both agree. There's no minority/majority dynamic. If one agent is temporarily miscalibrated, the whole system suffers. Should we add a third agent (but a better one than pattern_reader)?

---

## 12. Appendix: Complete Backtest Data

### V1 Backtest Raw Numbers

```
Period: March 1-15, 2026
Markets: 200 (all resolved)
Predictions: 801 (3 agents × ~267 each)
Bet sizing: flat $100 per market

Agent Results (non-flat calls only):
  base_rate:       105/212 = 49.5%  (53 flat calls, 20%)
  contrarian:      112/191 = 58.6%  (76 flat calls, 28%)
  news_momentum:   108/243 = 44.4%  (26 flat calls, 10%)

Ensemble (simple average):
  Correct: 94, Wrong: 91, Flat: 15
  Accuracy: 50.8%
  P&L: -$76
  Wagered: $18,500
  ROI: -0.4%
```

### V2 Backtest Raw Numbers

```
Period: March 1-15, 2026
Markets: 200 (all resolved)
Predictions: 600 (3 agents × 200 each)

Agent Results (non-flat calls only):
  contrarian:      90/151 = 59.6%   (49 flat, 25%)
  volume_wick:     87/149 = 58.4%   (51 flat, 26%)
  pattern_reader:  76/145 = 52.4%   (55 flat, 28%)
```

### V2 Configuration Comparison (all on same 200 markets)

```
Config                    | Ens Acc | MED Acc | P&L     | Wagered | ROI
--------------------------|---------|---------|---------|---------|--------
3-agent, LOW=$25          | 55.2%   | 69.2%   | +$596   | $3,275  | +18.2%
3-agent, LOW=$0           | 55.2%   | 69.2%   | +$696   | $1,950  | +35.7%
2-agent, LOW=$0 (CHOSEN)  | 59.4%   | 78.3%   | +$921   | $1,725  | +53.4%
2-agent, LOW=$25          | 59.4%   | 78.3%   | +$647   | $3,175  | +20.4%
contrarian solo           | 59.6%   | n/a     | +$417   | $1,200  | +34.8%
```

### V2.1 Conviction Tier Detail (2-agent, LOW=$0 — deployed config)

```
Tier       | Markets | Called | Correct | Accuracy | Bet Size | P&L
-----------|---------|--------|---------|----------|----------|--------
MEDIUM (3) | 23      | 23     | 18      | 78.3%    | $75      | +$921
LOW (2)    | 61      | 58     | 24      | 41.4%    | $0       | $0
NO_BET(0-1)| 116     | 94     | 62      | 66.0%    | $0       | $0
TOTAL      | 200     | 175    | 104     | 59.4%    | —        | +$921
```

### Live Performance (V2.1, as of March 17 2026 evening)

```
Markets: 138 total, 119 resolved, 22 predicted by v2 agents
Predictions: 44 (2 agents × 22 markets)

Agent accuracy (21 resolved with v2 predictions):
  contrarian:   13/21 = 61.9%
  volume_wick:  12/21 = 57.1%
```

### Evolution Log Summary

```
Total evolutions: 17 (March 15-17, 2026)
  news_momentum: 8 evolutions (most problematic, later retired)
  base_rate:     5 evolutions (later retired)
  volume_wick:   4 evolutions
  contrarian:    0 evolutions (never worst agent)

First evolution: Cycle 6, March 15
Last evolution:  Cycle 46, March 17
Manual reversions: 0
```
