# Consolidated Daily Report — 2026-05-26

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-26.md](2026-05-26.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 243 |
| Total wins | 132 |
| Total losses | 111 |
| Aggregate WR | 54.3% |
| Total P&L | **+$478.60** |
| Total wagered | $6,075.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 24 | 62.5% | +$150.00 | -0.026 | — | $600.00 |
| sol_hl | SOL | paper | 24 | 62.5% | +$150.00 | -0.033 | — | $600.00 |
| bybit | BTC | paper | 35 | 54.3% | +$75.00 | +0.005 | — | $875.00 |
| doge_bybit | DOGE | paper | 29 | 55.2% | +$75.00 | +0.045 | — | $725.00 |
| doge_hl | DOGE | paper | 29 | 55.2% | +$75.00 | +0.054 | — | $725.00 |
| btc_5m | BTC | paper | 32 | 53.1% | +$51.45 | -0.033 | -0.027 | $800.00 |
| hl | BTC | paper | 50 | 52.0% | +$50.00 | -0.016 | — | $1,250.00 |
| eth_5m | ETH | paper | 20 | 40.0% | -$147.85 | -0.014 | +0.034 | $500.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 117 | 53.0% | +$176.45 | $2,925.00 |
| **ETH** | eth_5m | 20 | 40.0% | -$147.85 | $500.00 |
| **SOL** | sol_bybit, sol_hl | 48 | 62.5% | +$300.00 | $1,200.00 |
| **DOGE** | doge_bybit, doge_hl | 58 | 55.2% | +$150.00 | $1,450.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0327 | -0.0268 | 170 | -0.6¢/$ |
| bybit | +0.0051 | — | 196 | — |
| doge_bybit | +0.0446 | — | 101 | — |
| doge_hl | +0.0545 | — | 101 | — |
| eth_5m | -0.0139 | +0.0342 | 122 | -4.8¢/$ |
| hl | -0.0164 | — | 275 | — |
| sol_bybit | -0.0259 | — | 135 | — |
| sol_hl | -0.0333 | — | 135 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 32 | 32 | 100.0% | 46.9% | +0.0495 |
| eth_5m | 20 | 20 | 100.0% | 60.0% | -0.0938 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 53.1% below 55% threshold (32 bets)
- ⚠️ Circuit breaker at 65% ($194 / $300)
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12828; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12814; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12811; +6 more
- 🚨 Signal EHR negative: -0.0327 over 170 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in HIGH_VOL / TRENDING is 33.3% WR on 6 bets ($-55.72); require cohort review before promotion

### bybit
- ⚠️ Daily WR 54.3% below 55% threshold (35 bets)
- ⚠️ orphaned_predictions: 23 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11777; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11773; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11772; +20 more

### doge_bybit
- 📉 WR declining: 67% → 52% over 7 days
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 15 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8385; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8384; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8383; +12 more

### doge_hl
- 📉 WR declining: 69% → 53% over 7 days
- ⚠️ orphaned_predictions: 18 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8943; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8942; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8941; +15 more

### eth_5m
- ⚠️ Daily WR 40.0% below 55% threshold (20 bets)
- ⚠️ Daily P&L $-147.85 — significant loss
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12671; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12670; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12637; +3 more
- 🚨 Signal EHR negative: -0.0139 over 122 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / TRENDING is 40.0% WR on 5 bets ($-63.97); require cohort review before promotion

### hl
- ⚠️ Daily WR 52.0% below 55% threshold (50 bets)
- ⚠️ orphaned_predictions: 35 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6415; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6412; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6411; +32 more
- 🚨 Signal EHR negative: -0.0164 over 275 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8867; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8866; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8865; +11 more
- 🚨 Signal EHR negative: -0.0259 over 135 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8865; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8864; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8863; +11 more
- 🚨 Signal EHR negative: -0.0333 over 135 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 123 |
| bybit_linear | connected | 3 |
| polymarket | connected | 83 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 11240 | 29801 | 665 |
| Bybit event lag (ms) | 864 | 49719 | 518 |
| TA build (ms) | 81 | 182 | 666 |
| Pipeline fanout (ms) | 11184 | 29728 | 665 |
| Strategy Lab runtime (ms) | 777 | 1685 | 665 |
| Total dispatch wall time (ms) | 12216 | 31095 | 665 |
| True orderbook age (ms) | 3492 | 79087 | 763 |
| BTC 5m executable orderbook age (ms) | 2289 | 7910 | 1000 |

- Slowest pipeline runtime: btc_5m p95=32119ms (118 samples)
- BTC 5m executable reads: fresh=6009 stale=4223 missing=15 partial=384 total=10631
- Orderbook cache: 28 tokens, 284 token-set changes (24h)
- Cycles: 1434
- Fallback fires (24h): 0
- Engine start: 2026-05-26T13:00:03.770856+00:00

- Polymarket events: book=953374, price_change=29672575, ignored={'last_trade_price': 415736, 'new_market': 4479, 'tick_size_change': 48, 'market_resolved': 2}
- Orderbook freshness detail: fresh/stale tokens: 16/14, updated last 60s/5m: 22/26, stale reasons: {'stale_updated_at': 10, 'missing_cache_entry': 4}
- REST snapshot seed: 6756/6772 successful (missing=0, invalid_bbo=16)
- Polymarket resubscribe: resubscribe debounced/executed: 166/128, added/removed tokens: 812/1084
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0163); execution_ehr_insufficient_sample (0/10); btc5m_executable_orderbook_age_p95_too_high (7910)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0163 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $194.12 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $106.16 | $300.0 | No |
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
