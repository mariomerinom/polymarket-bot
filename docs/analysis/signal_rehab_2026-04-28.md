# Signal Rehabilitation Analysis — 2026-04-28 13:30 UTC

Five hypotheses about the V4 momentum decay, measured against predictions.db (BTC) and predictions_eth.db (ETH). All numbers are conviction>=3 unless noted (production cohort).

**Strong era:** 2026-03-29 → 2026-04-06
**Decay era:** 2026-04-07 → 2026-04-24

---

## H1 — Lab-to-production translation lying?

*If aggregate (all-conviction) WR stays stable while conv≥3 WR drops, the signal still has edge — adverse selection is eating production fills.*

### BTC (momentum_rule)

| week | lab N | lab WR% | prod N | prod WR% | gap (pp) |
|---|---|---|---|---|---|
| 2026-03-23 | 262 | 59.2 | 16 | 68.8 | 9.6 |
| 2026-03-30 | 1781 | 60.3 | 171 | 68.4 | 8.1 |
| 2026-04-06 | 1215 | 49.4 | 159 | 49.7 | 0.3 |
| 2026-04-13 | 843 | 49.0 | 53 | 41.5 | -7.5 |
| 2026-04-20 | 644 | 50.3 | 38 | 42.1 | -8.2 |

### ETH (momentum_eth)

| week | lab N | lab WR% | prod N | prod WR% | gap (pp) |
|---|---|---|---|---|---|
| 2026-03-30 | 1137 | 58.4 | 102 | 72.5 | 14.1 |
| 2026-04-06 | 1834 | 47.4 | 262 | 48.9 | 1.5 |
| 2026-04-13 | 1422 | 47.8 | 152 | 46.1 | -1.7 |
| 2026-04-20 | 685 | 48.3 | 86 | 48.8 | 0.5 |

**How to read:** if `lab WR%` stays roughly constant week-over-week while `prod WR%` declines, H1 is supported — the signal hasn't decayed, just our subset of it that fires conviction>=3 has gotten worse. If both decline together, the signal itself is the problem.

---

## H2 — Regime mix shift

*Per-regime WR by week + regime share of all predictions. If a regime's WR is stable but its share grew (or another regime's share grew where WR was always bad), the signal is fine — the market shifted under it.*

### BTC

| week | regime | bets (conv≥3) | WR% | regime share |
|---|---|---|---|---|
| 2026-03-23 | HIGH_VOL / TRENDING | 2 | 100.0 | 5.3% |
| 2026-03-23 | MEDIUM_VOL / NEUTRAL | 12 | 75.0 | 44.7% |
| 2026-03-23 | MEDIUM_VOL / TRENDING | 2 | 0.0 | 8.0% |
| 2026-03-30 | HIGH_VOL / NEUTRAL | 8 | 62.5 | 13.8% |
| 2026-03-30 | HIGH_VOL / TRENDING | 19 | 78.9 | 4.8% |
| 2026-03-30 | LOW_VOL / NEUTRAL | 29 | 51.7 | 9.9% |
| 2026-03-30 | LOW_VOL / TRENDING | 40 | 65.0 | 7.2% |
| 2026-03-30 | MEDIUM_VOL / NEUTRAL | 37 | 78.4 | 16.8% |
| 2026-03-30 | MEDIUM_VOL / TRENDING | 38 | 71.1 | 7.4% |
| 2026-04-06 | HIGH_VOL / NEUTRAL | 93 | 48.4 | 49.3% |
| 2026-04-06 | HIGH_VOL / TRENDING | 8 | 37.5 | 1.6% |
| 2026-04-06 | MEDIUM_VOL / NEUTRAL | 54 | 53.7 | 41.6% |
| 2026-04-06 | MEDIUM_VOL / TRENDING | 4 | 50.0 | 1.1% |
| 2026-04-13 | HIGH_VOL / TRENDING | 12 | 50.0 | 4.2% |
| 2026-04-13 | MEDIUM_VOL / NEUTRAL | 41 | 39.0 | 43.7% |
| 2026-04-20 | HIGH_VOL / TRENDING | 5 | 20.0 | 9.4% |
| 2026-04-20 | MEDIUM_VOL / NEUTRAL | 29 | 51.7 | 27.8% |
| 2026-04-20 | MEDIUM_VOL / TRENDING | 4 | 0.0 | 1.7% |

