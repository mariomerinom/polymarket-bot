# Consolidated Daily Report — 2026-04-20

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-04-20.md](2026-04-20.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 22 |
| Total wins | 10 |
| Total losses | 12 |
| Aggregate WR | 45.5% |
| Total P&L | **-$42.45** |
| Total wagered | $550.00 |
| Active pipelines | 3 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_5m | ETH | paper | 12 | 50.0% | +$7.55 | -0.026 | -0.017 | $300.00 |
| eth_bybit | ETH | paper | 5 | 40.0% | -$25.00 | -0.073 | — | $125.00 |
| eth_hl | ETH | paper | 5 | 40.0% | -$25.00 | -0.073 | — | $125.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| btc_5m | BTC | live | 0 | — | $0.00 | -0.082 | -0.079 | $0.00 |
| bybit | BTC | paper | 0 | — | $0.00 | -0.110 | — | $0.00 |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | -0.022 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.029 | — | $0.00 |
| hl | BTC | paper | 0 | — | $0.00 | -0.026 | — | $0.00 |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.014 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.014 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **ETH** | eth_5m, eth_bybit, eth_hl | 22 | 45.5% | -$42.45 | $550.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0818 | -0.0794 | 53 | -0.2¢/$ |
| bybit | -0.1098 | — | 41 | — |
| doge_bybit | -0.0217 | — | 23 | — |
| doge_hl | -0.0294 | — | 34 | — |
| eth_5m | -0.0264 | -0.0172 | 164 | -0.9¢/$ |
| eth_bybit | -0.0728 | — | 103 | — |
| eth_hl | -0.0728 | — | 103 | — |
| hl | -0.0263 | — | 76 | — |
| sol_bybit | +0.0143 | — | 35 | — |
| sol_hl | +0.0143 | — | 35 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| eth_5m | 12 | 11 | 91.7% | 54.5% | -0.0316 |

## 6. Alerts (All Pipelines)

### btc_5m
- 🚨 3 consecutive losing days
- ℹ️ No bets placed today — all predictions skipped
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0818 over 53 bets (7-day) — model may be buying overpriced contracts

### bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 50.0% below 55% threshold (12 bets)
- ⚠️ expired_would_win: 11 expired order(s) would have won
- ⚠️ expired_would_win: 11 expired order(s) would have won
- 🚨 Signal EHR negative: -0.0264 over 164 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 40.0% below 55% threshold (5 bets)
- 🚨 Signal EHR negative: -0.0728 over 103 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 40.0% below 55% threshold (5 bets)
- 🚨 Signal EHR negative: -0.0728 over 103 bets (7-day) — model may be buying overpriced contracts

### hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0263 over 76 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 74 |
| bybit_linear | connected | 1 |
| polymarket | connected | 12 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Dispatch latency (ms) | 5994 | 15302 | 705 |
| Orderbook age (ms) | 0 | 0 | 571 |

- Cycles: 2596
- Fallback fires (24h): 0
- Engine start: 2026-04-20T04:00:02.678999+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| eth_5m | $50.00 | $300.0 | ✅ |
| eth_bybit | $0.00 | $300.0 | ✅ |
| eth_hl | $0.00 | $300.0 | ✅ |

## 9. Pipeline Config Snapshot

| Pipeline | Mode | Bet Size | Asset |
|----------|------|---------:|-------|
| btc_15m | paused | default | BTC |
| btc_5m | live | 25 | BTC |
| bybit | paper | 0.005 | BTC |
| doge_bybit | paper | 1000 | DOGE |
| doge_hl | paper | 1000 | DOGE |
| eth_5m | paper | 25 | ETH |
| eth_bybit | paper | 0.05 | ETH |
| eth_hl | paper | 0.05 | ETH |
| hl | paper | 0.005 | BTC |
| kalshi | paused | default | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
