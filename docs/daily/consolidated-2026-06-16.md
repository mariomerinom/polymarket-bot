# Consolidated Daily Report — 2026-06-16

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-16.md](2026-06-16.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 45 |
| Total wins | 27 |
| Total losses | 18 |
| Aggregate WR | 60.0% |
| Total P&L | **+$260.47** |
| Total wagered | $1,125.00 |
| Pipelines with resolved bets | 3 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| btc_5m | BTC | paper | 14 | 64.3% | +$135.47 | +0.062 | +0.035 | $350.00 |
| hl | BTC | paper | 21 | 57.1% | +$75.00 | +0.020 | — | $525.00 |
| bybit | BTC | paper | 10 | 60.0% | +$50.00 | +0.046 | — | $250.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.041 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.013 | — | $0.00 |
| eth_5m | ETH | paper | 0 | — | $0.00 | -0.012 | -0.124 | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.136 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.106 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 45 | 60.0% | +$260.47 | $1,125.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0623 | +0.0348 | 75 | +2.8¢/$ |
| bybit | +0.0465 | — | 86 | — |
| doge_bybit | +0.0405 | — | 37 | — |
| doge_hl | +0.0135 | — | 37 | — |
| eth_5m | -0.0120 | -0.1237 | 43 | +11.2¢/$ |
| hl | +0.0200 | — | 125 | — |
| sol_bybit | -0.1364 | — | 33 | — |
| sol_hl | -0.1061 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 16 | 14 | 100.0% | 35.7% | +0.1645 |
| eth_5m | 4 | 0 | — | — | — |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18224

### bybit
- 📉 WR declining: 65% → 54% over 7 days
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17597; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17596; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=17595; +2 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18848; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18842

### hl
- ⚠️ orphaned_predictions: 13 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11933; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11777; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11776; +10 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 200 |
| bybit_linear | connected | 9 |
| polymarket | connected | 102 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9801 | 22065 | 705 |
| Bybit event lag (ms) | 883 | 30301 | 861 |
| TA build (ms) | 69 | 154 | 705 |
| Pipeline fanout (ms) | 9725 | 22015 | 705 |
| Strategy Lab runtime (ms) | 177 | 1259 | 705 |
| Total dispatch wall time (ms) | 10208 | 22855 | 705 |
| True orderbook age (ms) | 10025 | 115057 | 752 |
| BTC 5m executable orderbook age (ms) | 175 | 1739 | 1000 |

- Slowest pipeline runtime: bybit p95=23015ms (241 samples)
- BTC 5m executable reads: fresh=195519 stale=280942 missing=809 partial=6381 total=483651
- Orderbook cache: 40 tokens, 525 token-set changes (24h)
- Cycles: 2624
- Fallback fires (24h): 0
- Engine start: 2026-06-16T04:00:01.613699+00:00

- Polymarket events: book=1555557, price_change=49178173, ignored={'last_trade_price': 705416, 'new_market': 9762, 'tick_size_change': 204, 'market_resolved': 2}
- Orderbook freshness detail: fresh/stale tokens: 8/32, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 32}
- REST snapshot seed: 11977/11982 successful (missing=0, invalid_bbo=75)
- Polymarket resubscribe: resubscribe debounced/executed: 305/274, added/removed tokens: 1530/1878
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: execution_ehr_insufficient_sample (0/10); unexplained_orphaned_predictions (1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=18412)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $80.23 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $0.00 | $300.0 | No |
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
