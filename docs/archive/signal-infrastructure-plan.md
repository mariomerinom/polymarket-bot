# Signal Infrastructure Plan — No Constraints

Last updated: 2026-03-29

---

## Why This Document Exists

Two questions came up during the 30-day backtest review:

1. **Why are we using only Kraken for BTC candle data?** No good reason — it was just the first exchange that worked. We could get a stronger signal from multiple sources.
2. **The NEUTRAL regime is a problem.** It accounts for most of our bets and drags overall WR down. We need to decide what to do about it.

This document explores both questions with no budget or complexity constraints. It's a menu of options to evaluate, not a commitment.

---

## Part 1: Multi-Source Signal Architecture

### Current State

```
Kraken API (free) → 20 candles × 5min → streak + exhaustion + regime → Polymarket bet
```

One exchange. One data type (OHLCV candles). One timeframe per pipeline.

### What We're Missing

| Data Source | What It Tells Us | Why It Matters |
|-------------|-----------------|----------------|
| **Multiple exchange candles** (Coinbase, OKX, Bybit) | Cross-exchange price consensus | A streak on 3 exchanges is stronger than 1. Reduces false signals from single-exchange noise |
| **Aggregated volume** | True market-wide participation | Our volume spike exhaustion signal currently sees only Kraken's ~15% of global volume |
| **Order book depth** | Where liquidity sits | Thin book above price = easy breakout. Thick book = likely rejection. Tells us if the streak has room to continue |
| **Funding rates** (perpetual futures) | Leveraged trader positioning | Extreme positive funding = overleveraged longs = correction risk. Negative = shorts getting squeezed |
| **Open interest** | How many contracts are outstanding | Rising OI + price move = conviction. Falling OI + price move = position closing, not new money |
| **Liquidation data** | Forced closes happening now | Cascade liquidations cause momentum extensions — exactly what our signal rides |
| **Mempool / on-chain flow** | Large BTC movements to/from exchanges | Big exchange inflows often precede sell pressure. Could pre-filter DOWN signals |

### Proposed Architecture

```
┌─────────────────────────────────────────────────────┐
│                   DATA LAYER                         │
├──────────────┬──────────────┬───────────────────────┤
│ Kraken       │ Coinbase     │ OKX / Bybit           │
│ OHLCV + Vol  │ OHLCV + Vol  │ OHLCV + Vol + OI + FR │
└──────┬───────┴──────┬───────┴───────────┬───────────┘
       │              │                   │
       ▼              ▼                   ▼
┌─────────────────────────────────────────────────────┐
│               AGGREGATION LAYER                      │
│                                                      │
│  • Volume-weighted average candles                   │
│  • Cross-exchange streak consensus (2/3 agree?)      │
│  • Combined volume for exhaustion detection          │
│  • Funding rate signal (extreme = caution)           │
│  • Open interest delta (rising/falling)              │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│               SIGNAL LAYER (enhanced V4)             │
│                                                      │
│  Existing:                                           │
│  • Streak detection (now from aggregated candles)    │
│  • Exhaustion (now from aggregated volume)           │
│  • Regime (autocorrelation, volatility)              │
│                                                      │
│  New:                                                │
│  • Cross-exchange consensus score (0-3)              │
│  • Leverage pressure score (funding + OI)            │
│  • Liquidation momentum boost                        │
│                                                      │
│  Conviction = f(streak, exhaustion, consensus,       │
│                  leverage, regime)                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│               EXECUTION LAYER                        │
│                                                      │
│  Polymarket bet (unchanged)                          │
│  But now with richer conviction tiers:               │
│  • Conv 5: consensus + trending + leverage aligned   │
│  • Conv 4: consensus + trending                      │
│  • Conv 3: single-source signal (current behavior)   │
└─────────────────────────────────────────────────────┘
```

### Data Source Options

| Source | Cost | Latency | Data Available |
|--------|------|---------|---------------|
| **Kraken** (current) | Free | ~1s | OHLCV |
| **Coinbase Advanced** | Free | ~1s | OHLCV |
| **OKX** | Free | ~500ms | OHLCV + funding + OI |
| **Bybit** | Free | ~500ms | OHLCV + funding + OI + liquidations |
| **CoinGlass** | $50/mo | ~2s | Aggregated OI + funding + liquidations across all exchanges |
| **Coinalyze** | $30/mo | ~2s | Similar to CoinGlass |
| **Glassnode** | $30/mo | ~30s | On-chain flows, exchange balances |

**Recommendation:** Start with Coinbase (free, easy API, adds consensus). Then OKX for funding/OI. CoinGlass if we want aggregated derivatives data without managing multiple exchange APIs.

### Latency: Does It Matter?

**No, and that's our advantage.**

Our signal takes 15+ minutes to form (3-candle streak × 5 min). We're not competing with HFT firms on speed — we're competing on *pattern recognition across time*. The market makers pricing Polymarket markets are fast but they're pricing the **current state**, not a multi-candle momentum pattern.

Where latency DOES matter:
- **Execution speed once we have a signal** — buying on Polymarket before the price moves. Currently ~2-3 seconds on CI. Acceptable for 5-min markets.
- **Data freshness** — if we use 4 sources and one is 10 seconds stale, the aggregation could be noisy. Keep all sources under 2 seconds.

