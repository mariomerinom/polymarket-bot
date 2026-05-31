# Consolidated Daily Report — 2026-05-30

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-30.md](2026-05-30.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 215 |
| Total wins | 105 |
| Total losses | 110 |
| Aggregate WR | 48.8% |
| Total P&L | **-$107.41** |
| Total wagered | $5,375.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 20 | 60.0% | +$78.37 | -0.016 | +0.021 | $500.00 |
| bybit | BTC | paper | 23 | 52.2% | +$25.00 | +0.005 | — | $575.00 |
| sol_bybit | SOL | paper | 38 | 50.0% | $0.00 | +0.024 | — | $950.00 |
| sol_hl | SOL | paper | 38 | 50.0% | $0.00 | +0.017 | — | $950.00 |
| doge_bybit | DOGE | paper | 17 | 47.1% | -$25.00 | +0.011 | — | $425.00 |
| doge_hl | DOGE | paper | 17 | 47.1% | -$25.00 | +0.011 | — | $425.00 |
| btc_5m | BTC | paper | 21 | 42.9% | -$35.78 | +0.015 | +0.044 | $525.00 |
| hl | BTC | paper | 41 | 43.9% | -$125.00 | -0.009 | — | $1,025.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 85 | 45.9% | -$135.78 | $2,125.00 |
| **ETH** | eth_5m | 20 | 60.0% | +$78.37 | $500.00 |
| **SOL** | sol_bybit, sol_hl | 76 | 50.0% | $0.00 | $1,900.00 |
| **DOGE** | doge_bybit, doge_hl | 34 | 47.1% | -$50.00 | $850.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0151 | +0.0439 | 180 | -2.9¢/$ |
| bybit | +0.0048 | — | 210 | — |
| doge_bybit | +0.0114 | — | 88 | — |
| doge_hl | +0.0114 | — | 88 | — |
| eth_5m | -0.0159 | +0.0213 | 111 | -3.7¢/$ |
| hl | -0.0085 | — | 293 | — |
| sol_bybit | +0.0235 | — | 149 | — |
| sol_hl | +0.0168 | — | 149 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 22 | 21 | 100.0% | 57.1% | -0.0321 |
| eth_5m | 21 | 20 | 100.0% | 40.0% | +0.0715 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 42.9% below 55% threshold (21 bets)
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13814; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13753; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13743; +4 more

### bybit
- ⚠️ Daily WR 52.2% below 55% threshold (23 bets)
- 🚨 47 integrity check failure(s) today
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12858; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12857; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12856; +1 more

### doge_bybit
- ⚠️ Daily WR 47.1% below 55% threshold (17 bets)
- 📉 WR declining: 51% → 34% over 7 days
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9605; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9604; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9594; +5 more

### doge_hl
- ⚠️ Daily WR 47.1% below 55% threshold (17 bets)
- 📉 WR declining: 52% → 34% over 7 days
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10224; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10163; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10162; +6 more

### eth_5m
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13828; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13787; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13786; +9 more
- 🚨 Signal EHR negative: -0.0159 over 111 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 43.9% below 55% threshold (41 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- ⚠️ orphaned_predictions: 27 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7442; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7410; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7409; +24 more
- 🚨 Signal EHR negative: -0.0085 over 293 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 36.4% WR on 11 bets ($-75.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (38 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10162; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10025; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10008; +5 more

### sol_hl
- ⚠️ Daily WR 50.0% below 55% threshold (38 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10169; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10165; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10160; +7 more

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 165 |
| bybit_linear | connected | 2 |
| polymarket | connected | 32 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8523 | 14661 | 705 |
| Bybit event lag (ms) | 862 | 23360 | 547 |
| TA build (ms) | 84 | 207 | 705 |
| Pipeline fanout (ms) | 8435 | 14560 | 705 |
| Strategy Lab runtime (ms) | 161 | 1002 | 705 |
| Total dispatch wall time (ms) | 8826 | 14972 | 705 |
| True orderbook age (ms) | 4014 | 93402 | 841 |
| BTC 5m executable orderbook age (ms) | 2264 | 8116 | 1000 |

- Slowest pipeline runtime: bybit p95=14691ms (241 samples)
- BTC 5m executable reads: fresh=55451 stale=38981 missing=239 partial=2840 total=97511
- Orderbook cache: 40 tokens, 506 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-05-30T04:00:02.061628+00:00

- Polymarket events: book=1375923, price_change=35461872, ignored={'last_trade_price': 644175, 'new_market': 7543, 'tick_size_change': 16}
- Orderbook freshness detail: fresh/stale tokens: 22/18, updated last 60s/5m: 30/40, stale reasons: {'stale_updated_at': 18}
- REST snapshot seed: 10453/10458 successful (missing=1, invalid_bbo=4)
- Polymarket resubscribe: resubscribe debounced/executed: 276/298, added/removed tokens: 1400/1762
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10); btc5m_executable_orderbook_age_p95_too_high (8116)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $135.80 | $300.0 | No |
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
