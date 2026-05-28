# Consolidated Daily Report — 2026-05-27

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-27.md](2026-05-27.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 132 |
| Total wins | 62 |
| Total losses | 70 |
| Aggregate WR | 47.0% |
| Total P&L | **-$213.46** |
| Total wagered | $3,300.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 26 | 50.0% | $0.00 | -0.024 | — | $650.00 |
| sol_hl | SOL | paper | 26 | 50.0% | $0.00 | -0.030 | — | $650.00 |
| bybit | BTC | paper | 19 | 47.4% | -$25.00 | +0.018 | — | $475.00 |
| btc_5m | BTC | paper | 21 | 47.6% | -$41.99 | -0.017 | +0.042 | $525.00 |
| eth_5m | ETH | paper | 12 | 41.7% | -$46.47 | -0.035 | +0.009 | $300.00 |
| hl | BTC | paper | 28 | 42.9% | -$100.00 | -0.021 | — | $700.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.045 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.054 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 68 | 45.6% | -$166.99 | $1,700.00 |
| **ETH** | eth_5m | 12 | 41.7% | -$46.47 | $300.00 |
| **SOL** | sol_bybit, sol_hl | 52 | 50.0% | $0.00 | $1,300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0168 | +0.0423 | 168 | -5.9¢/$ |
| bybit | +0.0181 | — | 193 | — |
| doge_bybit | +0.0446 | — | 101 | — |
| doge_hl | +0.0545 | — | 101 | — |
| eth_5m | -0.0350 | +0.0095 | 117 | -4.5¢/$ |
| hl | -0.0206 | — | 267 | — |
| sol_bybit | -0.0235 | — | 149 | — |
| sol_hl | -0.0302 | — | 149 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 21 | 21 | 100.0% | 52.4% | -0.0325 |
| eth_5m | 12 | 12 | 100.0% | 58.3% | -0.0377 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 47.6% below 55% threshold (21 bets)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13059; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12995; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12951; +1 more
- 🚨 Signal EHR negative: -0.0168 over 168 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 47.4% below 55% threshold (19 bets)
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12064; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12005; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12004; +8 more

### doge_bybit
- 📉 WR declining: 67% → 52% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- 📉 WR declining: 69% → 53% over 7 days
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 41.7% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12950; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12915; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12906
- 🚨 Signal EHR negative: -0.0350 over 117 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 42.9% below 55% threshold (28 bets)
- ⚠️ orphaned_predictions: 16 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6676; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6675; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6654; +13 more
- 🚨 Signal EHR negative: -0.0206 over 267 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 28 bets ($-100.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (26 bets)
- ⚠️ orphaned_predictions: 15 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9160; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9159; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9158; +12 more
- 🚨 Signal EHR negative: -0.0235 over 149 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ Daily WR 50.0% below 55% threshold (26 bets)
- ⚠️ orphaned_predictions: 15 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9158; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9157; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9156; +12 more
- 🚨 Signal EHR negative: -0.0302 over 149 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 207 |
| bybit_linear | connected | 5 |
| polymarket | connected | 48 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10912 | 24067 | 705 |
| Bybit event lag (ms) | 863 | 47079 | 686 |
| TA build (ms) | 81 | 181 | 705 |
| Pipeline fanout (ms) | 10863 | 23976 | 705 |
| Strategy Lab runtime (ms) | 345 | 1518 | 705 |
| Total dispatch wall time (ms) | 11357 | 24645 | 705 |
| True orderbook age (ms) | 5479 | 72926 | 572 |
| BTC 5m executable orderbook age (ms) | 2199 | 7789 | 1000 |

- Slowest pipeline runtime: btc_5m p95=27908ms (229 samples)
- BTC 5m executable reads: fresh=17361 stale=11839 missing=40 partial=1030 total=30270
- Orderbook cache: 30 tokens, 510 token-set changes (24h)
- Cycles: 2628
- Fallback fires (24h): 0
- Engine start: 2026-05-27T04:00:02.159640+00:00

- Polymarket events: book=1571699, price_change=44413730, ignored={'last_trade_price': 719601, 'new_market': 7164, 'tick_size_change': 48}
- Orderbook freshness detail: fresh/stale tokens: 16/14, updated last 60s/5m: 26/30, stale reasons: {'stale_updated_at': 14}
- REST snapshot seed: 8568/8580 successful (missing=2, invalid_bbo=10)
- Polymarket resubscribe: resubscribe debounced/executed: 281/258, added/removed tokens: 1336/1956
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0269); execution_ehr_insufficient_sample (1/10); btc5m_executable_orderbook_age_p95_too_high (7789)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0269 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $100.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $50.85 | $300.0 | No |
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
