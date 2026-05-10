# Consolidated Daily Report — 2026-05-09

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-09.md](2026-05-09.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 132 |
| Total wins | 74 |
| Total losses | 58 |
| Aggregate WR | 56.1% |
| Total P&L | **+$439.52** |
| Total wagered | $3,300.00 |
| Pipelines with resolved bets | 11 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| kalshi | BTC | paper | 19 | 84.2% | +$348.82 | — | — | $475.00 |
| eth_5m | ETH | paper | 15 | 66.7% | +$157.71 | +0.019 | -0.063 | $375.00 |
| sol_hl | SOL | paper | 6 | 83.3% | +$100.00 | +0.033 | — | $150.00 |
| sol_bybit | SOL | paper | 7 | 71.4% | +$75.00 | +0.019 | — | $175.00 |
| bybit | BTC | paper | 10 | 60.0% | +$50.00 | +0.129 | — | $250.00 |
| doge_hl | DOGE | paper | 4 | 75.0% | +$50.00 | +0.062 | — | $100.00 |
| doge_bybit | DOGE | paper | 3 | 66.7% | +$25.00 | +0.071 | — | $75.00 |
| hl | BTC | paper | 16 | 50.0% | $0.00 | +0.102 | — | $400.00 |
| btc_5m | BTC | paper | 11 | 45.5% | -$42.01 | +0.067 | -0.152 | $275.00 |
| eth_hl | ETH | paper | 20 | 40.0% | -$100.00 | -0.033 | — | $500.00 |
| eth_bybit | ETH | paper | 21 | 28.6% | -$225.00 | -0.068 | — | $525.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 56 | 62.5% | +$356.81 | $1,400.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 56 | 42.9% | -$167.29 | $1,400.00 |
| **SOL** | sol_bybit, sol_hl | 13 | 76.9% | +$175.00 | $325.00 |
| **DOGE** | doge_bybit, doge_hl | 7 | 71.4% | +$75.00 | $175.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0667 | -0.1519 | 64 | +21.9¢/$ |
| bybit | +0.1290 | — | 62 | — |
| doge_bybit | +0.0714 | — | 14 | — |
| doge_hl | +0.0625 | — | 16 | — |
| eth_5m | +0.0190 | -0.0633 | 91 | +8.2¢/$ |
| eth_bybit | -0.0683 | — | 139 | — |
| eth_hl | -0.0333 | — | 135 | — |
| hl | +0.1024 | — | 83 | — |
| sol_bybit | +0.0195 | — | 77 | — |
| sol_hl | +0.0325 | — | 77 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 10 | 9 | 90.0% | 66.7% | -0.0631 |
| eth_5m | 14 | 14 | 100.0% | 35.7% | +0.0380 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no order: ids=8378; 1 conv>=3 prediction(s) with no order: ids=8377; 1 conv>=3 prediction(s) with no order: ids=8305; +1 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 6 bets ($-45.73); require cohort review before promotion

### bybit
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no order: ids=6932; 1 conv>=3 prediction(s) with no order: ids=6908; 1 conv>=3 prediction(s) with no order: ids=6907; +4 more

### doge_bybit
- 📉 WR declining: 83% → 39% over 7 days
- 🚨 27 integrity check failure(s) today

### doge_hl
- 📉 WR declining: 56% → 42% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4258

### eth_5m
- 📉 WR declining: 65% → 41% over 7 days
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7883; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7867; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7843; +4 more

### eth_bybit
- ⚠️ Daily WR 28.6% below 55% threshold (21 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- 🚨 4 consecutive losing days
- 📉 WR declining: 64% → 35% over 7 days
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4370; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4369; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4368; +11 more
- 🚨 Signal EHR negative: -0.0683 over 139 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 23.1% WR on 13 bets ($-175.00); require cohort review before promotion

### eth_hl
- ⚠️ Daily WR 40.0% below 55% threshold (20 bets)
- 📉 WR declining: 64% → 42% over 7 days
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4369; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4368; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4367; +10 more
- 🚨 Signal EHR negative: -0.0333 over 135 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 38.5% WR on 13 bets ($-75.00); require cohort review before promotion

### hl
- ⚠️ Daily WR 50.0% below 55% threshold (16 bets)
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2079; 1 conv>=3 prediction(s) with no order: ids=2025; 1 conv>=3 prediction(s) with no order: ids=2023; +6 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 44.4% WR on 9 bets ($-25.00); require cohort review before promotion

### sol_bybit
- 🚨 7 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4330

### sol_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no order: ids=4330

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 6 |
| bybit_linear | connected | 6 |
| polymarket | connected | 4 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 34508 | 133256 | 18 |
| Bybit event lag (ms) | 19442 | 159316 | 50 |
| TA build (ms) | 96 | 2582 | 19 |
| Pipeline fanout (ms) | 34412 | 133181 | 18 |
| Strategy Lab runtime (ms) | 4403 | 61091 | 18 |
| Total dispatch wall time (ms) | 54021 | 139522 | 18 |
| True orderbook age (ms) | 107120 | 2595655607 | 830 |

- Slowest pipeline runtime: sol_bybit p95=69218ms (3 samples)
- Orderbook cache: 50 tokens, 6 token-set changes (24h)
- Cycles: 38
- Fallback fires (24h): 0
- Engine start: 2026-05-09T23:44:08.295935+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $100.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $67.01 | $300.0 | No |
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
