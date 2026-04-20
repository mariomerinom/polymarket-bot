# Consolidated Daily Report — 2026-04-19

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-19.md](2026-04-19.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 198 |
| Total wins | 82 |
| Total losses | 116 |
| Aggregate WR | 41.4% |
| Total P&L | **-$832.34** |
| Total wagered | $4,950.00 |
| Active pipelines | 10 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| hl | BTC | paper | 28 | 57.1% | +$100.00 | -0.025 | — | $700.00 |
| bybit | BTC | paper | 23 | 52.2% | +$25.00 | -0.092 | — | $575.00 |
| doge_bybit | DOGE | paper | 11 | 54.5% | +$25.00 | +0.000 | — | $275.00 |
| doge_hl | DOGE | paper | 11 | 54.5% | +$25.00 | -0.056 | — | $275.00 |
| btc_5m | BTC | paper | 19 | 47.4% | -$16.49 | -0.065 | -0.050 | $475.00 |
| sol_bybit | SOL | paper | 11 | 27.3% | -$125.00 | -0.038 | — | $275.00 |
| sol_hl | SOL | paper | 11 | 27.3% | -$125.00 | -0.051 | — | $275.00 |
| eth_5m | ETH | paper | 36 | 36.1% | -$240.85 | -0.037 | -0.037 | $900.00 |
| eth_bybit | ETH | paper | 24 | 29.2% | -$250.00 | -0.107 | — | $600.00 |
| eth_hl | ETH | paper | 24 | 29.2% | -$250.00 | -0.107 | — | $600.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 70 | 52.9% | +$108.51 | $1,750.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 84 | 32.1% | -$740.85 | $2,100.00 |
| **SOL** | sol_bybit, sol_hl | 22 | 27.3% | -$250.00 | $550.00 |
| **DOGE** | doge_bybit, doge_hl | 22 | 54.5% | +$50.00 | $550.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0651 | -0.0499 | 72 | -1.5¢/$ |
| bybit | -0.0921 | — | 76 | — |
| doge_bybit | +0.0000 | — | 34 | — |
| doge_hl | -0.0556 | — | 72 | — |
| eth_5m | -0.0367 | -0.0369 | 216 | +0.0¢/$ |
| eth_bybit | -0.1069 | — | 145 | — |
| eth_hl | -0.1069 | — | 145 | — |
| hl | -0.0250 | — | 120 | — |
| sol_bybit | -0.0385 | — | 78 | — |
| sol_hl | -0.0513 | — | 78 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 19 | 19 | 100.0% | 52.6% | +0.0230 |
| eth_5m | 36 | 36 | 100.0% | 63.9% | -0.0992 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 47.4% below 55% threshold (19 bets)
- 🚨 5 consecutive losing days
- ⚠️ Circuit breaker at 61% ($184 / $300)
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0651 over 72 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 52.2% below 55% threshold (23 bets)
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3956
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3955
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3954
- 🚨 Signal EHR negative: -0.0921 over 76 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ⚠️ Daily WR 54.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1140
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1139
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1138

### doge_hl
- ⚠️ Daily WR 54.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1699
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1698
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1697
- 🚨 Signal EHR negative: -0.0556 over 72 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ Daily WR 36.1% below 55% threshold (36 bets)
- ⚠️ Daily P&L $-240.85 — significant loss
- ⚠️ Circuit breaker at 71% ($214 / $300)
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0367 over 216 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 29.2% below 55% threshold (24 bets)
- ⚠️ Daily P&L $-250.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1898
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1823
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1805
- 🚨 Signal EHR negative: -0.1069 over 145 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 29.2% below 55% threshold (24 bets)
- ⚠️ Daily P&L $-250.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1897
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1822
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1804
- 🚨 Signal EHR negative: -0.1069 over 145 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1964
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1963
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1962
- 🚨 Signal EHR negative: -0.0250 over 120 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 27.3% below 55% threshold (11 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- 📉 WR declining: 51% → 36% over 7 days
- 🚨 24 integrity check failure(s) today
- 🚨 Signal EHR negative: -0.0385 over 78 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 27.3% below 55% threshold (11 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- 📉 WR declining: 51% → 36% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1760
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1690
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1689
- 🚨 Signal EHR negative: -0.0513 over 78 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 45 |
| bybit_linear | connected | 0 |
| polymarket | connected | 1 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 4282 | 11899 | 705 |
| Orderbook age (ms) | 0 | 0 | 649 |

- Cycles: 2608
- Fallback fires (24h): 0
- Engine start: 2026-04-19T04:00:02.133386+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $183.50 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| doge_bybit | $0.00 | $300.0 | ✅ |
| doge_hl | $0.00 | $300.0 | ✅ |
| eth_5m | $213.95 | $300.0 | ✅ |
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
