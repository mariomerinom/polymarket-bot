# Consolidated Daily Report — 2026-04-21

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-21.md](2026-04-21.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 249 |
| Total wins | 108 |
| Total losses | 141 |
| Aggregate WR | 43.4% |
| Total P&L | **-$813.70** |
| Total wagered | $6,225.00 |
| Active pipelines | 10 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 36 | 55.6% | +$109.63 | +0.004 | +0.012 | $900.00 |
| bybit | BTC | paper | 21 | 57.1% | +$75.00 | -0.044 | — | $525.00 |
| doge_bybit | DOGE | paper | 30 | 46.7% | -$50.00 | -0.028 | — | $750.00 |
| doge_hl | DOGE | paper | 30 | 46.7% | -$50.00 | -0.028 | — | $750.00 |
| hl | BTC | paper | 25 | 44.0% | -$75.00 | -0.031 | — | $625.00 |
| btc_5m | BTC | live | 23 | 39.1% | -$123.33 | -0.086 | -0.125 | $575.00 |
| eth_bybit | ETH | paper | 25 | 36.0% | -$175.00 | -0.081 | — | $625.00 |
| eth_hl | ETH | paper | 25 | 36.0% | -$175.00 | -0.081 | — | $625.00 |
| sol_bybit | SOL | paper | 17 | 29.4% | -$175.00 | -0.068 | — | $425.00 |
| sol_hl | SOL | paper | 17 | 29.4% | -$175.00 | -0.068 | — | $425.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 69 | 46.4% | -$123.33 | $1,725.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 86 | 44.2% | -$240.37 | $2,150.00 |
| **SOL** | sol_bybit, sol_hl | 34 | 29.4% | -$350.00 | $850.00 |
| **DOGE** | doge_bybit, doge_hl | 60 | 46.7% | -$100.00 | $1,500.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0859 | -0.1249 | 71 | +3.9¢/$ |
| bybit | -0.0439 | — | 57 | — |
| doge_bybit | -0.0283 | — | 53 | — |
| doge_hl | -0.0283 | — | 53 | — |
| eth_5m | +0.0040 | +0.0123 | 182 | -0.8¢/$ |
| eth_bybit | -0.0812 | — | 117 | — |
| eth_hl | -0.0812 | — | 117 | — |
| hl | -0.0312 | — | 96 | — |
| sol_bybit | -0.0682 | — | 44 | — |
| sol_hl | -0.0682 | — | 44 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 23 | 23 | 100.0% | 60.9% | -0.1024 |
| eth_5m | 36 | 36 | 100.0% | 44.4% | +0.0647 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 39.1% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-123.33 — significant loss
- 🚨 4 consecutive losing days
- 📉 WR declining: 47% → 34% over 7 days
- ⚠️ Circuit breaker at 60% ($180 / $300)
- 🚨 24 integrity check failure(s) today
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0859 over 71 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3828
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3826
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3819
- 🚨 Signal EHR negative: -0.0439 over 57 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ⚠️ Daily WR 46.7% below 55% threshold (30 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1226
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1225
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1224
- 🚨 Signal EHR negative: -0.0283 over 53 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ⚠️ Daily WR 46.7% below 55% threshold (30 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1785
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1784
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1783
- 🚨 Signal EHR negative: -0.0283 over 53 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- 📉 WR declining: 59% → 49% over 7 days
- 🚨 2 integrity check failure(s) today
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### eth_bybit
- ⚠️ Daily WR 36.0% below 55% threshold (25 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 48% → 36% over 7 days
- 🚨 73 integrity check failure(s) today
- 🚨 Signal EHR negative: -0.0812 over 117 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 36.0% below 55% threshold (25 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 48% → 36% over 7 days
- 🚨 25 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1815
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1814
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1786
- 🚨 Signal EHR negative: -0.0812 over 117 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 44.0% below 55% threshold (25 bets)
- 🚨 8 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1847
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1845
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1839
- 🚨 Signal EHR negative: -0.0312 over 96 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 29.4% below 55% threshold (17 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1731
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1730
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1721

### sol_hl
- ⚠️ Daily WR 29.4% below 55% threshold (17 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1731
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1730
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1721

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 1 |
| bybit_linear | connected | 0 |
| polymarket | connected | 0 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 7171 | 10861 | 15 |
| Orderbook age (ms) | 0 | 0 | 60 |

- Cycles: 33
- Fallback fires (24h): 0
- Engine start: 2026-04-21T23:54:43.719364+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $180.26 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| doge_bybit | $0.00 | $300.0 | ✅ |
| doge_hl | $0.00 | $300.0 | ✅ |
| eth_5m | $161.18 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
| hl | $0.00 | $300.0 | ✅ |
| sol_bybit | $0.00 | $300.0 | ✅ |
| sol_hl | $0.00 | $300.0 | ✅ |

## 9. Pipeline Config Snapshot

| Pipeline | Mode | Bet Size | Asset |
|----------|------|---------:|-------|
| btc_15m | paused | default | BTC |
| btc_5m | live | 25 | BTC |
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
