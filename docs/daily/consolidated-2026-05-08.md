# Consolidated Daily Report — 2026-05-08

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-08.md](2026-05-08.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 127 |
| Total wins | 91 |
| Total losses | 36 |
| Aggregate WR | 71.7% |
| Total P&L | **+$1,461.86** |
| Total wagered | $3,175.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 51 | 100.0% | +$1,389.91 | — | — | $1,275.00 |
| btc_5m | BTC | paper | 8 | 75.0% | +$72.68 | +0.073 | -0.163 | $200.00 |
| bybit | BTC | paper | 8 | 62.5% | +$50.00 | +0.103 | — | $200.00 |
| sol_bybit | SOL | paper | 2 | 100.0% | +$50.00 | -0.030 | — | $50.00 |
| sol_hl | SOL | paper | 2 | 100.0% | +$50.00 | -0.035 | — | $50.00 |
| doge_bybit | DOGE | paper | 2 | 50.0% | $0.00 | +0.115 | — | $50.00 |
| doge_hl | DOGE | paper | 2 | 50.0% | $0.00 | +0.000 | — | $50.00 |
| eth_hl | ETH | paper | 16 | 50.0% | $0.00 | -0.044 | — | $400.00 |
| hl | BTC | paper | 11 | 45.5% | -$25.00 | +0.086 | — | $275.00 |
| eth_5m | ETH | paper | 9 | 44.4% | -$25.73 | -0.016 | -0.068 | $225.00 |
| eth_bybit | ETH | paper | 16 | 37.5% | -$100.00 | -0.060 | — | $400.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 78 | 85.9% | +$1,487.59 | $1,950.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 41 | 43.9% | -$125.73 | $1,025.00 |
| **SOL** | sol_bybit, sol_hl | 4 | 100.0% | +$100.00 | $100.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 50.0% | $0.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0728 | -0.1633 | 65 | +23.6¢/$ |
| bybit | +0.1029 | — | 68 | — |
| doge_bybit | +0.1154 | — | 13 | — |
| doge_hl | +0.0000 | — | 14 | — |
| eth_5m | -0.0164 | -0.0684 | 91 | +5.2¢/$ |
| eth_bybit | -0.0600 | — | 150 | — |
| eth_hl | -0.0442 | — | 147 | — |
| hl | +0.0862 | — | 87 | — |
| sol_bybit | -0.0301 | — | 83 | — |
| sol_hl | -0.0349 | — | 86 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 7 | 7 | 100.0% | 28.6% | +0.0511 |
| eth_5m | 9 | 9 | 100.0% | 55.6% | -0.1047 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no order: ids=8288; 1 conv>=3 prediction(s) with no order: ids=8255; 1 conv>=3 prediction(s) with no order: ids=8197

### bybit
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6762; 1 conv>=3 prediction(s) with no order: ids=6761; 1 conv>=3 prediction(s) with no order: ids=6760; +2 more
- 🧯 side/regime promotion guardrail: DOWN in HIGH_VOL / TRENDING is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### doge_bybit
- 📉 WR declining: 67% → 50% over 7 days

### eth_5m
- ⚠️ Daily WR 44.4% below 55% threshold (9 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 61% → 43% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7688
- 🚨 Signal EHR negative: -0.0164 over 91 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 20.0% WR on 5 bets ($-72.92); require cohort review before promotion

### eth_bybit
- ⚠️ Daily WR 37.5% below 55% threshold (16 bets)
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4209; 1 conv>=3 prediction(s) with no order: ids=4207; 1 conv>=3 prediction(s) with no order: ids=4173; +5 more
- 🚨 Signal EHR negative: -0.0600 over 150 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 28.6% WR on 14 bets ($-150.00); require cohort review before promotion

### eth_hl
- ⚠️ Daily WR 50.0% below 55% threshold (16 bets)
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4208; 1 conv>=3 prediction(s) with no order: ids=4206; 1 conv>=3 prediction(s) with no order: ids=4172; +5 more
- 🚨 Signal EHR negative: -0.0442 over 147 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 14 bets ($-50.00); require cohort review before promotion

### hl
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no order: ids=1929; 1 conv>=3 prediction(s) with no order: ids=1923; 1 conv>=3 prediction(s) with no order: ids=1922; +4 more
- 🧯 side/regime promotion guardrail: UP in HIGH_VOL / TRENDING is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### kalshi
- 📉 WR declining: 100% → 50% over 7 days

### sol_bybit
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4121
- 🚨 Signal EHR negative: -0.0301 over 83 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4121
- 🚨 Signal EHR negative: -0.0349 over 86 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 25 |
| bybit_linear | connected | 37 |
| polymarket | connected | 22 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 79422 | 287511 | 68 |
| Orderbook age (ms) | 0 | 0 | 934 |

- Cycles: 142
- Fallback fires (24h): 4
- Engine start: 2026-05-08T21:30:33.780748+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $55.13 | $300.0 | No |
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