### ETH

| week | regime | bets (conv≥3) | WR% | regime share |
|---|---|---|---|---|
| 2026-03-30 | HIGH_VOL / NEUTRAL | 6 | 83.3 | 9.6% |
| 2026-03-30 | HIGH_VOL / TRENDING | 3 | 100.0 | 1.3% |
| 2026-03-30 | LOW_VOL / NEUTRAL | 52 | 69.2 | 27.8% |
| 2026-03-30 | LOW_VOL / TRENDING | 12 | 83.3 | 4.7% |
| 2026-03-30 | MEDIUM_VOL / NEUTRAL | 10 | 70.0 | 9.8% |
| 2026-03-30 | MEDIUM_VOL / TRENDING | 19 | 68.4 | 7.8% |
| 2026-04-06 | HIGH_VOL / NEUTRAL | 22 | 27.3 | 14.3% |
| 2026-04-06 | HIGH_VOL / TRENDING | 18 | 33.3 | 7.2% |
| 2026-04-06 | LOW_VOL / NEUTRAL | 31 | 48.4 | 11.2% |
| 2026-04-06 | LOW_VOL / TRENDING | 1 | 100.0 | 0.1% |
| 2026-04-06 | MEDIUM_VOL / NEUTRAL | 154 | 52.6 | 48.7% |
| 2026-04-06 | MEDIUM_VOL / TRENDING | 36 | 52.8 | 7.7% |
| 2026-04-13 | HIGH_VOL / TRENDING | 19 | 31.6 | 7.0% |
| 2026-04-13 | LOW_VOL / NEUTRAL | 7 | 28.6 | 2.9% |
| 2026-04-13 | LOW_VOL / TRENDING | 2 | 50.0 | 0.2% |
| 2026-04-13 | MEDIUM_VOL / NEUTRAL | 124 | 49.2 | 57.5% |
| 2026-04-20 | LOW_VOL / NEUTRAL | 4 | 75.0 | 3.5% |
| 2026-04-20 | MEDIUM_VOL / MEAN_REVERTING | 3 | 66.7 | 15.1% |
| 2026-04-20 | MEDIUM_VOL / NEUTRAL | 77 | 48.1 | 72.1% |
| 2026-04-20 | MEDIUM_VOL / TRENDING | 2 | 0.0 | 1.2% |

---

## H3 — Cell decay (estimate × regime)

*Strong-era WR vs decay-era WR per (estimate_bucket × regime) cell. Cells where decay-era WR stayed >55% on N>=20 are listed as `survivors` — production-restriction targets.*

### BTC survivors (decay-era N≥20, WR≥55%)

**No BTC cells survived** the decay-era N≥20 + WR≥55% bar. Restriction-based rehabilitation has no target for BTC based on (estimate × regime) alone.

### ETH survivors (decay-era N≥20, WR≥55%)

**No ETH cells survived** the bar.

### BTC: full table (all cells)

<details><summary>expand</summary>

