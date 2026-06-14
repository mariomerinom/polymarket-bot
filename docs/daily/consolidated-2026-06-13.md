# Consolidated Daily Report — 2026-06-13

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-13.md](2026-06-13.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 130 |
| Total wins | 53 |
| Total losses | 77 |
| Aggregate WR | 40.8% |
| Total P&L | **-$613.38** |
| Total wagered | $3,250.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 24 | 45.8% | -$50.00 | +0.058 | — | $600.00 |
| btc_5m | BTC | paper | 20 | 45.0% | -$57.01 | +0.060 | +0.002 | $500.00 |
| sol_hl | SOL | paper | 23 | 43.5% | -$75.00 | -0.065 | — | $575.00 |
| sol_bybit | SOL | paper | 23 | 39.1% | -$125.00 | -0.109 | — | $575.00 |
| hl | BTC | paper | 28 | 39.3% | -$150.00 | +0.009 | — | $700.00 |
| eth_5m | ETH | paper | 12 | 25.0% | -$156.37 | +0.025 | +0.001 | $300.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 72 | 43.1% | -$257.01 | $1,800.00 |
| **ETH** | eth_5m | 12 | 25.0% | -$156.37 | $300.00 |
| **SOL** | sol_bybit, sol_hl | 46 | 41.3% | -$200.00 | $1,150.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0600 | +0.0021 | 36 | +5.8¢/$ |
| bybit | +0.0581 | — | 43 | — |
| eth_5m | +0.0245 | +0.0012 | 43 | +2.3¢/$ |
| hl | +0.0085 | — | 59 | — |
| sol_bybit | -0.1087 | — | 23 | — |
| sol_hl | -0.0652 | — | 23 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 20 | 20 | 100.0% | 55.0% | -0.0195 |
| eth_5m | 12 | 12 | 100.0% | 75.0% | -0.2433 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 45.0% below 55% threshold (20 bets)
- ⚠️ Circuit breaker at 68% ($203 / $300)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17572; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17571; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17414

### bybit
- ⚠️ Daily WR 45.8% below 55% threshold (24 bets)
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16887; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16882; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16881; +6 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 25.0% below 55% threshold (12 bets)
- ⚠️ Daily P&L $-156.37 — significant loss
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17981; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17972; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17941; +4 more
- 🧯 side/regime promotion guardrail: DOWN in LOW_VOL / NEUTRAL is 33.3% WR on 6 bets ($-54.91); require cohort review before promotion

### hl
- ⚠️ Daily WR 39.3% below 55% threshold (28 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 📉 WR declining: 69% → 48% over 7 days
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11123; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11122; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11103; +10 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 39.3% WR on 28 bets ($-150.00); require cohort review before promotion

### sol_bybit
- ⚠️ Daily WR 39.1% below 55% threshold (23 bets)
- ⚠️ Daily P&L $-125.00 — significant loss
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14088; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14086; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14084; +10 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.9% WR on 22 bets ($-100.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 43.5% below 55% threshold (23 bets)
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14086; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14084; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=14082; +10 more

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 133 |
| bybit_linear | connected | 0 |
| polymarket | connected | 53 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8048 | 14663 | 705 |
| Bybit event lag (ms) | 868 | 25350 | 554 |
| TA build (ms) | 65 | 119 | 705 |
| Pipeline fanout (ms) | 7937 | 14598 | 705 |
| Strategy Lab runtime (ms) | 126 | 940 | 705 |
| Total dispatch wall time (ms) | 8289 | 15150 | 705 |
| True orderbook age (ms) | 8418 | 119172 | 759 |
| BTC 5m executable orderbook age (ms) | 229 | 1792 | 1000 |

- Slowest pipeline runtime: sol_hl p95=16451ms (241 samples)
- BTC 5m executable reads: fresh=172263 stale=238776 missing=727 partial=5783 total=417549
- Orderbook cache: 38 tokens, 529 token-set changes (24h)
- Cycles: 2618
- Fallback fires (24h): 0
- Engine start: 2026-06-13T04:00:02.067754+00:00

- Polymarket events: book=1372161, price_change=41397935, ignored={'last_trade_price': 618795, 'new_market': 9176, 'tick_size_change': 4, 'market_resolved': 1}
- Orderbook freshness detail: fresh/stale tokens: 18/20, updated last 60s/5m: 28/38, stale reasons: {'stale_updated_at': 20}
- REST snapshot seed: 11655/11668 successful (missing=2, invalid_bbo=91)
- Polymarket resubscribe: resubscribe debounced/executed: 296/301, added/removed tokens: 1422/1828
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (36/50); execution_ehr_insufficient_sample (0/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (36/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $202.98 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $63.74 | $300.0 | No |
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
