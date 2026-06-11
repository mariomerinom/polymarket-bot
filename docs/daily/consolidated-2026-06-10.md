# Consolidated Daily Report — 2026-06-10

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-10.md](2026-06-10.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 1 |
| Total wins | 0 |
| Total losses | 1 |
| Aggregate WR | 0.0% |
| Total P&L | **-$25.00** |
| Total wagered | $25.00 |
| Pipelines with resolved bets | 1 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 1 | 0.0% | -$25.00 | +0.124 | +0.182 | $25.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| btc_5m | BTC | paper | 0 | — | $0.00 | -0.335 | — | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | -0.500 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **ETH** | eth_5m | 1 | 0.0% | -$25.00 | $25.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.3350 | — | 1 | — |
| bybit | -0.5000 | — | 1 | — |
| eth_5m | +0.1236 | +0.1825 | 22 | -5.9¢/$ |
| hl | +0.0000 | — | 6 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| eth_5m | 1 | 1 | 100.0% | 100.0% | -0.2725 |

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
- 📉 WR declining: 63% → 0% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16920

### hl
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 233 |
| bybit_linear | connected | 10 |
| polymarket | connected | 123 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 14675 | 36329 | 705 |
| Bybit event lag (ms) | 900 | 58225 | 886 |
| TA build (ms) | 70 | 142 | 705 |
| Pipeline fanout (ms) | 14596 | 36259 | 705 |
| Strategy Lab runtime (ms) | 877 | 1568 | 705 |
| Total dispatch wall time (ms) | 15316 | 37604 | 705 |
| True orderbook age (ms) | 7474 | 178909 | 771 |
| BTC 5m executable orderbook age (ms) | 250 | 1815 | 1000 |

- Slowest pipeline runtime: doge_hl p95=41286ms (241 samples)
- BTC 5m executable reads: fresh=147089 stale=194915 missing=653 partial=5226 total=347883
- Orderbook cache: 40 tokens, 512 token-set changes (24h)
- Cycles: 2614
- Fallback fires (24h): 0
- Engine start: 2026-06-10T04:00:01.493774+00:00

- Polymarket events: book=1453189, price_change=65749074, ignored={'last_trade_price': 677467, 'new_market': 11849, 'market_resolved': 2, 'tick_size_change': 60}
- Orderbook freshness detail: fresh/stale tokens: 12/28, updated last 60s/5m: 18/40, stale reasons: {'stale_updated_at': 28}
- REST snapshot seed: 10953/10962 successful (missing=1, invalid_bbo=14)
- Polymarket resubscribe: resubscribe debounced/executed: 288/242, added/removed tokens: 1438/1936
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (0/50); execution_ehr_insufficient_sample (1/10); dispatch_p95_too_high (36329)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| _no order data today_ |  |  |  |

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