Where latency DOESN'T matter:
- **Signal generation** — a 3-candle 5-min streak is a 15-minute phenomenon. Milliseconds are irrelevant.
- **Regime detection** — computed over 20 candles (100 minutes). Updating every 5 minutes is plenty.

---

## Part 2: The NEUTRAL Regime Problem

### The Data

**Backtest (30 days, native Polymarket, 140 bets):**

| Regime | Bets | WR | P&L |
|--------|------|----|-----|
| TRENDING | 55 | 63.6% | +$2,250 |
| NEUTRAL | 85 | 45.9% | -$1,150 |

**Live (215 bets, Kraken candles):**

| Regime + Direction | Bets | WR |
|-------------------|------|----|
| UP / MED_VOL / NEUTRAL | 58 | 84.5% |
| DOWN / HIGH_VOL / NEUTRAL | 36 | 66.7% |
| DOWN / MED_VOL / NEUTRAL | 25 | 52.0% |
| UP / HIGH_VOL / NEUTRAL | 21 | 57.1% |
| UP / MED_VOL / TRENDING | 17 | 64.7% |
| DOWN / MED_VOL / TRENDING | 16 | 75.0% |
| DOWN / HIGH_VOL / TRENDING | 14 | 57.1% |
| UP / HIGH_VOL / TRENDING | 24 | 58.3% |

### The Contradiction

The backtest says NEUTRAL is terrible (45.9% WR). The live data says... it depends:

- **UP / MED_VOL / NEUTRAL: 84.5% WR on 58 bets** — this is our single best regime live
- **DOWN / MED_VOL / NEUTRAL: 52.0% WR on 25 bets** — this is the problem child

The difference? **The live bot uses Kraken candles (granular price data). The backtest uses binary Polymarket outcomes (UP/DOWN).** The Kraken candles carry more signal — they capture *how* BTC moved (range, volume, candle body), not just *which direction won*.

### What This Means

1. **The live regime labels and backtest regime labels mean different things.** Live regime is computed from BTC candle returns. Backtest regime is computed from binary outcome sequences. A "NEUTRAL" regime from candles (low autocorrelation of actual returns) is more informative than "NEUTRAL" from a coin-flip-like outcome sequence.

2. **The backtest underestimates our signal** because it uses weaker data. The 53% backtest WR vs 67% live WR gap is mostly explained by data quality, not luck.

3. **The DOWN + NEUTRAL combination is the real problem**, not NEUTRAL itself. Our live `direction_regime_filter` already targets this:
   - DOWN + MED_VOL/NEUTRAL: 52% WR (no edge) — correctly filtered
   - UP + MED_VOL/NEUTRAL: 84.5% WR (huge edge) — correctly kept

### Decisions

| # | Question | Data Available | Current Answer |
|---|----------|---------------|----------------|
| 1 | Should we filter ALL neutral regime bets? | Backtest says yes (45.9%). Live says no (many NEUTRAL combos are profitable). | **No.** Filter DOWN+NEUTRAL only. The Kraken candle signal finds edge in NEUTRAL that the binary outcome sequence cannot. |
| 2 | Should we increase conviction for TRENDING? | TRENDING: 63.6% backtest, 64.7-75% live. | **Yes.** TRENDING + momentum signal = highest conviction. Consider conv=5 tier for TRENDING + consensus (when multi-source is available). |
| 3 | Should we add a NEUTRAL penalty to sizing? | UP+NEUTRAL is fine. DOWN+NEUTRAL is not. | **Already done** via `direction_regime_filter`. Monitor at 50 bets. |
| 4 | Would multi-source data improve NEUTRAL regime detection? | Unknown. | **Likely yes.** Cross-exchange consensus could distinguish "genuinely directionless" from "directional on some exchanges but not others." This is the strongest argument for multi-source data. |

---

## Implementation Priority (if no constraints)

| Phase | What | Cost | Expected Impact |
|-------|------|------|-----------------|
| **1** | Add Coinbase as second candle source | $0, ~1 day | Cross-exchange streak consensus. Reduces false signals in NEUTRAL. |
| **2** | Add OKX for funding rate + open interest | $0, ~2 days | Leverage pressure signal. Filters overleveraged momentum traps. |
| **3** | Create conviction tier 5 (consensus + trending + leverage aligned) | $0, ~1 day | Higher sizing on highest-conviction bets. |
| **4** | CoinGlass for aggregated derivatives data | $50/mo, ~1 day | Liquidation cascade detection. Momentum boost signal. |
| **5** | Glassnode for on-chain flow | $30/mo, ~2 days | Pre-filter large exchange inflows before DOWN signals. |
| **6** | Full aggregation layer with weighted candles | $0, ~3 days | Replace single-source candles with volume-weighted multi-source. |

**Phase 1 alone** (Coinbase consensus) could meaningfully improve the NEUTRAL regime problem at zero cost.

---

## Validation Plan

Every phase follows our standard validation principles:

1. Paper trade first (200+ predictions before real money)
2. Register as optimization with baseline snapshot
3. 50-bet minimum before declaring victory
4. Track counterfactual (what would single-source have done?)
5. One change at a time

The multi-source architecture is an **infrastructure change**, not a signal change. The signal logic (streak + exhaustion + regime) stays the same. We're improving the *input quality*, not the *decision logic*.
