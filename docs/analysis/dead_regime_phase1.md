# Dead Regime Harvesting — Phase 1 Retroactive Analysis

**Date:** 2026-04-03
**Pipeline:** BTC 5m
**Dataset:** 1,117 resolved MEAN_REVERTING predictions from data/predictions.db

## Summary

**CONDITIONAL GO for Phase 2 (shadow mode)** — but ONLY with extreme-estimate filter.

Unfiltered MR betting is P&L-negative (-$1,769 simulated on 1,117 bets). The edge exists exclusively at extreme estimates (>0.65 or <0.35), where WR is 82.5% on 303 bets with +$183 simulated P&L.

## Sub-Regime Performance

| Sub-Regime | N | WR | Sim P&L/bet |
|---|---|---|---|
| HIGH_VOL / MEAN_REVERTING | 437 | 59.3% | -$1.58 |
| MEDIUM_VOL / MEAN_REVERTING | 658 | 56.8% | -$1.64 |
| LOW_VOL / MEAN_REVERTING | 22 | 40.9% | — |

## Price Bucket Analysis (Critical Finding)

| Bucket | N | WR | Assessment |
|---|---|---|---|
| **>0.65 or <0.35** | **303** | **82.5%** | ✅ Only P&L-positive slice (+$0.61/bet) |
| 0.55-0.65 | 87 | 59.8% | Marginal |
| 0.45-0.55 | 661 | **46.1%** | 🔴 Actively losing — majority of MR volume |
| 0.35-0.45 | 67 | 53.7% | Marginal |

The momentum model's directional call is highly reliable when confident (estimate far from 0.50), even in mean-reverting regimes. The coin-flip zone (0.45-0.55) is noise.

## Direction Bias

| Sub-Regime | Direction | N | WR |
|---|---|---|---|
| HIGH_VOL/MR | DOWN | 187 | **62.6%** |
| HIGH_VOL/MR | UP | 250 | 56.8% |
| MEDIUM_VOL/MR | DOWN | 283 | 56.9% |
| MEDIUM_VOL/MR | UP | 375 | 56.8% |

DOWN has directional edge in HIGH_VOL/MR (+5.8pp over UP). Aligns with reversion thesis.

## Hour-of-Day

Best MR hours (n≥35): **Hour 0 (69.2%)**, Hour 2 (67.2%), Hour 22 (67.4%).
Worst MR hours: Hour 16 (43.3%), Hour 4 (45.5%), Hour 19 (47.9%), Hour 21 (48.9%).

Note: The spec's Sub-Strategy B (dead hour fade targeting hours 3/21) is NOT supported. Best MR hours are 0/2/22.

## MR Regime Share Trend

| Date | Total | MR | MR % |
|---|---|---|---|
| Apr 3 | 176 | 99 | **56.3%** |
| Apr 2 | 288 | 138 | 47.9% |
| Apr 1 | 284 | 128 | 45.1% |
| Mar 31 | 263 | 114 | 43.3% |
| Mar 30 | 258 | 93 | 36.0% |
| Mar 25 | 253 | 44 | 17.4% |

MR rising from 17% to 56%. Pipeline is increasingly idle.

## Recommended Shadow Mode Criteria

```
regime:     HIGH_VOL/MEAN_REVERTING or MEDIUM_VOL/MEAN_REVERTING
estimate:   > 0.65 OR < 0.35 (EXCLUDE 0.35-0.65)
conviction: shadow at conv=2
direction:  both UP and DOWN
hours:      all (hours 0/2/22 as conviction booster, not gate)
```

Expected volume: ~30 predictions/day.
Projected P&L: ~$549/month at historical 82.5% WR (expect 65-70% forward degradation).

## Validation Gate (Phase 2 → Phase 3)

- Minimum 50 resolved shadow signals
- WR ≥ 60% (accounting for forward degradation from 82.5%)
- Positive simulated P&L at $25/bet
- If fails: shelve dead regime harvesting

## Risks

1. **Derived from ≠ validated by.** Same dataset for discovery and measurement.
2. **Payoff asymmetry at extremes.** Buying at 0.75: risk $25, profit ~$8. Thin margin.
3. **MR share may revert.** 56% could drop back to 20% if market regime shifts.
4. **Sub-Strategy B unsupported.** Dead hour fade spec needs redesign or shelving.
5. **No VWAP confirmation.** Only 27 VWAP-tagged MR predictions exist.
