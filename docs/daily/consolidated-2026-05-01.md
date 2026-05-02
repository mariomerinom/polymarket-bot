# Consolidated Daily Report — 2026-05-01

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-01.md](2026-05-01.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 159 |
| Total wins | 65 |
| Total losses | 94 |
| Aggregate WR | 40.9% |
| Total P&L | **-$698.68** |
| Total wagered | $3,975.00 |
| Active pipelines | 10 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| doge_bybit | DOGE | paper | 2 | 100.0% | +$50.00 | +0.500 | — | $50.00 |
| eth_5m | ETH | paper | 15 | 46.7% | +$14.66 | -0.081 | -0.066 | $375.00 |
| bybit | BTC | paper | 16 | 50.0% | $0.00 | +0.090 | — | $400.00 |
| doge_hl | DOGE | paper | 2 | 50.0% | $0.00 | +0.000 | — | $50.00 |
| btc_5m | BTC | paper | 12 | 50.0% | -$13.34 | +0.032 | +0.066 | $300.00 |
| hl | BTC | paper | 20 | 45.0% | -$50.00 | -0.011 | — | $500.00 |
| sol_bybit | SOL | paper | 13 | 30.8% | -$125.00 | -0.125 | — | $325.00 |
| sol_hl | SOL | paper | 15 | 26.7% | -$175.00 | -0.136 | — | $375.00 |
| eth_bybit | ETH | paper | 32 | 37.5% | -$200.00 | -0.109 | — | $800.00 |
| eth_hl | ETH | paper | 32 | 37.5% | -$200.00 | -0.109 | — | $800.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paper | 0 | — | $0.00 | — | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 48 | 47.9% | -$63.34 | $1,200.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 79 | 39.2% | -$385.34 | $1,975.00 |
| **SOL** | sol_bybit, sol_hl | 28 | 28.6% | -$300.00 | $700.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 75.0% | +$50.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0316 | +0.0664 | 69 | -3.5¢/$ |
| bybit | +0.0902 | — | 61 | — |
| doge_bybit | +0.5000 | — | 2 | — |
| doge_hl | +0.0000 | — | 2 | — |
| eth_5m | -0.0813 | -0.0664 | 74 | -1.5¢/$ |
| eth_bybit | -0.1092 | — | 87 | — |
| eth_hl | -0.1092 | — | 87 | — |
| hl | -0.0114 | — | 88 | — |
| sol_bybit | -0.1250 | — | 64 | — |
| sol_hl | -0.1364 | — | 66 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 11 | 11 | 100.0% | 54.5% | -0.0293 |
| eth_5m | 14 | 14 | 100.0% | 57.1% | -0.0187 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 50.0% below 55% threshold (12 bets)

### bybit
- ⚠️ Daily WR 50.0% below 55% threshold (16 bets)
- 🚨 44 integrity check failure(s) today

### eth_5m
- ⚠️ Daily WR 46.7% below 55% threshold (15 bets)
- 📉 WR declining: 61% → 39% over 7 days
- 🚨 Signal EHR negative: -0.0813 over 74 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 37.5% below 55% threshold (32 bets)
- ⚠️ Daily P&L $-200.00 — significant loss
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3004
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3003
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3002
- 🚨 Signal EHR negative: -0.1092 over 87 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 37.5% below 55% threshold (32 bets)
- ⚠️ Daily P&L $-200.00 — significant loss
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3003
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3002
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3001
- 🚨 Signal EHR negative: -0.1092 over 87 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 45.0% below 55% threshold (20 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=674
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=667
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=665
- 🚨 Signal EHR negative: -0.0114 over 88 bets (7-day) — model may be buying overpriced contracts

### kalshi
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ⚠️ Daily WR 30.8% below 55% threshold (13 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 68% → 36% over 7 days
- 🚨 17 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3016
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2906
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2882
- 🚨 Signal EHR negative: -0.1250 over 64 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 26.7% below 55% threshold (15 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 68% → 34% over 7 days
- 🚨 17 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3016
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2906
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2906
- 🚨 Signal EHR negative: -0.1364 over 66 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 37 |
| bybit_linear | connected | 43 |
| polymarket | connected | 22 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 28595 | 197311 | 107 |
| Orderbook age (ms) | 0 | 0 | 835 |

- Cycles: 234
- Fallback fires (24h): 2
- Engine start: 2026-05-01T21:31:07.402864+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $122.48 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| doge_bybit | $0.00 | $300.0 | ✅ |
| doge_hl | $0.00 | $300.0 | ✅ |
| eth_5m | $63.92 | $300.0 | ✅ |
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
| kalshi | paper | 25 | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
