# Bybit conviction calibration — Phase 5

Source: `predictions_bybit.db` × `asset_daily.db`
Resolved rows: **260**. Bet size assumption: $25.0.
Breakeven WR (symmetric binary): **50.0%**.

## By conviction tier
| Conviction | N | WR | EV/bet | Verdict |
|---:|---:|---:|---:|---|
| 3 | 190 | 52.6% | $+1.32 | marginal |
| 4 | 68 | 50.0% | $+0.00 | marginal |
| 5 | 2 | 50.0% | $+0.00 | marginal |

## By conviction × day trend
| Conv | Trend | N | WR | EV/bet |
|---:|---|---:|---:|---:|
| 3 | chop | 53 | 52.8% | $+1.42 |
| 3 | up | 99 | 59.6% | $+4.80 |
| 3 | — | 38 | 34.2% | $-7.89 |
| 4 | chop | 26 | 57.7% | $+3.85 |
| 4 | up | 39 | 46.2% | $-1.92 |

## By conviction × vol bucket
| Conv | Vol | N | WR | EV/bet |
|---:|---|---:|---:|---:|
| 3 | vol_hi | 57 | 45.6% | $-2.19 |
| 3 | vol_low | 66 | 71.2% | $+10.61 |
| 3 | vol_mid | 29 | 48.3% | $-0.86 |
| 3 | — | 38 | 34.2% | $-7.89 |
| 4 | vol_hi | 15 | 40.0% | $-5.00 |
| 4 | vol_low | 33 | 51.5% | $+0.76 |
| 4 | vol_mid | 17 | 58.8% | $+4.41 |

## Verdict
❌ Top tier (conv=5) below breakeven (50.0% on N=2). Tiers do not discriminate — consistent with Phase 2 sweep finding that no parameter combination produces stable edge on Bybit 5m perps.

