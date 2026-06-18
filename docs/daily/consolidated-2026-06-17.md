# Consolidated Daily Report — 2026-06-17

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-17.md](2026-06-17.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 79 |
| Total wins | 47 |
| Total losses | 32 |
| Aggregate WR | 59.5% |
| Total P&L | **+$444.51** |
| Total wagered | $1,975.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| hl | BTC | paper | 32 | 65.6% | +$250.00 | +0.048 | — | $800.00 |
| btc_5m | BTC | paper | 14 | 57.1% | +$104.01 | +0.057 | +0.037 | $350.00 |
| bybit | BTC | paper | 26 | 57.7% | +$100.00 | +0.054 | — | $650.00 |
| eth_5m | ETH | paper | 7 | 42.9% | -$9.50 | -0.049 | -0.138 | $175.00 |
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
| **BTC** | btc_5m, bybit, hl | 72 | 61.1% | +$454.01 | $1,800.00 |
| **ETH** | eth_5m | 7 | 42.9% | -$9.50 | $175.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0567 | +0.0366 | 91 | +2.0¢/$ |
| bybit | +0.0536 | — | 112 | — |
| doge_bybit | +0.0405 | — | 37 | — |
| doge_hl | +0.0135 | — | 37 | — |
| eth_5m | -0.0489 | -0.1375 | 54 | +8.9¢/$ |
| hl | +0.0478 | — | 157 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 14 | 14 | 100.0% | 42.9% | +0.1196 |
| eth_5m | 7 | 7 | 100.0% | 57.1% | -0.1075 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18526; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18478; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18455; +1 more

### bybit
- 📉 WR declining: 65% → 55% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17881; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17879; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17855; +6 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18991; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18990; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18916
- 🚨 Signal EHR negative: -0.0489 over 54 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 20.0% WR on 5 bets ($-72.37); require cohort review before promotion

### hl
- ⚠️ orphaned_predictions: 22 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12103; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12102; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12101; +19 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 199 |
| bybit_linear | connected | 2 |
| polymarket | connected | 79 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9403 | 18468 | 705 |
| Bybit event lag (ms) | 864 | 33937 | 949 |
| TA build (ms) | 69 | 127 | 705 |
| Pipeline fanout (ms) | 9327 | 18394 | 705 |
| Strategy Lab runtime (ms) | 180 | 1165 | 705 |
| Total dispatch wall time (ms) | 9789 | 19064 | 705 |
| True orderbook age (ms) | 8108 | 123560 | 882 |
| BTC 5m executable orderbook age (ms) | 109 | 1625 | 1000 |

- Slowest pipeline runtime: bybit p95=21362ms (241 samples)
- BTC 5m executable reads: fresh=203219 stale=295467 missing=823 partial=6596 total=506105
- Orderbook cache: 30 tokens, 507 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-06-17T04:00:02.297004+00:00

- Polymarket events: book=1552938, price_change=44742467, ignored={'last_trade_price': 690728, 'new_market': 13058, 'tick_size_change': 456}
- Orderbook freshness detail: fresh/stale tokens: 14/16, updated last 60s/5m: 24/30, stale reasons: {'stale_updated_at': 16}
- REST snapshot seed: 11232/11244 successful (missing=0, invalid_bbo=89)
- Polymarket resubscribe: resubscribe debounced/executed: 280/276, added/removed tokens: 1282/1784
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
| btc_5m | $100.00 | $300.0 | No |
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
