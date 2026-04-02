# Analysis: The Exhaustion Gate Is Backwards

**Date:** 2026-03-31
**Trigger:** Bot pass rate dropped from 16% to 4% over one week while BTC showed clear directional moves. Investigation revealed the exhaustion gate is filtering out the highest-quality momentum signals.

---

## The Headline Number

| Group | Sample | WR |
|-------|--------|-----|
| **Passed exhaustion** (our actual bets) | 245 | **66.9%** |
| **Failed exhaustion** (filtered out) | 100 | **85.0%** |
| **Delta** | — | **-18.1pp** |

The predictions we're *throwing away* outperform the ones we're *keeping* by 18 points. This holds across every single day since the gate was introduced:

| Day | Bet WR | Filtered WR | Delta |
|-----|--------|-------------|-------|
| Mar 23 | 60% | 70% | -10pp |
| Mar 24 | 65% | 100% | -35pp |
| Mar 25 | 79% | 92% | -13pp |
| Mar 26 | 58% | 91% | -33pp |
| Mar 27 | 65% | 80% | -15pp |
| Mar 28 | 77% | 80% | -3pp |
| Mar 29 | 69% | 100% | -31pp |
| Mar 30 | 73% | 80% | -7pp |
| Mar 31 | 58% | 91% | -33pp |

No day where exhaustion-passed bets beat the filtered ones. Not one.

---

## What the Exhaustion Gate Does

When a streak of 3+ candles forms, the gate requires at least one of three "exhaustion" signals before betting:

1. **Compression** — last 3 candle ranges strictly shrinking (range[0] > range[1] > range[2])
2. **Volume spike** — last candle volume > 1.8x average
3. **Shrinking range** — last candle range < 70% of average range

The intent was: "confirm the streak is real before betting on it." The theory was that exhaustion signals indicate the market has been through a move and is consolidating before the next leg.

---

## Why It's Backwards

The theory conflates two different things:

**Exhaustion in trend-following** means the move is *ending*. Compression, shrinking ranges, and volume spikes are all signs that the trend is running out of steam. These are signals that a contrarian strategy would use — "the move is exhausted, bet on reversal."

**For momentum**, the opposite is what you want. A streak of 3+ candles with NO exhaustion means the move still has energy. No compression = steady follow-through. No volume spike = orderly flow, not a blow-off top. No shrinking range = each candle is still making a full-sized move in the streak direction.

**The exhaustion gate is a contrarian filter bolted onto a momentum strategy.** It selects for tired, dying trends and rejects healthy, continuing ones.

---

## What Changed (Why This Is Visible Now)

The pass rate collapsed from 16% (Mar 25) to 4% (Mar 30-31). Two things converged:

### 1. BTC Volatility Regime Shifted

| Period | Avg Volatility | HIGH_VOL % | Avg Range Ratio |
|--------|---------------|------------|-----------------|
| Mar 23-26 | 0.12-0.20 | 38-70% | 0.63-0.89 |
| Mar 28-31 | 0.07-0.17 | 9-67% | 0.54-0.72 |

Range ratios dropped from ~0.87 to ~0.54. This means candle sizes became more uniform — the last candle in a streak is increasingly similar in size to the average. When range_ratio hovers around 0.6-0.7, it sits right at the 0.7 threshold. Small fluctuations determine whether shrinking_range fires or not.

### 2. Shrinking Range Was Always the Primary Gate-Opener

Which sub-signal let bets through:

| Day | Bets | Shrinking only | Compression only | Volume only | Multiple |
|-----|------|---------------|-----------------|-------------|----------|
| Mar 25 | 43 | **25** (58%) | 2 | 5 | 11 |
| Mar 26 | 38 | **13** (34%) | 3 | 5 | 17 |
| Mar 28 | 26 | **15** (58%) | 0 | 2 | 9 |
| Mar 30 | 11 | **4** (36%) | 0 | 2 | 5 |
| Mar 31 | 12 | **7** (58%) | 0 | 1 | 4 |

`shrinking_range` alone accounts for 36-58% of all bets. Compression and volume_spike rarely fire solo (0-8 per day). As the range ratio dropped, fewer predictions crossed the 0.7 threshold → fewer bets → collapsing pass rate.

### The Timing

This isn't an overnight change. It's a regime shift that's been building for a week:

```
Exhaustion pass rate:
  Mar 25: 77%  ← healthy
  Mar 26: 78%
  Mar 27: 76%
  Mar 28: 72%  ← declining
  Mar 29: 70%
  Mar 30: 63%  ← accelerating
  Mar 31: 54%  ← half our streaks blocked
```

The gate worked fine when BTC was in a wide-range volatile regime (big candles with clear exhaustion patterns). As BTC moved to tighter, more uniform candle sizes, the shrinking_range threshold became harder to hit — not because the market stopped trending, but because candle sizes converged.

---

## The Core Problem

The exhaustion gate was never validated. It was added as a "seems reasonable" filter — the idea that you shouldn't bet on a streak without some kind of confirmation. But:

1. **It was never backtested against the alternative.** We never asked "do streaks without exhaustion lose more?" The data says they don't — they win *more*.

2. **The theoretical basis is wrong for momentum.** Exhaustion confirms a move is ending. Momentum needs a move that's continuing. These are opposite requirements.

3. **The primary sub-signal (shrinking_range) is regime-dependent.** It works in high-volatility environments where candle sizes vary widely, and breaks in uniform-volatility environments. This makes the gate a hidden regime dependency that we never intended.

4. **Sample size is sufficient.** 100 counterfactual observations across 9 days, no day below 70%, overall 85% WR. This isn't noise.

---

## Decision

**Remove the exhaustion gate.** A streak of 3+ candles in a non-mean-reverting regime is sufficient. The regime gate already handles the contrarian case (autocorrelation < -0.15 → skip).

**Revert criteria:** If WR drops below 60% at 100+ bets post-change, restore the gate. Baseline is 66.9% with the gate.

**Expected impact:**
- Volume: ~40-60% more bets per day (recovering the filtered predictions)
- WR: should increase (adding 85% WR predictions to a 67% pool)
- Revenue: more bets × higher WR = significantly more profit

**Tracking:** Daily report filter breakdown section will show whether no_exhaustion skips reappear (they shouldn't — the gate will be gone). Track overall WR and volume daily for first 50 bets.

---

## What This Means for Live Trading

We went live today with $500 and placed 0 real orders. The exhaustion gate blocked 11 qualifying streaks, 10 of which would have won. At $25/bet, that's ~$250 wagered, ~$100 profit left on the table.

The py-clob-client fix is deployed. Removing the exhaustion gate means the next trending session should generate 50-100% more bets. Combined with the cooldown_flip removal (already shipped), the bot will capture significantly more of the directional moves that your 15m chart showed today.
