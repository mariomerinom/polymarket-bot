# Pipeline Improvement Recommendations — March 25–27, 2026

Analysis period: March 25–27, 2026 | BTC: $71,300 → $66,587 (-6.6%)

> **Tracking:** These recommendations are tracked with automated triggers in [`docs/decisions.md`](../decisions.md). The daily report alerts when conditions are met.

---

## 5-Minute Pipeline Recommendations

### Performance Summary

| Metric | 3-Day Aggregate |
|--------|----------------|
| Total Bets | 112 |
| Win Rate | 67.9% (76W / 36L) |
| P&L | +$2,490.30 |
| Wagered | $9,400.00 |
| ROI | 26.5% |
| Best Day | Mar 25: 79.1% WR, +$1,426.18 |
| Worst Day | Mar 26: 57.9% WR, +$437.67 |

### Key Findings

Directional performance correlates strongly with BTC macro movement. The best day (Mar 25, +$1,426) coincided with a relief rally where UP bets hit 90% WR. The weakest day (Mar 26, +$437) had the smallest BTC move. The model appears momentum-dependent—it finds less edge in range-bound conditions.

Conviction calibration is inverted. conv=3 bets are profitable every single day ($2,551 total), while conv=4 bets (only active Mar 27) lost $60.79 at 50% WR. Higher conviction is producing worse results.

The 0.50–0.70 price bucket is a consistent drag. WR is declining day-over-day (75% → 52% → 56%) despite being the highest-volume bucket. Contracts in this range are closest to fair value and hardest to predict.

Bet volume is declining (43 → 38 → 31) without obvious regime changes. This could indicate model confidence degradation or filter drift.

### Recommendations

| # | Area | Recommendation | Priority | Impact |
|---|------|---------------|----------|--------|
| 1 | Conviction Sizing | conv=4 lost $60.79 at 50% WR (Mar 27, only active day). conv=3 profitable all 3 days ($2,551 total). Cap at conv=3 until conv=4 threshold is recalibrated. | HIGH | ~$60/day |
| 2 | 0.50-0.70 Bucket | WR declining: 75% → 52% → 56%. This bucket generates the most bets but worst returns. Raise conviction threshold or add secondary confirmation filter for mid-range contracts. | HIGH | +5-10% WR |
| 3 | Regime Awareness | Model performs best when aligned with BTC macro direction. Weakest day (Mar 26, 57.9% WR) had smallest BTC move. Add a volatility/trend filter to reduce sizing in range-bound conditions. | MEDIUM | Avoid -EV days |
| 4 | Mean-Reversion | Zero bets across all MEAN_REVERTING regimes (170+ predictions skipped over 3 days). Backtest a dedicated mean-reversion strategy—this is a large untapped sample. | MEDIUM | New edge |
| 5 | Bet Count Decay | Volume declining: 43 → 38 → 31 bets/day. Investigate whether filters are tightening due to regime shifts or if model confidence is degrading. May indicate drift. | MEDIUM | Early warning |
| 6 | 0.70-0.85 Bucket | Only 6 bets total across 3 days, 50% WR, volatile P&L. High-priced contracts carry more downside risk. Require conv=4+ or exclude. | LOW | Risk reduction |
| 7 | 0.15-0.30 Bucket | Small sample (5 bets, 80% WR, +$14.89). Edge looks real but volume is minimal. Explore whether model generates more signals here that are being filtered out. | LOW | Volume upside |

---

## 15-Minute Pipeline Recommendations

### Performance Summary

| Metric | 3-Day Aggregate |
|--------|----------------|
| Total Bets | 12 |
| Win Rate | 66.7% (8W / 4L) |
| P&L | +$33.55 |
| Wagered | $1,400.00 |
| ROI | 2.4% |
| Active Days | 2 of 3 (Mar 25: 0 bets) |
| Best Day | Mar 26: 75% WR, +$45.17 |
| Worst Day | Mar 27: 62.5% WR, -$11.62 |

### Key Findings

The pipeline is barely viable at current volumes. 12 bets over 3 days generating $33.55 in P&L does not justify operational overhead. The pipeline was completely inactive on Mar 25 despite having 3 predictions—none met the conviction threshold.

The same conviction inversion exists here. conv=3 bets: 75% WR, +$67.20. conv=4 bets: 50% WR, -$33.65. This suggests a systematic issue in how conviction is scored, not a pipeline-specific problem.

Directional skew is even more pronounced than the 5-min pipeline. DOWN bets: 83.3% WR, +$124.08. UP bets: 57.1% WR, -$90.52. The model may only have reliable edge on the short side at this timeframe.

All bets were placed in HIGH_VOL/NEUTRAL regime only. The model has zero regime diversity at the 15-min timeframe.

### Recommendations

| # | Area | Recommendation | Priority | Impact |
|---|------|---------------|----------|--------|
| 1 | Pipeline Viability | Only 12 bets across 2 active days (Mar 26-27). Mar 25 produced 0 bets from 3 predictions. Volume is too low to generate meaningful P&L. Decision needed: retrain, loosen filters, or sunset. | HIGH | Simplify ops |
| 2 | 0.50-0.70 Bucket | 5 bets at 40% WR, -$238.12. Same problem as 5-min pipeline but worse. This bucket is destroying all gains from 0.30-0.50. Exclude entirely or require much higher conviction. | HIGH | +$238/day |
| 3 | Conviction Sizing | conv=3: 75% WR, +$67.20. conv=4: 50% WR, -$33.65. Same inversion as the 5-min pipeline. Do not use conv=4 sizing until root cause is identified. | HIGH | +$33/day |
| 4 | Directional Skew | DOWN bets: 83.3% WR (+$124.08). UP bets: 57.1% WR (-$90.52). Across both days the model is significantly better at calling DOWN on 15-min. Investigate if UP signals should be filtered out. | MEDIUM | Fewer losses |
| 5 | Regime Coverage | All bets placed in HIGH_VOL/NEUTRAL only. No bets in MEAN_REVERTING or TRENDING regimes. Either the model has no edge there or the filter is too conservative—worth testing. | LOW | Volume upside |

### Strategic Decision: Continue or Sunset?

The 15-min pipeline needs a go/no-go decision. At 12 bets over 3 days and $33.55 total P&L (2.4% ROI), it is not contributing meaningfully. Three options:

- **Retrain:** The 15-min model may need more training data or different features. The 5-min model is clearly better calibrated. Consider using the 5-min model's architecture as a starting point.
- **Loosen filters:** The pipeline is generating 22 predictions/day but only betting on 4-8. If the conv=0 predictions have 57-67% WR, there may be edge being filtered away. Test lowering the threshold.
- **Sunset:** Redirect engineering effort to improving the 5-min pipeline, which is clearly the primary revenue driver (+$2,490 vs +$33). Focus resources where edge is proven.
