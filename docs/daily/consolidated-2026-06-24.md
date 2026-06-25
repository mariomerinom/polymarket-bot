# Consolidated Daily Report — 2026-06-24

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-24.md](2026-06-24.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 52 |
| Total wins | 22 |
| Total losses | 30 |
| Aggregate WR | 42.3% |
| Total P&L | **-$239.30** |
| Total wagered | $1,300.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 8 | 62.5% | +$6.20 | -0.071 | +0.029 | $200.00 |
| btc_5m | BTC | paper | 9 | 44.4% | -$20.50 | +0.014 | +0.006 | $225.00 |
| doge_bybit | DOGE | paper | 2 | 0.0% | -$50.00 | -0.059 | — | $50.00 |
| doge_hl | DOGE | paper | 2 | 0.0% | -$50.00 | -0.103 | — | $50.00 |
| hl | BTC | paper | 18 | 44.4% | -$50.00 | +0.000 | — | $450.00 |
| bybit | BTC | paper | 13 | 38.5% | -$75.00 | +0.004 | — | $325.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.000 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 40 | 42.5% | -$145.50 | $1,000.00 |
| **ETH** | eth_5m | 8 | 62.5% | +$6.20 | $200.00 |
| **DOGE** | doge_bybit, doge_hl | 4 | 0.0% | -$100.00 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0142 | +0.0064 | 82 | +0.8¢/$ |
| bybit | +0.0037 | — | 135 | — |
| doge_bybit | -0.0588 | — | 68 | — |
| doge_hl | -0.1029 | — | 68 | — |
| eth_5m | -0.0707 | +0.0288 | 74 | -10.0¢/$ |
| hl | +0.0000 | — | 166 | — |
| sol_bybit | +0.0000 | — | 4 | — |
| sol_hl | +0.0000 | — | 4 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 9 | 9 | 100.0% | 55.6% | +0.0242 |
| eth_5m | 8 | 8 | 100.0% | 37.5% | +0.1381 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 44.4% below 55% threshold (9 bets)
- 🚨 3 consecutive losing days
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 44.4% WR on 9 bets ($-20.50); require cohort review before promotion

### bybit
- ⚠️ Daily WR 38.5% below 55% threshold (13 bets)
- 🚨 4 consecutive losing days
- 📉 WR declining: 60% → 40% over 7 days
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20094; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20091; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20075; +5 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 44.4% WR on 9 bets ($-25.00); require cohort review before promotion

### doge_bybit
- 📉 WR declining: 53% → 33% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=16571
- 🚨 Signal EHR negative: -0.0588 over 68 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=17129
- 🚨 Signal EHR negative: -0.1029 over 68 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20994; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20985
- 🚨 Signal EHR negative: -0.0707 over 74 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 44.4% below 55% threshold (18 bets)
- 🚨 3 consecutive losing days
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14034; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14031; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=14024; +7 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 197 |
| bybit_linear | connected | 2 |
| polymarket | connected | 73 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 10622 | 19479 | 705 |
| Bybit event lag (ms) | 863 | 37424 | 899 |
| TA build (ms) | 64 | 104 | 705 |
| Pipeline fanout (ms) | 10566 | 19402 | 705 |
| Strategy Lab runtime (ms) | 237 | 1181 | 705 |
| Total dispatch wall time (ms) | 11321 | 20110 | 705 |
| True orderbook age (ms) | 7691 | 95956 | 912 |
| BTC 5m executable orderbook age (ms) | 117 | 1466 | 1000 |

- Slowest pipeline runtime: bybit p95=20203ms (241 samples)
- BTC 5m executable reads: fresh=270097 stale=380860 missing=993 partial=7935 total=659885
- Orderbook cache: 40 tokens, 531 token-set changes (24h)
- Cycles: 2618
- Fallback fires (24h): 0
- Engine start: 2026-06-24T04:00:01.640184+00:00

- Polymarket events: book=1580513, price_change=55308925, ignored={'last_trade_price': 736831, 'new_market': 12260, 'market_resolved': 4, 'tick_size_change': 556}
- Orderbook freshness detail: fresh/stale tokens: 12/28, updated last 60s/5m: 28/40, stale reasons: {'stale_updated_at': 28}
- REST snapshot seed: 10489/10512 successful (missing=7, invalid_bbo=162)
- Polymarket resubscribe: resubscribe debounced/executed: 309/264, added/removed tokens: 1510/1904
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0029); execution_ehr_insufficient_sample (0/10); unexplained_orphaned_predictions (1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=20527)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.0029 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $75.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
