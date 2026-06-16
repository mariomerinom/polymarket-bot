# Consolidated Daily Report — 2026-06-15

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-15.md](2026-06-15.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 44 |
| Total wins | 25 |
| Total losses | 19 |
| Aggregate WR | 56.8% |
| Total P&L | **+$214.64** |
| Total wagered | $1,100.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 8 | 75.0% | +$186.44 | +0.034 | -0.016 | $200.00 |
| bybit | BTC | paper | 13 | 53.8% | +$25.00 | +0.040 | — | $325.00 |
| eth_5m | ETH | paper | 7 | 57.1% | +$3.20 | -0.031 | -0.165 | $175.00 |
| hl | BTC | paper | 16 | 50.0% | $0.00 | +0.010 | — | $400.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.041 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.013 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.136 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.106 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 37 | 56.8% | +$211.44 | $925.00 |
| **ETH** | eth_5m | 7 | 57.1% | +$3.20 | $175.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0338 | -0.0163 | 61 | +5.0¢/$ |
| bybit | +0.0395 | — | 76 | — |
| doge_bybit | +0.0405 | — | 37 | — |
| doge_hl | +0.0135 | — | 37 | — |
| eth_5m | -0.0310 | -0.1650 | 45 | +13.4¢/$ |
| hl | +0.0096 | — | 104 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 8 | 8 | 100.0% | 25.0% | +0.2612 |
| eth_5m | 7 | 7 | 100.0% | 42.9% | +0.0725 |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 67% → 51% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17984

### bybit
- ⚠️ Daily WR 53.8% below 55% threshold (13 bets)
- 📉 WR declining: 75% → 49% over 7 days
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17421; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17391; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17360; +3 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18337; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18333; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18330

### hl
- ⚠️ Daily WR 50.0% below 55% threshold (16 bets)
- 📉 WR declining: 67% → 47% over 7 days
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11593; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11592; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11591; +5 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 170 |
| bybit_linear | connected | 5 |
| polymarket | connected | 57 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 6541 | 17791 | 705 |
| Bybit event lag (ms) | 864 | 34099 | 964 |
| TA build (ms) | 68 | 110 | 705 |
| Pipeline fanout (ms) | 6470 | 17699 | 705 |
| Strategy Lab runtime (ms) | 102 | 1107 | 705 |
| Total dispatch wall time (ms) | 6694 | 18153 | 705 |
| True orderbook age (ms) | 4241 | 71046 | 914 |
| BTC 5m executable orderbook age (ms) | 265 | 1736 | 1000 |

- Slowest pipeline runtime: bybit p95=19015ms (241 samples)
- BTC 5m executable reads: fresh=187694 stale=265996 missing=767 partial=6167 total=460624
- Orderbook cache: 44 tokens, 537 token-set changes (24h)
- Cycles: 2608
- Fallback fires (24h): 0
- Engine start: 2026-06-15T04:00:01.562864+00:00

- Polymarket events: book=1234240, price_change=37516924, ignored={'last_trade_price': 559376, 'new_market': 7035, 'tick_size_change': 24}
- Orderbook freshness detail: fresh/stale tokens: 12/32, updated last 60s/5m: 44/44, stale reasons: {'stale_updated_at': 32}
- REST snapshot seed: 9152/9154 successful (missing=0, invalid_bbo=64)
- Polymarket resubscribe: resubscribe debounced/executed: 307/317, added/removed tokens: 4796/5400
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (1/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
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
