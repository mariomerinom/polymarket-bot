# Consolidated Daily Report — 2026-05-07

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-07.md](2026-05-07.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 68 |
| Total wins | 42 |
| Total losses | 26 |
| Aggregate WR | 61.8% |
| Total P&L | **+$393.11** |
| Total wagered | $1,700.00 |
| Pipelines with resolved bets | 9 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 23 | 87.0% | +$470.69 | — | — | $575.00 |
| hl | BTC | paper | 8 | 87.5% | +$150.00 | +0.093 | — | $200.00 |
| bybit | BTC | paper | 4 | 75.0% | +$50.00 | +0.102 | — | $100.00 |
| btc_5m | BTC | paper | 3 | 100.0% | +$33.31 | +0.071 | +0.017 | $75.00 |
| doge_bybit | DOGE | paper | 2 | 0.0% | -$50.00 | +0.136 | — | $50.00 |
| doge_hl | DOGE | paper | 2 | 0.0% | -$50.00 | +0.000 | — | $50.00 |
| eth_bybit | ETH | paper | 8 | 37.5% | -$50.00 | -0.053 | — | $200.00 |
| eth_hl | ETH | paper | 8 | 37.5% | -$50.00 | -0.050 | — | $200.00 |
| eth_5m | ETH | paper | 10 | 30.0% | -$110.89 | -0.050 | -0.055 | $250.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.050 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.053 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 38 | 86.8% | +$704.00 | $950.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 26 | 34.6% | -$210.89 | $650.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 0.0% | -$100.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0713 | +0.0167 | 89 | +5.5¢/$ |
| bybit | +0.1024 | — | 83 | — |
| doge_bybit | +0.1364 | — | 11 | — |
| doge_hl | +0.0000 | — | 12 | — |
| eth_5m | -0.0503 | -0.0548 | 105 | +0.5¢/$ |
| eth_bybit | -0.0526 | — | 152 | — |
| eth_hl | -0.0503 | — | 149 | — |
| hl | +0.0929 | — | 113 | — |
| sol_bybit | -0.0500 | — | 100 | — |
| sol_hl | -0.0534 | — | 103 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 1 | 1 | 100.0% | 0.0% | +0.0175 |
| eth_5m | 7 | 7 | 100.0% | 57.1% | -0.0579 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=8057

### bybit
- 🚨 1 integrity check failure(s) today

### doge_bybit
- 📉 WR declining: 83% → 56% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3400

### doge_hl
- 📉 WR declining: 61% → 33% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3959

### eth_5m
- ⚠️ Daily WR 30.0% below 55% threshold (10 bets)
- ⚠️ Daily P&L $-110.89 — significant loss
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7549; 1 conv>=3 prediction(s) with no order: ids=7523; 1 conv>=3 prediction(s) with no order: ids=7522; +1 more
- 🚨 Signal EHR negative: -0.0503 over 105 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 33.3% WR on 9 bets ($-85.89); require cohort review before promotion

### eth_bybit
- ⚠️ Daily WR 37.5% below 55% threshold (8 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4071; 1 conv>=3 prediction(s) with no order: ids=4061; 1 conv>=3 prediction(s) with no order: ids=4021; +3 more
- 🚨 Signal EHR negative: -0.0526 over 152 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 37.5% below 55% threshold (8 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4070; 1 conv>=3 prediction(s) with no order: ids=4060; 1 conv>=3 prediction(s) with no order: ids=4020; +3 more
- 🚨 Signal EHR negative: -0.0503 over 149 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no order: ids=1775; 1 conv>=3 prediction(s) with no order: ids=1752

### kalshi
- 📉 WR declining: 100% → 33% over 7 days

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0500 over 100 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0534 over 103 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 47 |
| bybit_linear | disconnected | 72 |
| polymarket | disconnected | 65 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 65472 | 253962 | 129 |
| Orderbook age (ms) | 0 | 0 | 625 |

- Cycles: 271
- Fallback fires (24h): 10
- Engine start: 2026-05-07T19:21:37.683796+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $5.70 | $300.0 | No |
| eth_bybit | $0.00 | $300.0 | No |
| eth_hl | $0.00 | $300.0 | No |
| hl | $0.00 | $300.0 | No |

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
