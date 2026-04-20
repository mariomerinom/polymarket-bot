# Consolidated Daily Report — 2026-04-18

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-18.md](2026-04-18.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 150 |
| Total wins | 57 |
| Total losses | 93 |
| Aggregate WR | 38.0% |
| Total P&L | **-$896.16** |
| Total wagered | $3,750.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 11 | 45.5% | -$25.00 | -0.021 | — | $275.00 |
| sol_hl | SOL | paper | 11 | 45.5% | -$25.00 | -0.035 | — | $275.00 |
| eth_5m | ETH | paper | 36 | 44.4% | -$95.34 | -0.039 | -0.053 | $900.00 |
| bybit | BTC | paper | 14 | 28.6% | -$150.00 | -0.100 | — | $350.00 |
| eth_bybit | ETH | paper | 24 | 37.5% | -$150.00 | -0.095 | — | $600.00 |
| eth_hl | ETH | paper | 24 | 37.5% | -$150.00 | -0.095 | — | $600.00 |
| hl | BTC | paper | 16 | 31.2% | -$150.00 | -0.058 | — | $400.00 |
| btc_5m | BTC | paper | 14 | 28.6% | -$150.82 | -0.068 | -0.101 | $350.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.022 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.067 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 44 | 29.5% | -$450.82 | $1,100.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 84 | 40.5% | -$395.34 | $2,100.00 |
| **SOL** | sol_bybit, sol_hl | 22 | 45.5% | -$50.00 | $550.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0681 | -0.1009 | 70 | +3.3¢/$ |
| bybit | -0.1000 | — | 70 | — |
| doge_bybit | -0.0217 | — | 23 | — |
| doge_hl | -0.0672 | — | 67 | — |
| eth_5m | -0.0390 | -0.0533 | 213 | +1.4¢/$ |
| eth_bybit | -0.0952 | — | 126 | — |
| eth_hl | -0.0952 | — | 126 | — |
| hl | -0.0579 | — | 95 | — |
| sol_bybit | -0.0211 | — | 71 | — |
| sol_hl | -0.0352 | — | 71 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 14 | 14 | 100.0% | 71.4% | -0.1434 |
| eth_5m | 36 | 34 | 94.4% | 58.8% | -0.0431 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 28.6% below 55% threshold (14 bets)
- ⚠️ Daily P&L $-150.82 — significant loss
- 🚨 4 consecutive losing days
- ⚠️ Circuit breaker at 67% ($200 / $300)
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0681 over 70 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 28.6% below 55% threshold (14 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3668
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3618
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3606
- 🚨 Signal EHR negative: -0.1000 over 70 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0672 over 67 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ Daily WR 44.4% below 55% threshold (36 bets)
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0390 over 213 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 37.5% below 55% threshold (24 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1615
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1595
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1593
- 🚨 Signal EHR negative: -0.0952 over 126 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 37.5% below 55% threshold (24 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1614
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1594
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1592
- 🚨 Signal EHR negative: -0.0952 over 126 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 31.2% below 55% threshold (16 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1702
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1654
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1617
- 🚨 Signal EHR negative: -0.0579 over 95 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1621
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1619
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1612
- 🚨 Signal EHR negative: -0.0211 over 71 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1621
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1619
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1612
- 🚨 Signal EHR negative: -0.0352 over 71 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 15 |
| bybit_linear | connected | 0 |
| polymarket | connected | 0 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 3988 | 10802 | 477 |
| Orderbook age (ms) | 0 | 0 | 538 |

- Cycles: 1037
- Fallback fires (24h): 0
- Engine start: 2026-04-18T16:13:04.820928+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $200.00 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $114.18 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
| hl | $0.00 | $300.0 | ✅ |
| sol_bybit | $0.00 | $300.0 | ✅ |
| sol_hl | $0.00 | $300.0 | ✅ |

## 9. Pipeline Config Snapshot

| Pipeline | Mode | Bet Size | Asset |
|----------|------|---------:|-------|
| btc_15m | paused | default | BTC |
| btc_5m | paper | 25 | BTC |
| bybit | paper | 0.005 | BTC |
| doge_bybit | paper | 1000 | DOGE |
| doge_hl | paper | 1000 | DOGE |
| eth_5m | paper | 25 | ETH |
| eth_bybit | paper | 0.05 | ETH |
| eth_hl | paper | 0.05 | ETH |
| hl | paper | 0.005 | BTC |
| kalshi | paused | default | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
