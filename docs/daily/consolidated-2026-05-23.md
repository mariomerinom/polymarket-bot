# Consolidated Daily Report — 2026-05-23

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-23.md](2026-05-23.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 109 |
| Total wins | 48 |
| Total losses | 61 |
| Aggregate WR | 44.0% |
| Total P&L | **-$343.30** |
| Total wagered | $2,725.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 30 | 53.3% | +$50.00 | +0.013 | — | $750.00 |
| sol_bybit | SOL | paper | 3 | 33.3% | -$25.00 | -0.077 | — | $75.00 |
| sol_hl | SOL | paper | 3 | 33.3% | -$25.00 | -0.077 | — | $75.00 |
| eth_5m | ETH | paper | 10 | 40.0% | -$47.39 | -0.010 | +0.064 | $250.00 |
| btc_5m | BTC | paper | 22 | 40.9% | -$120.91 | -0.108 | -0.092 | $550.00 |
| hl | BTC | paper | 41 | 41.5% | -$175.00 | -0.059 | — | $1,025.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.050 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.050 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 93 | 45.2% | -$245.91 | $2,325.00 |
| **ETH** | eth_5m | 10 | 40.0% | -$47.39 | $250.00 |
| **SOL** | sol_bybit, sol_hl | 6 | 33.3% | -$50.00 | $150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.1079 | -0.0925 | 137 | -1.5¢/$ |
| bybit | +0.0130 | — | 154 | — |
| doge_bybit | +0.0500 | — | 60 | — |
| doge_hl | +0.0500 | — | 60 | — |
| eth_5m | -0.0103 | +0.0641 | 101 | -7.4¢/$ |
| hl | -0.0586 | — | 222 | — |
| sol_bybit | -0.0775 | — | 142 | — |
| sol_hl | -0.0775 | — | 142 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 22 | 22 | 100.0% | 59.1% | -0.0967 |
| eth_5m | 10 | 10 | 100.0% | 60.0% | -0.1205 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 40.9% below 55% threshold (22 bets)
- ⚠️ Daily P&L $-120.91 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ Circuit breaker at 70% ($210 / $300)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11924; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11919; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11915; +1 more
- 🚨 Signal EHR negative: -0.1079 over 137 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 37.5% WR on 8 bets ($-43.09); require cohort review before promotion

### bybit
- ⚠️ Daily WR 53.3% below 55% threshold (30 bets)
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10873; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10858; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10857; +3 more
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 16.7% WR on 6 bets ($-100.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 40.0% below 55% threshold (10 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11740; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11739; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11735; +3 more
- 🚨 Signal EHR negative: -0.0103 over 101 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 41.5% below 55% threshold (41 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- ⚠️ orphaned_predictions: 26 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5596; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5584; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5583; +23 more
- 🚨 Signal EHR negative: -0.0586 over 222 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

### sol_bybit
- 🚨 4 consecutive losing days
- 📉 WR declining: 45% → 34% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7946
- 🚨 Signal EHR negative: -0.0775 over 142 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- 🚨 4 consecutive losing days
- 📉 WR declining: 45% → 34% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7944
- 🚨 Signal EHR negative: -0.0775 over 142 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 160 |
| bybit_linear | connected | 1 |
| polymarket | connected | 56 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8444 | 17576 | 705 |
| Bybit event lag (ms) | 864 | 35470 | 992 |
| TA build (ms) | 78 | 151 | 705 |
| Pipeline fanout (ms) | 8366 | 17438 | 705 |
| Strategy Lab runtime (ms) | 196 | 1210 | 705 |
| Total dispatch wall time (ms) | 8918 | 18353 | 705 |
| True orderbook age (ms) | 3766 | 96553 | 962 |

- Slowest pipeline runtime: bybit p95=17399ms (241 samples)
- Orderbook cache: 36 tokens, 519 token-set changes (24h)
- Cycles: 2616
- Fallback fires (24h): 0
- Engine start: 2026-05-23T04:00:02.672481+00:00

- Polymarket events: book=1682223, price_change=41010667, ignored={'last_trade_price': 781296, 'tick_size_change': 12}
- Orderbook freshness detail: fresh/stale tokens: 20/16, updated last 60s/5m: 36/36, stale reasons: {'stale_updated_at': 16}
- REST snapshot seed: 10294/10310 successful (missing=2, invalid_bbo=14)
- Polymarket resubscribe: resubscribe debounced/executed: 289/277, added/removed tokens: 1472/1888
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.1092); execution_ehr_insufficient_sample (0/10); orderbook_age_p95_too_high (96553)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.1092 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $209.98 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $8.13 | $300.0 | No |
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
