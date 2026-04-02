# Postmortem: Exhaustion Gate Removal

**Date:** 2026-03-31
**Author:** Claude (with user direction)
**Severity:** Performance degradation — not an outage, but a silent drain on signal quality and bet volume
**Status:** Resolved — exhaustion gate and cooldown flip gate removed from `src/predict.py`

---

## Timeline

- **Mar 23:** V4 momentum pipeline goes live (paper). Exhaustion gate included from day one.
- **Mar 23-26:** Bot averages 37 bets/day, 16% pass rate, 65% WR. Performance looks strong. No reason to question filters.
- **Mar 27-28:** Bets/day drops to 28. Pass rate falls to 11%. Attributed to "choppy market" — Incident 5 (whipsaw chop) happens on Mar 27, leading to the cooldown_flip gate being added.
- **Mar 29-31:** Bets/day collapses to 13. Pass rate hits 4-5%. Bot goes live with real money on Mar 31. First live trade attempt fails (missing `py-clob-client`). Second qualifying signal doesn't come — 6+ hours of silence while BTC trends clearly on the 15m chart.
- **Mar 31 evening:** User flags the silence. Investigation reveals exhaustion gate is filtering the best predictions.

## What Was the Exhaustion Gate?

The momentum signal required two things to fire:

1. **Streak >= 3** consecutive candles in the same direction
2. **At least one exhaustion signal** — compression (shrinking candle ranges), volume spike (1.8x avg), or shrinking range (last candle < 70% of avg range)

The gate was included from day one as a "confirmation" filter — the idea being that a streak alone isn't enough, you need some structural sign that the move is "ready" before betting on continuation.

## Why Was It Removed?

### The data was unambiguous

Over 9 days and 345 predictions with streak >= 3:

| Group | Bets | WR | Description |
|-------|------|----|-------------|
| **Passed exhaustion** | 245 | **66.9%** | What we actually bet on |
| **Failed exhaustion** | 100 | **85.0%** | What we filtered out |

The predictions we threw away were 18 percentage points better than the ones we kept. Every single day, the filtered group outperformed:

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

Nine days. No day where exhaustion helped. n=100 on the counterfactual, n=245 on the actual. This isn't noise.

### The theoretical basis was wrong

Exhaustion signals — compression, volume spikes, shrinking ranges — are signs that a move is **ending**. These are textbook reversal indicators. They make sense in a contrarian strategy ("the move is exhausted, fade it").

Our strategy is **momentum** ("the move is happening, ride it"). A streak with NO exhaustion means the trend still has energy: no compression, no blow-off top, no shrinking participation. The exhaustion gate was selecting for *dying trends* and rejecting *healthy ones*.

This is the V3 contrarian mindset leaking into V4 momentum. V3 faded streaks and lost at 37% WR. We inverted to momentum and won at 63%+. But we kept the contrarian confirmation filter. The gate was a relic of the old approach that happened to look reasonable on paper.

### The cooldown flip gate was the same problem

Also removed in this session. Cooldown suppressed direction reversals at streak=3 to prevent "whipsaw chop" (Incident 5). On Mar 31, it blocked 3 bets — all winners. Over all time, it blocked 22 bets at 73% counterfactual WR. The regime gate (mean-reverting skip) already handles chop. Cooldown was redundant drag.

## Why Did We See Great Results Even With the Gate?

This is the key question. If the gate was wrong, why was paper trading profitable?

**Because the 245 bets that DID pass were still good.** The gate wasn't letting through bad bets — it was a filter that randomly passed some good bets and blocked others that were even better. The momentum signal (streak >= 3 + non-mean-reverting regime) is the real edge. The exhaustion gate was a noisy additional filter that:

- **Passed ~70% of qualifying signals** on average (not 50/50)
- **Correlated weakly with actual quality** — the bets it kept hit 66.9%, which is profitable
- **Correlated negatively with the best signals** — the bets it rejected hit 85%

The paper P&L was +$8,141 on $28,750 wagered (28.3% ROI) with tiered sizing. This masked the problem because:

1. The WR was 66.9% — well above breakeven (~50%)
2. The volume was still decent in the first week (37 bets/day)
3. Nobody was tracking the counterfactual (what we would have made WITHOUT the gate)

At $25 flat sizing, the missed 100 bets would have added **+$1,144** in profit. The gate silently cost us money every day, but the base signal was strong enough to be profitable anyway.

## Why Was This Not Spotted in Paper Trading?

Four reasons:

### 1. No counterfactual tracking

The system logged what it bet on but not what it filtered. There was no "what would have happened if we'd bet this?" tracking for exhaustion-filtered predictions. The daily report showed WR, P&L, regimes, and directions — but never showed "here are the 10 bets we skipped today and 8 of them would have won."

**Fix shipped:** Daily report now includes a "Filter Breakdown" section showing each filter's skip count and counterfactual WR.

### 2. Volume decline was gradual

The pass rate collapsed slowly:

| Period | Pass Rate | Bets/Day |
|--------|-----------|----------|
| Mar 23-24 | 13% | 34 |
| Mar 25-26 | 15% | 41 |
| Mar 27-28 | 11% | 29 |
| Mar 29-30 | 5% | 14 |
| Mar 31 | 5% | 12 |

Each day's drop was small enough to attribute to "market conditions." It wasn't until 6 straight hours of silence during a clearly trending market that the user flagged it.

### 3. The shrinking_range threshold was regime-dependent

