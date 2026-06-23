# Consolidated Daily Report — 2026-06-22

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-22.md](2026-06-22.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 48 |
| Total wins | 20 |
| Total losses | 28 |
| Aggregate WR | 41.7% |
| Total P&L | **-$176.15** |
| Total wagered | $1,200.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| doge_bybit | DOGE | paper | 6 | 50.0% | $0.00 | -0.045 | — | $150.00 |
| doge_hl | DOGE | paper | 6 | 50.0% | $0.00 | -0.091 | — | $150.00 |
| btc_5m | BTC | paper | 7 | 42.9% | -$19.82 | +0.084 | +0.099 | $175.00 |
| bybit | BTC | paper | 7 | 42.9% | -$25.00 | +0.037 | — | $175.00 |
| hl | BTC | paper | 11 | 45.5% | -$25.00 | +0.023 | — | $275.00 |
| eth_5m | ETH | paper | 11 | 27.3% | -$106.33 | -0.094 | -0.002 | $275.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 25 | 44.0% | -$69.82 | $625.00 |
| **ETH** | eth_5m | 11 | 27.3% | -$106.33 | $275.00 |
| **DOGE** | doge_bybit, doge_hl | 12 | 50.0% | $0.00 | $300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0844 | +0.0992 | 87 | -1.5¢/$ |
| bybit | +0.0373 | — | 134 | — |
| doge_bybit | -0.0455 | — | 66 | — |
| doge_hl | -0.0909 | — | 66 | — |
| eth_5m | -0.0937 | -0.0021 | 73 | -9.2¢/$ |
| hl | +0.0233 | — | 172 | — |
| sol_bybit | +0.0000 | — | 4 | — |
| sol_hl | +0.0000 | — | 4 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 7 | 7 | 100.0% | 57.1% | -0.0282 |
| eth_5m | 11 | 11 | 100.0% | 72.7% | -0.2298 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19849

### bybit
- ⚠️ Daily WR 42.9% below 55% threshold (7 bets)
- 📉 WR declining: 64% → 48% over 7 days
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19380; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19361; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=19248; +1 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 7 bets ($-25.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (6 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16130; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16124; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16123
- 🚨 Signal EHR negative: -0.0455 over 66 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### doge_hl
- ⚠️ Daily WR 50.0% below 55% threshold (6 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16688; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16682; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16681
- 🚨 Signal EHR negative: -0.0909 over 66 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### eth_5m
- ⚠️ Daily WR 27.3% below 55% threshold (11 bets)
- ⚠️ Daily P&L $-106.33 — significant loss
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20585; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20582; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20572; +2 more
- 🚨 Signal EHR negative: -0.0937 over 73 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 0.0% WR on 5 bets ($-125.00); require cohort review before promotion

### hl
- ⚠️ Daily WR 45.5% below 55% threshold (11 bets)
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13495; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13380; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=13365; +2 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 210 |
| bybit_linear | connected | 7 |
| polymarket | connected | 123 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 11601 | 26456 | 705 |
| Bybit event lag (ms) | 873 | 47203 | 753 |
| TA build (ms) | 65 | 111 | 705 |
| Pipeline fanout (ms) | 11543 | 26364 | 705 |
| Strategy Lab runtime (ms) | 393 | 1322 | 705 |
| Total dispatch wall time (ms) | 12147 | 27294 | 705 |
| True orderbook age (ms) | 3139 | 81086 | 612 |
| BTC 5m executable orderbook age (ms) | 132 | 1413 | 1000 |

- Slowest pipeline runtime: btc_5m p95=26501ms (223 samples)
- BTC 5m executable reads: fresh=248415 stale=357917 missing=934 partial=7511 total=614777
- Orderbook cache: 42 tokens, 525 token-set changes (24h)
- Cycles: 2616
- Fallback fires (24h): 0
- Engine start: 2026-06-22T04:00:01.742014+00:00

- Polymarket events: book=1382232, price_change=59931234, ignored={'last_trade_price': 638726, 'new_market': 8871, 'tick_size_change': 584, 'market_resolved': 2}
- Orderbook freshness detail: fresh/stale tokens: 18/24, updated last 60s/5m: 42/42, stale reasons: {'stale_updated_at': 24}
- REST snapshot seed: 12794/12850 successful (missing=56, invalid_bbo=26)
- Polymarket resubscribe: resubscribe debounced/executed: 301/268, added/removed tokens: 1534/1844
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (1/10)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $100.00 | $300.0 | No |
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
