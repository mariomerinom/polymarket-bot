# Consolidated Daily Report — 2026-04-29

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-29.md](2026-04-29.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 217 |
| Total wins | 89 |
| Total losses | 128 |
| Aggregate WR | 41.0% |
| Total P&L | **-$944.78** |
| Total wagered | $5,425.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 19 | 63.2% | +$125.00 | +0.081 | — | $475.00 |
| btc_5m | BTC | paper | 21 | 47.6% | -$6.12 | -0.036 | +0.021 | $525.00 |
| hl | BTC | paper | 28 | 42.9% | -$100.00 | -0.081 | — | $700.00 |
| eth_5m | ETH | paper | 29 | 37.9% | -$163.66 | -0.056 | -0.036 | $725.00 |
| eth_bybit | ETH | paper | 29 | 37.9% | -$175.00 | -0.060 | — | $725.00 |
| eth_hl | ETH | paper | 29 | 37.9% | -$175.00 | -0.060 | — | $725.00 |
| sol_bybit | SOL | paper | 31 | 35.5% | -$225.00 | -0.118 | — | $775.00 |
| sol_hl | SOL | paper | 31 | 35.5% | -$225.00 | -0.118 | — | $775.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 68 | 50.0% | +$18.88 | $1,700.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 87 | 37.9% | -$513.66 | $2,175.00 |
| **SOL** | sol_bybit, sol_hl | 62 | 35.5% | -$450.00 | $1,550.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0361 | +0.0208 | 40 | -5.7¢/$ |
| bybit | +0.0806 | — | 31 | — |
| eth_5m | -0.0560 | -0.0357 | 73 | -2.0¢/$ |
| eth_bybit | -0.0600 | — | 75 | — |
| eth_hl | -0.0600 | — | 75 | — |
| hl | -0.0806 | — | 31 | — |
| sol_bybit | -0.1176 | — | 34 | — |
| sol_hl | -0.1176 | — | 34 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 21 | 21 | 100.0% | 52.4% | +0.0051 |
| eth_5m | 29 | 29 | 100.0% | 62.1% | -0.0815 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 47.6% below 55% threshold (21 bets)

### bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4473
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4462
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4461

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 37.9% below 55% threshold (29 bets)
- ⚠️ Daily P&L $-163.66 — significant loss
- 🚨 Signal EHR negative: -0.0560 over 73 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 37.9% below 55% threshold (29 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2461
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2421
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2401
- 🚨 Signal EHR negative: -0.0600 over 75 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 37.9% below 55% threshold (29 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2460
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2420
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2400
- 🚨 Signal EHR negative: -0.0600 over 75 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 42.9% below 55% threshold (28 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=212
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=165
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=142

### sol_bybit
- ⚠️ Daily WR 35.5% below 55% threshold (31 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2378
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2320
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2316

### sol_hl
- ⚠️ Daily WR 35.5% below 55% threshold (31 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2378
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2320
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2316

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 111 |
| bybit_linear | connected | 0 |
| polymarket | connected | 6 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 7204 | 27607 | 690 |
| Orderbook age (ms) | 0 | 0 | 639 |

- Cycles: 1510
- Fallback fires (24h): 0
- Engine start: 2026-04-29T12:37:56.460297+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $135.79 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $145.99 | $300.0 | ✅ |
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
