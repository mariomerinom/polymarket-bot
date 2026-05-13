# Consolidated Daily Report — 2026-05-12

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-12.md](2026-05-12.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 163 |
| Total wins | 57 |
| Total losses | 106 |
| Aggregate WR | 35.0% |
| Total P&L | **-$1,223.47** |
| Total wagered | $4,075.00 |
| Pipelines with resolved bets | 7 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| eth_bybit | ETH | paper | 27 | 51.9% | +$25.00 | -0.047 | — | $675.00 |
| eth_hl | ETH | paper | 27 | 51.9% | +$25.00 | -0.026 | — | $675.00 |
| eth_5m | ETH | paper | 18 | 50.0% | +$1.87 | -0.032 | -0.156 | $450.00 |
| bybit | BTC | paper | 14 | 42.9% | -$50.00 | +0.090 | — | $350.00 |
| btc_5m | BTC | paper | 18 | 38.9% | -$100.34 | +0.045 | -0.090 | $450.00 |
| hl | BTC | paper | 20 | 35.0% | -$150.00 | +0.026 | — | $500.00 |
| kalshi | BTC | paper | 39 | 0.0% | -$975.00 | — | — | $975.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.100 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | +0.083 | — | $0.00 |
| sol_bybit | SOL | paper | 0 | — | $0.00 | +0.143 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | +0.130 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl, kalshi | 91 | 22.0% | -$1,275.34 | $2,275.00 |
| **ETH** | eth_5m, eth_bybit, eth_hl | 72 | 51.4% | +$51.87 | $1,800.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | +0.0446 | -0.0905 | 60 | +13.5¢/$ |
| bybit | +0.0902 | — | 61 | — |
| doge_bybit | +0.1000 | — | 10 | — |
| doge_hl | +0.0833 | — | 12 | — |
| eth_5m | -0.0318 | -0.1556 | 94 | +12.4¢/$ |
| eth_bybit | -0.0474 | — | 137 | — |
| eth_hl | -0.0263 | — | 133 | — |
| hl | +0.0256 | — | 78 | — |
| sol_bybit | +0.1429 | — | 28 | — |
| sol_hl | +0.1296 | — | 27 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 18 | 16 | 88.9% | 68.8% | -0.1666 |
| eth_5m | 18 | 18 | 100.0% | 50.0% | -0.0004 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 38.9% below 55% threshold (18 bets)
- ⚠️ Daily P&L $-100.34 — significant loss
- 📉 WR declining: 83% → 41% over 7 days
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9073; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8937; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8909; +1 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 38.9% WR on 18 bets ($-100.34); require cohort review before promotion

### bybit
- ⚠️ Daily WR 42.9% below 55% threshold (14 bets)
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7761; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7652; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=7651; +6 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 42.9% WR on 14 bets ($-50.00); require cohort review before promotion

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 50.0% below 55% threshold (18 bets)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8407; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8401; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=8334; +1 more
- 🚨 Signal EHR negative: -0.0318 over 94 bets (7-day) — model may be buying overpriced contracts

### eth_bybit
- ⚠️ Daily WR 51.9% below 55% threshold (27 bets)
- 🚨 25 integrity check failure(s) today
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4844; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4815; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4814; +6 more
- 🚨 Signal EHR negative: -0.0474 over 137 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### eth_hl
- ⚠️ Daily WR 51.9% below 55% threshold (27 bets)
- 🚨 24 integrity check failure(s) today
- ⚠️ orphaned_predictions: 9 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4843; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4814; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=4813; +6 more
- 🚨 Signal EHR negative: -0.0263 over 133 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in LOW_VOL / NEUTRAL is 40.0% WR on 5 bets ($-25.00); require cohort review before promotion

### hl
- ⚠️ Daily WR 35.0% below 55% threshold (20 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 📉 WR declining: 66% → 38% over 7 days
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2681; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2653; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=2652; +9 more
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 35.0% WR on 20 bets ($-150.00); require cohort review before promotion

### kalshi
- ⚠️ Daily WR 0.0% below 55% threshold (39 bets)
- ⚠️ Daily P&L $-975.00 — significant loss
- 🚨 3 consecutive losing days
- 📉 WR declining: 67% → 28% over 7 days

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped

### sol_hl
- ℹ️ No bets placed today — all predictions skipped

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 209 |
| bybit_linear | connected | 1 |
| polymarket | connected | 25 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 6121 | 14858 | 704 |
| Bybit event lag (ms) | 1083 | 36573 | 947 |
| TA build (ms) | 87 | 147 | 704 |
| Pipeline fanout (ms) | 6038 | 14762 | 704 |
| Strategy Lab runtime (ms) | 148 | 650 | 704 |
| Total dispatch wall time (ms) | 6405 | 14988 | 704 |
| True orderbook age (ms) | 106945 | 282805 | 731 |

- Slowest pipeline runtime: eth_5m p95=17189ms (241 samples)
- Orderbook cache: 70 tokens, 458 token-set changes (24h)
- Cycles: 2625
- Fallback fires (24h): 0
- Engine start: 2026-05-12T04:00:01.731251+00:00

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $150.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $121.99 | $300.0 | No |
| eth_bybit | $0.00 | $300.0 | No |
| eth_hl | $0.00 | $300.0 | No |
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
| eth_bybit | paper | 0.05 | ETH |
| eth_hl | paper | 0.05 | ETH |
| hl | paper | 0.005 | BTC |
| kalshi | paper | 25 | BTC |
| sol_bybit | paper | 1.0 | SOL |
| sol_hl | paper | 1.0 | SOL |
