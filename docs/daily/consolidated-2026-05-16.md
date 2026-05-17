# Consolidated Daily Report — 2026-05-16

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-16.md](2026-05-16.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 95 |
| Total wins | 45 |
| Total losses | 50 |
| Aggregate WR | 47.4% |
| Total P&L | **-$124.73** |
| Total wagered | $2,375.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 11 | 63.6% | +$75.00 | +0.040 | — | $275.00 |
| sol_hl | SOL | paper | 11 | 63.6% | +$75.00 | +0.051 | — | $275.00 |
| eth_5m | ETH | paper | 5 | 60.0% | +$26.56 | +0.006 | -0.131 | $125.00 |
| doge_bybit | DOGE | paper | 3 | 66.7% | +$25.00 | +0.250 | — | $75.00 |
| doge_hl | DOGE | paper | 3 | 66.7% | +$25.00 | +0.278 | — | $75.00 |
| bybit | BTC | paper | 17 | 47.1% | -$25.00 | -0.024 | — | $425.00 |
| btc_5m | BTC | paper | 18 | 38.9% | -$101.29 | -0.030 | -0.114 | $450.00 |
| hl | BTC | paper | 27 | 33.3% | -$225.00 | -0.050 | — | $675.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 62 | 38.7% | -$351.29 | $1,550.00 |
| **ETH** | eth_5m | 5 | 60.0% | +$26.56 | $125.00 |
| **SOL** | sol_bybit, sol_hl | 22 | 63.6% | +$150.00 | $550.00 |
| **DOGE** | doge_bybit, doge_hl | 6 | 66.7% | +$50.00 | $150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0298 | -0.1143 | 116 | +8.4¢/$ |
| bybit | -0.0243 | — | 103 | — |
| doge_bybit | +0.2500 | — | 8 | — |
| doge_hl | +0.2778 | — | 9 | — |
| eth_5m | +0.0061 | -0.1306 | 117 | +13.7¢/$ |
| hl | -0.0497 | — | 151 | — |
| sol_bybit | +0.0400 | — | 50 | — |
| sol_hl | +0.0510 | — | 49 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 18 | 18 | 100.0% | 61.1% | -0.1063 |
| eth_5m | 5 | 5 | 100.0% | 40.0% | +0.0740 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 38.9% below 55% threshold (18 bets)
- ⚠️ Daily P&L $-101.29 — significant loss
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10104; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10085; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9959
- 🚨 Signal EHR negative: -0.0298 over 116 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 47.1% below 55% threshold (17 bets)
- 📉 WR declining: 64% → 46% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8716; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8675
- 🚨 Signal EHR negative: -0.0243 over 103 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5659

### doge_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6217

### eth_5m
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9681; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9615; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9604; +1 more

### hl
- ⚠️ Daily WR 33.3% below 55% threshold (27 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3711; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3710; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3708; +14 more
- 🚨 Signal EHR negative: -0.0497 over 151 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 0.0% WR on 6 bets ($-150.00); require cohort review before promotion

### sol_bybit
- 📉 WR declining: 82% → 43% over 7 days
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6083; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6082; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6081; +4 more

### sol_hl
- 📉 WR declining: 82% → 43% over 7 days
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6081; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6080; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6079; +4 more

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 47 |
| bybit_linear | connected | 0 |
| polymarket | connected | 18 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 5542 | 8283 | 705 |
| Bybit event lag (ms) | 674 | 16951 | 598 |
| TA build (ms) | 81 | 194 | 705 |
| Pipeline fanout (ms) | 5444 | 8206 | 705 |
| Strategy Lab runtime (ms) | 112 | 420 | 705 |
| Total dispatch wall time (ms) | 5735 | 8483 | 705 |
| True orderbook age (ms) | 3280 | 122521 | 680 |

- Slowest pipeline runtime: eth_5m p95=8830ms (241 samples)
- Orderbook cache: 38 tokens, 481 token-set changes (24h)
- Cycles: 2616
- Fallback fires (24h): 0
- Engine start: 2026-05-16T04:00:02.216086+00:00

- Polymarket events: book=0, price_change=0, ignored={}
- Orderbook freshness detail: fresh/stale tokens: 0/0, updated last 60s/5m: 0/0, stale reasons: {}
- REST snapshot seed: 0/0 successful (missing=0, invalid_bbo=0)
- Polymarket resubscribe: resubscribe debounced/executed: 0/0, added/removed tokens: 0/0
- Orderbook freshness decision: dominant cause: no websocket book/price_change events

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0270); execution_ehr_insufficient_sample (2/10); metrics_schema_stale (None); metrics_written_at_missing; orderbook_age_p95_too_high (122521); orderbook_fresh_tokens_missing
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $93.96 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
