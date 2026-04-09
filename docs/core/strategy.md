# Trading Strategy — V4 Momentum System

Last updated: 2026-04-09

---

## Core Principle

**Ride streaks, don't fade them.** When BTC or ETH moves in one direction for 3+ candles, the next candle is more likely to continue than reverse. V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). V4 rides them and validates at 67%+ WR.

---

## BTC 5-Minute Pipeline (Paper — reverted from live 2026-04-09)

### Signal Logic
1. Fetch 20 most recent 5-minute BTC candles
2. Compute **regime** from candle data:
   - Volatility (stdev of returns): LOW / MEDIUM / HIGH
   - Autocorrelation (lag-1): TRENDING (>0.15) / NEUTRAL / MEAN_REVERTING (<-0.15)
3. If **mean-reverting** → skip (no edge; market already prices reversion correctly)
4. Count consecutive same-direction candles from most recent backward = **streak**
5. If streak >= 3 → **RIDE the streak**

No exhaustion gate. Removed 2026-03-31 after analysis showed exhaustion signals (compression, volume spike, shrinking range) were filtering out the best predictions (85% WR filtered vs 67% WR kept). These are contrarian indicators — they confirm a trend is ending, which is the opposite of what a momentum strategy needs.

### Conviction & Sizing
| Condition | Conviction | Action |
|-----------|-----------|--------|
| UP in price sweet spot (0.20-0.70) | 4 | $25 flat bet |
| Qualifying signal + consensus boost | 4-5 | $25 flat bet (capped at 5) |
| Qualifying signal (standard) | 3 | $25 flat bet |
| HIGH_VOL non-trending regime | 2 | $0 (tracked only) |
| DOWN + NEUTRAL regime (non-HIGH_VOL) | 2 | $0 (tracked only) |
| No signal / low confidence | 0 | $0 |

### Active Filters (5m only)
- **HIGH_VOL non-trending gate** (2026-04-09): Skip HIGH_VOL/NEUTRAL and HIGH_VOL/MEAN_REVERTING. 54.8% WR on 126 bets — below breakeven after fees. Does NOT apply to 15m (64.3% WR there). Issue #71.
- **DOWN + NEUTRAL filter**: DOWN bets in NEUTRAL regime (non-HIGH_VOL) demoted to conv=2 (52% WR = no edge)
- **Price gate**: Skip if market price > 0.85 or < 0.15 (breakeven WR exceeds signal capacity)
- **Dead hour gate**: Skip UTC hours 3 and 21 (41.7% and 37.5% WR respectively)
- **Consensus boost**: When cross-exchange consensus score = 2 (both sources agree), conviction +1 (capped at 5). Stored in reasoning JSON.

