# Consolidated Daily Report — 2026-05-06

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-06.md](2026-05-06.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 184 |
| Total wins | 65 |
| Total losses | 119 |
| Aggregate WR | 35.3% |
| Total P&L | **-$1,362.22** |
| Total wagered | $4,600.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 17 | 70.6% | +$175.00 | +0.102 | — | $425.00 |
| btc_5m | BTC | paper | 12 | 75.0% | +$142.26 | +0.050 | +0.031 | $300.00 |
| hl | BTC | paper | 14 | 64.3% | +$100.00 | +0.041 | — | $350.00 |
| doge_bybit | DOGE | paper | 1 | 100.0% | +$25.00 | +0.278 | — | $25.00 |
| doge_hl | DOGE | paper | 1 | 100.0% | +$25.00 | +0.100 | — | $25.00 |
| sol_bybit | SOL | paper | 2 | 0.0% | -$50.00 | -0.072 | — | $50.00 |
| sol_hl | SOL | paper | 3 | 0.0% | -$75.00 | -0.075 | — | $75.00 |
| eth_hl | ETH | paper | 27 | 40.7% | -$125.00 | -0.059 | — | $675.00 |
| eth_bybit | ETH | paper | 30 | 36.7% | -$200.00 | -0.061 | — | $750.00 |
| eth_5m | ETH | paper | 14 | 21.4% | -$202.88 | -0.049 | -0.029 | $350.00 |
| kalshi | BTC | paper | 63 | 12.7% | -$1,176.60 | — | — | $1,575.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 106 | 35.8% | -$759.34 | $2,650.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 71 | 35.2% | -$527.88 | $1,775.00 |
| **SOL** | sol_bybit, sol_hl | 5 | 0.0% | -$125.00 | $125.00 |
| **DOGE** | doge_bybit, doge_hl | 2 | 100.0% | +$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0498 | +0.0306 | 107 | +1.9¢/$ |
| bybit | +0.1020 | — | 98 | — |
| doge_bybit | +0.2778 | — | 9 | — |
| doge_hl | +0.1000 | — | 10 | — |
| eth_5m | -0.0494 | -0.0291 | 124 | -2.0¢/$ |
| eth_bybit | -0.0607 | — | 173 | — |
| eth_hl | -0.0588 | — | 170 | — |
| hl | +0.0414 | — | 133 | — |
| sol_bybit | -0.0725 | — | 131 | — |
| sol_hl | -0.0746 | — | 134 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 10 | 10 | 100.0% | 30.0% | +0.1420 |
| eth_5m | 12 | 12 | 100.0% | 75.0% | -0.1344 |

## 6. Alerts (All Pipelines)

### bybit
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6204; 1 conv>=3 prediction(s) with no order: ids=6203; 1 conv>=3 prediction(s) with no order: ids=6202; +8 more

### eth_5m
- ⚠️ Daily WR 21.4% below 55% threshold (14 bets)
- ⚠️ Daily P&L $-202.88 — significant loss
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=7343; 1 conv>=3 prediction(s) with no order: ids=7335; 1 conv>=3 prediction(s) with no order: ids=7307; +1 more
- 🚨 Signal EHR negative: -0.0494 over 124 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 6 bets ($-50.50); require cohort review before promotion

### eth_bybit
- ⚠️ Daily WR 36.7% below 55% threshold (30 bets)
- ⚠️ Daily P&L $-200.00 — significant loss
- ⚠️ orphaned_predictions: 19 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3908; 1 conv>=3 prediction(s) with no order: ids=3907; 1 conv>=3 prediction(s) with no order: ids=3899; +16 more
- 🚨 Signal EHR negative: -0.0607 over 173 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 25.0% WR on 8 bets ($-100.00); require cohort review before promotion

### eth_hl
- ⚠️ Daily WR 40.7% below 55% threshold (27 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- ⚠️ orphaned_predictions: 18 issue(s) - 1 conv>=3 prediction(s) with no order: ids=3907; 1 conv>=3 prediction(s) with no order: ids=3906; 1 conv>=3 prediction(s) with no order: ids=3898; +15 more
- 🚨 Signal EHR negative: -0.0588 over 170 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 25.0% WR on 8 bets ($-100.00); require cohort review before promotion

### hl
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no order: ids=1556; 1 conv>=3 prediction(s) with no order: ids=1554; 1 conv>=3 prediction(s) with no order: ids=1553; +5 more

### kalshi
- ⚠️ Daily WR 12.7% below 55% threshold (63 bets)
- ⚠️ Daily P&L $-1176.60 — significant loss
- 📉 WR declining: 100% → 38% over 7 days

### sol_bybit
- 🚨 Signal EHR negative: -0.0725 over 131 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- 🚨 Signal EHR negative: -0.0746 over 134 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 24 |
| bybit_linear | connected | 33 |
| polymarket | connected | 23 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 58210 | 187773 | 60 |
| Orderbook age (ms) | 0 | 0 | 802 |

- Cycles: 128
- Fallback fires (24h): 4
- Engine start: 2026-05-06T22:17:32.644743+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $64.74 | $300.0 | No |
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
