# Consolidated Daily Report — 2026-05-19

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-19.md](2026-05-19.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 122 |
| Total wins | 55 |
| Total losses | 67 |
| Aggregate WR | 45.1% |
| Total P&L | **-$286.67** |
| Total wagered | $3,050.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 17 | 58.8% | +$81.95 | -0.001 | -0.037 | $425.00 |
| sol_bybit | SOL | paper | 12 | 50.0% | $0.00 | -0.073 | — | $300.00 |
| sol_hl | SOL | paper | 12 | 50.0% | $0.00 | -0.073 | — | $300.00 |
| hl | BTC | paper | 36 | 47.2% | -$50.00 | -0.066 | — | $900.00 |
| bybit | BTC | paper | 22 | 36.4% | -$150.00 | -0.055 | — | $550.00 |
| btc_5m | BTC | paper | 23 | 34.8% | -$168.62 | -0.096 | -0.165 | $575.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.017 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 81 | 40.7% | -$368.62 | $2,025.00 |
| **ETH** | eth_5m | 17 | 58.8% | +$81.95 | $425.00 |
| **SOL** | sol_bybit, sol_hl | 24 | 50.0% | $0.00 | $600.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0957 | -0.1650 | 143 | +6.9¢/$ |
| bybit | -0.0547 | — | 137 | — |
| doge_bybit | +0.0172 | — | 29 | — |
| doge_hl | -0.0172 | — | 29 | — |
| eth_5m | -0.0005 | -0.0369 | 123 | +3.6¢/$ |
| hl | -0.0659 | — | 205 | — |
| sol_bybit | -0.0727 | — | 110 | — |
| sol_hl | -0.0727 | — | 110 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 23 | 23 | 100.0% | 65.2% | -0.0973 |
| eth_5m | 17 | 17 | 100.0% | 41.2% | +0.1207 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 34.8% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-168.62 — significant loss
- 🚨 5 consecutive losing days
- 📉 WR declining: 43% → 25% over 7 days
- ⚠️ Circuit breaker at 85% ($256 / $300)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10892; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10798; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10786
- 🚨 Signal EHR negative: -0.0957 over 143 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 34.8% WR on 23 bets ($-168.62); require cohort review before promotion

### bybit
- ⚠️ Daily WR 36.4% below 55% threshold (22 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9547; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9546; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9545; +2 more
- 🚨 Signal EHR negative: -0.0547 over 137 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 36.4% WR on 22 bets ($-150.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10554; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10371
- 🚨 Signal EHR negative: -0.0005 over 123 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 20.0% WR on 5 bets ($-74.49); require cohort review before promotion

### hl
- ⚠️ Daily WR 47.2% below 55% threshold (36 bets)
- 🚨 5 consecutive losing days
- 📉 WR declining: 49% → 37% over 7 days
- ⚠️ orphaned_predictions: 19 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4576; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4498; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4492; +16 more
- 🚨 Signal EHR negative: -0.0659 over 205 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7012; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7011; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7010; +4 more
- 🚨 Signal EHR negative: -0.0727 over 110 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 33.3% WR on 6 bets ($-50.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 50.0% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7010; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7009; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7008; +4 more
- 🚨 Signal EHR negative: -0.0727 over 110 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 33.3% WR on 6 bets ($-50.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 183 |
| bybit_linear | connected | 6 |
| polymarket | connected | 26 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8480 | 16084 | 705 |
| Bybit event lag (ms) | 863 | 29140 | 984 |
| TA build (ms) | 87 | 164 | 705 |
| Pipeline fanout (ms) | 8394 | 16004 | 705 |
| Strategy Lab runtime (ms) | 185 | 1167 | 705 |
| Total dispatch wall time (ms) | 8711 | 16535 | 705 |
| True orderbook age (ms) | 8251 | 106173 | 581 |

- Slowest pipeline runtime: bybit p95=17148ms (241 samples)
- Orderbook cache: 38 tokens, 537 token-set changes (24h)
- Cycles: 2622
- Fallback fires (24h): 0
- Engine start: 2026-05-19T04:00:02.552344+00:00

- Polymarket events: book=1715980, price_change=40731110, ignored={'last_trade_price': 835745, 'tick_size_change': 252}
- Orderbook freshness detail: fresh/stale tokens: 12/26, updated last 60s/5m: 22/34, stale reasons: {'stale_updated_at': 22, 'missing_cache_entry': 4}
- REST snapshot seed: 10613/10624 successful (missing=0, invalid_bbo=11)
- Polymarket resubscribe: resubscribe debounced/executed: 304/285, added/removed tokens: 1518/1952
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0927); execution_ehr_insufficient_sample (1/10); orderbook_age_p95_too_high (106173); orderbook_stale_tokens_exceed_fresh (26/12)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $256.48 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $66.67 | $300.0 | No |
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
