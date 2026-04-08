# Bybit perp signal sweep — 6mo BTCUSDT

Grid over bar size × hold × min_streak × entry × exit.
Filtered to cells with N >= 100 trades.

## Top 25 by WR
| Bar | Hold | Streak | Entry | Exit | N | WR | P&L |
|---|---:|---:|---|---|---:|---:|---:|
| 1h | 24 | 3 | fade | time_only | 126 | 56.3% | $42.09 |
| 1h | 6 | 4 | fade | time_only | 180 | 50.6% | $-125.78 |
| 15m | 12 | 5 | fade | time_only | 315 | 49.8% | $-82.49 |
| 15m | 24 | 5 | fade | time_only | 248 | 49.6% | $-54.77 |
| 15m | 24 | 3 | fade | time_only | 512 | 49.2% | $-245.57 |
| 1h | 12 | 4 | fade | time_only | 139 | 48.9% | $-106.75 |
| 15m | 6 | 5 | fade | time_only | 361 | 48.2% | $-89.40 |
| 1h | 12 | 3 | fade | time_only | 209 | 47.8% | $-87.54 |
| 15m | 6 | 5 | fade | trailing_1p0 | 378 | 47.1% | $-117.35 |
| 15m | 24 | 4 | fade | time_only | 386 | 45.9% | $-320.73 |
| 15m | 12 | 5 | fade | trailing_1p0 | 342 | 45.3% | $-159.66 |
| 1h | 6 | 3 | fade | time_only | 309 | 45.0% | $-223.78 |
| 1h | 6 | 4 | fade | trailing_1p0 | 212 | 44.8% | $-133.24 |
| 1h | 3 | 4 | fade | time_only | 217 | 44.7% | $-142.64 |
| 1h | 3 | 5 | ride | streak_break | 101 | 44.6% | $-17.64 |
| 1h | 3 | 5 | ride | time_only | 101 | 44.6% | $-17.64 |
| 1h | 3 | 5 | ride | trailing_1p0 | 101 | 44.6% | $-12.98 |
| 15m | 6 | 5 | fade | trailing_0p5 | 421 | 44.4% | $-114.41 |
| 15m | 12 | 4 | fade | time_only | 569 | 44.1% | $-305.38 |
| 15m | 6 | 4 | fade | time_only | 729 | 44.0% | $-276.37 |
| 1h | 6 | 3 | ride | time_only | 309 | 44.0% | $-68.22 |
| 15m | 24 | 5 | fade | trailing_1p0 | 298 | 44.0% | $-64.09 |
| 1h | 12 | 4 | ride | time_only | 139 | 43.9% | $-23.84 |
| 15m | 3 | 5 | fade | time_only | 415 | 43.9% | $-131.62 |
| 15m | 3 | 5 | fade | trailing_1p0 | 420 | 43.8% | $-129.20 |

## Top 10 by P&L
| Bar | Hold | Streak | Entry | Exit | N | WR | P&L |
|---|---:|---:|---|---|---:|---:|---:|
| 1h | 24 | 3 | fade | time_only | 126 | 56.3% | $42.09 |
| 1h | 12 | 4 | ride | trailing_1p0 | 157 | 42.7% | $19.55 |
| 1h | 3 | 5 | ride | trailing_1p0 | 101 | 44.6% | $-12.98 |
| 1h | 3 | 5 | ride | streak_break | 101 | 44.6% | $-17.64 |
| 1h | 3 | 5 | ride | time_only | 101 | 44.6% | $-17.64 |
| 1h | 3 | 5 | ride | trailing_0p5 | 101 | 41.6% | $-18.60 |
| 1h | 12 | 4 | ride | time_only | 139 | 43.9% | $-23.84 |
| 1h | 12 | 4 | ride | streak_break | 164 | 43.3% | $-35.29 |
| 1h | 24 | 3 | ride | trailing_0p5 | 301 | 34.2% | $-39.97 |
| 15m | 24 | 4 | ride | time_only | 386 | 42.5% | $-42.31 |

## Verdict
Best WR cell: **56.3%** (1h, hold=24, streak=3, fade/time_only, N=126, P&L=$42.09)
Best P&L cell: **$42.09** (1h, hold=24, streak=3, fade/time_only, N=126, WR=56.3%)

✅ A cell clears the 55% bar — investigate further, confirm with an out-of-sample split, then rebuild the pivot.
