# Consolidated Daily Report — 2026-06-14

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-14.md](2026-06-14.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 182 |
| Total wins | 88 |
| Total losses | 94 |
| Aggregate WR | 48.4% |
| Total P&L | **-$181.67** |
| Total wagered | $4,550.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| doge_bybit | DOGE | paper | 37 | 54.1% | +$75.00 | +0.041 | — | $925.00 |
| eth_5m | ETH | paper | 14 | 64.3% | +$53.24 | +0.019 | -0.023 | $350.00 |
| doge_hl | DOGE | paper | 37 | 51.4% | +$25.00 | +0.013 | — | $925.00 |
| hl | BTC | paper | 35 | 51.4% | +$25.00 | +0.016 | — | $875.00 |
| bybit | BTC | paper | 21 | 47.6% | -$25.00 | +0.031 | — | $525.00 |
| sol_bybit | SOL | paper | 10 | 30.0% | -$100.00 | -0.136 | — | $250.00 |
| sol_hl | SOL | paper | 10 | 30.0% | -$100.00 | -0.106 | — | $250.00 |
| btc_5m | BTC | paper | 18 | 33.3% | -$134.91 | -0.011 | -0.051 | $450.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 74 | 45.9% | -$134.91 | $1,850.00 |
| **ETH** | eth_5m | 14 | 64.3% | +$53.24 | $350.00 |
| **SOL** | sol_bybit, sol_hl | 20 | 30.0% | -$200.00 | $500.00 |
| **DOGE** | doge_bybit, doge_hl | 74 | 52.7% | +$100.00 | $1,850.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0108 | -0.0514 | 54 | +4.1¢/$ |
| bybit | +0.0312 | — | 64 | — |
| doge_bybit | +0.0405 | — | 37 | — |
| doge_hl | +0.0135 | — | 37 | — |
| eth_5m | +0.0193 | -0.0229 | 49 | +4.2¢/$ |
| hl | +0.0161 | — | 93 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 18 | 18 | 100.0% | 66.7% | -0.1792 |
| eth_5m | 14 | 14 | 100.0% | 35.7% | +0.1136 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 33.3% below 55% threshold (18 bets)
- ⚠️ Daily P&L $-134.91 — significant loss
- 📉 WR declining: 67% → 39% over 7 days
- ⚠️ Circuit breaker at 65% ($196 / $300)
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17821
- 🚨 Signal EHR negative: -0.0108 over 54 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 47.6% below 55% threshold (21 bets)
- 📉 WR declining: 75% → 47% over 7 days
- 🚨 23 integrity check failure(s) today
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17125; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17113; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17064; +7 more

### doge_bybit
- ⚠️ Daily WR 54.1% below 55% threshold (37 bets)
- 🚨 47 integrity check failure(s) today
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=13843; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=13833; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=13723

### doge_hl
- ⚠️ Daily WR 51.4% below 55% threshold (37 bets)
- ⚠️ orphaned_predictions: 24 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14501; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14500; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14499; +21 more

### eth_5m
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18221; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18220; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18211; +4 more

### hl
- ⚠️ Daily WR 51.4% below 55% threshold (35 bets)
- 📉 WR declining: 67% → 45% over 7 days
- ⚠️ orphaned_predictions: 21 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11397; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11394; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11380; +18 more
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 16.7% WR on 6 bets ($-100.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 30.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14307; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14306; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14296; +2 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.0% WR on 10 bets ($-100.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 30.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14305; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14304; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14294; +2 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.0% WR on 10 bets ($-100.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 189 |
| bybit_linear | connected | 1 |
| polymarket | connected | 37 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9652 | 17742 | 705 |
| Bybit event lag (ms) | 863 | 41795 | 509 |
| TA build (ms) | 70 | 134 | 705 |
| Pipeline fanout (ms) | 9589 | 17651 | 705 |
| Strategy Lab runtime (ms) | 172 | 1064 | 705 |
| Total dispatch wall time (ms) | 10066 | 18121 | 705 |
| True orderbook age (ms) | 6195 | 94660 | 598 |
| BTC 5m executable orderbook age (ms) | 358 | 1663 | 1000 |

- Slowest pipeline runtime: bybit p95=17641ms (241 samples)
- BTC 5m executable reads: fresh=180905 stale=253024 missing=744 partial=5968 total=440641
- Orderbook cache: 40 tokens, 514 token-set changes (24h)
- Cycles: 2614
- Fallback fires (24h): 0
- Engine start: 2026-06-14T04:00:01.847523+00:00

- Polymarket events: book=1382303, price_change=40801696, ignored={'last_trade_price': 624194, 'new_market': 8917, 'tick_size_change': 32}
- Orderbook freshness detail: fresh/stale tokens: 24/16, updated last 60s/5m: 32/40, stale reasons: {'stale_updated_at': 16}
- REST snapshot seed: 10289/10290 successful (missing=0, invalid_bbo=43)
- Polymarket resubscribe: resubscribe debounced/executed: 277/285, added/removed tokens: 1442/1856
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0047); execution_ehr_insufficient_sample (1/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0047 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $196.30 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $50.00 | $300.0 | No |
| hl | $0.00 | $300.0 | No |
| sol_bybit | $0.00 | $300.0 | No |
| sol_hl | $0.00 | $300.0 | No |

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
