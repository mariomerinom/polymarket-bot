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
- 3-agent prediction system (base_rate, news_momentum, contrarian)
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

**First backtest results (200 markets, ~600 predictions):**
| Agent | Accuracy | Verdict |
|-------|----------|---------|
| contrarian | 54.6% | Only one beating coin flip |
| base_rate | 49.2% | Noise — no edge |
| news_momentum | 42.1% | Actively destructive |

---

## Part 3: Prediction Engine v2 (NEXT)

Rebuild the entire prediction stack: new agents focused on micro-TA, human macro bias layer, and conviction-based decision framework. These are one integrated system — agents, context, and conviction all ship together.

---

### 3.1 Strip & Refocus Agents

**Problem:** Agents reason about broad signals (time-of-day, macro catalysts, 1h trends) that don't predict 5-minute candle direction. Backtest proves only microstructure signals (exhaustion, wicks, body sizes) have edge.

**Strip:**
- Time-of-day and day-of-week effects
- "Macro catalysts" and "news momentum"
- 1-hour trend/regime classification
- Market-price anchoring rules (evolution-injected)

**Add — Micro-Technical Analysis** (last 2-3 candles only):

| Signal | What It Reads | Edge |
|--------|--------------|------|
| Candle Patterns | Doji, hammer, engulfing, inside bar | Reversal/continuation |
| Range Position | Price in top/bottom 20% of 12-candle range | Overbought/oversold |
| Volume | Spike vs fade, relative to 12-candle avg | Conviction/exhaustion |
| Wick Rejection | Wick > 2x body | Buyer/seller rejection |
| Compression | 3 shrinking ranges → breakout pending | Volatility expansion |

**New Agent Roster:**

| Agent | Replaces | Focus | Max Deviation |
|-------|----------|-------|---------------|
| Pattern Reader | base_rate | Candle patterns + range position + macro prior | 8pp from prior |
| Volume/Wick | news_momentum | Volume spikes + wick rejection signals | 8pp from prior |
| Contrarian v2 | contrarian | Exhaustion + compression (last 3-4 candles only) | 10pp from prior |

**Enhanced BTC Context** — pre-computed fields added to `btc_data.py`:
- `range_position` (0-1, where price sits in 12-candle range)
- `last_volume_ratio` (last candle volume / 12-candle average)
- `last_3_range_shrinking` (compression detection)
- `last_candle_pattern` (doji/hammer/engulfing/inside_bar/none)
- `last_wick_upper_ratio`, `last_wick_lower_ratio`

---

### 3.2 Macro Bias Layer — Human-in-the-Loop

**Problem:** BTC doesn't always have an UP bias. The 4-year cycle, key technical levels (200 EMA), and macro structure shift the base probability. This can't be computed from 12 candles — it requires human judgment.

**Layer 1: Human Macro Read** (`config/macro_bias.md`)

You edit this when your thesis changes — maybe once a week, or when structure shifts. 30 seconds.

```markdown
## Current Regime: CHOPPY
## Direction Bias: NEUTRAL
## Prior: 0.50

BTC attempting to reclaim 200 EMA as support. Expect failed breakouts
and mean reversion. No sustained trend until reclaim is confirmed.
Favor contrarian/fade signals over momentum.

Last updated: 2026-03-16
```

| Regime | Prior | When |
|--------|-------|------|
| BEARISH | 0.44-0.47 | Below 200 EMA, accelerating down, lower highs |
| CHOPPY | 0.48-0.52 | Testing key level, no conviction, whipsaws |
| EARLY_BULL | 0.53-0.55 | Reclaimed 200 EMA, holding as support, dips bought |
| BULL | 0.55-0.58 | Above all major MAs, higher highs/lows confirmed |

The narrative also tells agents *how* to interpret ambiguous signals:
- "Expect mean reversion" → contrarian leans harder
- "Favor UP candles" → pattern reader treats ambiguous as bullish
- "No sustained trend" → volume/wick agent ignores continuation

**Layer 2: Rolling Computed Bias** (automatic sanity check)

Computed from Binance before each cycle:
```
7-day UP%:  53.2%  (2,016 candles)
24-hour UP%: 48.1% (288 candles)
1-hour UP%:  58.3% (12 candles)
Blended:     0.2 × hourly + 0.3 × daily + 0.5 × weekly = 51.9%
```

- If layers agree (human BULL 0.55, data 54% UP) → strong conviction
- If they conflict (human BULL 0.55, data 46% UP) → tension, reduce confidence
- Human read = thesis; computed data = reality check

**Context Injection Order** (what agents see):
```
1. Macro bias (human thesis + computed check)
2. Pre-computed micro-TA signals
3. Raw candle table (last 12 five-minute candles)
4. Market question + price
```

---

### 3.3 Conviction Framework

Conviction is agreement across independent layers. A single agent at 55% is noise. All three agents aligned with macro thesis and computed bias — that's conviction.

**Step 1: ANALYZE — What Creates Conviction**

Conviction score (0-5) from five independent layers:

| Layer | +1 Point When |
|-------|---------------|
| **Agent Agreement** | All 3 agents point same direction (all >0.50 or all <0.50) |
| **Agent Magnitude** | Average deviation from prior exceeds ±4pp |
| **Agent Confidence** | 2+ agents report medium or high confidence |
| **Macro Alignment** | Micro signals agree with human macro bias direction |
| **Computed Bias** | Rolling 7d/24h UP% confirms the direction |

