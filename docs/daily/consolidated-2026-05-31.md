# Consolidated Daily Report — 2026-05-31

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-31.md](2026-05-31.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 316 |
| Total wins | 159 |
| Total losses | 157 |
| Aggregate WR | 50.3% |
| Total P&L | **+$63.84** |
| Total wagered | $7,900.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 25 | 72.0% | +$264.07 | +0.054 | +0.109 | $625.00 |
| hl | BTC | paper | 39 | 59.0% | +$175.00 | +0.015 | — | $975.00 |
| eth_5m | ETH | paper | 14 | 50.0% | +$24.77 | -0.006 | -0.028 | $350.00 |
| bybit | BTC | paper | 20 | 45.0% | -$50.00 | -0.005 | — | $500.00 |
| sol_bybit | SOL | paper | 59 | 47.5% | -$75.00 | +0.012 | — | $1,475.00 |
| sol_hl | SOL | paper | 59 | 47.5% | -$75.00 | +0.007 | — | $1,475.00 |
| doge_bybit | DOGE | paper | 50 | 46.0% | -$100.00 | -0.007 | — | $1,250.00 |
| doge_hl | DOGE | paper | 50 | 46.0% | -$100.00 | -0.007 | — | $1,250.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 84 | 59.5% | +$389.07 | $2,100.00 |
| **ETH** | eth_5m | 14 | 50.0% | +$24.77 | $350.00 |
| **SOL** | sol_bybit, sol_hl | 118 | 47.5% | -$150.00 | $2,950.00 |
| **DOGE** | doge_bybit, doge_hl | 100 | 46.0% | -$200.00 | $2,500.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0540 | +0.1090 | 184 | -5.5¢/$ |
| bybit | -0.0050 | — | 200 | — |
| doge_bybit | -0.0072 | — | 138 | — |
| doge_hl | -0.0072 | — | 138 | — |
| eth_5m | -0.0063 | -0.0276 | 116 | +2.1¢/$ |
| hl | +0.0155 | — | 291 | — |
| sol_bybit | +0.0122 | — | 205 | — |
| sol_hl | +0.0073 | — | 205 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 25 | 25 | 100.0% | 28.0% | +0.2028 |
| eth_5m | 14 | 14 | 100.0% | 50.0% | +0.0143 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14114; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14086; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13981; +2 more

### bybit
- ⚠️ Daily WR 45.0% below 55% threshold (20 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13189; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13179; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13112; +7 more
- 🚨 Signal EHR negative: -0.0050 over 200 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 43.8% WR on 16 bets ($-50.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 46.0% below 55% threshold (50 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 54% → 31% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9885; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9884; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9861; +11 more
- 🚨 Signal EHR negative: -0.0072 over 138 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ⚠️ Daily WR 46.0% below 55% threshold (50 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 52% → 31% over 7 days
- ⚠️ orphaned_predictions: 31 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10496; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10482; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10481; +28 more
- 🚨 Signal EHR negative: -0.0072 over 138 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ Daily WR 50.0% below 55% threshold (14 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14034; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13964; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13897; +2 more
- 🚨 Signal EHR negative: -0.0063 over 116 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 42.9% WR on 7 bets ($-35.40); require cohort review before promotion

### hl
- ⚠️ orphaned_predictions: 22 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7713; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7712; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7702; +19 more
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 20.0% WR on 5 bets ($-75.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 47.5% below 55% threshold (59 bets)
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10451; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10450; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10449; +10 more

### sol_hl
- ⚠️ Daily WR 47.5% below 55% threshold (59 bets)
- ⚠️ orphaned_predictions: 38 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10449; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10448; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=10447; +35 more
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / MEAN_REVERTING is 44.4% WR on 9 bets ($-25.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 109 |
| bybit_linear | connected | 1 |
| polymarket | connected | 23 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9727 | 21022 | 645 |
| Bybit event lag (ms) | 862 | 50158 | 655 |
| TA build (ms) | 75 | 143 | 645 |
| Pipeline fanout (ms) | 9604 | 20924 | 645 |
| Strategy Lab runtime (ms) | 194 | 1377 | 645 |
| Total dispatch wall time (ms) | 10168 | 21348 | 645 |
| True orderbook age (ms) | 3288 | 100235 | 555 |
| BTC 5m executable orderbook age (ms) | 218 | 1731 | 1000 |

- Slowest pipeline runtime: bybit p95=23409ms (129 samples)
- BTC 5m executable reads: fresh=65682 stale=50110 missing=395 partial=3112 total=119299
- Orderbook cache: 40 tokens, 288 token-set changes (24h)
- Cycles: 1395
- Fallback fires (24h): 0
- Engine start: 2026-05-31T13:22:33.722829+00:00

- Polymarket events: book=780121, price_change=25273109, ignored={'last_trade_price': 364835, 'new_market': 3560, 'tick_size_change': 16}
- Orderbook freshness detail: fresh/stale tokens: 16/24, updated last 60s/5m: 30/40, stale reasons: {'stale_updated_at': 24}
- REST snapshot seed: 5186/5189 successful (missing=0, invalid_bbo=50)
- Polymarket resubscribe: resubscribe debounced/executed: 164/142, added/removed tokens: 840/1096
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
| btc_5m | $100.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $94.05 | $300.0 | No |
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
