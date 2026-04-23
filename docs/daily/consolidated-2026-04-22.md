# Consolidated Daily Report — 2026-04-22

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-22.md](2026-04-22.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 105 |
| Total wins | 45 |
| Total losses | 60 |
| Aggregate WR | 42.9% |
| Total P&L | **-$361.64** |
| Total wagered | $2,625.00 |
| Active pipelines | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 9 | 55.6% | +$25.00 | -0.030 | — | $225.00 |
| eth_bybit | ETH | paper | 23 | 47.8% | -$25.00 | -0.084 | — | $575.00 |
| eth_hl | ETH | paper | 23 | 47.8% | -$25.00 | -0.084 | — | $575.00 |
| btc_5m | BTC | live | 15 | 40.0% | -$71.65 | -0.087 | -0.125 | $375.00 |
| hl | BTC | paper | 15 | 33.3% | -$125.00 | -0.065 | — | $375.00 |
| eth_5m | ETH | paper | 20 | 35.0% | -$139.99 | +0.013 | +0.056 | $500.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.031 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.031 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.167 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.167 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 39 | 41.0% | -$171.65 | $975.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 66 | 43.9% | -$189.99 | $1,650.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0870 | -0.1249 | 86 | +3.8¢/$ |
| bybit | -0.0303 | — | 66 | — |
| doge_bybit | -0.0312 | — | 32 | — |
| doge_hl | -0.0312 | — | 32 | — |
| eth_5m | +0.0125 | +0.0558 | 161 | -4.3¢/$ |
| eth_bybit | -0.0842 | — | 101 | — |
| eth_hl | -0.0842 | — | 101 | — |
| hl | -0.0652 | — | 92 | — |
| sol_bybit | -0.1667 | — | 21 | — |
| sol_hl | -0.1667 | — | 21 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 15 | 15 | 100.0% | 60.0% | -0.0742 |
| eth_5m | 20 | 20 | 100.0% | 65.0% | -0.1176 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 40.0% below 55% threshold (15 bets)
- 🚨 5 consecutive losing days
- 📉 WR declining: 47% → 36% over 7 days
- 🚨 174 integrity check failure(s) today
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0870 over 86 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4254
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4148
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4147
- 🚨 Signal EHR negative: -0.0303 over 66 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 35.0% below 55% threshold (20 bets)
- ⚠️ Daily P&L $-139.99 — significant loss
- 📉 WR declining: 57% → 47% over 7 days
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### eth_bybit
- ⚠️ Daily WR 47.8% below 55% threshold (23 bets)
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2042
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2041
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2032
- 🚨 Signal EHR negative: -0.0842 over 101 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 47.8% below 55% threshold (23 bets)
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2041
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2040
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2031
- 🚨 Signal EHR negative: -0.0842 over 101 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 33.3% below 55% threshold (15 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 52% → 35% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2247
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2150
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2149
- 🚨 Signal EHR negative: -0.0652 over 92 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 16 |
| bybit_linear | connected | 0 |
| polymarket | connected | 7 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 6342 | 10289 | 265 |
| Orderbook age (ms) | 0 | 0 | 717 |

- Cycles: 579
- Fallback fires (24h): 0
- Engine start: 2026-04-22T19:43:58.784198+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $37.24 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
| hl | $0.00 | $300.0 | ✅ |

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
