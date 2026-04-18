# Consolidated Daily Report — 2026-04-17

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-17.md](2026-04-17.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 188 |
| Total wins | 59 |
| Total losses | 129 |
| Aggregate WR | 31.4% |
| Total P&L | **-$1,735.76** |
| Total wagered | $4,700.00 |
| Active pipelines | 10 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 17 | 70.6% | +$190.27 | -0.007 | -0.031 | $425.00 |
| hl | BTC | paper | 24 | 58.3% | +$100.00 | -0.032 | — | $600.00 |
| btc_15m | BTC | paper | 8 | 50.0% | +$0.72 | -0.050 | -0.058 | $200.00 |
| bybit | BTC | paper | 14 | 50.0% | $0.00 | +0.000 | — | $350.00 |
| doge_bybit | DOGE | paper | 2 | 50.0% | $0.00 | -0.022 | — | $50.00 |
| doge_hl | DOGE | paper | 2 | 50.0% | $0.00 | -0.067 | — | $50.00 |
| eth_bybit | ETH | paper | 10 | 50.0% | $0.00 | -0.088 | — | $250.00 |
| eth_hl | ETH | paper | 10 | 50.0% | $0.00 | -0.088 | — | $250.00 |
| btc_5m | BTC | paper | 21 | 47.6% | -$26.75 | +0.035 | +0.055 | $525.00 |
| kalshi | BTC | paused | 80 | 0.0% | -$2,000.00 | — | — | $2,000.00 |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.033 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_15m, btc_5m, bybit, hl, kalshi | 147 | 23.8% | -$1,926.03 | $3,675.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 37 | 59.5% | +$190.27 | $925.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 50.0% | $0.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_15m | -0.0495 | -0.0578 | 29 | +0.8¢/$ |
| btc_5m | +0.0348 | +0.0550 | 107 | -2.0¢/$ |
| bybit | +0.0000 | — | 78 | — |
| doge_bybit | -0.0217 | — | 23 | — |
| doge_hl | -0.0672 | — | 67 | — |
| eth_5m | -0.0074 | -0.0314 | 224 | +2.4¢/$ |
| eth_bybit | -0.0882 | — | 102 | — |
| eth_hl | -0.0882 | — | 102 | — |
| hl | -0.0316 | — | 79 | — |
| sol_bybit | -0.0167 | — | 60 | — |
| sol_hl | -0.0333 | — | 60 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_15m | 9 | 0 | — | — | — |
| btc_5m | 19 | 0 | — | — | — |
| eth_5m | 17 | 0 | — | — | — |

## 6. Alerts (All Pipelines)

### btc_15m
- ⚠️ Daily WR 50.0% below 55% threshold (8 bets)
- 📉 WR declining: 47% → 33% over 7 days

### btc_5m
- ⚠️ Daily WR 47.6% below 55% threshold (21 bets)
- 🚨 4 consecutive losing days
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### bybit
- ⚠️ Daily WR 50.0% below 55% threshold (14 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3407
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3406
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3404

### doge_bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=751

### doge_hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1310
- 🚨 Signal EHR negative: -0.0672 over 67 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0074 over 224 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1203
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1202
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1201
- 🚨 Signal EHR negative: -0.0882 over 102 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 50.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1203
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1202
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1201
- 🚨 Signal EHR negative: -0.0882 over 102 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1459
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1458
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1456
- 🚨 Signal EHR negative: -0.0316 over 79 bets (7-day) — model may be buying overpriced contracts

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (80 bets)
- ⚠️ Daily P&L $-2000.00 — significant loss
- 🚨 4 consecutive losing days
- 📉 WR declining: 16% → 0% over 7 days

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0167 over 60 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0333 over 60 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 0 |
| bybit_linear | connected | 0 |
| polymarket | connected | 0 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 0 | 0 | 0 |
| Orderbook age (ms) | 0 | 0 | 170 |

- Cycles: 0
- Fallback fires (24h): 0
- Engine start: 2026-04-18T00:05:49.506381+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_15m | $50.00 | $300.0 | ✅ |
| btc_5m | $113.79 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| doge_bybit | $0.00 | $300.0 | ✅ |
| doge_hl | $0.00 | $300.0 | ✅ |
| eth_5m | $25.00 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
| hl | $0.00 | $300.0 | ✅ |

## 9. Pipeline Config Snapshot

| Pipeline | Mode | Bet Size | Asset |
|----------|------|---------:|-------|
| btc_15m | paper | default | BTC |
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
