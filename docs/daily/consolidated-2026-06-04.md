# Consolidated Daily Report — 2026-06-04

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-04.md](2026-06-04.md) file.

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
| btc_5m | BTC | paper | 0 | — | $0.00 | +0.090 | +0.140 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | +0.014 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| eth_5m | ETH | paper | 0 | — | $0.00 | +0.015 | -0.046 | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | +0.025 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.004 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.004 | — | $0.00 |

## 3. Per-Asset Roll-up

_No bets across any asset today._

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0904 | +0.1396 | 97 | -4.9¢/$ |
| bybit | +0.0138 | — | 109 | — |
| doge_bybit | -0.0493 | — | 71 | — |
| doge_hl | -0.0493 | — | 71 | — |
| eth_5m | +0.0151 | -0.0462 | 63 | +6.1¢/$ |
| hl | +0.0253 | — | 158 | — |
| sol_bybit | +0.0042 | — | 119 | — |
| sol_hl | +0.0042 | — | 119 | — |

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
- 🚨 4 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0493 over 71 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- 🚨 4 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0493 over 71 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- 📉 WR declining: 56% → 36% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### hl
- 📉 WR declining: 54% → 37% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 236 |
| bybit_linear | connected | 15 |
| polymarket | connected | 77 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 11627 | 23787 | 705 |
| Bybit event lag (ms) | 949 | 41263 | 503 |
| TA build (ms) | 78 | 179 | 705 |
| Pipeline fanout (ms) | 11548 | 23683 | 705 |
| Strategy Lab runtime (ms) | 348 | 1518 | 705 |
| Total dispatch wall time (ms) | 12365 | 24687 | 705 |
| True orderbook age (ms) | 12539 | 106051 | 767 |
| BTC 5m executable orderbook age (ms) | 250 | 1778 | 1000 |

- Slowest pipeline runtime: btc_5m p95=34367ms (225 samples)
- BTC 5m executable reads: fresh=98585 stale=108295 missing=491 partial=4017 total=211388
- Orderbook cache: 42 tokens, 534 token-set changes (24h)
- Cycles: 2618
- Fallback fires (24h): 0
- Engine start: 2026-06-04T04:00:02.383480+00:00

- Polymarket events: book=1804066, price_change=53615833, ignored={'last_trade_price': 818509, 'new_market': 6290, 'market_resolved': 8, 'tick_size_change': 176}
- Orderbook freshness detail: fresh/stale tokens: 18/24, updated last 60s/5m: 42/42, stale reasons: {'stale_updated_at': 24}
- REST snapshot seed: 10760/10782 successful (missing=0, invalid_bbo=48)
- Polymarket resubscribe: resubscribe debounced/executed: 310/253, added/removed tokens: 1524/1972
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
