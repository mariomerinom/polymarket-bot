# Consolidated Daily Report — 2026-06-12

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-12.md](2026-06-12.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 40 |
| Total wins | 25 |
| Total losses | 15 |
| Aggregate WR | 62.5% |
| Total P&L | **+$241.61** |
| Total wagered | $1,000.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 11 | 63.6% | +$75.00 | +0.184 | — | $275.00 |
| btc_5m | BTC | paper | 8 | 62.5% | +$70.85 | +0.181 | +0.150 | $200.00 |
| hl | BTC | paper | 16 | 56.2% | +$50.00 | +0.113 | — | $400.00 |
| eth_5m | ETH | paper | 5 | 80.0% | +$45.76 | +0.131 | +0.099 | $125.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 35 | 60.0% | +$195.85 | $875.00 |
| **ETH** | eth_5m | 5 | 80.0% | +$45.76 | $125.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.1806 | +0.1500 | 16 | +3.1¢/$ |
| bybit | +0.1842 | — | 19 | — |
| eth_5m | +0.1308 | +0.0986 | 31 | +3.2¢/$ |
| hl | +0.1129 | — | 31 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 8 | 8 | 100.0% | 37.5% | +0.1963 |
| eth_5m | 5 | 5 | 100.0% | 20.0% | +0.2745 |

## 6. Alerts (All Pipelines)

### bybit
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16530; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16485; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16484; +4 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17443; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17436

### hl
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10772; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10730; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10729; +7 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 221 |
| bybit_linear | connected | 7 |
| polymarket | connected | 157 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10345 | 25802 | 705 |
| Bybit event lag (ms) | 862 | 38539 | 708 |
| TA build (ms) | 69 | 124 | 705 |
| Pipeline fanout (ms) | 10287 | 25756 | 705 |
| Strategy Lab runtime (ms) | 292 | 1284 | 705 |
| Total dispatch wall time (ms) | 10882 | 26427 | 705 |
| True orderbook age (ms) | 2535 | 72990 | 650 |
| BTC 5m executable orderbook age (ms) | 165 | 1705 | 1000 |

- Slowest pipeline runtime: btc_5m p95=30814ms (218 samples)
- BTC 5m executable reads: fresh=163566 stale=224149 missing=695 partial=5623 total=394033
- Orderbook cache: 40 tokens, 514 token-set changes (24h)
- Cycles: 2606
- Fallback fires (24h): 0
- Engine start: 2026-06-12T04:00:02.479533+00:00

- Polymarket events: book=1465664, price_change=64278217, ignored={'last_trade_price': 674371, 'new_market': 11489, 'tick_size_change': 28}
- Orderbook freshness detail: fresh/stale tokens: 14/22, updated last 60s/5m: 36/36, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 12250/12258 successful (missing=0, invalid_bbo=72)
- Polymarket resubscribe: resubscribe debounced/executed: 293/240, added/removed tokens: 1384/1956
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (16/50); execution_ehr_insufficient_sample (1/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (16/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $0.00 | $300.0 | No |
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
