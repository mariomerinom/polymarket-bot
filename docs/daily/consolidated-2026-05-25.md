# Consolidated Daily Report — 2026-05-25

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-25.md](2026-05-25.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 200 |
| Total wins | 96 |
| Total losses | 104 |
| Aggregate WR | 48.0% |
| Total P&L | **-$183.54** |
| Total wagered | $5,000.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 24 | 58.3% | +$96.51 | -0.066 | -0.053 | $600.00 |
| eth_5m | ETH | paper | 13 | 53.8% | +$44.95 | -0.014 | +0.087 | $325.00 |
| doge_bybit | DOGE | paper | 23 | 52.2% | +$25.00 | +0.042 | — | $575.00 |
| hl | BTC | paper | 42 | 50.0% | $0.00 | -0.032 | — | $1,050.00 |
| bybit | BTC | paper | 31 | 48.4% | -$25.00 | -0.003 | — | $775.00 |
| doge_hl | DOGE | paper | 23 | 47.8% | -$25.00 | +0.056 | — | $575.00 |
| sol_bybit | SOL | paper | 22 | 36.4% | -$150.00 | -0.059 | — | $550.00 |
| sol_hl | SOL | paper | 22 | 36.4% | -$150.00 | -0.068 | — | $550.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 97 | 51.5% | +$71.51 | $2,425.00 |
| **ETH** | eth_5m | 13 | 53.8% | +$44.95 | $325.00 |
| **SOL** | sol_bybit, sol_hl | 44 | 36.4% | -$300.00 | $1,100.00 |
| **DOGE** | doge_bybit, doge_hl | 46 | 50.0% | $0.00 | $1,150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0660 | -0.0531 | 144 | -1.3¢/$ |
| bybit | -0.0030 | — | 169 | — |
| doge_bybit | +0.0417 | — | 72 | — |
| doge_hl | +0.0556 | — | 72 | — |
| eth_5m | -0.0143 | +0.0873 | 114 | -10.2¢/$ |
| hl | -0.0319 | — | 235 | — |
| sol_bybit | -0.0586 | — | 111 | — |
| sol_hl | -0.0676 | — | 111 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 24 | 24 | 100.0% | 41.7% | +0.1067 |
| eth_5m | 13 | 13 | 100.0% | 46.2% | +0.0737 |

## 6. Alerts (All Pipelines)

### btc_5m
- 📉 WR declining: 45% → 31% over 7 days
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12530; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12409; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12408; +5 more
- 🚨 Signal EHR negative: -0.0660 over 144 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 48.4% below 55% threshold (31 bets)
- 📉 WR declining: 53% → 42% over 7 days
- ⚠️ orphaned_predictions: 21 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11491; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11490; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11381; +18 more
- 🚨 Signal EHR negative: -0.0030 over 169 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 28.6% WR on 7 bets ($-75.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 52.2% below 55% threshold (23 bets)
- 📉 WR declining: 67% → 51% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8074; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8073; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8062; +2 more

### doge_hl
- ⚠️ Daily WR 47.8% below 55% threshold (23 bets)
- 📉 WR declining: 69% → 52% over 7 days
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8793; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8715; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8714; +11 more

### eth_5m
- ⚠️ Daily WR 53.8% below 55% threshold (13 bets)
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12233
- 🚨 Signal EHR negative: -0.0143 over 114 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 20.0% WR on 5 bets ($-45.63); require cohort review before promotion

### hl
- ⚠️ Daily WR 50.0% below 55% threshold (42 bets)
- 📉 WR declining: 54% → 33% over 7 days
- ⚠️ orphaned_predictions: 29 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6155; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6150; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6117; +26 more
- 🚨 Signal EHR negative: -0.0319 over 235 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 40.0% WR on 10 bets ($-50.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 36.4% below 55% threshold (22 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8734; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8724; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8695; +9 more
- 🚨 Signal EHR negative: -0.0586 over 111 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 41.2% WR on 17 bets ($-75.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 36.4% below 55% threshold (22 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8732; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8722; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8693; +9 more
- 🚨 Signal EHR negative: -0.0676 over 111 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 41.2% WR on 17 bets ($-75.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 210 |
| bybit_linear | connected | 5 |
| polymarket | connected | 80 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10128 | 22187 | 705 |
| Bybit event lag (ms) | 873 | 34386 | 815 |
| TA build (ms) | 81 | 180 | 705 |
| Pipeline fanout (ms) | 10023 | 22103 | 705 |
| Strategy Lab runtime (ms) | 247 | 1549 | 705 |
| Total dispatch wall time (ms) | 10667 | 23396 | 705 |
| True orderbook age (ms) | 5876 | 113610 | 589 |
| BTC 5m executable orderbook age (ms) | 1862 | 7999 | 35 |

- Slowest pipeline runtime: btc_5m p95=24120ms (215 samples)
- BTC 5m executable reads: fresh=35 stale=1 missing=0 partial=0 total=36
- Orderbook cache: 40 tokens, 523 token-set changes (24h)
- Cycles: 2600
- Fallback fires (24h): 0
- Engine start: 2026-05-25T04:00:02.434949+00:00

- Polymarket events: book=1549944, price_change=43427602, ignored={'last_trade_price': 714962, 'new_market': 6894, 'tick_size_change': 32}
- Orderbook freshness detail: fresh/stale tokens: 14/26, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 26}
- REST snapshot seed: 11892/11892 successful (missing=0, invalid_bbo=0)
- Polymarket resubscribe: resubscribe debounced/executed: 297/267, added/removed tokens: 1480/1948
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0472); execution_ehr_insufficient_sample (2/10); btc5m_executable_orderbook_age_p95_too_high (7999)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0472 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $89.36 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
