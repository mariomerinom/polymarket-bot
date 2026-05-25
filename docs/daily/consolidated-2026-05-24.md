# Consolidated Daily Report — 2026-05-24

Cross-pipeline aggregation across all 12 BOTSY pipelines. Per-pipeline drill-down is in the companion [2026-05-24.md](2026-05-24.md) file.

## 1. Portfolio Totals

| Metric | Value |
|--------|-------|
| Total bets | 145 |
| Total wins | 67 |
| Total losses | 78 |
| Aggregate WR | 46.2% |
| Total P&L | **-$210.13** |
| Total wagered | $3,625.00 |
| Pipelines with resolved bets | 8 of 12 |

## 2. Pipeline Leaderboard

All pipelines, sorted by today's P&L (descending).

| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |
|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|
| sol_bybit | SOL | paper | 16 | 62.5% | +$100.00 | -0.071 | — | $400.00 |
| doge_hl | DOGE | paper | 18 | 55.6% | +$50.00 | +0.047 | — | $450.00 |
| sol_hl | SOL | paper | 16 | 56.2% | +$50.00 | -0.078 | — | $400.00 |
| eth_5m | ETH | paper | 17 | 47.1% | +$29.66 | -0.010 | +0.097 | $425.00 |
| doge_bybit | DOGE | paper | 18 | 50.0% | $0.00 | +0.033 | — | $450.00 |
| hl | BTC | paper | 26 | 42.3% | -$100.00 | -0.048 | — | $650.00 |
| bybit | BTC | paper | 18 | 33.3% | -$150.00 | -0.003 | — | $450.00 |
| btc_5m | BTC | paper | 16 | 25.0% | -$189.79 | -0.117 | -0.074 | $400.00 |
| btc_15m | BTC | paused | 0 | — | $0.00 | — | — | — |
| eth_bybit | ETH | paused | 0 | — | $0.00 | — | — | — |
| eth_hl | ETH | paused | 0 | — | $0.00 | — | — | — |
| kalshi | BTC | paused | 0 | — | $0.00 | — | — | — |

## 3. Per-Asset Roll-up

| Asset | Pipelines | Bets | WR | P&L | Wagered |
|-------|-----------|-----:|----|-----|--------:|
| **BTC** | btc_5m, bybit, hl | 60 | 35.0% | -$439.79 | $1,500.00 |
| **ETH** | eth_5m | 17 | 47.1% | +$29.66 | $425.00 |
| **SOL** | sol_bybit, sol_hl | 32 | 59.4% | +$150.00 | $800.00 |
| **DOGE** | doge_bybit, doge_hl | 36 | 52.8% | +$50.00 | $900.00 |

## 4. Signal vs Execution EHR (7-day rolling)

Gap = signal EHR − execution EHR. The edge that execution destroys.

| Pipeline | Signal EHR | Exec EHR | n | Gap |
|----------|-----------:|---------:|--:|----:|
| btc_5m | -0.1168 | -0.0744 | 135 | -4.2¢/$ |
| bybit | -0.0032 | — | 155 | — |
| doge_bybit | +0.0333 | — | 75 | — |
| doge_hl | +0.0467 | — | 75 | — |
| eth_5m | -0.0098 | +0.0972 | 113 | -10.7¢/$ |
| hl | -0.0475 | — | 221 | — |
| sol_bybit | -0.0714 | — | 147 | — |
| sol_hl | -0.0782 | — | 147 | — |

## 5. Shadow Maker (Phase 1)

Hypothetical maker fills — what would have filled if we posted passively.

| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |
|----------|-------:|-------:|----------:|----------:|-----------:|
| btc_5m | 16 | 16 | 100.0% | 75.0% | -0.1897 |
| eth_5m | 17 | 17 | 100.0% | 52.9% | +0.0035 |

## 6. Alerts (All Pipelines)

### btc_5m
- ⚠️ Daily WR 25.0% below 55% threshold (16 bets)
- ⚠️ Daily P&L $-189.79 — significant loss
- 🚨 4 consecutive losing days
- ⚠️ orphaned_predictions: 5 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12310; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12281; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12252; +2 more
- 🚨 Signal EHR negative: -0.1168 over 135 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 30.8% WR on 13 bets ($-114.79); require cohort review before promotion

### bybit
- ⚠️ Daily WR 33.3% below 55% threshold (18 bets)
- ⚠️ Daily P&L $-150.00 — significant loss
- ⚠️ orphaned_predictions: 12 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11205; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11203; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=11158; +9 more
- 🚨 Signal EHR negative: -0.0032 over 155 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: UP in MEDIUM_VOL / NEUTRAL is 40.0% WR on 15 bets ($-75.00); require cohort review before promotion

