# Consolidated Daily Report — 2026-05-13

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-13.md](2026-05-13.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 256 |
| Total wins | 87 |
| Total losses | 169 |
| Aggregate WR | 34.0% |
| Total P&L | **-$2,037.60** |
| Total wagered | $6,400.00 |
| Pipelines with resolved bets | 9 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 19 | 47.4% | -$25.00 | +0.076 | — | $475.00 |
| sol_hl | SOL | paper | 19 | 47.4% | -$25.00 | +0.076 | — | $475.00 |
| bybit | BTC | paper | 21 | 42.9% | -$75.00 | +0.058 | — | $525.00 |
| eth_bybit | ETH | paused | 27 | 44.4% | -$75.00 | -0.075 | — | $675.00 |
| eth_hl | ETH | paused | 27 | 44.4% | -$75.00 | -0.057 | — | $675.00 |
| btc_5m | BTC | paper | 26 | 42.3% | -$99.20 | +0.021 | -0.087 | $650.00 |
| hl | BTC | paper | 33 | 39.4% | -$175.00 | -0.019 | — | $825.00 |
| eth_5m | ETH | paper | 24 | 33.3% | -$187.46 | -0.074 | -0.214 | $600.00 |
| kalshi | BTC | paused | 60 | 6.7% | -$1,300.94 | — | — | $1,500.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.100 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.136 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 140 | 26.4% | -$1,650.14 | $3,500.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 78 | 41.0% | -$337.46 | $1,950.00 |
| **SOL** | sol_bybit, sol_hl | 38 | 47.4% | -$50.00 | $950.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0208 | -0.0874 | 84 | +10.8¢/$ |
| bybit | +0.0584 | — | 77 | — |
| doge_bybit | +0.1000 | — | 10 | — |
| doge_hl | +0.1364 | — | 11 | — |
| eth_5m | -0.0738 | -0.2143 | 110 | +14.0¢/$ |
| eth_bybit | -0.0752 | — | 153 | — |
| eth_hl | -0.0570 | — | 149 | — |
| hl | -0.0189 | — | 106 | — |
| sol_bybit | +0.0758 | — | 33 | — |
| sol_hl | +0.0758 | — | 33 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 26 | 24 | 92.3% | 62.5% | -0.1057 |
| eth_5m | 24 | 24 | 100.0% | 66.7% | -0.1352 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 42.3% below 55% threshold (26 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 74% → 40% over 7 days
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9348; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9314; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9213; +2 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 44.0% WR on 25 bets ($-74.20); require cohort review before promotion

### bybit
- ⚠️ Daily WR 42.9% below 55% threshold (21 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 8 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8025; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7986; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7985; +5 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 20 bets ($-100.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 33.3% below 55% threshold (24 bets)
- ⚠️ Daily P&L $-187.46 — significant loss
- 📉 WR declining: 47% → 33% over 7 days
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8839; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8833; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8832; +6 more
- 🚨 Signal EHR negative: -0.0738 over 110 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 16.7% WR on 6 bets ($-97.37); require cohort review before promotion

### eth_bybit
- ⚠️ Daily WR 44.4% below 55% threshold (27 bets)
- ⚠️ orphaned_predictions: 14 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5160; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5135; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5126; +11 more
- 🚨 Signal EHR negative: -0.0752 over 153 bets (7-day) — model may be buying overpriced contracts

### eth_hl
- ⚠️ Daily WR 44.4% below 55% threshold (27 bets)
- ⚠️ orphaned_predictions: 15 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5204; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5159; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5134; +12 more
- 🚨 Signal EHR negative: -0.0570 over 149 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 39.4% below 55% threshold (33 bets)
- ⚠️ Daily P&L $-175.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 61% → 35% over 7 days
- ⚠️ orphaned_predictions: 20 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2982; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2967; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2956; +17 more
- 🚨 Signal EHR negative: -0.0189 over 106 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.6% WR on 32 bets ($-150.00); require cohort review before promotion

### kalshi
- ⚠️ Daily WR 6.7% below 55% threshold (60 bets)
- ⚠️ Daily P&L $-1300.94 — significant loss
- 🚨 4 consecutive losing days
- 📉 WR declining: 90% → 8% over 7 days

### sol_bybit
- ⚠️ Daily WR 47.4% below 55% threshold (19 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5117; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5100; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5095; +8 more

### sol_hl
- ⚠️ Daily WR 47.4% below 55% threshold (19 bets)
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5115; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5098; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=5093; +8 more

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 222 |
| bybit_linear | connected | 2 |
| polymarket | connected | 15 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 7807 | 15648 | 700 |
| Bybit event lag (ms) | 1089 | 38706 | 833 |
| TA build (ms) | 89 | 159 | 701 |
| Pipeline fanout (ms) | 7707 | 15539 | 700 |
| Strategy Lab runtime (ms) | 164 | 1121 | 700 |
| Total dispatch wall time (ms) | 8192 | 16166 | 700 |
| True orderbook age (ms) | 34012 | 228131 | 930 |

- Slowest pipeline runtime: btc_5m p95=19101ms (226 samples)
- Orderbook cache: 60 tokens, 464 token-set changes (24h)
- Cycles: 2614
- Fallback fires (24h): 0
- Engine start: 2026-05-13T04:00:03.155647+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $175.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $125.04 | $300.0 | No |
| eth_bybit | $0.00 | $300.0 | No |
| eth_hl | $0.00 | $300.0 | No |
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
