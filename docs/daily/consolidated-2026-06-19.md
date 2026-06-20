# Consolidated Daily Report — 2026-06-19

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-19.md](2026-06-19.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 55 |
| Total wins | 32 |
| Total losses | 23 |
| Aggregate WR | 58.2% |
| Total P&L | **+$286.35** |
| Total wagered | $1,375.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 18 | 55.6% | +$101.37 | -0.020 | -0.013 | $450.00 |
| doge_bybit | DOGE | paper | 8 | 75.0% | +$100.00 | +0.078 | — | $200.00 |
| doge_hl | DOGE | paper | 8 | 62.5% | +$50.00 | +0.033 | — | $200.00 |
| btc_5m | BTC | paper | 3 | 66.7% | +$34.98 | +0.038 | +0.025 | $75.00 |
| hl | BTC | paper | 9 | 55.6% | +$25.00 | +0.027 | — | $225.00 |
| bybit | BTC | paper | 9 | 44.4% | -$25.00 | +0.041 | — | $225.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.136 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.106 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 21 | 52.4% | +$34.98 | $525.00 |
| **ETH** | eth_5m | 18 | 55.6% | +$101.37 | $450.00 |
| **DOGE** | doge_bybit, doge_hl | 16 | 68.8% | +$150.00 | $400.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0381 | +0.0247 | 94 | +1.3¢/$ |
| bybit | +0.0410 | — | 122 | — |
| doge_bybit | +0.0778 | — | 45 | — |
| doge_hl | +0.0333 | — | 45 | — |
| eth_5m | -0.0199 | -0.0131 | 70 | -0.7¢/$ |
| hl | +0.0269 | — | 167 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 3 | 3 | 100.0% | 33.3% | +0.1308 |
| eth_5m | 18 | 18 | 100.0% | 44.4% | +0.0621 |

## 6. Alerts (All Pipelines)

### bybit
- ⚠️ Daily WR 44.4% below 55% threshold (9 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18545; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18544; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18543; +3 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 44.4% WR on 9 bets ($-25.00); require cohort review before promotion

### doge_bybit
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15413; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15412; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15403; +3 more

### doge_hl
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15971; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15970; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15961; +3 more

### eth_5m
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19724; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19719; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19687; +6 more
- 🚨 Signal EHR negative: -0.0199 over 70 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12613; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12611; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12610; +3 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 194 |
| bybit_linear | connected | 4 |
| polymarket | connected | 102 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9855 | 21669 | 705 |
| Bybit event lag (ms) | 861 | 29197 | 870 |
| TA build (ms) | 65 | 116 | 705 |
| Pipeline fanout (ms) | 9777 | 21563 | 705 |
| Strategy Lab runtime (ms) | 187 | 1218 | 705 |
| Total dispatch wall time (ms) | 10337 | 22670 | 705 |
| True orderbook age (ms) | 1736 | 76307 | 512 |
| BTC 5m executable orderbook age (ms) | 107 | 1474 | 1000 |

- Slowest pipeline runtime: bybit p95=22035ms (241 samples)
- BTC 5m executable reads: fresh=218653 stale=324376 missing=877 partial=6976 total=550882
- Orderbook cache: 36 tokens, 528 token-set changes (24h)
- Cycles: 2610
- Fallback fires (24h): 0
- Engine start: 2026-06-19T04:00:01.476895+00:00

- Polymarket events: book=1381791, price_change=46282466, ignored={'last_trade_price': 622987, 'new_market': 9368, 'tick_size_change': 504, 'market_resolved': 1}
- Orderbook freshness detail: fresh/stale tokens: 24/12, updated last 60s/5m: 30/36, stale reasons: {'stale_updated_at': 12}
- REST snapshot seed: 12340/12350 successful (missing=0, invalid_bbo=119)
- Polymarket resubscribe: resubscribe debounced/executed: 302/277, added/removed tokens: 1490/1888
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
| btc_5m | $0.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
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
