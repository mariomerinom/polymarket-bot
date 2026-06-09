# Consolidated Daily Report — 2026-06-08

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-08.md](2026-06-08.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 2 |
| Total wins | 0 |
| Total losses | 2 |
| Aggregate WR | 0.0% |
| Total P&L | **-$50.00** |
| Total wagered | $50.00 |
| Pipelines with resolved bets | 1 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 2 | 0.0% | -$50.00 | +0.108 | +0.246 | $50.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| btc_5m | BTC | paper | 0 | — | $0.00 | -0.166 | -0.443 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | -0.038 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.167 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.167 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | -0.184 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **ETH** | eth_5m | 2 | 0.0% | -$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.1657 | -0.4425 | 7 | +27.7¢/$ |
| bybit | -0.0385 | — | 13 | — |
| doge_bybit | -0.1667 | — | 3 | — |
| doge_hl | -0.1667 | — | 3 | — |
| eth_5m | +0.1077 | +0.2461 | 30 | -13.8¢/$ |
| hl | -0.1842 | — | 19 | — |
| sol_bybit | +0.0000 | — | 2 | — |
| sol_hl | +0.0000 | — | 2 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| eth_5m | 2 | 2 | 100.0% | 100.0% | -0.4025 |

## 6. Alerts (All Pipelines)

### btc_5m
- ℹ️ No bets placed today — all predictions skipped

### bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16431

### hl
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 236 |
| bybit_linear | connected | 12 |
| polymarket | connected | 205 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13604 | 36923 | 705 |
| Bybit event lag (ms) | 984 | 63060 | 769 |
| TA build (ms) | 75 | 156 | 705 |
| Pipeline fanout (ms) | 13554 | 36856 | 705 |
| Strategy Lab runtime (ms) | 902 | 1566 | 705 |
| Total dispatch wall time (ms) | 14700 | 37996 | 705 |
| True orderbook age (ms) | 5285 | 65982 | 716 |
| BTC 5m executable orderbook age (ms) | 203 | 1751 | 1000 |

- Slowest pipeline runtime: btc_5m p95=40988ms (216 samples)
- BTC 5m executable reads: fresh=130371 stale=167250 missing=600 partial=4809 total=303030
- Orderbook cache: 42 tokens, 497 token-set changes (24h)
- Cycles: 2602
- Fallback fires (24h): 0
- Engine start: 2026-06-08T04:00:02.467942+00:00

- Polymarket events: book=1597309, price_change=65697966, ignored={'last_trade_price': 746660, 'new_market': 6278, 'market_resolved': 9, 'tick_size_change': 92}
- Orderbook freshness detail: fresh/stale tokens: 34/8, updated last 60s/5m: 38/41, stale reasons: {'stale_updated_at': 7, 'missing_cache_entry': 1}
- REST snapshot seed: 13451/13461 successful (missing=1, invalid_bbo=14)
- Polymarket resubscribe: resubscribe debounced/executed: 280/229, added/removed tokens: 1248/1880
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (0/50); execution_ehr_insufficient_sample (1/10); dispatch_p95_too_high (36923)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| eth_5m | $0.00 | $300.0 | No |

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
