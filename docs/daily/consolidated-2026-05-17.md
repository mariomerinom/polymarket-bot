# Consolidated Daily Report — 2026-05-17

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-17.md](2026-05-17.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 240 |
| Total wins | 99 |
| Total losses | 141 |
| Aggregate WR | 41.2% |
| Total P&L | **-$1,040.45** |
| Total wagered | $6,000.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 12 | 58.3% | +$65.27 | -0.012 | -0.082 | $300.00 |
| doge_bybit | DOGE | paper | 26 | 50.0% | $0.00 | +0.048 | — | $650.00 |
| bybit | BTC | paper | 17 | 47.1% | -$25.00 | -0.036 | — | $425.00 |
| doge_hl | DOGE | paper | 26 | 46.2% | -$50.00 | +0.016 | — | $650.00 |
| hl | BTC | paper | 28 | 39.3% | -$150.00 | -0.064 | — | $700.00 |
| btc_5m | BTC | paper | 15 | 26.7% | -$180.72 | -0.054 | -0.098 | $375.00 |
| sol_bybit | SOL | paper | 58 | 37.9% | -$350.00 | -0.064 | — | $1,450.00 |
| sol_hl | SOL | paper | 58 | 37.9% | -$350.00 | -0.064 | — | $1,450.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 60 | 38.3% | -$355.72 | $1,500.00 |
| **ETH** | eth_5m | 12 | 58.3% | +$65.27 | $300.00 |
| **SOL** | sol_bybit, sol_hl | 116 | 37.9% | -$700.00 | $2,900.00 |
| **DOGE** | doge_bybit, doge_hl | 52 | 48.1% | -$50.00 | $1,300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0543 | -0.0983 | 120 | +4.4¢/$ |
| bybit | -0.0364 | — | 110 | — |
| doge_bybit | +0.0484 | — | 31 | — |
| doge_hl | +0.0161 | — | 31 | — |
| eth_5m | -0.0118 | -0.0823 | 114 | +7.0¢/$ |
| hl | -0.0644 | — | 163 | — |
| sol_bybit | -0.0644 | — | 101 | — |
| sol_hl | -0.0644 | — | 101 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 15 | 14 | 93.3% | 78.6% | -0.2655 |
| eth_5m | 12 | 12 | 100.0% | 41.7% | +0.1192 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 26.7% below 55% threshold (15 bets)
- ⚠️ Daily P&L $-180.72 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10358; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10268; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10254
- 🚨 Signal EHR negative: -0.0543 over 120 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 36.4% WR on 11 bets ($-80.72); require cohort review before promotion

### bybit
- ⚠️ Daily WR 47.1% below 55% threshold (17 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 62% → 47% over 7 days
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9171; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9170; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9142; +2 more
- 🚨 Signal EHR negative: -0.0364 over 110 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 41.7% WR on 12 bets ($-50.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (26 bets)
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5788; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5784; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5783; +11 more
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / MEAN_REVERTING is 33.3% WR on 6 bets ($-50.00); require cohort review before promotion

### doge_hl
- ⚠️ Daily WR 46.2% below 55% threshold (26 bets)
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6346; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6342; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6341; +11 more
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / MEAN_REVERTING is 33.3% WR on 6 bets ($-50.00); require cohort review before promotion

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10034; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10033
- 🚨 Signal EHR negative: -0.0118 over 114 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 39.3% below 55% threshold (28 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4019; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3993; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=3979; +9 more
- 🚨 Signal EHR negative: -0.0644 over 163 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 31.2% WR on 16 bets ($-150.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 37.9% below 55% threshold (58 bets)
- ⚠️ Daily P&L $-350.00 — significant loss
- ⚠️ orphaned_predictions: 40 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6413; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6412; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6407; +37 more
- 🚨 Signal EHR negative: -0.0644 over 101 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 34.4% WR on 32 bets ($-250.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 37.9% below 55% threshold (58 bets)
- ⚠️ Daily P&L $-350.00 — significant loss
- ⚠️ orphaned_predictions: 40 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6411; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6410; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6405; +37 more
- 🚨 Signal EHR negative: -0.0644 over 101 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 34.4% WR on 32 bets ($-250.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 66 |
| bybit_linear | connected | 0 |
| polymarket | connected | 12 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 5857 | 10135 | 705 |
| Bybit event lag (ms) | 799 | 21932 | 590 |
| TA build (ms) | 89 | 207 | 705 |
| Pipeline fanout (ms) | 5739 | 10022 | 705 |
| Strategy Lab runtime (ms) | 109 | 370 | 705 |
| Total dispatch wall time (ms) | 6006 | 10383 | 705 |
| True orderbook age (ms) | 7692 | 79750 | 611 |

- Slowest pipeline runtime: eth_5m p95=11871ms (241 samples)
- Orderbook cache: 40 tokens, 485 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-05-17T04:00:02.753750+00:00

- Polymarket events: book=1416740, price_change=17671428, ignored={'last_trade_price': 693125, 'tick_size_change': 132}
- Orderbook freshness detail: fresh/stale tokens: 12/28, updated last 60s/5m: 18/40, stale reasons: {'stale_updated_at': 28}
- REST snapshot seed: 10214/10224 successful (missing=1, invalid_bbo=9)
- Polymarket resubscribe: resubscribe debounced/executed: 249/336, added/removed tokens: 1352/1552
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0699); execution_ehr_insufficient_sample (0/10); orderbook_age_p95_too_high (79750); orderbook_stale_tokens_exceed_fresh (28/12)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $100.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $13.09 | $300.0 | No |
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
