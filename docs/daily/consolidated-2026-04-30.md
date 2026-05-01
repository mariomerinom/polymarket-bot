# Consolidated Daily Report — 2026-04-30

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-30.md](2026-04-30.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 187 |
| Total wins | 91 |
| Total losses | 96 |
| Aggregate WR | 48.7% |
| Total P&L | **-$78.72** |
| Total wagered | $4,675.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 32 | 59.4% | +$186.25 | +0.050 | +0.121 | $800.00 |
| bybit | BTC | paper | 23 | 60.9% | +$125.00 | +0.109 | — | $575.00 |
| hl | BTC | paper | 37 | 56.8% | +$125.00 | +0.000 | — | $925.00 |
| eth_bybit | ETH | paper | 18 | 44.4% | -$50.00 | -0.071 | — | $450.00 |
| eth_hl | ETH | paper | 18 | 44.4% | -$50.00 | -0.071 | — | $450.00 |
| sol_bybit | SOL | paper | 18 | 38.9% | -$100.00 | -0.115 | — | $450.00 |
| sol_hl | SOL | paper | 18 | 38.9% | -$100.00 | -0.115 | — | $450.00 |
| eth_5m | ETH | paper | 23 | 30.4% | -$214.97 | -0.072 | -0.081 | $575.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 92 | 58.7% | +$436.25 | $2,300.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 59 | 39.0% | -$314.97 | $1,475.00 |
| **SOL** | sol_bybit, sol_hl | 36 | 38.9% | -$200.00 | $900.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0496 | +0.1215 | 58 | -7.2¢/$ |
| bybit | +0.1087 | — | 46 | — |
| eth_5m | -0.0724 | -0.0811 | 76 | +0.9¢/$ |
| eth_bybit | -0.0714 | — | 70 | — |
| eth_hl | -0.0714 | — | 70 | — |
| hl | +0.0000 | — | 68 | — |
| sol_bybit | -0.1154 | — | 52 | — |
| sol_hl | -0.1154 | — | 52 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 32 | 31 | 96.9% | 41.9% | +0.1380 |
| eth_5m | 22 | 22 | 100.0% | 68.2% | -0.1932 |

## 6. Alerts (All Pipelines)

### bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4817
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4816
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=4739

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 30.4% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-214.97 — significant loss
- 🚨 Signal EHR negative: -0.0724 over 76 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2788
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2787
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2758
- 🚨 Signal EHR negative: -0.0714 over 70 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2787
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2786
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2757
- 🚨 Signal EHR negative: -0.0714 over 70 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=553
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=544
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=543

### sol_bybit
- ⚠️ Daily WR 38.9% below 55% threshold (18 bets)
- 🚨 17 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2798
- 🚨 Signal EHR negative: -0.1154 over 52 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 38.9% below 55% threshold (18 bets)
- 🚨 17 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2798
- 🚨 Signal EHR negative: -0.1154 over 52 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 120 |
| bybit_linear | connected | 109 |
| polymarket | connected | 99 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 32572 | 144293 | 331 |
| Orderbook age (ms) | 0 | 0 | 715 |

- Cycles: 709
- Fallback fires (24h): 8
- Engine start: 2026-04-30T16:24:27.359503+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $170.26 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $101.02 | $300.0 | ✅ |
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
