# Consolidated Daily Report — 2026-06-20

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-20.md](2026-06-20.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 125 |
| Total wins | 45 |
| Total losses | 80 |
| Aggregate WR | 36.0% |
| Total P&L | **-$890.97** |
| Total wagered | $3,125.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 27 | 59.3% | +$125.00 | +0.043 | — | $675.00 |
| btc_5m | BTC | paper | 9 | 22.2% | -$128.41 | +0.002 | +0.008 | $225.00 |
| eth_5m | ETH | paper | 12 | 25.0% | -$162.56 | -0.076 | -0.029 | $300.00 |
| hl | BTC | paper | 31 | 38.7% | -$175.00 | +0.000 | — | $775.00 |
| doge_bybit | DOGE | paper | 23 | 30.4% | -$225.00 | -0.015 | — | $575.00 |
| doge_hl | DOGE | paper | 23 | 21.7% | -$325.00 | -0.073 | — | $575.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.136 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.106 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 67 | 44.8% | -$178.41 | $1,675.00 |
| **ETH** | eth_5m | 12 | 25.0% | -$162.56 | $300.00 |
| **DOGE** | doge_bybit, doge_hl | 46 | 26.1% | -$550.00 | $1,150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0017 | +0.0083 | 95 | -0.7¢/$ |
| bybit | +0.0435 | — | 138 | — |
| doge_bybit | -0.0147 | — | 68 | — |
| doge_hl | -0.0735 | — | 68 | — |
| eth_5m | -0.0759 | -0.0291 | 77 | -4.7¢/$ |
| hl | +0.0000 | — | 182 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 9 | 9 | 100.0% | 77.8% | -0.2258 |
| eth_5m | 12 | 12 | 100.0% | 75.0% | -0.2392 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 22.2% below 55% threshold (9 bets)
- ⚠️ Daily P&L $-128.41 — significant loss
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19433; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19284
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 22.2% WR on 9 bets ($-128.41); require cohort review before promotion

### bybit
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18941; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18927; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18919; +14 more

### doge_bybit
- ⚠️ Daily WR 30.4% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-225.00 — significant loss
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15591; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15590; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=15529; +10 more
- 🚨 Signal EHR negative: -0.0147 over 68 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.0% WR on 20 bets ($-200.00); require cohort review before promotion

### doge_hl
- ⚠️ Daily WR 21.7% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-325.00 — significant loss
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16149; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16148; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16087; +10 more
- 🚨 Signal EHR negative: -0.0735 over 68 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 20.0% WR on 20 bets ($-300.00); require cohort review before promotion

### eth_5m
- ⚠️ Daily WR 25.0% below 55% threshold (12 bets)
- ⚠️ Daily P&L $-162.56 — significant loss
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20016; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19988; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19985; +5 more
- 🚨 Signal EHR negative: -0.0759 over 77 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 16.7% WR on 6 bets ($-110.00); require cohort review before promotion

### hl
- ⚠️ Daily WR 38.7% below 55% threshold (31 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- ⚠️ orphaned_predictions: 18 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12977; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12970; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12958; +15 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 30 bets ($-150.00); require cohort review before promotion

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 54 |
| bybit_linear | connected | 0 |
| polymarket | connected | 32 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 5762 | 14591 | 606 |
| Bybit event lag (ms) | 674 | 18498 | 532 |
| TA build (ms) | 62 | 130 | 606 |
| Pipeline fanout (ms) | 5690 | 14405 | 606 |
| Strategy Lab runtime (ms) | 85 | 803 | 606 |
| Total dispatch wall time (ms) | 5919 | 15125 | 606 |
| True orderbook age (ms) | 387506 | 1769469 | 901 |
| BTC 5m executable orderbook age (ms) | 184 | 1540 | 1000 |

- Slowest pipeline runtime: bybit p95=16260ms (121 samples)
- BTC 5m executable reads: fresh=227200 stale=335456 missing=896 partial=7125 total=570677
- Orderbook cache: 40 tokens, 262 token-set changes (24h)
- Cycles: 1308
- Fallback fires (24h): 0
- Engine start: 2026-06-20T14:03:24.757960+00:00

- Polymarket events: book=420810, price_change=14809196, ignored={'last_trade_price': 187497, 'new_market': 2871, 'tick_size_change': 76}
- Orderbook freshness detail: fresh/stale tokens: 0/32, updated last 60s/5m: 0/0, stale reasons: {'missing_cache_entry': 32}
- REST snapshot seed: 3906/3910 successful (missing=2, invalid_bbo=36)
- Polymarket resubscribe: resubscribe debounced/executed: 149/189, added/removed tokens: 3850/3872
- Orderbook freshness decision: dominant cause: token not subscribed or not cached

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (1/10); polymarket_last_event_stale (14757s); orderbook_fresh_tokens_missing
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (+0.0119 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $75.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $27.70 | $300.0 | No |
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
