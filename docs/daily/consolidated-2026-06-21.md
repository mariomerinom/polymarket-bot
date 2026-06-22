# Consolidated Daily Report — 2026-06-21

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-21.md](2026-06-21.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 176 |
| Total wins | 90 |
| Total losses | 86 |
| Aggregate WR | 51.1% |
| Total P&L | **+$105.49** |
| Total wagered | $4,400.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 23 | 65.2% | +$183.85 | +0.049 | +0.064 | $575.00 |
| hl | BTC | paper | 42 | 54.8% | +$100.00 | +0.025 | — | $1,050.00 |
| sol_bybit | SOL | paper | 4 | 50.0% | $0.00 | -0.143 | — | $100.00 |
| sol_hl | SOL | paper | 4 | 50.0% | $0.00 | -0.143 | — | $100.00 |
| doge_bybit | DOGE | paper | 29 | 48.3% | -$25.00 | -0.015 | — | $725.00 |
| doge_hl | DOGE | paper | 29 | 48.3% | -$25.00 | -0.057 | — | $725.00 |
| eth_5m | ETH | paper | 11 | 45.5% | -$28.36 | -0.043 | +0.033 | $275.00 |
| bybit | BTC | paper | 34 | 44.1% | -$100.00 | +0.034 | — | $850.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 99 | 53.5% | +$183.85 | $2,475.00 |
| **ETH** | eth_5m | 11 | 45.5% | -$28.36 | $275.00 |
| **SOL** | sol_bybit, sol_hl | 8 | 50.0% | $0.00 | $200.00 |
| **DOGE** | doge_bybit, doge_hl | 58 | 48.3% | -$50.00 | $1,450.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0487 | +0.0638 | 98 | -1.5¢/$ |
| bybit | +0.0338 | — | 148 | — |
| doge_bybit | -0.0155 | — | 97 | — |
| doge_hl | -0.0567 | — | 97 | — |
| eth_5m | -0.0435 | +0.0333 | 76 | -7.7¢/$ |
| hl | +0.0255 | — | 196 | — |
| sol_bybit | -0.1429 | — | 14 | — |
| sol_hl | -0.1429 | — | 14 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 23 | 23 | 100.0% | 34.8% | +0.1966 |
| eth_5m | 11 | 11 | 100.0% | 54.5% | -0.0375 |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 63% → 49% over 7 days
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19674; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19673; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19661; +1 more

### bybit
- ⚠️ Daily WR 44.1% below 55% threshold (34 bets)
- ⚠️ orphaned_predictions: 21 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19186; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19181; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19177; +18 more

### doge_bybit
- ⚠️ Daily WR 48.3% below 55% threshold (29 bets)
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15923; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15918; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15908; +11 more
- 🚨 Signal EHR negative: -0.0155 over 97 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ⚠️ Daily WR 48.3% below 55% threshold (29 bets)
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16499; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16497; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16496; +14 more
- 🚨 Signal EHR negative: -0.0567 over 97 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20273; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20266; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20261; +2 more
- 🚨 Signal EHR negative: -0.0435 over 76 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 54.8% below 55% threshold (42 bets)
- 📉 WR declining: 58% → 47% over 7 days
- ⚠️ orphaned_predictions: 27 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13239; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13235; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13202; +24 more

### sol_bybit
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16313; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16312; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16286

### sol_hl
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16311; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16310; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16284

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 136 |
| bybit_linear | connected | 1 |
| polymarket | connected | 63 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 7850 | 14498 | 705 |
| Bybit event lag (ms) | 863 | 35567 | 562 |
| TA build (ms) | 60 | 109 | 705 |
| Pipeline fanout (ms) | 7790 | 14397 | 705 |
| Strategy Lab runtime (ms) | 113 | 922 | 705 |
| Total dispatch wall time (ms) | 8077 | 14850 | 705 |
| True orderbook age (ms) | 4259 | 87781 | 777 |
| BTC 5m executable orderbook age (ms) | 173 | 1333 | 1000 |

- Slowest pipeline runtime: bybit p95=15053ms (241 samples)
- BTC 5m executable reads: fresh=237138 stale=345383 missing=904 partial=7272 total=590697
- Orderbook cache: 40 tokens, 522 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-06-21T04:00:02.407779+00:00

- Polymarket events: book=1217409, price_change=43823152, ignored={'last_trade_price': 556928, 'new_market': 8780, 'tick_size_change': 432}
- Orderbook freshness detail: fresh/stale tokens: 20/20, updated last 60s/5m: 34/40, stale reasons: {'stale_updated_at': 20}
- REST snapshot seed: 12145/12154 successful (missing=5, invalid_bbo=71)
- Polymarket resubscribe: resubscribe debounced/executed: 295/300, added/removed tokens: 1530/1792
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (2/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $140.95 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $56.40 | $300.0 | No |
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
