# Consolidated Daily Report — 2026-06-05

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-05.md](2026-06-05.md) file.

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
| btc_5m | BTC | paper | 0 | — | $0.00 | +0.088 | +0.149 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | +0.015 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| eth_5m | ETH | paper | 0 | — | $0.00 | +0.044 | +0.035 | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | +0.037 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.004 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.004 | — | $0.00 |

## 3. Per-Asset Roll-up

_No bets across any asset today._

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0880 | +0.1494 | 92 | -6.1¢/$ |
| bybit | +0.0149 | — | 101 | — |
| doge_bybit | -0.0493 | — | 71 | — |
| doge_hl | -0.0493 | — | 71 | — |
| eth_5m | +0.0445 | +0.0350 | 53 | +0.9¢/$ |
| hl | +0.0369 | — | 149 | — |
| sol_bybit | +0.0043 | — | 115 | — |
| sol_hl | +0.0043 | — | 115 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| _no shadow data today_ |  |  |  |  |  |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 59% → 38% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_bybit
- 🚨 3 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0493 over 71 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- 🚨 3 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0493 over 71 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- 📉 WR declining: 54% → 29% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### hl
- 📉 WR declining: 51% → 26% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | disconnected | 213 |
| bybit_linear | connected | 10 |
| polymarket | connected | 161 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13877 | 35605 | 705 |
| Bybit event lag (ms) | 1224 | 70823 | 519 |
| TA build (ms) | 82 | 192 | 705 |
| Pipeline fanout (ms) | 13800 | 35533 | 705 |
| Strategy Lab runtime (ms) | 956 | 1672 | 705 |
| Total dispatch wall time (ms) | 14963 | 36846 | 705 |
| True orderbook age (ms) | 7425 | 86093 | 876 |
| BTC 5m executable orderbook age (ms) | 303 | 1796 | 1000 |

- Slowest pipeline runtime: doge_hl p95=37159ms (241 samples)
- BTC 5m executable reads: fresh=106557 stale=122441 missing=534 partial=4210 total=233742
- Orderbook cache: 40 tokens, 492 token-set changes (24h)
- Cycles: 2602
- Fallback fires (24h): 0
- Engine start: 2026-06-05T04:00:02.686167+00:00

- Polymarket events: book=1605436, price_change=52046091, ignored={'last_trade_price': 698057, 'new_market': 7334, 'tick_size_change': 112, 'market_resolved': 3}
- Orderbook freshness detail: fresh/stale tokens: 12/28, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 28}
- REST snapshot seed: 12667/12686 successful (missing=0, invalid_bbo=63)
- Polymarket resubscribe: resubscribe debounced/executed: 276/261, added/removed tokens: 1280/1712
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10); dispatch_p95_too_high (35605)
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
