# Consolidated Daily Report — 2026-06-02

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-02.md](2026-06-02.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 14 |
| Total wins | 4 |
| Total losses | 10 |
| Aggregate WR | 28.6% |
| Total P&L | **-$153.27** |
| Total wagered | $350.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 2 | 50.0% | -$3.27 | +0.062 | +0.114 | $50.00 |
| hl | BTC | paper | 5 | 40.0% | -$25.00 | +0.013 | — | $125.00 |
| eth_5m | ETH | paper | 2 | 0.0% | -$50.00 | -0.017 | -0.061 | $50.00 |
| bybit | BTC | paper | 5 | 20.0% | -$75.00 | +0.015 | — | $125.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.020 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.020 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.021 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.021 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 12 | 33.3% | -$103.27 | $300.00 |
| **ETH** | eth_5m | 2 | 0.0% | -$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0619 | +0.1143 | 150 | -5.2¢/$ |
| bybit | +0.0153 | — | 163 | — |
| doge_bybit | -0.0200 | — | 100 | — |
| doge_hl | -0.0200 | — | 100 | — |
| eth_5m | -0.0172 | -0.0615 | 95 | +4.4¢/$ |
| hl | +0.0127 | — | 236 | — |
| sol_bybit | +0.0207 | — | 169 | — |
| sol_hl | +0.0207 | — | 169 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 2 | 2 | 100.0% | 50.0% | +0.0163 |
| eth_5m | 2 | 2 | 100.0% | 100.0% | -0.4850 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14675

### bybit
- ⚠️ Daily WR 20.0% below 55% threshold (5 bets)
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13785; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13763

### doge_bybit
- 🚨 4 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0200 over 100 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- 🚨 4 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0200 over 100 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- 🚨 Signal EHR negative: -0.0172 over 95 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 40.0% below 55% threshold (5 bets)
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8245; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8226

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 237 |
| bybit_linear | connected | 14 |
| polymarket | connected | 101 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13396 | 31222 | 705 |
| Bybit event lag (ms) | 1054 | 51430 | 847 |
| TA build (ms) | 87 | 216 | 705 |
| Pipeline fanout (ms) | 13240 | 31095 | 705 |
| Strategy Lab runtime (ms) | 937 | 1861 | 705 |
| Total dispatch wall time (ms) | 14057 | 32150 | 705 |
| True orderbook age (ms) | 3131 | 61417 | 888 |
| BTC 5m executable orderbook age (ms) | 248 | 1674 | 1000 |

- Slowest pipeline runtime: btc_5m p95=34542ms (214 samples)
- BTC 5m executable reads: fresh=82517 stale=79655 missing=427 partial=3551 total=166150
- Orderbook cache: 40 tokens, 525 token-set changes (24h)
- Cycles: 2596
- Fallback fires (24h): 0
- Engine start: 2026-06-02T04:00:02.240644+00:00

- Polymarket events: book=1741952, price_change=54694662, ignored={'last_trade_price': 806617, 'new_market': 6926, 'tick_size_change': 128}
- Orderbook freshness detail: fresh/stale tokens: 10/30, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 30}
- REST snapshot seed: 10678/10706 successful (missing=1, invalid_bbo=65)
- Polymarket resubscribe: resubscribe debounced/executed: 299/244, added/removed tokens: 1442/2004
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10); dispatch_p95_too_high (31222)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
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
