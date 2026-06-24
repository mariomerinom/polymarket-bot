# Consolidated Daily Report — 2026-06-23

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-23.md](2026-06-23.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 38 |
| Total wins | 14 |
| Total losses | 24 |
| Aggregate WR | 36.8% |
| Total P&L | **-$246.50** |
| Total wagered | $950.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 4 | 50.0% | +$16.48 | -0.100 | +0.021 | $100.00 |
| bybit | BTC | paper | 11 | 36.4% | -$75.00 | +0.023 | — | $275.00 |
| hl | BTC | paper | 13 | 38.5% | -$75.00 | +0.015 | — | $325.00 |
| btc_5m | BTC | paper | 10 | 30.0% | -$112.98 | +0.033 | +0.047 | $250.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.045 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.091 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 34 | 35.3% | -$262.98 | $850.00 |
| **ETH** | eth_5m | 4 | 50.0% | +$16.48 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0326 | +0.0474 | 89 | -1.5¢/$ |
| bybit | +0.0227 | — | 132 | — |
| doge_bybit | -0.0455 | — | 66 | — |
| doge_hl | -0.0909 | — | 66 | — |
| eth_5m | -0.1001 | +0.0205 | 70 | -12.1¢/$ |
| hl | +0.0148 | — | 169 | — |
| sol_bybit | +0.0000 | — | 4 | — |
| sol_hl | +0.0000 | — | 4 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 10 | 10 | 100.0% | 70.0% | -0.2062 |
| eth_5m | 4 | 4 | 100.0% | 50.0% | +0.0012 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 30.0% below 55% threshold (10 bets)
- ⚠️ Daily P&L $-112.98 — significant loss
- 📉 WR declining: 56% → 40% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20079
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.0% WR on 10 bets ($-112.98); require cohort review before promotion

### bybit
- ⚠️ Daily WR 36.4% below 55% threshold (11 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 59% → 46% over 7 days
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19810; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19809; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19789; +3 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 36.4% WR on 11 bets ($-75.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0455 over 66 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0909 over 66 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20905; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20856
- 🚨 Signal EHR negative: -0.1001 over 70 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 38.5% below 55% threshold (13 bets)
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13774; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13773; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13755; +4 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 38.5% WR on 13 bets ($-75.00); require cohort review before promotion

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 228 |
| bybit_linear | connected | 9 |
| polymarket | connected | 118 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10936 | 21171 | 705 |
| Bybit event lag (ms) | 863 | 37537 | 779 |
| TA build (ms) | 65 | 106 | 705 |
| Pipeline fanout (ms) | 10884 | 21123 | 705 |
| Strategy Lab runtime (ms) | 243 | 1128 | 705 |
| Total dispatch wall time (ms) | 11356 | 21898 | 705 |
| True orderbook age (ms) | 3611 | 56047 | 904 |
| BTC 5m executable orderbook age (ms) | 156 | 1414 | 1000 |

- Slowest pipeline runtime: btc_5m p95=28003ms (222 samples)
- BTC 5m executable reads: fresh=259279 stale=369606 missing=981 partial=7733 total=637599
- Orderbook cache: 40 tokens, 525 token-set changes (24h)
- Cycles: 2614
- Fallback fires (24h): 0
- Engine start: 2026-06-23T04:00:02.484015+00:00

- Polymarket events: book=1499315, price_change=66593672, ignored={'last_trade_price': 704495, 'new_market': 13348, 'tick_size_change': 476, 'market_resolved': 2}
- Orderbook freshness detail: fresh/stale tokens: 18/22, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 11345/11354 successful (missing=0, invalid_bbo=99)
- Polymarket resubscribe: resubscribe debounced/executed: 304/249, added/removed tokens: 1566/1988
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (2/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (+0.0159 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $75.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
