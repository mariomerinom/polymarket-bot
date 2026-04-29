# Consolidated Daily Report — 2026-04-28

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-28.md](2026-04-28.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 31 |
| Total wins | 17 |
| Total losses | 14 |
| Aggregate WR | 54.8% |
| Total P&L | **+$76.28** |
| Total wagered | $775.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 6 | 83.3% | +$100.77 | +0.019 | -0.019 | $150.00 |
| bybit | BTC | paper | 3 | 66.7% | +$25.00 | +0.045 | — | $75.00 |
| sol_bybit | SOL | paper | 1 | 100.0% | +$25.00 | -0.150 | — | $25.00 |
| sol_hl | SOL | paper | 1 | 100.0% | +$25.00 | -0.150 | — | $25.00 |
| btc_5m | BTC | paper | 3 | 33.3% | -$24.49 | -0.077 | -0.329 | $75.00 |
| eth_bybit | ETH | paper | 7 | 42.9% | -$25.00 | -0.063 | — | $175.00 |
| eth_hl | ETH | paper | 7 | 42.9% | -$25.00 | -0.063 | — | $175.00 |
| hl | BTC | paper | 3 | 33.3% | -$25.00 | -0.167 | — | $75.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.033 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.033 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 9 | 44.4% | -$24.49 | $225.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 20 | 55.0% | +$50.77 | $500.00 |
| **SOL** | sol_bybit, sol_hl | 2 | 100.0% | +$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0768 | -0.3286 | 41 | +25.2¢/$ |
| bybit | +0.0455 | — | 33 | — |
| doge_bybit | -0.0333 | — | 30 | — |
| doge_hl | -0.0333 | — | 30 | — |
| eth_5m | +0.0189 | -0.0193 | 80 | +3.8¢/$ |
| eth_bybit | -0.0634 | — | 71 | — |
| eth_hl | -0.0634 | — | 71 | — |
| hl | -0.1667 | — | 3 | — |
| sol_bybit | -0.1500 | — | 20 | — |
| sol_hl | -0.1500 | — | 20 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 4 | 3 | 100.0% | 66.7% | -0.1558 |
| eth_5m | 6 | 6 | 100.0% | 16.7% | +0.3925 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### eth_bybit
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- 📉 WR declining: 51% → 21% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2247
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2230
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2229
- 🚨 Signal EHR negative: -0.0634 over 71 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- 📉 WR declining: 51% → 21% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2246
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2229
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2228
- 🚨 Signal EHR negative: -0.0634 over 71 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=20

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 11 |
| bybit_linear | connected | 0 |
| polymarket | connected | 1 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 7555 | 26180 | 55 |
| Orderbook age (ms) | 0 | 0 | 735 |

- Cycles: 119
- Fallback fires (24h): 0
- Engine start: 2026-04-28T23:11:36.614784+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $25.00 | $300.0 | ✅ |
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
