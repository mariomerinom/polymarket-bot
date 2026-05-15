# Consolidated Daily Report — 2026-05-14

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-14.md](2026-05-14.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 116 |
| Total wins | 66 |
| Total losses | 50 |
| Aggregate WR | 56.9% |
| Total P&L | **+$449.34** |
| Total wagered | $2,900.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 28 | 64.3% | +$231.19 | +0.036 | -0.058 | $700.00 |
| hl | BTC | paper | 33 | 63.6% | +$225.00 | +0.004 | — | $825.00 |
| eth_5m | ETH | paper | 20 | 65.0% | +$168.15 | -0.012 | -0.164 | $500.00 |
| bybit | BTC | paper | 23 | 52.2% | +$25.00 | +0.018 | — | $575.00 |
| sol_bybit | SOL | paper | 6 | 16.7% | -$100.00 | +0.041 | — | $150.00 |
| sol_hl | SOL | paper | 6 | 16.7% | -$100.00 | +0.056 | — | $150.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.056 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.100 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 84 | 60.7% | +$481.19 | $2,100.00 |
| **ETH** | eth_5m | 20 | 65.0% | +$168.15 | $500.00 |
| **SOL** | sol_bybit, sol_hl | 12 | 16.7% | -$200.00 | $300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0358 | -0.0581 | 100 | +9.4¢/$ |
| bybit | +0.0181 | — | 83 | — |
| doge_bybit | +0.0556 | — | 9 | — |
| doge_hl | +0.1000 | — | 10 | — |
| eth_5m | -0.0117 | -0.1643 | 116 | +15.3¢/$ |
| hl | +0.0040 | — | 125 | — |
| sol_bybit | +0.0405 | — | 37 | — |
| sol_hl | +0.0556 | — | 36 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 28 | 28 | 100.0% | 35.7% | +0.1041 |
| eth_5m | 20 | 20 | 100.0% | 35.0% | +0.1826 |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 67% → 36% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9416

### bybit
- ⚠️ Daily WR 52.2% below 55% threshold (23 bets)
- ⚠️ orphaned_predictions: 15 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8233; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8232; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8231; +12 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- 📉 WR declining: 54% → 37% over 7 days
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9177; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9140; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9139; +3 more
- 🚨 Signal EHR negative: -0.0117 over 116 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 7 bets ($-20.89); require cohort review before promotion

### hl
- 📉 WR declining: 54% → 34% over 7 days
- ⚠️ orphaned_predictions: 22 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3174; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3173; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3172; +19 more

### sol_bybit
- ⚠️ Daily WR 16.7% below 55% threshold (6 bets)
- 📉 WR declining: 90% → 55% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5445; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5336; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5335

### sol_hl
- ⚠️ Daily WR 16.7% below 55% threshold (6 bets)
- 📉 WR declining: 94% → 55% over 7 days
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5443; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5334; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5333

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 154 |
| bybit_linear | connected | 0 |
| polymarket | connected | 34 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 6821 | 11204 | 705 |
| Bybit event lag (ms) | 733 | 25337 | 952 |
| TA build (ms) | 87 | 200 | 705 |
| Pipeline fanout (ms) | 6707 | 11085 | 705 |
| Strategy Lab runtime (ms) | 132 | 876 | 705 |
| Total dispatch wall time (ms) | 7084 | 11716 | 705 |
| True orderbook age (ms) | 1534 | 97829 | 707 |

- Slowest pipeline runtime: eth_5m p95=14937ms (241 samples)
- Orderbook cache: 34 tokens, 482 token-set changes (24h)
- Cycles: 2608
- Fallback fires (24h): 0
- Engine start: 2026-05-14T04:00:02.012931+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $154.94 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $60.12 | $300.0 | No |
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
| eth_bybit | paused | 0.05 | ETH |
| eth_hl | paused | 0.05 | ETH |
| hl | paper | 0.005 | BTC |
| kalshi | paused | 25 | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
