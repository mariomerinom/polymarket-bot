# Consolidated Daily Report — 2026-06-01

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-01.md](2026-06-01.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 36 |
| Total wins | 15 |
| Total losses | 21 |
| Aggregate WR | 41.7% |
| Total P&L | **-$102.70** |
| Total wagered | $900.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 7 | 71.4% | +$75.00 | +0.018 | — | $175.00 |
| eth_5m | ETH | paper | 7 | 57.1% | +$73.28 | +0.002 | -0.044 | $175.00 |
| sol_bybit | SOL | paper | 2 | 50.0% | $0.00 | +0.003 | — | $50.00 |
| sol_hl | SOL | paper | 2 | 50.0% | $0.00 | +0.003 | — | $50.00 |
| doge_bybit | DOGE | paper | 3 | 33.3% | -$25.00 | -0.012 | — | $75.00 |
| doge_hl | DOGE | paper | 3 | 33.3% | -$25.00 | -0.020 | — | $75.00 |
| btc_5m | BTC | paper | 4 | 25.0% | -$50.98 | +0.069 | +0.120 | $100.00 |
| hl | BTC | paper | 8 | 12.5% | -$150.00 | +0.013 | — | $200.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 19 | 36.8% | -$125.98 | $475.00 |
| **ETH** | eth_5m | 7 | 57.1% | +$73.28 | $175.00 |
| **SOL** | sol_bybit, sol_hl | 4 | 50.0% | $0.00 | $100.00 |
| **DOGE** | doge_bybit, doge_hl | 6 | 33.3% | -$50.00 | $150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0691 | +0.1205 | 172 | -5.1¢/$ |
| bybit | +0.0185 | — | 189 | — |
| doge_bybit | -0.0122 | — | 123 | — |
| doge_hl | -0.0203 | — | 123 | — |
| eth_5m | +0.0024 | -0.0441 | 106 | +4.7¢/$ |
| hl | +0.0128 | — | 273 | — |
| sol_bybit | +0.0026 | — | 191 | — |
| sol_hl | +0.0026 | — | 191 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 4 | 4 | 100.0% | 75.0% | -0.2375 |
| eth_5m | 7 | 7 | 100.0% | 42.9% | +0.1825 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14252; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14211

### bybit
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13271; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13216; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13215

### doge_bybit
- 🚨 4 consecutive losing days
- 🚨 24 integrity check failure(s) today
- 🚨 Signal EHR negative: -0.0122 over 123 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10523; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10522
- 🚨 Signal EHR negative: -0.0203 over 123 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14372; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14371; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14366

### hl
- ⚠️ Daily WR 12.5% below 55% threshold (8 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7828; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7787; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7769; +2 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 12.5% WR on 8 bets ($-150.00); require cohort review before promotion

### sol_bybit
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10461; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10460

### sol_hl
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10459; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10458

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 222 |
| bybit_linear | connected | 9 |
| polymarket | connected | 64 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 11400 | 24412 | 705 |
| Bybit event lag (ms) | 864 | 48461 | 653 |
| TA build (ms) | 79 | 152 | 705 |
| Pipeline fanout (ms) | 11322 | 24338 | 705 |
| Strategy Lab runtime (ms) | 503 | 1571 | 705 |
| Total dispatch wall time (ms) | 12008 | 25410 | 705 |
| True orderbook age (ms) | 2922 | 48992 | 809 |
| BTC 5m executable orderbook age (ms) | 313 | 1741 | 1000 |

- Slowest pipeline runtime: btc_5m p95=29856ms (216 samples)
- BTC 5m executable reads: fresh=74225 stale=65188 missing=413 partial=3326 total=143152
- Orderbook cache: 40 tokens, 537 token-set changes (24h)
- Cycles: 2602
- Fallback fires (24h): 0
- Engine start: 2026-06-01T04:00:02.012014+00:00

- Polymarket events: book=1631823, price_change=52873692, ignored={'last_trade_price': 755142, 'new_market': 7316, 'tick_size_change': 16}
- Orderbook freshness detail: fresh/stale tokens: 16/24, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 24}
- REST snapshot seed: 10591/10600 successful (missing=1, invalid_bbo=56)
- Polymarket resubscribe: resubscribe debounced/executed: 306/252, added/removed tokens: 1570/2052
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
| hl | $0.00 | $300.0 | No |

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
