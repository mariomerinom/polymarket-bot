# Consolidated Daily Report — 2026-06-18

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-18.md](2026-06-18.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 28 |
| Total wins | 14 |
| Total losses | 14 |
| Aggregate WR | 50.0% |
| Total P&L | **+$20.25** |
| Total wagered | $700.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 8 | 75.0% | +$100.00 | +0.067 | — | $200.00 |
| btc_5m | BTC | paper | 7 | 42.9% | -$12.22 | +0.051 | +0.038 | $175.00 |
| eth_5m | ETH | paper | 3 | 33.3% | -$17.53 | -0.048 | -0.119 | $75.00 |
| hl | BTC | paper | 10 | 40.0% | -$50.00 | +0.039 | — | $250.00 |
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
| **BTC** | btc_5m, bybit, hl | 25 | 52.0% | +$37.78 | $625.00 |
| **ETH** | eth_5m | 3 | 33.3% | -$17.53 | $75.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0507 | +0.0378 | 98 | +1.3¢/$ |
| bybit | +0.0667 | — | 120 | — |
| doge_bybit | +0.0405 | — | 37 | — |
| doge_hl | +0.0135 | — | 37 | — |
| eth_5m | -0.0479 | -0.1190 | 56 | +7.1¢/$ |
| hl | +0.0389 | — | 167 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 7 | 7 | 100.0% | 57.1% | -0.0096 |
| eth_5m | 3 | 3 | 100.0% | 66.7% | -0.1242 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 7 bets ($-12.22); require cohort review before promotion

### bybit
- 🚨 24 integrity check failure(s) today

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- 🚨 3 consecutive losing days
- 📉 WR declining: 56% → 40% over 7 days
- 🚨 Signal EHR negative: -0.0479 over 56 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 40.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12342; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12341; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12290; +2 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 10 bets ($-50.00); require cohort review before promotion

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 203 |
| bybit_linear | connected | 3 |
| polymarket | connected | 96 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10837 | 26711 | 705 |
| Bybit event lag (ms) | 862 | 34837 | 816 |
| TA build (ms) | 69 | 125 | 705 |
| Pipeline fanout (ms) | 10763 | 26662 | 705 |
| Strategy Lab runtime (ms) | 234 | 1283 | 705 |
| Total dispatch wall time (ms) | 11324 | 27690 | 705 |
| True orderbook age (ms) | 3605 | 78319 | 808 |
| BTC 5m executable orderbook age (ms) | 255 | 1725 | 1000 |

- Slowest pipeline runtime: doge_hl p95=27043ms (241 samples)
- BTC 5m executable reads: fresh=210317 stale=309607 missing=846 partial=6789 total=527559
- Orderbook cache: 42 tokens, 525 token-set changes (24h)
- Cycles: 2582
- Fallback fires (24h): 0
- Engine start: 2026-06-18T04:00:02.441535+00:00

- Polymarket events: book=1534933, price_change=51254628, ignored={'last_trade_price': 679213, 'new_market': 9634, 'tick_size_change': 480, 'market_resolved': 2}
- Orderbook freshness detail: fresh/stale tokens: 20/22, updated last 60s/5m: 30/42, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 11102/11110 successful (missing=0, invalid_bbo=80)
- Polymarket resubscribe: resubscribe debounced/executed: 299/266, added/removed tokens: 1488/1916
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
| btc_5m | $75.00 | $300.0 | No |
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
