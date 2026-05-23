# Consolidated Daily Report — 2026-05-22

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-22.md](2026-05-22.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 104 |
| Total wins | 43 |
| Total losses | 61 |
| Aggregate WR | 41.3% |
| Total P&L | **-$453.11** |
| Total wagered | $2,600.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| doge_hl | DOGE | paper | 26 | 57.7% | +$100.00 | +0.050 | — | $650.00 |
| doge_bybit | DOGE | paper | 26 | 53.8% | +$50.00 | +0.050 | — | $650.00 |
| bybit | BTC | paper | 6 | 33.3% | -$50.00 | -0.004 | — | $150.00 |
| btc_5m | BTC | paper | 3 | 0.0% | -$75.00 | -0.124 | -0.094 | $75.00 |
| sol_bybit | SOL | paper | 11 | 36.4% | -$75.00 | -0.073 | — | $275.00 |
| sol_hl | SOL | paper | 11 | 36.4% | -$75.00 | -0.073 | — | $275.00 |
| eth_5m | ETH | paper | 12 | 33.3% | -$103.11 | -0.013 | +0.064 | $300.00 |
| hl | BTC | paper | 9 | 0.0% | -$225.00 | -0.053 | — | $225.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 18 | 11.1% | -$350.00 | $450.00 |
| **ETH** | eth_5m | 12 | 33.3% | -$103.11 | $300.00 |
| **SOL** | sol_bybit, sol_hl | 22 | 36.4% | -$150.00 | $550.00 |
| **DOGE** | doge_bybit, doge_hl | 52 | 55.8% | +$150.00 | $1,300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.1239 | -0.0942 | 124 | -3.0¢/$ |
| bybit | -0.0036 | — | 139 | — |
| doge_bybit | +0.0500 | — | 60 | — |
| doge_hl | +0.0500 | — | 60 | — |
| eth_5m | -0.0125 | +0.0640 | 106 | -7.6¢/$ |
| hl | -0.0528 | — | 199 | — |
| sol_bybit | -0.0734 | — | 143 | — |
| sol_hl | -0.0734 | — | 143 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 3 | 3 | 100.0% | 100.0% | -0.2508 |
| eth_5m | 12 | 12 | 100.0% | 66.7% | -0.1954 |

## 6. Alerts (All Pipelines)

### btc_5m
- 🚨 Signal EHR negative: -0.1239 over 124 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 33.3% below 55% threshold (6 bets)
- 🚨 48 integrity check failure(s) today
- 🚨 Signal EHR negative: -0.0036 over 139 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 6 bets ($-50.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 53.8% below 55% threshold (26 bets)
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7238; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7237; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7235; +14 more

### doge_hl
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7796; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7795; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7793; +14 more

### eth_5m
- ⚠️ Daily WR 33.3% below 55% threshold (12 bets)
- ⚠️ Daily P&L $-103.11 — significant loss
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11509; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11476; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11354; +1 more
- 🚨 Signal EHR negative: -0.0125 over 106 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 40.0% WR on 5 bets ($-21.86); require cohort review before promotion

### hl
- ⚠️ Daily WR 0.0% below 55% threshold (9 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- 🚨 8 integrity check failure(s) today
- 🚨 Signal EHR negative: -0.0528 over 199 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 0.0% WR on 9 bets ($-225.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 36.4% below 55% threshold (11 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 50% → 38% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7692
- 🚨 Signal EHR negative: -0.0734 over 143 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 36.4% WR on 11 bets ($-75.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 36.4% below 55% threshold (11 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 50% → 38% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7690
- 🚨 Signal EHR negative: -0.0734 over 143 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 36.4% WR on 11 bets ($-75.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 166 |
| bybit_linear | connected | 1 |
| polymarket | connected | 37 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8636 | 19729 | 705 |
| Bybit event lag (ms) | 863 | 31884 | 971 |
| TA build (ms) | 82 | 149 | 705 |
| Pipeline fanout (ms) | 8564 | 19657 | 705 |
| Strategy Lab runtime (ms) | 213 | 1389 | 705 |
| Total dispatch wall time (ms) | 9183 | 20533 | 705 |
| True orderbook age (ms) | 2998 | 101517 | 589 |

- Slowest pipeline runtime: btc_5m p95=19854ms (224 samples)
- Orderbook cache: 40 tokens, 516 token-set changes (24h)
- Cycles: 2618
- Fallback fires (24h): 0
- Engine start: 2026-05-22T04:00:02.674765+00:00

- Polymarket events: book=1690855, price_change=34316232, ignored={'last_trade_price': 778623, 'tick_size_change': 12}
- Orderbook freshness detail: fresh/stale tokens: 16/24, updated last 60s/5m: 36/36, stale reasons: {'rest_snapshot_missing': 4, 'stale_updated_at': 20}
- REST snapshot seed: 11235/11254 successful (missing=10, invalid_bbo=9)
- Polymarket resubscribe: resubscribe debounced/executed: 290/293, added/removed tokens: 1382/1816
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.1116); execution_ehr_insufficient_sample (1/10); orderbook_age_p95_too_high (101517); orderbook_stale_tokens_exceed_fresh (24/16)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.1116 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $0.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $64.04 | $300.0 | No |
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
