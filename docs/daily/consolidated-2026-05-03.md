# Consolidated Daily Report — 2026-05-03

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-03.md](2026-05-03.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 130 |
| Total wins | 58 |
| Total losses | 72 |
| Aggregate WR | 44.6% |
| Total P&L | **-$386.21** |
| Total wagered | $3,250.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 8 | 100.0% | +$212.00 | — | — | $200.00 |
| bybit | BTC | paper | 3 | 100.0% | +$75.00 | +0.083 | — | $75.00 |
| hl | BTC | paper | 5 | 80.0% | +$75.00 | +0.005 | — | $125.00 |
| doge_bybit | DOGE | paper | 3 | 66.7% | +$25.00 | +0.250 | — | $75.00 |
| doge_hl | DOGE | paper | 3 | 66.7% | +$25.00 | +0.125 | — | $75.00 |
| eth_5m | ETH | paper | 13 | 53.8% | -$6.33 | -0.032 | -0.030 | $325.00 |
| sol_hl | SOL | paper | 18 | 44.4% | -$50.00 | -0.074 | — | $450.00 |
| btc_5m | BTC | paper | 8 | 37.5% | -$66.88 | +0.017 | +0.036 | $200.00 |
| sol_bybit | SOL | paper | 19 | 36.8% | -$125.00 | -0.080 | — | $475.00 |
| eth_bybit | ETH | paper | 25 | 28.0% | -$275.00 | -0.094 | — | $625.00 |
| eth_hl | ETH | paper | 25 | 28.0% | -$275.00 | -0.102 | — | $625.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 24 | 75.0% | +$295.12 | $600.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 63 | 33.3% | -$556.33 | $1,575.00 |
| **SOL** | sol_bybit, sol_hl | 37 | 40.5% | -$175.00 | $925.00 |
| **DOGE** | doge_bybit, doge_hl | 6 | 66.7% | +$50.00 | $150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0167 | +0.0363 | 88 | -2.0¢/$ |
| bybit | +0.0833 | — | 72 | — |
| doge_bybit | +0.2500 | — | 8 | — |
| doge_hl | +0.1250 | — | 8 | — |
| eth_5m | -0.0317 | -0.0300 | 102 | -0.2¢/$ |
| eth_bybit | -0.0940 | — | 133 | — |
| eth_hl | -0.1015 | — | 133 | — |
| hl | +0.0047 | — | 107 | — |
| sol_bybit | -0.0804 | — | 112 | — |
| sol_hl | -0.0739 | — | 115 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 6 | 6 | 100.0% | 83.3% | -0.2854 |
| eth_5m | 9 | 9 | 100.0% | 55.6% | -0.0936 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 37.5% below 55% threshold (8 bets)

### bybit
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=5438

### doge_bybit
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=2829

### doge_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3388

### eth_5m
- ⚠️ Daily WR 53.8% below 55% threshold (13 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6805; 1 conv>=3 prediction(s) with no order: ids=6802; 1 conv>=3 prediction(s) with no order: ids=6735
- 🚨 Signal EHR negative: -0.0317 over 102 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 28.0% below 55% threshold (25 bets)
- ⚠️ Daily P&L $-275.00 — significant loss
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3275; 1 conv>=3 prediction(s) with no order: ids=3265; 1 conv>=3 prediction(s) with no order: ids=3264; +11 more
- 🚨 Signal EHR negative: -0.0940 over 133 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 28.0% below 55% threshold (25 bets)
- ⚠️ Daily P&L $-275.00 — significant loss
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3274; 1 conv>=3 prediction(s) with no order: ids=3264; 1 conv>=3 prediction(s) with no order: ids=3263; +11 more
- 🚨 Signal EHR negative: -0.1015 over 133 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 36.8% below 55% threshold (19 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- 📉 WR declining: 59% → 41% over 7 days
- 🚨 8 integrity check failure(s) today
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3387; 1 conv>=3 prediction(s) with no order: ids=3380; 1 conv>=3 prediction(s) with no order: ids=3378; +9 more
- 🚨 Signal EHR negative: -0.0804 over 112 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 📉 WR declining: 59% → 42% over 7 days
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3387; 1 conv>=3 prediction(s) with no order: ids=3380; 1 conv>=3 prediction(s) with no order: ids=3334; +8 more
- 🚨 Signal EHR negative: -0.0739 over 115 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 117 |
| bybit_linear | connected | 151 |
| polymarket | connected | 106 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 49872 | 182266 | 264 |
| Orderbook age (ms) | 0 | 0 | 929 |

- Cycles: 557
- Fallback fires (24h): 17
- Engine start: 2026-05-03T16:09:42.713662+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $34.10 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
