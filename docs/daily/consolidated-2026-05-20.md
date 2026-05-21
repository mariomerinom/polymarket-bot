# Consolidated Daily Report — 2026-05-20

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-20.md](2026-05-20.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 174 |
| Total wins | 93 |
| Total losses | 81 |
| Aggregate WR | 53.4% |
| Total P&L | **+$296.22** |
| Total wagered | $4,350.00 |
| Pipelines with resolved bets | 6 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| hl | BTC | paper | 41 | 63.4% | +$275.00 | -0.022 | — | $1,025.00 |
| bybit | BTC | paper | 29 | 62.1% | +$175.00 | -0.020 | — | $725.00 |
| btc_5m | BTC | paper | 22 | 54.5% | +$45.65 | -0.071 | -0.136 | $550.00 |
| eth_5m | ETH | paper | 12 | 41.7% | -$49.43 | -0.010 | +0.044 | $300.00 |
| sol_bybit | SOL | paper | 35 | 45.7% | -$75.00 | -0.066 | — | $875.00 |
| sol_hl | SOL | paper | 35 | 45.7% | -$75.00 | -0.066 | — | $875.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.017 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 92 | 60.9% | +$495.65 | $2,300.00 |
| **ETH** | eth_5m | 12 | 41.7% | -$49.43 | $300.00 |
| **SOL** | sol_bybit, sol_hl | 70 | 45.7% | -$150.00 | $1,750.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0713 | -0.1364 | 147 | +6.5¢/$ |
| bybit | -0.0197 | — | 152 | — |
| doge_bybit | +0.0172 | — | 29 | — |
| doge_hl | -0.0172 | — | 29 | — |
| eth_5m | -0.0096 | +0.0439 | 117 | -5.3¢/$ |
| hl | -0.0221 | — | 226 | — |
| sol_bybit | -0.0655 | — | 145 | — |
| sol_hl | -0.0655 | — | 145 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 22 | 22 | 100.0% | 45.5% | +0.0518 |
| eth_5m | 12 | 12 | 100.0% | 58.3% | -0.1317 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 54.5% below 55% threshold (22 bets)
- 📉 WR declining: 42% → 29% over 7 days
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11210; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11096; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11049; +3 more
- 🚨 Signal EHR negative: -0.0713 over 147 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 42.9% WR on 7 bets ($-23.44); require cohort review before promotion

### bybit
- 🚨 48 integrity check failure(s) today
- ⚠️ orphaned_predictions: 7 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10060; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10029; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10028; +4 more
- 🚨 Signal EHR negative: -0.0197 over 152 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 41.7% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10931; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10928; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10888
- 🚨 Signal EHR negative: -0.0096 over 117 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ orphaned_predictions: 27 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4843; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4842; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4812; +24 more
- 🚨 Signal EHR negative: -0.0221 over 226 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ Daily WR 45.7% below 55% threshold (35 bets)
- ⚠️ orphaned_predictions: 22 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7194; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7193; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7162; +19 more
- 🚨 Signal EHR negative: -0.0655 over 145 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 41.7% WR on 12 bets ($-50.00); require cohort review before promotion

### sol_hl
- ⚠️ Daily WR 45.7% below 55% threshold (35 bets)
- ⚠️ orphaned_predictions: 22 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7192; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7191; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7160; +19 more
- 🚨 Signal EHR negative: -0.0655 over 145 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / TRENDING is 41.7% WR on 12 bets ($-50.00); require cohort review before promotion

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 116 |
| bybit_linear | connected | 1 |
| polymarket | connected | 18 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 6713 | 11168 | 705 |
| Bybit event lag (ms) | 862 | 22711 | 566 |
| TA build (ms) | 83 | 150 | 705 |
| Pipeline fanout (ms) | 6616 | 11066 | 705 |
| Strategy Lab runtime (ms) | 127 | 740 | 705 |
| Total dispatch wall time (ms) | 6949 | 11383 | 705 |
| True orderbook age (ms) | 1799 | 76809 | 810 |

- Slowest pipeline runtime: eth_5m p95=12826ms (241 samples)
- Orderbook cache: 32 tokens, 504 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-05-20T04:00:02.226877+00:00

- Polymarket events: book=1509306, price_change=29089459, ignored={'last_trade_price': 711414, 'tick_size_change': 120}
- Orderbook freshness detail: fresh/stale tokens: 18/12, updated last 60s/5m: 30/30, stale reasons: {'stale_updated_at': 12}
- REST snapshot seed: 10446/10450 successful (missing=0, invalid_bbo=4)
- Polymarket resubscribe: resubscribe debounced/executed: 268/302, added/removed tokens: 1424/1760
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0716); execution_ehr_insufficient_sample (0/10); orderbook_age_p95_too_high (76809)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $87.11 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $31.52 | $300.0 | No |
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