49% of all bets passed the exhaustion gate through `shrinking_range` alone (last candle range < 70% of average). This sub-signal depends on candle size uniformity:

- **Wide-range days** (high volatility, varied candle sizes): avg range_ratio = 0.87-0.89. Threshold (0.70) is easy to cross. Gate passes most streaks.
- **Tight-range days** (uniform candle sizes): avg range_ratio = 0.54-0.63. Threshold is hard to cross. Gate blocks most streaks.

BTC shifted from wide-range to tight-range between Mar 25-28:

| Day | Avg Range Ratio | Avg Volatility | HIGH_VOL % |
|-----|-----------------|----------------|------------|
| Mar 23 | 0.873 | 0.2006 | 70% |
| Mar 25 | 0.629 | 0.1207 | 39% |
| Mar 28 | 0.608 | 0.0748 | 11% |
| Mar 31 | 0.541 | 0.1717 | 68% |

The gate was effectively a hidden regime dependency: it worked in high-volatility markets (where candle sizes vary enough for the last candle to look "small") and broke in medium-volatility markets (where candle sizes are uniform). This wasn't by design — it was an accident of the 0.70 threshold interacting with different market microstructures.

### 4. The WR stayed high, masking the damage

66.9% WR is excellent. There was no "it's broken" signal — just a gradually quieter bot. Paper trading success metrics (WR, P&L, ROI) were all positive. The failure mode wasn't bad bets — it was *missing* bets. And you can't see missing bets unless you track the counterfactual.

## Backtest Contradicts Live Data

The native Polymarket backtest (8,896 markets, 30 days) says the opposite of the live counterfactual:

| Config | Bets | WR | P&L |
|--------|------|----|-----|
| With exhaustion | 140 | 52.9% | +$1,100 |
| Without exhaustion | 1,755 | 49.0% | -$6,750 |

**The backtest says removing the gate makes things worse.** 49.0% WR is below breakeven. The gate adds +3.9pp and turns a losing strategy into a marginally winning one. On this data, the exhaustion gate is the only thing standing between the signal and a coin flip.

**The live data says the opposite.** Filtered predictions hit 85% WR (n=100) vs 66.9% for kept predictions (n=245), consistently across 9 days with no day below 70%.

These two data sources disagree, and we cannot reconcile them cleanly. The backtest uses Polymarket binary outcome sequences to detect streaks; the live system uses Kraken/Coinbase BTC candle data. These are correlated but not identical — a sequence of 5-minute market outcomes resolving UP is not the same thing as 3 consecutive green candles on an exchange. The backtest structurally underperforms live by ~15pp on absolute WR, but if the offset were uniform, the *relative* comparison (with vs without gate) should still hold — and it favors keeping the gate.

**We are choosing to trust the live data.** This is a judgment call, not a certainty. The reasoning:

1. The live signal uses the actual data source that production runs on. The backtest approximates it.
2. The live counterfactual has 100 observations across 9 independent days. Small, but consistent.
3. The theoretical argument (exhaustion is a contrarian filter on a momentum strategy) supports the live data's direction, not the backtest's.

**But we could be wrong.** If the live counterfactual's 85% WR was an artifact of the specific market regime during Mar 23-31 (e.g., BTC happened to trend cleanly enough that even unconfirmed streaks won), then removing the gate will hurt in choppier conditions. The backtest covers a wider date range (Feb 26 - Mar 28) and may capture regimes the live window missed.

**This is the risk we're carrying.** The revert criteria exist for this reason: if WR drops below 60% at 100+ bets, restore the gate. The daily filter breakdown will surface any degradation early.

## What Changed

### Code changes (all in `src/predict.py`, frozen file — approved by user)

1. **Exhaustion gate removed.** No more compression, volume spike, or shrinking range checks. Momentum signal fires on streak >= 3 alone.
2. **Cooldown flip gate removed.** Direction reversals at streak=3 are no longer suppressed. The regime gate handles chop.
3. **Confidence logic simplified.** `high` confidence now only from streak >= 5 (removed `volume_spike and compression` boost).

### Monitoring added

- Daily report "Filter Breakdown" section tracks every skip reason with counterfactual WR
- Analysis document at `docs/analysis/analysis_exhaustion_gate.md`
- Break-fix log updated with revert criteria

### Revert criteria

- WR drops below 60% at 100+ bets → restore exhaustion gate
- Baseline: 66.9% with gate. Expected: higher (adding 85% WR predictions to pool)

## Lessons

1. **Track the counterfactual.** Every filter should log what it would have done. You can't evaluate a gate without seeing both sides.

2. **Confirmation bias in filter design.** The exhaustion gate "seemed reasonable" and the system was profitable, so nobody questioned it. The data was always there — we just weren't looking.

3. **Contrarian intuition doesn't transfer to momentum.** The exhaustion check came from a contrarian mindset (V3). When we flipped to momentum (V4), we inverted the direction but kept the confirmation logic. The inversion should have applied to the filters too.

4. **Gradual degradation is harder to spot than sudden failure.** A gate that blocks 30% of bets on day 1 and 50% on day 9 doesn't trigger any alarm. Volume declining from 43 to 11 bets/day happened over a week with no single day looking obviously broken.

5. **Thresholds are regime-dependent until proven otherwise.** The 0.70 range_ratio threshold worked in one volatility regime and failed in another. Any fixed threshold on a market-derived metric will have this problem. If you must use thresholds, test them across multiple market conditions.
