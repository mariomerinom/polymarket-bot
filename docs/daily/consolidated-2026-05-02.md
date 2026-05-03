# Consolidated Daily Report — 2026-05-02

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-02.md](2026-05-02.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 171 |
| Total wins | 100 |
| Total losses | 71 |
| Aggregate WR | 58.5% |
| Total P&L | **+$877.64** |
| Total wagered | $4,275.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 12 | 100.0% | +$348.42 | — | — | $300.00 |
| eth_5m | ETH | paper | 16 | 62.5% | +$209.53 | -0.039 | -0.021 | $400.00 |
| eth_bybit | ETH | paper | 22 | 59.1% | +$100.00 | -0.065 | — | $550.00 |
| sol_bybit | SOL | paper | 29 | 55.2% | +$75.00 | -0.070 | — | $725.00 |
| sol_hl | SOL | paper | 31 | 54.8% | +$75.00 | -0.077 | — | $775.00 |
| eth_hl | ETH | paper | 22 | 54.5% | +$50.00 | -0.074 | — | $550.00 |
| doge_bybit | DOGE | paper | 3 | 66.7% | +$25.00 | +0.300 | — | $75.00 |
| doge_hl | DOGE | paper | 3 | 66.7% | +$25.00 | +0.100 | — | $75.00 |
| btc_5m | BTC | paper | 11 | 54.5% | +$19.69 | +0.033 | +0.058 | $275.00 |
| hl | BTC | paper | 14 | 50.0% | $0.00 | -0.010 | — | $350.00 |
| bybit | BTC | paper | 8 | 37.5% | -$50.00 | +0.065 | — | $200.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 45 | 62.2% | +$318.11 | $1,125.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 60 | 58.3% | +$359.53 | $1,500.00 |
| **SOL** | sol_bybit, sol_hl | 60 | 55.0% | +$150.00 | $1,500.00 |
| **DOGE** | doge_bybit, doge_hl | 6 | 66.7% | +$50.00 | $150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0327 | +0.0575 | 80 | -2.5¢/$ |
| bybit | +0.0652 | — | 69 | — |
| doge_bybit | +0.3000 | — | 5 | — |
| doge_hl | +0.1000 | — | 5 | — |
| eth_5m | -0.0387 | -0.0210 | 89 | -1.8¢/$ |
| eth_bybit | -0.0648 | — | 108 | — |
| eth_hl | -0.0741 | — | 108 | — |
| hl | -0.0098 | — | 102 | — |
| sol_bybit | -0.0699 | — | 93 | — |
| sol_hl | -0.0773 | — | 97 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 11 | 11 | 100.0% | 45.5% | +0.0223 |
| eth_5m | 15 | 14 | 93.3% | 42.9% | +0.0666 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 54.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7217; 1 conv>=3 prediction(s) with no order: ids=7191

### bybit
- ⚠️ Daily WR 37.5% below 55% threshold (8 bets)
- 📉 WR declining: 65% → 49% over 7 days
- 🚨 22 integrity check failure(s) today
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no order: ids=5361; 1 conv>=3 prediction(s) with no order: ids=5309; 1 conv>=3 prediction(s) with no order: ids=5308; +2 more

### eth_5m
- 📉 WR declining: 61% → 47% over 7 days
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6599; 1 conv>=3 prediction(s) with no order: ids=6558; 1 conv>=3 prediction(s) with no order: ids=6550; +3 more
- 🚨 Signal EHR negative: -0.0387 over 89 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- 🚨 18 integrity check failure(s) today
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3200; 1 conv>=3 prediction(s) with no order: ids=3199; 1 conv>=3 prediction(s) with no order: ids=3174; +7 more
- 🚨 Signal EHR negative: -0.0648 over 108 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 54.5% below 55% threshold (22 bets)
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3199; 1 conv>=3 prediction(s) with no order: ids=3198; 1 conv>=3 prediction(s) with no order: ids=3173; +10 more
- 🚨 Signal EHR negative: -0.0741 over 108 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 50.0% below 55% threshold (14 bets)
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no order: ids=920; 1 conv>=3 prediction(s) with no order: ids=901; 1 conv>=3 prediction(s) with no order: ids=900; +6 more
- 🚨 Signal EHR negative: -0.0098 over 102 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- 📉 WR declining: 68% → 43% over 7 days
- 🚨 26 integrity check failure(s) today
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3163; 1 conv>=3 prediction(s) with no order: ids=3161; 1 conv>=3 prediction(s) with no order: ids=3081; +4 more
- 🚨 Signal EHR negative: -0.0699 over 93 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 54.8% below 55% threshold (31 bets)
- 📉 WR declining: 68% → 41% over 7 days
- ⚠️ orphaned_predictions: 19 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3205; 1 conv>=3 prediction(s) with no order: ids=3163; 1 conv>=3 prediction(s) with no order: ids=3161; +16 more
- 🚨 Signal EHR negative: -0.0773 over 97 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 175 |
| bybit_linear | connected | 187 |
| polymarket | connected | 157 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 43398 | 151848 | 384 |
| Orderbook age (ms) | 0 | 0 | 838 |

- Cycles: 809
- Fallback fires (24h): 15
- Engine start: 2026-05-02T13:37:55.082643+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $7.13 | $300.0 | No |
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
