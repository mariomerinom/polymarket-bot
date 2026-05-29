# Consolidated Daily Report — 2026-05-28

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-28.md](2026-05-28.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 40 |
| Total wins | 18 |
| Total losses | 22 |
| Aggregate WR | 45.0% |
| Total P&L | **-$129.70** |
| Total wagered | $1,000.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 5 | 60.0% | +$16.32 | -0.022 | +0.030 | $125.00 |
| bybit | BTC | paper | 8 | 50.0% | $0.00 | +0.000 | — | $200.00 |
| sol_bybit | SOL | paper | 4 | 50.0% | $0.00 | -0.017 | — | $100.00 |
| sol_hl | SOL | paper | 4 | 50.0% | $0.00 | -0.025 | — | $100.00 |
| eth_5m | ETH | paper | 10 | 40.0% | -$71.02 | -0.040 | -0.060 | $250.00 |
| hl | BTC | paper | 9 | 33.3% | -$75.00 | -0.053 | — | $225.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.045 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.054 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 22 | 45.5% | -$58.68 | $550.00 |
| **ETH** | eth_5m | 10 | 40.0% | -$71.02 | $250.00 |
| **SOL** | sol_bybit, sol_hl | 8 | 50.0% | $0.00 | $200.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0216 | +0.0296 | 151 | -5.1¢/$ |
| bybit | +0.0000 | — | 172 | — |
| doge_bybit | +0.0446 | — | 101 | — |
| doge_hl | +0.0545 | — | 101 | — |
| eth_5m | -0.0397 | -0.0599 | 115 | +2.0¢/$ |
| hl | -0.0532 | — | 235 | — |
| sol_bybit | -0.0169 | — | 118 | — |
| sol_hl | -0.0254 | — | 118 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 5 | 5 | 100.0% | 40.0% | +0.1675 |
| eth_5m | 10 | 10 | 100.0% | 60.0% | -0.1380 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13223
- 🚨 Signal EHR negative: -0.0216 over 151 bets (7-day) — model may be buying overpriced contracts

### bybit
- ⚠️ Daily WR 50.0% below 55% threshold (8 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12346; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12196; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12194

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 40.0% below 55% threshold (10 bets)
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13245; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13201; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13200; +1 more
- 🚨 Signal EHR negative: -0.0397 over 115 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 33.3% below 55% threshold (9 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6946; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6809; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=6807
- 🚨 Signal EHR negative: -0.0532 over 235 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 37.5% WR on 8 bets ($-50.00); require cohort review before promotion

### sol_bybit
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9465; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9464
- 🚨 Signal EHR negative: -0.0169 over 118 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9463; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=9462
- 🚨 Signal EHR negative: -0.0254 over 118 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 222 |
| bybit_linear | connected | 9 |
| polymarket | connected | 45 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10872 | 23539 | 705 |
| Bybit event lag (ms) | 864 | 42471 | 654 |
| TA build (ms) | 86 | 177 | 705 |
| Pipeline fanout (ms) | 10793 | 23420 | 705 |
| Strategy Lab runtime (ms) | 336 | 1532 | 705 |
| Total dispatch wall time (ms) | 11401 | 24650 | 705 |
| True orderbook age (ms) | 5313 | 84434 | 860 |
| BTC 5m executable orderbook age (ms) | 2463 | 8783 | 1000 |

- Slowest pipeline runtime: btc_5m p95=27501ms (221 samples)
- BTC 5m executable reads: fresh=30099 stale=20713 missing=88 partial=1794 total=52694
- Orderbook cache: 34 tokens, 534 token-set changes (24h)
- Cycles: 2610
- Fallback fires (24h): 0
- Engine start: 2026-05-28T04:00:02.349955+00:00

- Polymarket events: book=1654718, price_change=45881260, ignored={'last_trade_price': 774423, 'new_market': 6716, 'tick_size_change': 44}
- Orderbook freshness detail: fresh/stale tokens: 34/0, updated last 60s/5m: 34/34, stale reasons: {}
- REST snapshot seed: 9748/9768 successful (missing=0, invalid_bbo=20)
- Polymarket resubscribe: resubscribe debounced/executed: 303/262, added/removed tokens: 1494/2004
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0200); execution_ehr_insufficient_sample (0/10); btc5m_executable_orderbook_age_p95_too_high (8783)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0200 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $30.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
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