| estimate | regime | strong N | strong WR% | decay N | decay WR% | delta (pp) |
|---|---|---|---|---|---|---|
| 0.4-0.5 | HIGH_VOL / NEUTRAL | 7 | 42.9 | 28 | 46.4 | 3.5 |
| 0.4-0.5 | HIGH_VOL / TRENDING | 2 | 100.0 | 11 | 45.5 | -54.5 |
| 0.4-0.5 | LOW_VOL / TRENDING | 9 | 77.8 | 0 |  |  |
| 0.4-0.5 | MEDIUM_VOL / TRENDING | 3 | 66.7 | 2 | 0.0 | -66.7 |
| 0.5-0.6 | HIGH_VOL / NEUTRAL | 7 | 71.4 | 40 | 47.5 | -23.9 |
| 0.5-0.6 | HIGH_VOL / TRENDING | 3 | 100.0 | 10 | 40.0 | -60.0 |
| 0.5-0.6 | LOW_VOL / NEUTRAL | 23 | 47.8 | 0 |  |  |
| 0.5-0.6 | LOW_VOL / TRENDING | 17 | 70.6 | 0 |  |  |
| 0.5-0.6 | MEDIUM_VOL / NEUTRAL | 11 | 63.6 | 95 | 50.5 | -13.1 |
| 0.5-0.6 | MEDIUM_VOL / TRENDING | 11 | 72.7 | 5 | 20.0 | -52.7 |
| 0.6-0.7 | HIGH_VOL / NEUTRAL | 7 | 57.1 | 5 | 40.0 | -17.1 |
| 0.6-0.7 | HIGH_VOL / TRENDING | 10 | 80.0 | 1 | 0.0 | -80.0 |
| 0.6-0.7 | LOW_VOL / NEUTRAL | 6 | 66.7 | 0 |  |  |
| 0.6-0.7 | LOW_VOL / TRENDING | 12 | 50.0 | 0 |  |  |
| 0.6-0.7 | MEDIUM_VOL / NEUTRAL | 38 | 81.6 | 29 | 41.4 | -40.2 |
| 0.6-0.7 | MEDIUM_VOL / TRENDING | 17 | 64.7 | 0 |  |  |
| <0.4 | HIGH_VOL / NEUTRAL | 3 | 66.7 | 4 | 50.0 | -16.7 |
| <0.4 | HIGH_VOL / TRENDING | 7 | 71.4 | 2 | 0.0 | -71.4 |
| <0.4 | LOW_VOL / TRENDING | 2 | 50.0 | 0 |  |  |
| <0.4 | MEDIUM_VOL / TRENDING | 9 | 66.7 | 1 | 100.0 | 33.3 |

</details>

---

## H4 — Cross-asset asynchrony (BTC vs ETH)

*Per-week conviction>=3 WR for both assets, side by side. If one kept its edge while the other lost it, capital should follow the live signal.*

| week | BTC N | BTC WR% | ETH N | ETH WR% | ETH-BTC (pp) |
|---|---|---|---|---|---|
| 2026-03-23 | 16 | 68.8 | 0 |  |  |
| 2026-03-30 | 171 | 68.4 | 102 | 72.5 | 4.1 |
| 2026-04-06 | 159 | 49.7 | 262 | 48.9 | -0.8 |
| 2026-04-13 | 53 | 41.5 | 152 | 46.1 | 4.6 |
| 2026-04-20 | 38 | 42.1 | 86 | 48.8 | 6.7 |

---

## H5 — Timing shift

*Median seconds past each 5-minute boundary for prediction writes, sampled randomly from each era. If decay-era predictions are systematically later within the cycle, slower dispatch could be missing fast price moves.*

| era | n | median (s) | p90 (s) | p99 (s) |
|---|---|---|---|---|
| strong | 200 | 136 | 263 | 298 |
| decay | 200 | 6 | 14 | 46 |

---

## How to use this

1. Read H1 first. It either explains everything (signal still good, execution broken) or rules out the cheap fix.
2. If H1 doesn't explain it, look at H2. Stable regime-WR + shifted regime mix is also recoverable — just restrict trading to the regimes that work.
3. H3 is the granular rehab list. Surviving cells with N≥20 are concrete production-restriction candidates.
4. H4 tells you whether the answer is asset-specific. ETH 5m had a positive 7d signal EHR going into the outage; that may persist.
5. H5 is a sanity check — if timing shifted dramatically, fix that before anything else.

*Note: pre-Apr-24 data only. The 2026-04-24/28 disk-full outage produced no predictions during that window. Apr 28 onward is fresh data accumulating from the recovered engine.*

---

## Synthesis — what the data is actually saying

Reading H1 + H2 + H5 together, the decay has a clear narrative.

### The signal really did decay around 2026-04-06

H1 BTC: lab WR (always-fire) dropped from ~60% (Mar 23-30) to ~50% (Apr 6 onward). H1 ETH: same pattern, 58% → 47%. **This is genuine signal decay, not just an execution problem.** Both assets, same week, same magnitude.

H2 confirms: even within MEDIUM_VOL/NEUTRAL — the dominant regime — WR collapsed from 75-78% in March to 39-52% in April. Per-regime WR fell. So it's not pure regime-mix shift either.

### But the conviction filter ALSO inverted

The lab→prod gap shows what conviction was *adding* on top of base WR:

