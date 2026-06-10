# Consolidated Daily Report — 2026-06-09

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-09.md](2026-06-09.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 0 |
| Total wins | 0 |
| Total losses | 0 |
| Aggregate WR | 0.0% |
| Total P&L | **$0.00** |
| Total wagered | $0.00 |
| Pipelines with resolved bets | 0 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| btc_5m | BTC | paper | 0 | — | $0.00 | -0.112 | -0.520 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | -0.333 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| eth_5m | ETH | paper | 0 | — | $0.00 | +0.077 | +0.268 | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | -0.045 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |

## 3. Per-Asset Roll-up

_No bets across any asset today._

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.1117 | -0.5200 | 3 | +40.8¢/$ |
| bybit | -0.3333 | — | 6 | — |
| eth_5m | +0.0772 | +0.2679 | 23 | -19.1¢/$ |
| hl | -0.0455 | — | 11 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| _no shadow data today_ |  |  |  |  |  |

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
- ℹ️ No bets placed today — all predictions skipped

### hl
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 234 |
| bybit_linear | connected | 3 |
| polymarket | connected | 160 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13480 | 32969 | 705 |
| Bybit event lag (ms) | 863 | 44902 | 940 |
| TA build (ms) | 71 | 141 | 705 |
| Pipeline fanout (ms) | 13342 | 32895 | 705 |
| Strategy Lab runtime (ms) | 817 | 1613 | 705 |
| Total dispatch wall time (ms) | 14271 | 34657 | 705 |
| True orderbook age (ms) | 5043 | 126181 | 749 |
| BTC 5m executable orderbook age (ms) | 311 | 1734 | 1000 |

- Slowest pipeline runtime: btc_5m p95=35332ms (223 samples)
- BTC 5m executable reads: fresh=139067 stale=180610 missing=637 partial=5006 total=325320
- Orderbook cache: 44 tokens, 518 token-set changes (24h)
- Cycles: 2616
- Fallback fires (24h): 0
- Engine start: 2026-06-09T04:00:02.034556+00:00

- Polymarket events: book=1555726, price_change=62908949, ignored={'last_trade_price': 725638, 'new_market': 9426, 'tick_size_change': 40}
- Orderbook freshness detail: fresh/stale tokens: 0/44, updated last 60s/5m: 26/38, stale reasons: {'stale_updated_at': 38, 'missing_cache_entry': 6}
- REST snapshot seed: 11900/11915 successful (missing=2, invalid_bbo=34)
- Polymarket resubscribe: resubscribe debounced/executed: 297/243, added/removed tokens: 1400/1944
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (0/50); execution_ehr_insufficient_sample (1/10); dispatch_p95_too_high (32969); orderbook_fresh_tokens_missing
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
