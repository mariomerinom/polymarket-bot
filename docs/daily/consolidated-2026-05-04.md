# Consolidated Daily Report — 2026-05-04

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-04.md](2026-05-04.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 78 |
| Total wins | 62 |
| Total losses | 16 |
| Aggregate WR | 79.5% |
| Total P&L | **+$1,191.69** |
| Total wagered | $1,950.00 |
| Pipelines with resolved bets | 9 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 26 | 100.0% | +$693.01 | — | — | $650.00 |
| eth_bybit | ETH | paper | 6 | 83.3% | +$100.00 | -0.075 | — | $150.00 |
| eth_hl | ETH | paper | 6 | 83.3% | +$100.00 | -0.083 | — | $150.00 |
| hl | BTC | paper | 10 | 70.0% | +$100.00 | +0.021 | — | $250.00 |
| bybit | BTC | paper | 7 | 71.4% | +$75.00 | +0.095 | — | $175.00 |
| eth_5m | ETH | paper | 6 | 66.7% | +$72.63 | -0.019 | -0.030 | $150.00 |
| btc_5m | BTC | paper | 9 | 66.7% | +$51.05 | +0.028 | +0.018 | $225.00 |
| sol_bybit | SOL | paper | 4 | 50.0% | $0.00 | -0.078 | — | $100.00 |
| sol_hl | SOL | paper | 4 | 50.0% | $0.00 | -0.071 | — | $100.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.250 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.125 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 52 | 84.6% | +$919.06 | $1,300.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 18 | 77.8% | +$272.63 | $450.00 |
| **SOL** | sol_bybit, sol_hl | 8 | 50.0% | $0.00 | $200.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0278 | +0.0185 | 97 | +0.9¢/$ |
| bybit | +0.0949 | — | 79 | — |
| doge_bybit | +0.2500 | — | 8 | — |
| doge_hl | +0.1250 | — | 8 | — |
| eth_5m | -0.0194 | -0.0300 | 108 | +1.1¢/$ |
| eth_bybit | -0.0755 | — | 139 | — |
| eth_hl | -0.0827 | — | 139 | — |
| hl | +0.0214 | — | 117 | — |
| sol_bybit | -0.0776 | — | 116 | — |
| sol_hl | -0.0714 | — | 119 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 7 | 7 | 100.0% | 42.9% | -0.0139 |
| eth_5m | 6 | 6 | 100.0% | 33.3% | +0.0604 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7568; 1 conv>=3 prediction(s) with no order: ids=7544

### bybit
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=5742; 1 conv>=3 prediction(s) with no order: ids=5730; 1 conv>=3 prediction(s) with no order: ids=5702; +1 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7015; 1 conv>=3 prediction(s) with no order: ids=7013; 1 conv>=3 prediction(s) with no order: ids=6991; +1 more
- 🚨 Signal EHR negative: -0.0194 over 108 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3533; 1 conv>=3 prediction(s) with no order: ids=3427; 1 conv>=3 prediction(s) with no order: ids=3421; +1 more
- 🚨 Signal EHR negative: -0.0755 over 139 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3532; 1 conv>=3 prediction(s) with no order: ids=3426; 1 conv>=3 prediction(s) with no order: ids=3420; +1 more
- 🚨 Signal EHR negative: -0.0827 over 139 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no order: ids=1214; 1 conv>=3 prediction(s) with no order: ids=1200; 1 conv>=3 prediction(s) with no order: ids=1192

### sol_bybit
- 📉 WR declining: 59% → 43% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3460
- 🚨 Signal EHR negative: -0.0776 over 116 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- 📉 WR declining: 59% → 44% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3460
- 🚨 Signal EHR negative: -0.0714 over 119 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 62 |
| bybit_linear | connected | 83 |
| polymarket | connected | 65 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 65724 | 210073 | 145 |
| Orderbook age (ms) | 0 | 0 | 770 |

- Cycles: 303
- Fallback fires (24h): 10
- Engine start: 2026-05-04T19:14:44.379338+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_bybit | $0.00 | $300.0 | No |
| eth_hl | $0.00 | $300.0 | No |
| hl | $0.00 | $300.0 | No |
| sol_bybit | $0.00 | $300.0 | No |
| sol_hl | $0.00 | $300.0 | No |

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
| kalshi | paper | 25 | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
