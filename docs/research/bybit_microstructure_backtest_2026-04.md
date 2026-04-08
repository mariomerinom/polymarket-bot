# Bybit microstructure signals — backtest

Capture window: 0.0 hours.
Signals tested on enriched 5m candles (candle OHLCV + CVD + liquidation aggregates + avg book imbalance + taker counts).

## Inventory
| Topic | Bars with data |
|---|--:|
| publicTrade | 1 |
| liquidation | 0 |
| orderbook | 1 |
| tickers | 1 |

## Results
| Signal | N | WR | P&L | Avg/trade |
|--------|--:|---:|----:|----------:|
| cvd_div | 0 | — | — | — |
| liq_cascade_250k | 0 | — | — | — |
| liq_cascade_500k | 0 | — | — | — |
| liq_cascade_1000k | 0 | — | — | — |
| book_imb_20 | 0 | — | — | — |
| book_imb_30 | 0 | — | — | — |
| book_imb_40 | 0 | — | — | — |
| taker_agg_2p5 | 0 | — | — | — |
| taker_agg_3p0 | 0 | — | — | — |
| taker_agg_4p0 | 0 | — | — | — |

## Verdict
❌ No microstructure signal clears 55% WR on N≥100 with positive P&L in the captured window. Either the window is too short (re-run after more capture) or the microstructure data class is also dead on this venue at 5m. If the latter holds after ≥14 days of capture, the exhaustive-negative conclusion extends to L2 + taker flow + liquidations + intra-bar funding, which is the strongest possible negative result on Bybit BTCUSDT 5m.

