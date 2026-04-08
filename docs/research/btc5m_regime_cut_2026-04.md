# BTC 5m momentum — 6mo backtest regime cut

Re-cut of `tools/backtest_bybit.py` output conditioned on
`data/asset_daily.db` trend_label and velocity buckets. Tests
the hypothesis (from 2026-04-08 live decay analysis) that the
headline 6mo WR was a chop-regime artifact: the signal wins in
chop and loses in trends — the inverse of its design intent.

- Trades (enriched): **4555**
- Overall WR: **28.6%**
- Overall P&L: **$-2365.97**

## By trend_label
| Bucket | N | WR | P&L |
|---|--:|--:|--:|
| chop | 1803 | 27.3% | $-1013.01 |
| down | 1478 | 31.3% | $-628.84 |
| strong_up | 56 | 33.9% | $-24.77 |
| up | 1218 | 26.9% | $-699.35 |

## By velocity bucket
| Bucket | N | WR | P&L |
|---|--:|--:|--:|
| extreme >1.5 | 442 | 28.5% | $-170.08 |
| flat |v|<0.3 | 1021 | 29.3% | $-507.01 |
| mild 0.3-0.8 | 2185 | 27.7% | $-1207.76 |
| strong 0.8-1.5 | 907 | 30.0% | $-481.13 |

## By trend_label × velocity bucket
| Bucket | N | WR | P&L |
|---|--:|--:|--:|
| chop / flat |v|<0.3 | 1021 | 29.3% | $-507.01 |
| chop / mild 0.3-0.8 | 782 | 24.7% | $-506.00 |
| down / extreme >1.5 | 207 | 28.0% | $-66.33 |
| down / mild 0.3-0.8 | 815 | 31.4% | $-343.07 |
| down / strong 0.8-1.5 | 456 | 32.7% | $-219.43 |
| strong_up / extreme >1.5 | 56 | 33.9% | $-24.77 |
| up / extreme >1.5 | 179 | 27.4% | $-78.97 |
| up / mild 0.3-0.8 | 588 | 26.5% | $-358.68 |
| up / strong 0.8-1.5 | 451 | 27.3% | $-261.70 |

## Rank-based gate (velocity_zscore / range_zscore)
Trades with both zscores computed (≥5d trailing history): **4433**

Gate: skip trade if `abs(velocity_zscore) ≥ v_thresh` OR `range_zscore ≥ r_thresh`. Rationale: high-velocity / wide-range days are where the 12-day live tape saw momentum collapse.

| v_thresh | r_thresh | Kept | Skipped | WR kept | P&L kept | WR skipped | P&L skipped |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 99.0 | 99.0 | 4433 | 0 | 28.3% | $-2335.96 | 0.0% | $+0.00 |
| 2.0 | 2.5 | 3988 | 445 | 28.3% | $-2156.59 | 28.1% | $-179.37 |
| 1.5 | 2.0 | 3610 | 823 | 27.9% | $-1989.73 | 30.0% | $-346.23 |
| 1.0 | 1.5 | 2926 | 1507 | 27.9% | $-1598.38 | 29.1% | $-737.58 |
| 1.5 | 99.0 | 3652 | 781 | 28.1% | $-2010.30 | 28.9% | $-325.66 |
| 99.0 | 2.0 | 4168 | 265 | 27.8% | $-2250.92 | 36.6% | $-85.04 |

## Verdict
- chop WR: **27.3%** (N=1803)
- trending WR (up+down): **29.3%** (N=2696)
- chop − trend gap: **-2.1 pts**

➖ **No material regime skew in the 6mo backtest** (chop−trend gap -2.1 pts within noise). The live Apr 4–7 collapse must be explained by something other than trend_label alone — candidates: realized_vol regime shift, range_pct tail, or drawdown clustering.