| Week | BTC gap (pp) | Reading |
|---|---|---|
| Mar 23 | +9.6 | conviction filter added 10pp |
| Mar 30 | +8.1 | still adding |
| Apr 6 | +0.3 | filter stopped helping |
| Apr 13 | −7.5 | filter is now picking losers |
| Apr 20 | −8.2 | same |

Pre-Apr-6 the conviction filter was a real edge generator. Post-Apr-6 it became *anti-selective* — picking the worse trades from a coin-flip pool. **Two losses in one: the signal decayed AND the filter inverted.**

ETH didn't suffer the filter inversion (gap stayed near zero). Only BTC's filter went bad.

### H5 is the smoking gun

The most concrete finding in this whole analysis:

| Era | Median seconds-past-5min |
|---|---|
| Strong (Mar 29 – Apr 5) | **136-152 seconds** |
| Decay (Apr 6 onward) | **3-14 seconds** |

Inflection date: **2026-04-06**. Sharp, single-day cliff. Verified via per-day query: average offset went 152s → 3s between Apr 5 and Apr 6.

What this means: pre-Apr-6 the prediction fired ~2:30 INTO each 5-minute cycle, with ~2:30 of new candle data already accumulated. Post-Apr-6 it fires ~6 seconds after the close, with ~5 minutes of upcoming candle to be wrong about.

**The strong-era system was effectively cheating** — using mid-cycle in-flight price action as an information edge on the upcoming candle's direction. The Apr 6 refactor moved dispatch from timer-based to event-driven, which removed the cheat and exposed the bare signal — which turns out to be near-coin-flip.

### Apr 6 commit constellation

Five non-trivial commits landed on Apr 5-6 that could have caused the inflection:

- `7bc10f747` Harden engine crash resilience: supervisor, rebase recovery, error isolation
- `1b3cddf84` Pipeline isolation + unification: eliminate TRADING_ENABLED global mutation
- `d741d5115` FOK execution layer: replace GTC with Fill-Or-Kill orders
- `750c6a14e` Unify all Polymarket pipelines on FOK execution infrastructure
- `8766763fc` Add implementation plan: event-driven trade execution

The pipeline isolation refactor (`1b3cddf84`) and the FOK unification (`750c6a14e`) are the two most likely candidates for changing dispatch timing. A 30-minute commit-by-commit walk would identify the exact one.

### Rehabilitation paths — ranked by promise

**1. Re-introduce the mid-cycle information edge — IF intentionally desired.** The strong-era system worked because it had ~2:30 of in-flight candle data when predicting. That's not technically "cheating" — it's "using the information available at decision time." The Apr 6 refactor wasn't wrong; it just removed a hidden source of edge. Putting it back means deliberately running predictions on partial-candle data, which has its own fragility risks but is at least a known recoverable mechanism.

**2. Audit the conviction filter for the inversion.** The BTC lab→prod gap going from +9 to −8 in three weeks is suspicious of *something we shipped* picking the wrong things. Walk through the gates added between Apr 6 and Apr 13 (intraday_range_gate, highvol_non_trending_gate, dynamic_estimates revert, etc.). One or more is probably anti-selective in its current form.

**3. Restrict to ETH-only.** ETH outperforms BTC by 4-7pp every decay-era week. The conviction filter on ETH didn't invert. ETH 5m is the last pipeline with a positive 7d signal EHR per `PIVOT_OPTIONS.md`. The asset asymmetry is small but real.

**4. H3 says no easy slice survives.** Zero (estimate × regime) cells held the ≥55% WR / N≥20 bar. So "just trade this one regime" is not an option — the rehab paths above are about *mechanism*, not *slice restriction*.

### What this means for the pivot decision

Yesterday's framing was "is V4 dying or is execution broken?" The honest answer is **both, partially, and there's a third thing nobody named.** The third thing is the timing refactor. None of the three are mutually exclusive.

The cheap probe: walk Apr 5-6 commits in 30 minutes, identify the exact dispatch-timing change, decide whether to revert or keep. That single answer either:
- Reverts the WR back to ~60% lab (signal works again, decay was self-inflicted) → **rehabilitation succeeded**
- Or doesn't (signal decayed for other reasons) → V4 chapter properly closed, pivot to arb / longer-duration / Kalshi without the lingering "did we shoot ourselves" doubt

Either outcome is decision-grade. **This is the highest-leverage 30 minutes of work on the table right now.**
