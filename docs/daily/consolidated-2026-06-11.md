# Consolidated Daily Report — 2026-06-11

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-11.md](2026-06-11.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 27 |
| Total wins | 20 |
| Total losses | 7 |
| Aggregate WR | 74.1% |
| Total P&L | **+$348.37** |
| Total wagered | $675.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 7 | 85.7% | +$125.00 | +0.250 | — | $175.00 |
| hl | BTC | paper | 9 | 77.8% | +$125.00 | +0.167 | — | $225.00 |
| btc_5m | BTC | paper | 7 | 71.4% | +$103.42 | +0.189 | +0.193 | $175.00 |
| eth_5m | ETH | paper | 4 | 50.0% | -$5.05 | +0.105 | +0.115 | $100.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | — | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | — | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 23 | 78.3% | +$353.42 | $575.00 |
| **ETH** | eth_5m | 4 | 50.0% | -$5.05 | $100.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.1888 | +0.1930 | 8 | -0.4¢/$ |
| bybit | +0.2500 | — | 8 | — |
| eth_5m | +0.1054 | +0.1150 | 26 | -1.0¢/$ |
| hl | +0.1667 | — | 15 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 7 | 7 | 100.0% | 28.6% | +0.2789 |
| eth_5m | 4 | 4 | 100.0% | 50.0% | +0.0125 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16916; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16915

### bybit
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16216; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16215; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16214; +3 more

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- 🚨 3 consecutive losing days
- 📉 WR declining: 63% → 17% over 7 days

### hl
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10483; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10482; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10481; +3 more

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 203 |
| bybit_linear | connected | 3 |
| polymarket | connected | 163 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 13631 | 36041 | 570 |
| Bybit event lag (ms) | 1024 | 52669 | 875 |
| TA build (ms) | 73 | 149 | 570 |
| Pipeline fanout (ms) | 13558 | 35992 | 570 |
| Strategy Lab runtime (ms) | 839 | 1615 | 570 |
| Total dispatch wall time (ms) | 14573 | 37008 | 570 |
| True orderbook age (ms) | 14122 | 178372 | 806 |
| BTC 5m executable orderbook age (ms) | 178 | 1735 | 1000 |

- Slowest pipeline runtime: btc_5m p95=38466ms (199 samples)
- BTC 5m executable reads: fresh=155287 stale=210018 missing=681 partial=5436 total=371422
- Orderbook cache: 42 tokens, 439 token-set changes (24h)
- Cycles: 2325
- Fallback fires (24h): 0
- Engine start: 2026-06-11T06:16:38.478631+00:00

- Polymarket events: book=1178220, price_change=56841798, ignored={'last_trade_price': 547510, 'new_market': 7883, 'market_resolved': 5, 'tick_size_change': 8}
- Orderbook freshness detail: fresh/stale tokens: 12/30, updated last 60s/5m: 42/42, stale reasons: {'stale_updated_at': 30}
- REST snapshot seed: 11710/11718 successful (missing=0, invalid_bbo=32)
- Polymarket resubscribe: resubscribe debounced/executed: 249/215, added/removed tokens: 1214/1616
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (8/50); execution_ehr_insufficient_sample (1/10); dispatch_p95_too_high (36041)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (8/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $25.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $11.75 | $300.0 | No |
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
