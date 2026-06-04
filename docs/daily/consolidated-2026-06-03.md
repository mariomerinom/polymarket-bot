# Consolidated Daily Report — 2026-06-03

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-03.md](2026-06-03.md) file.

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
| btc_5m | BTC | paper | 0 | — | $0.00 | +0.071 | +0.134 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | +0.008 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.049 | — | $0.00 |
| eth_5m | ETH | paper | 0 | — | $0.00 | +0.004 | -0.043 | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| hl | BTC | paper | 0 | — | $0.00 | +0.011 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.003 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.003 | — | $0.00 |

## 3. Per-Asset Roll-up

_No bets across any asset today._

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0706 | +0.1336 | 118 | -6.3¢/$ |
| bybit | +0.0078 | — | 128 | — |
| doge_bybit | -0.0493 | — | 71 | — |
| doge_hl | -0.0493 | — | 71 | — |
| eth_5m | +0.0041 | -0.0425 | 75 | +4.7¢/$ |
| hl | +0.0108 | — | 186 | — |
| sol_bybit | +0.0034 | — | 145 | — |
| sol_hl | +0.0034 | — | 145 | — |

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
- 📉 WR declining: 51% → 36% over 7 days
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
| bybit_spot | connected | 187 |
| bybit_linear | connected | 10 |
| polymarket | connected | 51 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 11306 | 29974 | 529 |
| Bybit event lag (ms) | 974 | 58343 | 724 |
| TA build (ms) | 77 | 171 | 529 |
| Pipeline fanout (ms) | 11239 | 29902 | 529 |
| Strategy Lab runtime (ms) | 783 | 1601 | 529 |
| Total dispatch wall time (ms) | 12324 | 30997 | 529 |
| True orderbook age (ms) | 6713 | 127280 | 875 |
| BTC 5m executable orderbook age (ms) | 210 | 1731 | 1000 |

- Slowest pipeline runtime: btc_5m p95=34333ms (190 samples)
- BTC 5m executable reads: fresh=90314 stale=93761 missing=452 partial=3765 total=188292
- Orderbook cache: 38 tokens, 446 token-set changes (24h)
- Cycles: 2234
- Fallback fires (24h): 0
- Engine start: 2026-06-03T06:55:28.016912+00:00

- Polymarket events: book=1330832, price_change=41764907, ignored={'last_trade_price': 604788, 'new_market': 5938, 'market_resolved': 4, 'tick_size_change': 100}
- Orderbook freshness detail: fresh/stale tokens: 38/0, updated last 60s/5m: 38/38, stale reasons: {}
- REST snapshot seed: 7822/7824 successful (missing=0, invalid_bbo=30)
- Polymarket resubscribe: resubscribe debounced/executed: 251/212, added/removed tokens: 1266/1704
- Orderbook freshness decision: dominant cause: subscription reconnect churn

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
