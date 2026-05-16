# Consolidated Daily Report — 2026-05-15

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-15.md](2026-05-15.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 65 |
| Total wins | 26 |
| Total losses | 39 |
| Aggregate WR | 40.0% |
| Total P&L | **-$326.66** |
| Total wagered | $1,625.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 4 | 50.0% | $0.00 | +0.037 | — | $100.00 |
| sol_hl | SOL | paper | 4 | 50.0% | $0.00 | +0.050 | — | $100.00 |
| hl | BTC | paper | 18 | 44.4% | -$50.00 | -0.026 | — | $450.00 |
| eth_5m | ETH | paper | 15 | 40.0% | -$72.89 | -0.002 | -0.130 | $375.00 |
| bybit | BTC | paper | 15 | 40.0% | -$75.00 | -0.011 | — | $375.00 |
| btc_5m | BTC | paper | 9 | 22.2% | -$128.77 | +0.002 | -0.085 | $225.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.214 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.250 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 42 | 38.1% | -$253.77 | $1,050.00 |
| **ETH** | eth_5m | 15 | 40.0% | -$72.89 | $375.00 |
| **SOL** | sol_bybit, sol_hl | 8 | 50.0% | $0.00 | $200.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0015 | -0.0849 | 106 | +8.6¢/$ |
| bybit | -0.0106 | — | 94 | — |
| doge_bybit | +0.2143 | — | 7 | — |
| doge_hl | +0.2500 | — | 8 | — |
| eth_5m | -0.0021 | -0.1299 | 121 | +12.8¢/$ |
| hl | -0.0259 | — | 135 | — |
| sol_bybit | +0.0366 | — | 41 | — |
| sol_hl | +0.0500 | — | 40 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 9 | 9 | 100.0% | 77.8% | -0.2800 |
| eth_5m | 15 | 15 | 100.0% | 60.0% | -0.0992 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 22.2% below 55% threshold (9 bets)
- ⚠️ Daily P&L $-128.77 — significant loss
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9847; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9784; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9731; +1 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 28.6% WR on 7 bets ($-78.77); require cohort review before promotion

### bybit
- ⚠️ Daily WR 40.0% below 55% threshold (15 bets)
- 📉 WR declining: 70% → 44% over 7 days
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8595; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8555; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8513; +6 more
- 🚨 Signal EHR negative: -0.0106 over 94 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 28.6% WR on 7 bets ($-75.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 40.0% below 55% threshold (15 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9414; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9413; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9380; +3 more
- 🚨 Signal EHR negative: -0.0021 over 121 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 40.0% WR on 10 bets ($-46.94); require cohort review before promotion

### hl
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3492; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3455; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3415; +9 more
- 🚨 Signal EHR negative: -0.0259 over 135 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

### sol_bybit
- 📉 WR declining: 90% → 38% over 7 days
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5858; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5857; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5855

### sol_hl
- 📉 WR declining: 94% → 38% over 7 days
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5856; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5855; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5853

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 84 |
| bybit_linear | connected | 0 |
| polymarket | connected | 28 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 6091 | 9412 | 705 |
| Bybit event lag (ms) | 710 | 19084 | 554 |
| TA build (ms) | 86 | 192 | 705 |
| Pipeline fanout (ms) | 6003 | 9311 | 705 |
| Strategy Lab runtime (ms) | 122 | 501 | 705 |
| Total dispatch wall time (ms) | 6266 | 9611 | 705 |
| True orderbook age (ms) | 3157 | 129761 | 664 |

- Slowest pipeline runtime: bybit p95=10556ms (241 samples)
- Orderbook cache: 36 tokens, 489 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-05-15T04:00:01.829337+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $100.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $36.27 | $300.0 | No |
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
