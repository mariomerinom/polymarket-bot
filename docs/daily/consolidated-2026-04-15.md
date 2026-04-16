# Consolidated Daily Report — 2026-04-15

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-15.md](2026-04-15.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 82 |
| Total wins | 32 |
| Total losses | 50 |
| Aggregate WR | 39.0% |
| Total P&L | **-$417.16** |
| Total wagered | $2,050.00 |
| Active pipelines | 7 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_15m | BTC | paper | 3 | 33.3% | -$17.53 | +0.001 | +0.002 | $75.00 |
| bybit | BTC | paper | 1 | 0.0% | -$25.00 | -0.061 | — | $25.00 |
| hl | BTC | paper | 1 | 0.0% | -$25.00 | -0.095 | — | $25.00 |
| eth_5m | ETH | paper | 33 | 45.5% | -$49.63 | -0.033 | -0.040 | $825.00 |
| eth_bybit | ETH | paper | 18 | 44.4% | -$50.00 | -0.100 | — | $450.00 |
| eth_hl | ETH | paper | 18 | 44.4% | -$50.00 | -0.100 | — | $450.00 |
| kalshi | BTC | paper | 8 | 0.0% | -$200.00 | — | — | $200.00 |
| btc_5m | BTC | paper | 0 | — | $0.00 | +0.018 | +0.035 | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.024 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.069 | — | $0.00 |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.033 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_15m, bybit, hl, kalshi | 13 | 7.7% | -$267.53 | $325.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 69 | 44.9% | -$149.63 | $1,725.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_15m | +0.0010 | +0.0022 | 24 | -0.1¢/$ |
| btc_5m | +0.0183 | +0.0354 | 111 | -1.7¢/$ |
| bybit | -0.0613 | — | 155 | — |
| doge_bybit | -0.0238 | — | 21 | — |
| doge_hl | -0.0692 | — | 65 | — |
| eth_5m | -0.0332 | -0.0402 | 270 | +0.7¢/$ |
| eth_bybit | -0.1000 | — | 90 | — |
| eth_hl | -0.1000 | — | 90 | — |
| hl | -0.0952 | — | 42 | — |
| sol_bybit | -0.0167 | — | 60 | — |
| sol_hl | -0.0333 | — | 60 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| _no shadow data today_ |  |  |  |  |  |

## 6. Alerts (All Pipelines)

### btc_15m
- 🚨 3 consecutive losing days
- 📉 WR declining: 47% → 19% over 7 days

### btc_5m
- ℹ️ No bets placed today — all predictions skipped
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### bybit
- 🚨 3 consecutive losing days
- 📉 WR declining: 56% → 20% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=2773
- 🚨 Signal EHR negative: -0.0613 over 155 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- 🚨 3 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0692 over 65 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ Daily WR 45.5% below 55% threshold (33 bets)
- 🚨 3 consecutive losing days
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0332 over 270 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 🚨 5 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1011
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=988
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=972
- 🚨 Signal EHR negative: -0.1000 over 90 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 🚨 5 consecutive losing days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1011
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=988
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=972
- 🚨 Signal EHR negative: -0.1000 over 90 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=849

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (8 bets)
- ⚠️ Daily P&L $-200.00 — significant loss
- 📉 WR declining: 24% → 0% over 7 days

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0167 over 60 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0333 over 60 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 9 |
| bybit_linear | connected | 0 |
| polymarket | connected | 3 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 5182 | 16328 | 140 |
| Orderbook age (ms) | 0 | 0 | 806 |

- Cycles: 300
- Fallback fires (24h): 0
- Engine start: 2026-04-16T14:44:38.291343+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_15m | $33.32 | $300.0 | ✅ |
| eth_5m | $130.84 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |

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
| kalshi | paper | default | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
