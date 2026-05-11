# Consolidated Daily Report — 2026-05-10

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-10.md](2026-05-10.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 111 |
| Total wins | 55 |
| Total losses | 56 |
| Aggregate WR | 49.5% |
| Total P&L | **-$76.06** |
| Total wagered | $2,775.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 5 | 80.0% | +$78.72 | +0.092 | -0.173 | $125.00 |
| eth_bybit | ETH | paper | 23 | 56.5% | +$75.00 | -0.071 | — | $575.00 |
| doge_bybit | DOGE | paper | 2 | 100.0% | +$50.00 | +0.115 | — | $50.00 |
| doge_hl | DOGE | paper | 2 | 100.0% | +$50.00 | +0.100 | — | $50.00 |
| sol_bybit | SOL | paper | 2 | 100.0% | +$50.00 | +0.020 | — | $50.00 |
| sol_hl | SOL | paper | 2 | 100.0% | +$50.00 | +0.042 | — | $50.00 |
| hl | BTC | paper | 3 | 66.7% | +$25.00 | +0.125 | — | $75.00 |
| bybit | BTC | paper | 2 | 50.0% | $0.00 | +0.161 | — | $50.00 |
| eth_5m | ETH | paper | 18 | 50.0% | -$71.26 | -0.009 | -0.100 | $450.00 |
| eth_hl | ETH | paper | 23 | 43.5% | -$75.00 | -0.051 | — | $575.00 |
| kalshi | BTC | paper | 29 | 27.6% | -$308.52 | — | — | $725.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 39 | 38.5% | -$204.80 | $975.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 64 | 50.0% | -$71.26 | $1,600.00 |
| **SOL** | sol_bybit, sol_hl | 4 | 100.0% | +$100.00 | $100.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 100.0% | +$100.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0925 | -0.1731 | 58 | +26.6¢/$ |
| bybit | +0.1607 | — | 56 | — |
| doge_bybit | +0.1154 | — | 13 | — |
| doge_hl | +0.1000 | — | 15 | — |
| eth_5m | -0.0085 | -0.1000 | 93 | +9.2¢/$ |
| eth_bybit | -0.0714 | — | 140 | — |
| eth_hl | -0.0515 | — | 136 | — |
| hl | +0.1250 | — | 72 | — |
| sol_bybit | +0.0200 | — | 50 | — |
| sol_hl | +0.0417 | — | 48 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 4 | 4 | 100.0% | 25.0% | +0.1481 |
| eth_5m | 11 | 11 | 100.0% | 45.5% | +0.0430 |

## 6. Alerts (All Pipelines)

### doge_bybit
- 🚨 11 integrity check failure(s) today

### eth_5m
- ⚠️ Daily WR 50.0% below 55% threshold (18 bets)
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8028; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8005
- 🚨 Signal EHR negative: -0.0085 over 93 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in LOW_VOL / MEAN_REVERTING is 37.5% WR on 8 bets ($-65.96); require cohort review before promotion

### eth_bybit
- 📉 WR declining: 67% → 40% over 7 days
- ⚠️ orphaned_predictions: 16 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4522; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4510; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4509; +13 more
- 🚨 Signal EHR negative: -0.0714 over 140 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in LOW_VOL / MEAN_REVERTING is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

### eth_hl
- ⚠️ Daily WR 43.5% below 55% threshold (23 bets)
- 📉 WR declining: 69% → 43% over 7 days
- ⚠️ orphaned_predictions: 16 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4521; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4509; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4508; +13 more
- 🚨 Signal EHR negative: -0.0515 over 136 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in LOW_VOL / MEAN_REVERTING is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

### hl
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2218; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2217

### kalshi
- ⚠️ Daily WR 27.6% below 55% threshold (29 bets)
- ⚠️ Daily P&L $-308.52 — significant loss

### sol_bybit
- 🚨 5 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4490

### sol_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4489

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 2 |
| bybit_linear | connected | 0 |
| polymarket | connected | 1 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8407 | 91150 | 7 |
| Bybit event lag (ms) | 9614 | 140804 | 34 |
| TA build (ms) | 103 | 3466 | 8 |
| Pipeline fanout (ms) | 8261 | 91051 | 7 |
| Strategy Lab runtime (ms) | 3435 | 5248 | 7 |
| Total dispatch wall time (ms) | 11841 | 96398 | 7 |
| True orderbook age (ms) | 118241 | 2682302671 | 352 |

- Slowest pipeline runtime: eth_5m p95=84025ms (1 samples)
- Orderbook cache: 50 tokens, 1 token-set changes (24h)
- Cycles: 13
- Fallback fires (24h): 0
- Engine start: 2026-05-10T23:56:07.676030+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $75.00 | $300.0 | No |
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
