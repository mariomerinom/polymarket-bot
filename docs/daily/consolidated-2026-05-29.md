# Consolidated Daily Report — 2026-05-29

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-29.md](2026-05-29.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 184 |
| Total wins | 107 |
| Total losses | 77 |
| Aggregate WR | 58.2% |
| Total P&L | **+$996.78** |
| Total wagered | $4,600.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| hl | BTC | paper | 56 | 64.3% | +$400.00 | -0.017 | — | $1,400.00 |
| btc_5m | BTC | paper | 39 | 59.0% | +$388.15 | +0.014 | +0.053 | $975.00 |
| bybit | BTC | paper | 46 | 54.3% | +$100.00 | -0.003 | — | $1,150.00 |
| eth_5m | ETH | paper | 9 | 55.6% | +$58.63 | -0.053 | -0.048 | $225.00 |
| sol_bybit | SOL | paper | 16 | 56.2% | +$50.00 | +0.008 | — | $400.00 |
| sol_hl | SOL | paper | 16 | 56.2% | +$50.00 | +0.000 | — | $400.00 |
| doge_bybit | DOGE | paper | 1 | 0.0% | -$25.00 | +0.026 | — | $25.00 |
| doge_hl | DOGE | paper | 1 | 0.0% | -$25.00 | +0.036 | — | $25.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 141 | 59.6% | +$888.15 | $3,525.00 |
| **ETH** | eth_5m | 9 | 55.6% | +$58.63 | $225.00 |
| **SOL** | sol_bybit, sol_hl | 32 | 56.2% | +$100.00 | $800.00 |
| **DOGE** | doge_bybit, doge_hl | 2 | 0.0% | -$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0137 | +0.0530 | 162 | -3.9¢/$ |
| bybit | -0.0026 | — | 193 | — |
| doge_bybit | +0.0258 | — | 97 | — |
| doge_hl | +0.0361 | — | 97 | — |
| eth_5m | -0.0528 | -0.0476 | 103 | -0.5¢/$ |
| hl | -0.0172 | — | 261 | — |
| sol_bybit | +0.0082 | — | 122 | — |
| sol_hl | +0.0000 | — | 122 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 39 | 39 | 100.0% | 41.0% | +0.1329 |
| eth_5m | 9 | 9 | 100.0% | 44.4% | +0.1025 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Circuit breaker at 83% ($250 / $300)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13615; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13612; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13589; +2 more
- 🧯 side/regime promotion guardrail: UP in HIGH_VOL / TRENDING is 20.0% WR on 5 bets ($-82.98); require cohort review before promotion

### bybit
- ⚠️ Daily WR 54.3% below 55% threshold (46 bets)
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12611; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12607; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12466; +2 more
- 🚨 Signal EHR negative: -0.0026 over 193 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 42.9% WR on 7 bets ($-25.00); require cohort review before promotion

### doge_bybit
- 📉 WR declining: 51% → 28% over 7 days

### doge_hl
- 📉 WR declining: 52% → 28% over 7 days

### eth_5m
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13534; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13533; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13318; +1 more
- 🚨 Signal EHR negative: -0.0528 over 103 bets (7-day) — model may be buying overpriced contracts

### hl
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 27 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7199; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7196; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7193; +24 more
- 🚨 Signal EHR negative: -0.0172 over 261 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9710; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9701; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9700; +7 more

### sol_hl
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9708; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9699; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9698; +7 more

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 200 |
| bybit_linear | connected | 1 |
| polymarket | connected | 31 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9066 | 19865 | 705 |
| Bybit event lag (ms) | 864 | 34508 | 881 |
| TA build (ms) | 87 | 190 | 705 |
| Pipeline fanout (ms) | 8961 | 19675 | 705 |
| Strategy Lab runtime (ms) | 162 | 1441 | 705 |
| Total dispatch wall time (ms) | 9692 | 20438 | 705 |
| True orderbook age (ms) | 2035 | 38294 | 644 |
| BTC 5m executable orderbook age (ms) | 2290 | 7867 | 1000 |

- Slowest pipeline runtime: bybit p95=21509ms (241 samples)
- BTC 5m executable reads: fresh=42456 stale=29834 missing=165 partial=2434 total=74889
- Orderbook cache: 38 tokens, 531 token-set changes (24h)
- Cycles: 2604
- Fallback fires (24h): 0
- Engine start: 2026-05-29T04:00:02.183985+00:00

- Polymarket events: book=1553159, price_change=36688575, ignored={'last_trade_price': 729641, 'new_market': 6519, 'tick_size_change': 40, 'market_resolved': 4}
- Orderbook freshness detail: fresh/stale tokens: 16/22, updated last 60s/5m: 38/38, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 9074/9088 successful (missing=3, invalid_bbo=11)
- Polymarket resubscribe: resubscribe debounced/executed: 303/261, added/removed tokens: 1438/2004
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10); btc5m_executable_orderbook_age_p95_too_high (7867)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $250.00 | $300.0 | No |
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
