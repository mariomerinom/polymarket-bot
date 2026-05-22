# Consolidated Daily Report — 2026-05-21

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-21.md](2026-05-21.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 138 |
| Total wins | 71 |
| Total losses | 67 |
| Aggregate WR | 51.4% |
| Total P&L | **+$108.92** |
| Total wagered | $3,450.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 25 | 60.0% | +$125.00 | +0.006 | — | $625.00 |
| eth_5m | ETH | paper | 21 | 57.1% | +$79.32 | +0.036 | +0.108 | $525.00 |
| doge_bybit | DOGE | paper | 5 | 80.0% | +$75.00 | +0.059 | — | $125.00 |
| doge_hl | DOGE | paper | 5 | 80.0% | +$75.00 | +0.029 | — | $125.00 |
| hl | BTC | paper | 30 | 50.0% | $0.00 | -0.007 | — | $750.00 |
| btc_5m | BTC | paper | 28 | 46.4% | -$45.40 | -0.064 | -0.071 | $700.00 |
| sol_bybit | SOL | paper | 12 | 33.3% | -$100.00 | -0.080 | — | $300.00 |
| sol_hl | SOL | paper | 12 | 33.3% | -$100.00 | -0.080 | — | $300.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 83 | 51.8% | +$79.60 | $2,075.00 |
| **ETH** | eth_5m | 21 | 57.1% | +$79.32 | $525.00 |
| **SOL** | sol_bybit, sol_hl | 24 | 33.3% | -$200.00 | $600.00 |
| **DOGE** | doge_bybit, doge_hl | 10 | 80.0% | +$150.00 | $250.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0635 | -0.0708 | 149 | +0.7¢/$ |
| bybit | +0.0064 | — | 156 | — |
| doge_bybit | +0.0588 | — | 34 | — |
| doge_hl | +0.0294 | — | 34 | — |
| eth_5m | +0.0358 | +0.1076 | 114 | -7.2¢/$ |
| hl | -0.0067 | — | 223 | — |
| sol_bybit | -0.0797 | — | 138 | — |
| sol_hl | -0.0797 | — | 138 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 28 | 28 | 100.0% | 53.6% | -0.0189 |
| eth_5m | 21 | 20 | 95.2% | 45.0% | +0.0419 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 46.4% below 55% threshold (28 bets)
- ⚠️ Circuit breaker at 62% ($186 / $300)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11509; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11504; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11313
- 🚨 Signal EHR negative: -0.0635 over 149 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10345; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10339; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10322; +14 more

### doge_bybit
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6819; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6818; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=6817; +1 more

### doge_hl
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7377; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7376; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7375; +1 more

### eth_5m
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11212; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11180; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11179; +5 more

### hl
- ⚠️ Daily WR 50.0% below 55% threshold (30 bets)
- 🚨 13 integrity check failure(s) today
- ⚠️ orphaned_predictions: 16 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5021; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5017; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5007; +13 more
- 🚨 Signal EHR negative: -0.0067 over 223 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 33.3% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7426; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7398; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7397; +3 more
- 🚨 Signal EHR negative: -0.0797 over 138 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 33.3% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7424; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7396; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7395; +3 more
- 🚨 Signal EHR negative: -0.0797 over 138 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 33.3% WR on 12 bets ($-100.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 144 |
| bybit_linear | connected | 1 |
| polymarket | connected | 18 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 7262 | 11666 | 705 |
| Bybit event lag (ms) | 865 | 24211 | 562 |
| TA build (ms) | 89 | 170 | 705 |
| Pipeline fanout (ms) | 7177 | 11499 | 705 |
| Strategy Lab runtime (ms) | 134 | 893 | 705 |
| Total dispatch wall time (ms) | 7543 | 12135 | 705 |
| True orderbook age (ms) | 2312 | 68510 | 655 |

- Slowest pipeline runtime: eth_5m p95=13675ms (241 samples)
- Orderbook cache: 36 tokens, 504 token-set changes (24h)
- Cycles: 2618
- Fallback fires (24h): 0
- Engine start: 2026-05-21T04:00:02.743400+00:00

- Polymarket events: book=1553631, price_change=26335096, ignored={'last_trade_price': 726732, 'tick_size_change': 24}
- Orderbook freshness detail: fresh/stale tokens: 16/20, updated last 60s/5m: 36/36, stale reasons: {'stale_updated_at': 20}
- REST snapshot seed: 10936/10940 successful (missing=0, invalid_bbo=4)
- Polymarket resubscribe: resubscribe debounced/executed: 270/324, added/removed tokens: 1408/1636
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.1145); execution_ehr_insufficient_sample (0/10); orderbook_age_p95_too_high (68510); orderbook_stale_tokens_exceed_fresh (20/16)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $186.03 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $31.43 | $300.0 | No |
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
