# Consolidated Daily Report — 2026-04-23

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-23.md](2026-04-23.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 53 |
| Total wins | 29 |
| Total losses | 24 |
| Aggregate WR | 54.7% |
| Total P&L | **+$125.72** |
| Total wagered | $1,325.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 16 | 56.2% | +$46.96 | +0.028 | +0.028 | $400.00 |
| btc_5m | BTC | live | 1 | 100.0% | +$28.76 | -0.075 | -0.125 | $25.00 |
| eth_bybit | ETH | paper | 15 | 53.3% | +$25.00 | -0.071 | — | $375.00 |
| eth_hl | ETH | paper | 15 | 53.3% | +$25.00 | -0.071 | — | $375.00 |
| hl | BTC | paper | 1 | 100.0% | +$25.00 | -0.050 | — | $25.00 |
| sol_bybit | SOL | paper | 2 | 50.0% | $0.00 | -0.152 | — | $50.00 |
| sol_hl | SOL | paper | 2 | 50.0% | $0.00 | -0.152 | — | $50.00 |
| bybit | BTC | paper | 1 | 0.0% | -$25.00 | -0.038 | — | $25.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.031 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.031 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 3 | 66.7% | +$28.76 | $75.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 46 | 54.3% | +$96.96 | $1,150.00 |
| **SOL** | sol_bybit, sol_hl | 4 | 50.0% | $0.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0749 | -0.1249 | 86 | +5.0¢/$ |
| bybit | -0.0385 | — | 65 | — |
| doge_bybit | -0.0312 | — | 32 | — |
| doge_hl | -0.0312 | — | 32 | — |
| eth_5m | +0.0278 | +0.0276 | 144 | +0.0¢/$ |
| eth_bybit | -0.0714 | — | 98 | — |
| eth_hl | -0.0714 | — | 98 | — |
| hl | -0.0495 | — | 91 | — |
| sol_bybit | -0.1522 | — | 23 | — |
| sol_hl | -0.1522 | — | 23 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 1 | 1 | 100.0% | 0.0% | +0.6175 |
| eth_5m | 16 | 10 | 66.7% | 60.0% | -0.0705 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0749 over 86 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4213
- 🚨 Signal EHR negative: -0.0385 over 65 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=5659

### eth_bybit
- ⚠️ Daily WR 53.3% below 55% threshold (15 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2215
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2214
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2202
- 🚨 Signal EHR negative: -0.0714 over 98 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 53.3% below 55% threshold (15 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2214
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2213
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2201
- 🚨 Signal EHR negative: -0.0714 over 98 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2207
- 🚨 Signal EHR negative: -0.0495 over 91 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2124

### sol_hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2124

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 2 |
| bybit_linear | connected | 0 |
| polymarket | connected | 0 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 7552 | 33625 | 12 |
| Orderbook age (ms) | 0 | 0 | 964 |

- Cycles: 28
- Fallback fires (24h): 0
- Engine start: 2026-04-23T23:51:19.277377+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| eth_5m | $75.00 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
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
