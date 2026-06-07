# Consolidated Daily Report — 2026-06-06

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-06.md](2026-06-06.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 9 |
| Total wins | 5 |
| Total losses | 4 |
| Aggregate WR | 55.6% |
| Total P&L | **+$49.67** |
| Total wagered | $225.00 |
| Pipelines with resolved bets | 2 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 8 | 62.5% | +$74.67 | +0.058 | +0.052 | $200.00 |
| hl | BTC | paper | 1 | 0.0% | -$25.00 | -0.032 | — | $25.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| btc_5m | BTC | paper | 0 | — | $0.00 | +0.065 | +0.102 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | -0.009 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.043 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.043 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.005 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.005 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | hl | 1 | 0.0% | -$25.00 | $25.00 |
| **ETH** | eth_5m | 8 | 62.5% | +$74.67 | $200.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0646 | +0.1016 | 53 | -3.7¢/$ |
| bybit | -0.0091 | — | 55 | — |
| doge_bybit | -0.0429 | — | 70 | — |
| doge_hl | -0.0429 | — | 70 | — |
| eth_5m | +0.0582 | +0.0519 | 52 | +0.6¢/$ |
| hl | -0.0319 | — | 94 | — |
| sol_bybit | -0.0051 | — | 99 | — |
| sol_hl | -0.0051 | — | 99 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| eth_5m | 8 | 8 | 100.0% | 37.5% | +0.1169 |

## 6. Alerts (All Pipelines)

### btc_5m
- ℹ️ No bets placed today — all predictions skipped

### bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0091 over 55 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0429 over 70 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0429 over 70 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- 📉 WR declining: 54% → 31% over 7 days
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=15824; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=15823; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=15815; +1 more

### hl
- 🚨 3 consecutive losing days
- 📉 WR declining: 36% → 20% over 7 days
- 🚨 Signal EHR negative: -0.0319 over 94 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0051 over 99 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0051 over 99 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 237 |
| bybit_linear | connected | 8 |
| polymarket | connected | 239 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13446 | 35147 | 705 |
| Bybit event lag (ms) | 998 | 58717 | 755 |
| TA build (ms) | 76 | 146 | 705 |
| Pipeline fanout (ms) | 13340 | 35059 | 705 |
| Strategy Lab runtime (ms) | 915 | 1640 | 705 |
| Total dispatch wall time (ms) | 14224 | 35964 | 705 |
| True orderbook age (ms) | 3662 | 67392 | 642 |
| BTC 5m executable orderbook age (ms) | 209 | 1858 | 1000 |

- Slowest pipeline runtime: btc_5m p95=38903ms (222 samples)
- BTC 5m executable reads: fresh=114074 stale=136499 missing=549 partial=4404 total=255526
- Orderbook cache: 40 tokens, 493 token-set changes (24h)
- Cycles: 2614
- Fallback fires (24h): 0
- Engine start: 2026-06-06T04:00:01.982374+00:00

- Polymarket events: book=1364263, price_change=67186033, ignored={'last_trade_price': 631313, 'new_market': 8110, 'market_resolved': 5, 'tick_size_change': 152}
- Orderbook freshness detail: fresh/stale tokens: 20/20, updated last 60s/5m: 36/40, stale reasons: {'stale_updated_at': 20}
- REST snapshot seed: 13794/13801 successful (missing=0, invalid_bbo=6)
- Polymarket resubscribe: resubscribe debounced/executed: 273/229, added/removed tokens: 1380/1868
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (31/50); execution_ehr_insufficient_sample (0/10); dispatch_p95_too_high (35147)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (31/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
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
