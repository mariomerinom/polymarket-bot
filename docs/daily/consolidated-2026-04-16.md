# Consolidated Daily Report — 2026-04-16

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-16.md](2026-04-16.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 149 |
| Total wins | 28 |
| Total losses | 121 |
| Aggregate WR | 18.8% |
| Total P&L | **-$2,316.46** |
| Total wagered | $3,725.00 |
| Active pipelines | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 17 | 58.8% | +$85.43 | -0.012 | -0.042 | $425.00 |
| eth_bybit | ETH | paper | 2 | 50.0% | $0.00 | -0.098 | — | $50.00 |
| eth_hl | ETH | paper | 2 | 50.0% | $0.00 | -0.098 | — | $50.00 |
| btc_15m | BTC | paper | 1 | 0.0% | -$25.00 | -0.106 | -0.096 | $25.00 |
| bybit | BTC | paper | 9 | 44.4% | -$25.00 | -0.014 | — | $225.00 |
| hl | BTC | paper | 13 | 46.2% | -$25.00 | -0.082 | — | $325.00 |
| btc_5m | BTC | paper | 13 | 46.2% | -$26.89 | +0.049 | +0.055 | $325.00 |
| kalshi | BTC | paper | 92 | 0.0% | -$2,300.00 | — | — | $2,300.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.024 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.069 | — | $0.00 |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.033 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_15m, btc_5m, bybit, hl, kalshi | 128 | 12.5% | -$2,401.89 | $3,200.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 21 | 57.1% | +$85.43 | $525.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_15m | -0.1062 | -0.0957 | 20 | -1.1¢/$ |
| btc_5m | +0.0488 | +0.0550 | 86 | -0.6¢/$ |
| bybit | -0.0143 | — | 105 | — |
| doge_bybit | -0.0238 | — | 21 | — |
| doge_hl | -0.0692 | — | 65 | — |
| eth_5m | -0.0122 | -0.0422 | 241 | +3.0¢/$ |
| eth_bybit | -0.0978 | — | 92 | — |
| eth_hl | -0.0978 | — | 92 | — |
| hl | -0.0818 | — | 55 | — |
| sol_bybit | -0.0167 | — | 60 | — |
| sol_hl | -0.0333 | — | 60 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_15m | 1 | 0 | — | — | — |
| eth_5m | 3 | 0 | — | — | — |

## 6. Alerts (All Pipelines)

### btc_15m
- 🚨 4 consecutive losing days
- 📉 WR declining: 47% → 15% over 7 days

### btc_5m
- ⚠️ Daily WR 46.2% below 55% threshold (13 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 54% → 43% over 7 days
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won

### bybit
- ⚠️ Daily WR 44.4% below 55% threshold (9 bets)
- 🚨 4 consecutive losing days
- 📉 WR declining: 47% → 28% over 7 days
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3098
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3097
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=3096
- 🚨 Signal EHR negative: -0.0143 over 105 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- 🚨 3 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0692 over 65 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0122 over 241 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1015
- 🚨 Signal EHR negative: -0.0978 over 92 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1015
- 🚨 Signal EHR negative: -0.0978 over 92 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 46.2% below 55% threshold (13 bets)
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1147
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1146
- ⚠️ orphaned_predictions: 1 conv>=3 prediction(s) with no order: ids=1145
- 🚨 Signal EHR negative: -0.0818 over 55 bets (7-day) — model may be buying overpriced contracts

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (92 bets)
- ⚠️ Daily P&L $-2300.00 — significant loss
- 🚨 3 consecutive losing days
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
| bybit_spot | connected | 18 |
| bybit_linear | connected | 0 |
| polymarket | connected | 2 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 3869 | 12219 | 420 |
| Orderbook age (ms) | 0 | 0 | 844 |

- Cycles: 914
- Fallback fires (24h): 0
- Engine start: 2026-04-16T17:09:38.102165+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_15m | $0.00 | $300.0 | ✅ |
| btc_5m | $75.00 | $300.0 | ✅ |
| bybit | $0.00 | $300.0 | ✅ |
| eth_5m | $57.58 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |
| hl | $0.00 | $300.0 | ✅ |

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