### doge_bybit
- ⚠️ Daily WR 50.0% below 55% threshold (18 bets)
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7829; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7821; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=7790; +8 more

### doge_hl
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8387; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8379; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8348; +8 more

### eth_5m
- ⚠️ Daily WR 47.1% below 55% threshold (17 bets)
- ⚠️ orphaned_predictions: 11 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12096; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12093; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=12092; +8 more
- 🚨 Signal EHR negative: -0.0098 over 113 bets (7-day) — model may be buying overpriced contracts
- 🧯 side/regime promotion guardrail: DOWN in MEDIUM_VOL / NEUTRAL is 42.9% WR on 7 bets ($+15.18); require cohort review before promotion

### hl
- ⚠️ Daily WR 42.3% below 55% threshold (26 bets)
- 🚨 3 consecutive losing days
- 📉 WR declining: 47% → 33% over 7 days
- ⚠️ orphaned_predictions: 17 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5897; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5868; 1 conv>=3 prediction(s) with no terminal execution classification: missing_terminal_classification: 1 prediction(s) ids=5858; +14 more
- 🚨 Signal EHR negative: -0.0475 over 221 bets (7-day) — model may be buying overpriced contracts

### sol_bybit
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8323; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8322; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8301; +7 more
- 🚨 Signal EHR negative: -0.0714 over 147 bets (7-day) — model may be buying overpriced contracts

### sol_hl
- ⚠️ orphaned_predictions: 10 issue(s) - 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8321; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8320; 1 conv>=3 prediction(s) with no terminal execution classification: missing_fill_diagnostic_table: 1 prediction(s) ids=8299; +7 more
- 🚨 Signal EHR negative: -0.0782 over 147 bets (7-day) — model may be buying overpriced contracts

## 7. Engine Health

| Feed | Status | Reconnects (24h) |
|------|--------|-----------------:|
| bybit_spot | connected | 179 |
| bybit_linear | connected | 3 |
| polymarket | connected | 60 |

| Metric | p50 | p95 | Samples |
|--------|----:|----:|--------:|
| Production dispatch latency (ms) | 9309 | 19989 | 704 |
| Bybit event lag (ms) | 863 | 45137 | 956 |
| TA build (ms) | 76 | 159 | 704 |
| Pipeline fanout (ms) | 9243 | 19884 | 704 |
| Strategy Lab runtime (ms) | 202 | 1322 | 704 |
| Total dispatch wall time (ms) | 9624 | 20954 | 704 |
| True orderbook age (ms) | 7877 | 154796 | 775 |
| BTC 5m executable orderbook age (ms) | ? | ? | 0 |

- Slowest pipeline runtime: bybit p95=20436ms (239 samples)
- BTC 5m executable reads: fresh=0 stale=0 missing=0 partial=0 total=0
- Orderbook cache: 44 tokens, 517 token-set changes (24h)
- Cycles: 2607
- Fallback fires (24h): 0
- Engine start: 2026-05-24T04:00:02.625776+00:00

- Polymarket events: book=1635275, price_change=43162170, ignored={'last_trade_price': 755703, 'new_market': 5508, 'tick_size_change': 8}
- Orderbook freshness detail: fresh/stale tokens: 14/30, updated last 60s/5m: 44/44, stale reasons: {'stale_updated_at': 30}
- REST snapshot seed: 10014/10018 successful (missing=0, invalid_bbo=4)
- Polymarket resubscribe: resubscribe debounced/executed: 289/261, added/removed tokens: 1510/1920
- Orderbook freshness decision: dominant cause: missing snapshots before price_change

### BTC 5m Production Readiness

- Verdict: BLOCKED
- Live canary blockers: signal_ehr_not_positive (-0.1008); execution_ehr_insufficient_sample (0/10); orderbook_age_p95_too_high (154796); orderbook_stale_tokens_exceed_fresh (30/14)
- Delayed FAK blockers: delayed_ehr_insufficient_sample (0/50)
- Production promotion blockers: promotion_signal_ehr_below_threshold (-0.1008 < +0.0200)

✅ Kill switch clear (no `data/KILL_SWITCH` file).

## 8. Circuit Breaker Status

Daily loss vs $300 per-pipeline limit.

| Pipeline | Daily Loss | Breaker Limit | Tripped? |
|----------|-----------:|--------------:|:--------:|
| btc_5m | $150.00 | $300.0 | No |
| bybit | $0.00 | $300.0 | No |
| doge_bybit | $0.00 | $300.0 | No |
| doge_hl | $0.00 | $300.0 | No |
| eth_5m | $17.64 | $300.0 | No |
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
