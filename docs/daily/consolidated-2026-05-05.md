# Consolidated Daily Report — 2026-05-05

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-05.md](2026-05-05.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 97 |
| Total wins | 44 |
| Total losses | 53 |
| Aggregate WR | 45.4% |
| Total P&L | **-$266.52** |
| Total wagered | $2,425.00 |
| Pipelines with resolved bets | 10 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_bybit | ETH | paper | 11 | 81.8% | +$175.00 | -0.047 | — | $275.00 |
| eth_hl | ETH | paper | 11 | 81.8% | +$175.00 | -0.053 | — | $275.00 |
| eth_5m | ETH | paper | 8 | 75.0% | +$58.48 | -0.005 | +0.002 | $200.00 |
| sol_bybit | SOL | paper | 14 | 57.1% | +$50.00 | -0.061 | — | $350.00 |
| hl | BTC | paper | 5 | 60.0% | +$25.00 | +0.025 | — | $125.00 |
| sol_hl | SOL | paper | 13 | 53.8% | +$25.00 | -0.061 | — | $325.00 |
| bybit | BTC | paper | 5 | 40.0% | -$25.00 | +0.083 | — | $125.00 |
| doge_hl | DOGE | paper | 1 | 0.0% | -$25.00 | +0.056 | — | $25.00 |
| btc_5m | BTC | paper | 2 | 0.0% | -$50.00 | +0.018 | +0.018 | $50.00 |
| kalshi | BTC | paper | 27 | 0.0% | -$675.00 | — | — | $675.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.250 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 39 | 12.8% | -$725.00 | $975.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 30 | 80.0% | +$408.48 | $750.00 |
| **SOL** | sol_bybit, sol_hl | 27 | 55.6% | +$75.00 | $675.00 |
| **DOGE** | doge_hl | 1 | 0.0% | -$25.00 | $25.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0182 | +0.0185 | 99 | -0.0¢/$ |
| bybit | +0.0833 | — | 84 | — |
| doge_bybit | +0.2500 | — | 8 | — |
| doge_hl | +0.0556 | — | 9 | — |
| eth_5m | -0.0052 | +0.0024 | 116 | -0.8¢/$ |
| eth_bybit | -0.0467 | — | 150 | — |
| eth_hl | -0.0533 | — | 150 | — |
| hl | +0.0246 | — | 122 | — |
| sol_bybit | -0.0615 | — | 130 | — |
| sol_hl | -0.0606 | — | 132 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 2 | 2 | 100.0% | 100.0% | -0.3675 |
| eth_5m | 7 | 7 | 100.0% | 14.3% | +0.1339 |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 52% → 40% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7715

### bybit
- ⚠️ Daily WR 40.0% below 55% threshold (5 bets)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6047; 1 conv>=3 prediction(s) with no order: ids=6046; 1 conv>=3 prediction(s) with no order: ids=6045; +1 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- 📉 WR declining: 58% → 33% over 7 days

### eth_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7210
- 🚨 Signal EHR negative: -0.0052 over 116 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3740; 1 conv>=3 prediction(s) with no order: ids=3700; 1 conv>=3 prediction(s) with no order: ids=3699; +4 more
- 🚨 Signal EHR negative: -0.0467 over 150 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3739; 1 conv>=3 prediction(s) with no order: ids=3699; 1 conv>=3 prediction(s) with no order: ids=3698; +4 more
- 🚨 Signal EHR negative: -0.0533 over 150 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no order: ids=1440; 1 conv>=3 prediction(s) with no order: ids=1439; 1 conv>=3 prediction(s) with no order: ids=1369

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (27 bets)
- ⚠️ Daily P&L $-675.00 — significant loss
- 📉 WR declining: 100% → 50% over 7 days

### sol_bybit
- 🚨 28 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3582
- 🚨 Signal EHR negative: -0.0615 over 130 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 53.8% below 55% threshold (13 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3711; 1 conv>=3 prediction(s) with no order: ids=3697; 1 conv>=3 prediction(s) with no order: ids=3696; +3 more
- 🚨 Signal EHR negative: -0.0606 over 132 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 78 |
| bybit_linear | connected | 130 |
| polymarket | connected | 88 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 69664 | 206845 | 204 |
| Orderbook age (ms) | 0 | 0 | 961 |

- Cycles: 426
- Fallback fires (24h): 14
- Engine start: 2026-05-05T16:57:37.200329+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $0.00 | $300.0 | No |
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