### Removed Filters
- **Exhaustion gate**: Removed 2026-03-31. Was filtering 85% WR predictions. See `docs/analysis/analysis_exhaustion_gate.md`.
- **Cooldown flip gate**: Removed 2026-03-31. Was blocking 73% WR predictions. Regime gate handles chop.
- **Daily regime gate** (#68): Added and reverted 2026-04-09. Range z-score gate did not target the right dimension.

### Performance
- Paper: 484 bets at 63.4% WR
- Live: Was live 2026-03-31 to 2026-04-09 ($25 flat). Reverted to paper — adverse selection (winners expire, losers fill). Signal quality is strong; execution is the blocker.

---

## BTC 15-Minute Pipeline (Paper)

### Signal Logic — 5m as Atomic Unit
The 15m pipeline does **not** use 15m candles. It uses the same 5m candles as the BTC 5m pipeline — same `min_streak=3`, same `autocorr_threshold=-0.15`, same regime classification. The 5m candle is the atomic signal unit across both pipelines.

**Why:** A streak visible in 5m candles (3+ candles = 15 min of momentum) may not register in coarser 15m candles until the move is nearly over. 15m candles aggregate 3× the data, masking micro-trends. Using 5m candles gives the 15m pipeline the same resolution advantage as production.

### 5m Confirmation Boost
When the 5m pipeline has 2+ recent predictions in the same direction as the 15m signal, conviction gets a +1 boost (capped at 5). This is a cross-pipeline confirmation — if two independent pipelines agree, confidence is higher. Tracked in reasoning JSON as `sibling_5m_boost`.

### Loose Mode
The 15m pipeline runs in `loose_mode`:
- No dead hour gate (derived from 5m data, unvalidated on 15m)
- HIGH_VOL non-trending gate does NOT apply (64.3% WR on 56 bets — different dynamics)
- DOWN+NEUTRAL demotion applied **post-hoc** in `ci_run_15m.py` (not inline in predict.py)

### Active Filters (15m only)
- **Price gate**: Same as 5m (skip > 0.85 or < 0.15)
- **Mean-reversion regime gate**: Same threshold as 5m (-0.15, since we use 5m candles)
- **DOWN+NEUTRAL demotion**: Post-prediction demotion to conv=2 (symmetric with 5m). HIGH_VOL/NEUTRAL+DOWN allowed through (64% WR on 50 bets on 5m).

---

## ETH 5-Minute Pipeline (Paper)

### Signal Logic
Same momentum signal as BTC: streak >= 3 in non-mean-reverting regime → ride the streak.

### History
- Phase 2 pattern mining validated contrarian at 54.4% WR on 1,601 historical markets
- Live contrarian signal hit **33.3% WR on 54 resolved predictions** — catastrophic
- Momentum counterfactual on same 54 bets: **66.7%** (exact complement)
- Flipped to momentum 2026-04-01. Same V3→V4 pattern as BTC.

### Current State (Phase 1 complete, Phase 2 conditional GO)
- 267 resolved bets at 57.7% WR — clears 55% threshold and 200-bet minimum
- Conviction filter works well: conv=3 at 57.7% vs conv=2 counterfactual at 46.6% (11pp gap)
- Deteriorating trend: first 4 days 69.6% WR, last 4 days 48.5% — regime shift
- Phase 2 priority: volatility regime recalibration (BTC thresholds misclassify ETH)

### Conviction Scoring
| Condition | Conviction | Action |
|-----------|-----------|--------|
| HIGH_VOL non-trending | 2 | $0 (tracked — 40.7% WR on 27 bets) |
| Medium confidence (streak 3-4) | 3 | $25 paper bet |
| High confidence (streak 5+) | 2 | $0 (20% WR on 5 bets — long streaks reverse on ETH) |

### Active Filters
- **HIGH_VOL non-trending gate** (2026-04-09): Same as BTC 5m. 40.7% WR on 27 bets. Issue #71.
- **Price gate**: Skip > 0.85 or < 0.15
- **Mean-reversion regime gate**: Same as BTC (uses BTC thresholds — recalibration planned for Phase 2)
- **Dead hours**: Auto-calibrated from ETH data: [3, 16, 21]

---

## Bybit BTC Perpetual Pipeline (Paper)

### Signal Logic
Same momentum signal as BTC 5m (`momentum_signal()` from `predict.py`), applied to Bybit BTCUSDT perpetual futures. Paper trading only (conviction=2 minimum to log).

### Architecture
- Entry point: `src/ci_run_bybit.py` → `data/predictions_bybit.db`
- Trade execution: `src/bybit_trade.py` — limit orders, maker fees (0.02%)
- Position management: max 1 concurrent position, time_ceiling + stop_loss exits
- Scoring: `src/bybit_score.py` — candle-based resolution (mock resolver removed 2026-04-09)

### Rehabilitation (2026-04-09) — Issue #70
Pipeline was at 50.5% WR on 319 bets. Root cause analysis found:
- No conviction filtering (all signals fired equally)
- No dead hours gate
- Concurrent position stacking
- streak_break exit at 9% WR (1/11 — anti-predictive)
- Mock resolution contaminating 7% of WR data
- Fee rate using taker (0.055%) instead of maker (0.02%)

**Fixes applied:**
- DOWN+NEUTRAL demotion (ported from BTC 5m predict.py:400)
- HIGH_VOL non-trending gate (skip entirely)
- Dead hours: {1, 3, 8, 12, 16, 17, 20, 22} UTC (calibrated from 319 bets)
- Max 1 concurrent position
- streak_break exit removed (positions close on time_ceiling or stop_loss only)
- Mock resolution removed (candle-based resolution only)
- Fee rate corrected to maker (0.02%)

### Conviction Scoring
| Condition | Conviction | Action |
|-----------|-----------|--------|
| Qualifying + streak >= 5 | 4 | Paper bet |
| Qualifying signal | 3 | Paper bet |
| DOWN + NEUTRAL (non-HIGH_VOL) | 2 | Tracked only |
| HIGH_VOL non-trending | skip | Not stored |
| No signal | 0 | Skip |

---

## Kalshi BTC Pipeline (Paper — Phase 0)

Same momentum signal as BTC production, running against Kalshi BTC strike-price markets. Uses Kraken/Coinbase candles for price data.

- **Signal**: `momentum_signal(candles, min_streak=2)`
- **Regime gate**: `autocorr_threshold=-0.20` — skip mean-reverting regimes
- **Resolution**: Strike-price markets resolved using real BTC candle data. Market ID encodes strike (e.g. `BTCUSD-2604021350-84000` → $84,000). Hash-based mock resolver removed 2026-04-09.
- **Entry point**: `src/ci_run_kalshi.py` → `data/predictions_kalshi.db`
- **Phase 0 gate**: 200+ resolved predictions. WR > 55% → Phase 0.5. WR < 50% → signal is venue-specific.

See [docs/plans/KALSHI_INTEGRATION_PLAN.md](../plans/KALSHI_INTEGRATION_PLAN.md) for cross-market arbitrage strategy (Phase 1+).

---

## Shadow Conviction Scorer (All Pipelines)

Runs alongside all 4 pipelines. Computes a continuous strength signal (0.0–1.0) from two components:

- **Length**: `min(log(streak) / log(baseline), 1.0)` — longer streaks score higher, log curve prevents over-weighting
- **Magnitude**: `min(|net_return| / (realized_vol × multiplier), 1.0)` — bigger moves relative to volatility score higher

`strength = length × magnitude` → mapped to estimate (0.50 ± max_edge × strength) → conviction tier (2/3/4/5).

Always on, zero production impact. Shadow scores stored in reasoning JSON as `shadow_generic_scorer`. Daily report surfaces tier-by-tier WR comparison and divergence analysis (when shadow ≠ production, who was right?).

---

## What We Don't Do

- **No contrarian/fading.** V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). The signal direction is MOMENTUM for all assets. This is non-negotiable.
- **No mean-reversion trading.** 334 observations show the market already prices mean-reversion correctly. No independent signal found.
- **No HIGH_VOL non-trending trading.** 54.8% WR on 126 BTC bets, 40.7% on 27 ETH bets. Momentum streaks in choppy high-vol markets are noise that reverses. The longer the streak, the worse it performs (streak 4+ went 20.8% on Apr 7-8).
- **No LLM agents.** V1/V2 used GPT-4 for predictions at $15-50/day. V4 is pure computation from candle data. Cost: $0/day.
- **No agent bias.** The bot has no built-in directional bias. All bias comes from human macro config, not prompts or code.
- **No betting at extreme prices.** At price 0.95, you need 95% WR to break even. Our signal can't deliver that.

---

## Validation Rules

Every optimization follows these principles (enforced by `src/optimization_tracker.py`):

1. **Baseline before shipping.** Snapshot WR, P&L, bet count at registration time.
2. **Revert criteria before shipping.** Define failure while still objective.
3. **50-bet minimum.** Anything less is noise.
4. **Forward validation only.** The data that found the edge can't confirm it.
5. **Track the counterfactual.** Filtered predictions stored at conv=2 for comparison.
6. **One change at a time.** Can't attribute results to stacked changes.

---

## Decision Tracker

All decisions tracked via GitHub Issues with `decision` label on the [BOTSY Kanban](https://github.com/users/mariomerinom/projects/1). The daily report checks trigger conditions and alerts when action is needed.
