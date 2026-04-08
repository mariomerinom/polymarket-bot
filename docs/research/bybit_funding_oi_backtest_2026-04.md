# Bybit funding & open-interest signals — 6mo backtest

After the candle-only signal families (streak momentum, breakout, VWAP mean-reversion, cross-venue lead/lag) all failed on Bybit 5m, test two non-candle signal classes:

1. **funding_extreme** — fade crowding via funding rate decile
2. **oi_delta** — fade crowded chases via OI change + price confirm

Both are MOMENTUM signals (ride the crowd). Fade variants were tested first and produced 37-44% WR — inverting gives numbers below.

## Headline results
| Signal | N | WR | P&L | Avg/trade |
|--------|--:|---:|----:|----------:|
| fund_p5_h24 | 272 | 38.97% | $-155.86 | $-0.573 |
| fund_p5_h48 | 136 | 45.59% | $-95.62 | $-0.703 |
| fund_p10_h24 | 440 | 40.23% | $-247.93 | $-0.563 |
| fund_p10_h48 | 220 | 46.36% | $-150.53 | $-0.684 |
| fund_p20_h24 | 774 | 40.70% | $-381.13 | $-0.492 |
| fund_p20_h48 | 387 | 43.15% | $-208.41 | $-0.539 |
| oi_k6_p10_h6 | 1363 | 33.16% | $-673.46 | $-0.494 |
| oi_k6_p10_h12 | 1031 | 36.66% | $-506.34 | $-0.491 |
| oi_k12_p10_h12 | 750 | 37.73% | $-350.87 | $-0.468 |
| oi_k12_p10_h24 | 570 | 41.05% | $-130.54 | $-0.229 |
| oi_k24_p10_h24 | 412 | 41.26% | $-43.70 | $-0.106 |
| oi_k6_p5_h12 | 586 | 37.88% | $-168.57 | $-0.288 |
| oi_k12_p5_h12 | 402 | 35.32% | $-164.03 | $-0.408 |

## Verdict

❌ No funding or OI cell clears 55% WR + positive P&L on N≥100. Combined with the candle-signal failures, this is the strongest evidence yet that BTCUSDT 5m perp on Bybit is not edge-extractable from public OHLCV + derivatives telemetry. Next options: order-book imbalance (needs L2 snapshots, not available from REST), or a different venue/asset entirely.