```
0-1: NO BET  — noise, skip entirely
  2: LOW     — micro signal only, no confirmation
  3: MEDIUM  — signal + one confirmation layer
4-5: HIGH    — multi-layer convergence, strong bet
```

**Step 2: PROVE — Backtest Conviction Tiers**

Before risking money, validate that tiers correlate with accuracy:

1. Run 500+ candle backtest with new agents + conviction scoring
2. Compute accuracy by tier:
```
Conviction 0-1: ~50% (noise, correctly skipped)
Conviction 2:   ~52-54% (weak edge)
Conviction 3:   ~55-58% (real edge)
Conviction 4-5: ~60%+ (strong edge, rare)
```
3. Tiers must be **monotonically increasing**. If not, the signals aren't independent or aren't real → rethink.

**Step 3: BET — Conviction-Scaled Position Sizing**

Only after Step 2 proves the tiers work:

```
Conviction 0-1: $0      — no bet
Conviction 2:   $25     — minimum, testing the signal
Conviction 3:   $75     — standard position
Conviction 4-5: $200    — max position, full conviction
```

**Kelly criterion as guardrail:** Compute optimal fraction per tier from backtest. If Kelly says don't bet a tier → don't bet it, regardless of conviction score.

---

### 3.4 Implementation Summary

| File | Action |
|------|--------|
| `prompts/pattern_reader.md` | NEW — replaces `base_rate.md` |
| `prompts/volume_wick.md` | NEW — replaces `news_momentum.md` |
| `prompts/contrarian.md` | UPDATE — tighter micro focus |
| `config/macro_bias.md` | NEW — human-edited macro context |
| `src/btc_data.py` | ADD micro-TA fields + `compute_rolling_bias()` |
| `src/predict.py` | MODIFY — load macro bias, new context order, weighted ensemble |
| `src/conviction.py` | NEW — conviction scoring from all layers |
| `src/dashboard.py` | MODIFY — conviction charts, accuracy by tier, P&L by tier |
| `src/backtest.py` | MODIFY — conviction tagging, tier-based reporting |
| DB schema | ADD `conviction_score INTEGER` to predictions table |

### 3.5 Dashboard v2

The dashboard must answer one question: **is conviction working?**

**Top Banner — System Status**
```
REGIME: CHOPPY (prior: 0.50) | Computed Bias: 51.2% UP | Last updated: 2h ago
Pipeline: 142/150 on-time (95%) | BTC: $84,302 (+0.12% 1h)
```
- Shows current macro regime + human prior
- Computed bias next to it (agree/conflict visible at a glance)
- Pipeline health + BTC price (carried over from v1)

**Conviction Scoreboard — The Proof**
```
Tier     | Predictions | Accuracy | P&L      | Avg Bet
---------|-------------|----------|----------|--------
0-1 SKIP |         312 |    49.7% |       $0 |     $0
2 LOW    |          98 |    53.1% |     +$82 |    $25
3 MEDIUM |          64 |    57.8% |    +$441 |    $75
4-5 HIGH |          26 |    65.4% |    +$892 |   $200
```
- This is the single most important table. If tiers aren't monotonically increasing → system is broken.
- Color-coded: green if tier accuracy > tier below, red if not.

**Conviction Distribution Chart** (SVG bar chart)
- X axis: conviction tiers 0-5
- Y axis: count of predictions
- Shows what % of candles we skip vs act on
- Healthy: 50-60% skipped (0-1), 10-20% HIGH (4-5)

**P&L by Conviction Tier** (SVG stacked area or grouped bars)
- Where does the money come from?
- Should show HIGH tier generating most profit despite fewer bets
- Total portfolio P&L still shown as consolidated banner

**Per-Agent Performance Cards**
- Pattern Reader / Volume-Wick / Contrarian v2
- Accuracy, win/loss, current streak
- Rolling last-20 accuracy sparkline
- Agent vs coin flip comparison bar

**Last Result + Current Prediction** (live context)
```
LAST: 03-16 15:25 → UP ▲  |  Conviction: 3 (MEDIUM)
  pattern_reader: 54% ✓  |  volume_wick: 52% ✓  |  contrarian: 48% ✗

NOW:  03-16 15:30 → Conviction: 4 (HIGH) — betting $200 UP
  pattern_reader: 56%  |  volume_wick: 55%  |  contrarian: 54%
  Macro: CHOPPY (0.50)  |  Computed: 52.1% UP  |  All layers agree ✓
```
- Clear hit/miss on last result per agent
- Current prediction shows conviction breakdown — why we're betting or skipping

**Backtest Comparison** (if backtest DB exists)
- Side-by-side: v1 agents vs v2 agents on same date range
- Accuracy, P&L, ROI for each
- Proves the upgrade worked

**Evolution History** (kept from v1)
- Log of prompt modifications
- Filtered to v2 agents only after transition

### 3.6 Verification

1. Backtest new agents on March 1-15 data (fresh DB, 200 candles) → compare vs old agents
2. Target: >55% on contrarian_v2, >52% on pattern_reader and volume_wick
3. Conviction tiers monotonically increasing in accuracy
4. HIGH conviction fires 10-20% of the time
5. Kelly positive for conviction 3+ tiers
6. Conviction-sized P&L beats flat betting by >20%

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
