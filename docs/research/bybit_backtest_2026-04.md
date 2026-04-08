# Bybit perp backtest — 6mo BTCUSDT 5m, momentum

- Trades: **4570**
- Wins / Losses: 1305 / 3265
- Win rate: **28.6%**
- Total P&L (pre-funding): **$-2366.57**
- Avg P&L / trade: $-0.518

## By regime label
| Regime | Trades | WR | P&L |
|---|---:|---:|---:|
| HIGH_VOL / NEUTRAL | 1607 | 33.9% | $-885.30 |
| MEDIUM_VOL / NEUTRAL | 1542 | 25.0% | $-803.22 |
| HIGH_VOL / TRENDING | 578 | 34.9% | $-222.88 |
| MEDIUM_VOL / TRENDING | 510 | 25.5% | $-272.38 |
| LOW_VOL / NEUTRAL | 263 | 11.0% | $-155.64 |
| LOW_VOL / TRENDING | 70 | 21.4% | $-27.17 |

## By direction
| Side | Trades | WR | P&L |
|---|---:|---:|---:|
| Buy | 2290 | 28.1% | $-1273.51 |
| Sell | 2280 | 29.0% | $-1093.06 |

## By streak length (conviction proxy)
| |streak| | Trades | WR | P&L |
|---:|---:|---:|---:|
| 3 | 4113 | 28.8% | $-2107.64 |
| 4 | 265 | 22.3% | $-187.23 |
| 5 | 123 | 31.7% | $-32.83 |
| 6 | 20 | 15.0% | $-15.40 |
| 7 | 8 | 25.0% | $-3.20 |
| 8 | 1 | 0.0% | $-4.81 |
| 9 | 36 | 36.1% | $-18.12 |
| 10 | 2 | 50.0% | $-0.81 |
| 11 | 1 | 100.0% | $1.94 |
| 13 | 1 | 100.0% | $1.53 |

## By exit reason
| Reason | Trades | WR | P&L |
|---|---:|---:|---:|
| time_ceiling | 3364 | 38.0% | $-496.30 |
| streak_break | 1206 | 2.3% | $-1870.27 |

## Decision gate
❌ WR 28.6% < 52% — Phase 2 gate FAILED. Pause pivot, re-examine signal.
