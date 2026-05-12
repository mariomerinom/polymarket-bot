# Consolidated Daily Report — 2026-05-11

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-11.md](2026-05-11.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 15 |
| Total wins | 3 |
| Total losses | 12 |
| Aggregate WR | 20.0% |
| Total P&L | **-$225.00** |
| Total wagered | $375.00 |
| Pipelines with resolved bets | 9 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 1 | 100.0% | +$25.00 | +0.148 | — | $25.00 |
| sol_bybit | SOL | paper | 1 | 100.0% | +$25.00 | +0.125 | — | $25.00 |
| sol_hl | SOL | paper | 1 | 100.0% | +$25.00 | +0.113 | — | $25.00 |
| btc_5m | BTC | paper | 1 | 0.0% | -$25.00 | +0.118 | -0.153 | $25.00 |
| eth_bybit | ETH | paper | 1 | 0.0% | -$25.00 | -0.043 | — | $25.00 |
| eth_hl | ETH | paper | 1 | 0.0% | -$25.00 | -0.018 | — | $25.00 |
| hl | BTC | paper | 1 | 0.0% | -$25.00 | +0.103 | — | $25.00 |
| eth_5m | ETH | paper | 2 | 0.0% | -$50.00 | -0.024 | -0.107 | $50.00 |
| kalshi | BTC | paper | 6 | 0.0% | -$150.00 | — | — | $150.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.100 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.083 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 9 | 11.1% | -$175.00 | $225.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 4 | 0.0% | -$100.00 | $100.00 |
| **SOL** | sol_bybit, sol_hl | 2 | 100.0% | +$50.00 | $50.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.1177 | -0.1531 | 51 | +27.1¢/$ |
| bybit | +0.1481 | — | 54 | — |
| doge_bybit | +0.1000 | — | 10 | — |
| doge_hl | +0.0833 | — | 12 | — |
| eth_5m | -0.0240 | -0.1068 | 82 | +8.3¢/$ |
| eth_bybit | -0.0431 | — | 116 | — |
| eth_hl | -0.0179 | — | 112 | — |
| hl | +0.1029 | — | 68 | — |
| sol_bybit | +0.1250 | — | 32 | — |
| sol_hl | +0.1129 | — | 31 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 1 | 1 | 100.0% | 100.0% | -0.2550 |
| eth_5m | 2 | 2 | 100.0% | 100.0% | -0.3987 |

## 6. Alerts (All Pipelines)

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8209
- 🚨 Signal EHR negative: -0.0240 over 82 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- 📉 WR declining: 52% → 31% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4689
- 🚨 Signal EHR negative: -0.0431 over 116 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- 🚨 3 consecutive losing days
- 📉 WR declining: 53% → 33% over 7 days
- ⚠️ orphaned_predictions: 1 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4688
- 🚨 Signal EHR negative: -0.0179 over 112 bets (7-day) — model may be buying overpriced contracts

### hl
- 📉 WR declining: 71% → 41% over 7 days

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (6 bets)
- ⚠️ Daily P&L $-150.00 — significant loss

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 65 |
| bybit_linear | connected | 1 |
| polymarket | connected | 10 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 5778 | 13884 | 440 |
| Bybit event lag (ms) | 1130 | 41508 | 666 |
| TA build (ms) | 91 | 206 | 440 |
| Pipeline fanout (ms) | 5705 | 13776 | 440 |
| Strategy Lab runtime (ms) | 162 | 732 | 440 |
| Total dispatch wall time (ms) | 6174 | 14364 | 440 |
| True orderbook age (ms) | 107275 | 246241 | 588 |

- Slowest pipeline runtime: eth_5m p95=17425ms (88 samples)
- Orderbook cache: 72 tokens, 170 token-set changes (24h)
- Cycles: 960
- Fallback fires (24h): 0
- Engine start: 2026-05-11T16:48:23.102622+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| bybit | $0.00 | $300.0 | No |
| eth_5m | $25.00 | $300.0 | No |
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
| eth_bybit | paper | 0.05 | ETH |
| eth_hl | paper | 0.05 | ETH |
| hl | paper | 0.005 | BTC |
| kalshi | paper | 25 | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
