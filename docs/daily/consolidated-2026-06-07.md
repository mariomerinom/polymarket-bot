# Consolidated Daily Report — 2026-06-07

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-06-07.md](2026-06-07.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 18 |
| Total wins | 10 |
| Total losses | 8 |
| Aggregate WR | 55.6% |
| Total P&L | **+$199.53** |
| Total wagered | $450.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 11 | 63.6% | +$224.53 | +0.108 | +0.036 | $275.00 |
| hl | BTC | paper | 5 | 60.0% | +$25.00 | +0.000 | — | $125.00 |
| btc_5m | BTC | paper | 1 | 0.0% | -$25.00 | +0.113 | +0.195 | $25.00 |
| bybit | BTC | paper | 1 | 0.0% | -$25.00 | -0.045 | — | $25.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.047 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.047 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.025 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.025 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 7 | 42.9% | -$25.00 | $175.00 |
| **ETH** | eth_5m | 11 | 63.6% | +$224.53 | $275.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.1125 | +0.1950 | 32 | -8.2¢/$ |
| bybit | -0.0455 | — | 33 | — |
| doge_bybit | -0.0472 | — | 53 | — |
| doge_hl | -0.0472 | — | 53 | — |
| eth_5m | +0.1082 | +0.0364 | 42 | +7.2¢/$ |
| hl | +0.0000 | — | 58 | — |
| sol_bybit | -0.0246 | — | 61 | — |
| sol_hl | -0.0246 | — | 61 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 1 | 1 | 100.0% | 100.0% | -0.3025 |
| eth_5m | 11 | 11 | 100.0% | 36.4% | +0.2198 |

## 6. Alerts (All Pipelines)

### btc_5m
- 🚨 3 consecutive losing days

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0472 over 53 bets (7-day) — model may be buying overpriced contracts

### doge_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0472 over 53 bets (7-day) — model may be buying overpriced contracts

### eth_5m
- ⚠️ orphaned_predictions: 2 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16118; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=16081

### hl
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9441; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9440; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9439

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0246 over 61 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0246 over 61 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 240 |
| bybit_linear | connected | 10 |
| polymarket | connected | 185 |

- Git auto-commit bail: clear

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 15295 | 38755 | 705 |
| Bybit event lag (ms) | 1121 | 75678 | 698 |
| TA build (ms) | 73 | 161 | 705 |
| Pipeline fanout (ms) | 15240 | 38652 | 705 |
| Strategy Lab runtime (ms) | 990 | 1764 | 705 |
| Total dispatch wall time (ms) | 16513 | 39993 | 705 |
| True orderbook age (ms) | 7963 | 81798 | 599 |
| BTC 5m executable orderbook age (ms) | 211 | 1692 | 1000 |

- Slowest pipeline runtime: btc_5m p95=41258ms (230 samples)
- BTC 5m executable reads: fresh=122216 stale=151973 missing=579 partial=4618 total=279386
- Orderbook cache: 40 tokens, 503 token-set changes (24h)
- Cycles: 2630
- Fallback fires (24h): 0
- Engine start: 2026-06-07T04:00:02.496122+00:00

- Polymarket events: book=1358058, price_change=66511083, ignored={'last_trade_price': 626209, 'new_market': 6566, 'market_resolved': 7, 'tick_size_change': 80}
- Orderbook freshness detail: fresh/stale tokens: 18/22, updated last 60s/5m: 40/40, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 12996/13004 successful (missing=2, invalid_bbo=10)
- Polymarket resubscribe: resubscribe debounced/executed: 288/231, added/removed tokens: 1330/1864
- Orderbook freshness decision: dominant cause: no recent websocket deltas

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_insufficient_sample (7/50); execution_ehr_insufficient_sample (1/10); dispatch_p95_too_high (38755)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_insufficient_sample (7/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $0.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $37.46 | $300.0 | No |
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
