# Consolidated Daily Report — 2026-05-18

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-18.md](2026-05-18.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 36 |
| Total wins | 11 |
| Total losses | 25 |
| Aggregate WR | 30.6% |
| Total P&L | **-$348.94** |
| Total wagered | $900.00 |
| Pipelines with resolved bets | 4 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| bybit | BTC | paper | 8 | 50.0% | $0.00 | -0.035 | — | $200.00 |
| eth_5m | ETH | paper | 12 | 33.3% | -$98.94 | -0.026 | -0.082 | $300.00 |
| hl | BTC | paper | 10 | 30.0% | -$100.00 | -0.076 | — | $250.00 |
| btc_5m | BTC | paper | 6 | 0.0% | -$150.00 | -0.091 | -0.109 | $150.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| doge_bybit | DOGE | paper | 0 | — | $0.00 | +0.017 | — | $0.00 |
| doge_hl | DOGE | paper | 0 | — | $0.00 | -0.017 | — | $0.00 |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |
| sol_bybit | SOL | paper | 0 | — | $0.00 | -0.076 | — | $0.00 |
| sol_hl | SOL | paper | 0 | — | $0.00 | -0.076 | — | $0.00 |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 24 | 29.2% | -$250.00 | $600.00 |
| **ETH** | eth_5m | 12 | 33.3% | -$98.94 | $300.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.0912 | -0.1087 | 121 | +1.8¢/$ |
| bybit | -0.0345 | — | 116 | — |
| doge_bybit | +0.0172 | — | 29 | — |
| doge_hl | -0.0172 | — | 29 | — |
| eth_5m | -0.0258 | -0.0815 | 108 | +5.6¢/$ |
| hl | -0.0765 | — | 170 | — |
| sol_bybit | -0.0758 | — | 99 | — |
| sol_hl | -0.0758 | — | 99 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 6 | 6 | 100.0% | 100.0% | -0.4896 |
| eth_5m | 12 | 12 | 100.0% | 66.7% | -0.1188 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 0.0% below 55% threshold (6 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- 🚨 4 consecutive losing days
- 📉 WR declining: 48% → 22% over 7 days
- 🚨 Signal EHR negative: -0.0912 over 121 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 0.0% WR on 6 bets ($-150.00); require cohort review before promotion

### bybit
- ⚠️ Daily WR 50.0% below 55% threshold (8 bets)
- ⚠️ orphaned_predictions: 4 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9478; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9341; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=9227; +1 more
- 🚨 Signal EHR negative: -0.0345 over 116 bets (7-day) — model may be buying overpriced contracts

### doge_bybit
- ℹ️ No bets placed today — all predictions skipped

### doge_hl
- ℹ️ No bets placed today — all predictions skipped

### eth_5m
- ⚠️ Daily WR 33.3% below 55% threshold (12 bets)
- ⚠️ orphaned_predictions: 6 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10350; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10347; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=10280; +3 more
- 🚨 Signal EHR negative: -0.0258 over 108 bets (7-day) — model may be buying overpriced contracts

### hl
- ⚠️ Daily WR 30.0% below 55% threshold (10 bets)
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 3 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4302; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4073; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=4072
- 🚨 Signal EHR negative: -0.0765 over 170 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.0% WR on 10 bets ($-100.00); require cohort review before promotion

### sol_bybit
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0758 over 99 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ℹ️ No bets placed today — all predictions skipped
- 🚨 Signal EHR negative: -0.0758 over 99 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 176 |
| bybit_linear | connected | 4 |
| polymarket | connected | 28 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 8425 | 15320 | 705 |
| Bybit event lag (ms) | 850 | 28526 | 514 |
| TA build (ms) | 90 | 196 | 705 |
| Pipeline fanout (ms) | 8352 | 15233 | 705 |
| Strategy Lab runtime (ms) | 199 | 1185 | 705 |
| Total dispatch wall time (ms) | 8831 | 16119 | 705 |
| True orderbook age (ms) | 3981 | 105488 | 967 |

- Slowest pipeline runtime: btc_5m p95=16419ms (221 samples)
- Orderbook cache: 38 tokens, 519 token-set changes (24h)
- Cycles: 2612
- Fallback fires (24h): 0
- Engine start: 2026-05-18T04:00:02.564498+00:00

- Polymarket events: book=1778955, price_change=37126020, ignored={'last_trade_price': 868638, 'tick_size_change': 244}
- Orderbook freshness detail: fresh/stale tokens: 16/22, updated last 60s/5m: 38/38, stale reasons: {'stale_updated_at': 22}
- REST snapshot seed: 10633/10650 successful (missing=0, invalid_bbo=17)
- Polymarket resubscribe: resubscribe debounced/executed: 287/287, added/removed tokens: 1474/1872
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.0877); execution_ehr_insufficient_sample (2/10); orderbook_age_p95_too_high (105488); orderbook_stale_tokens_exceed_fresh (22/16)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $50.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| eth_5m | $14.64 | $300.0 | No |
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
