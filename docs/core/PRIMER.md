# Polymarket Bot — System Primer

A bot that bets on 5-minute "Bitcoin/Ethereum Up or Down" markets on Polymarket, trades BTCUSDT perpetual futures on Bybit, and is expanding to Kalshi. Pure math from candlestick data — no LLMs at runtime, $0/day operating cost.

**Live trading since 2026-03-31.** Flat $25 per bet (Polymarket) / 0.005 BTC per position (Bybit).

---

## The Five Pipelines

| Pipeline | Schedule | Signal | Status | Database |
|----------|----------|--------|--------|----------|
| **BTC 5m** | Every 5 min | Momentum | **LIVE** ($25/bet) | `predictions.db` |
| **BTC 15m** | Every 15 min | Momentum (5m signal) | Paper | `predictions_15m.db` |
| **ETH 5m** | Every 5 min | Momentum | Paper | `predictions_eth.db` |
| **Bybit BTCUSDT** | Every 5 min | Momentum | Paper (0.005 BTC) | `predictions_bybit.db` |
| **Kalshi BTC** | Every 15 min | Momentum | Phase 0 (mock) | `predictions_kalshi.db` |

Each pipeline is **fully isolated** — separate DB, workflow, dashboard, and CI job. If one crashes, the others are unaffected. All dashboards are cross-linked at [GitHub Pages](https://mariomerinom.github.io/polymarket-bot/).

---

## How a Prediction Becomes a Bet

This is the complete lifecycle. Every step is a real function call, not a concept.

```
 FETCH           ANALYZE          GATE             SCORE           TRADE            SETTLE
 ─────           ───────          ────             ─────           ─────            ──────
 Candles    →  Regime + Streak  →  Dead Hour?   →  Conviction   →  Circuit Check  →  Resolution
 (Kraken,      (vol, autocorr,     Price Gate?     (0-5)           Daily Loss?      P&L Calc
  Coinbase)     streak >= 3)       MR Regime?      Consensus?      Consec Loss?     Brier Score
                                   Extreme Est?    Sweet Spot?     Book Depth?
```

### Stage 1: Data Fetch

Every cycle fetches 20 candles from exchange APIs. All pipelines use 5-minute candles — the atomic unit for streak detection.

| Asset | Primary Source | Secondary Source | Consensus                                 |
| ----- | -------------- | ---------------- | ----------------------------------------- |
| BTC   | Kraken         | Coinbase         | Yes — both must see streak for conv boost |
| ETH   | Coinbase       | —                | No                                        |
| Bybit | Bybit API      | —                | No                                        |

### Stage 2: Regime Classification

Two dimensions computed from candle returns:

**Volatility** (stdev of returns):

| Label | BTC Threshold | ETH Threshold |
|-------|--------------|---------------|
| LOW_VOL | < 0.05% | < 0.10% |
| MEDIUM_VOL | 0.05% – 0.12% | 0.10% – 0.20% |
| HIGH_VOL | >= 0.12% | >= 0.20% |

**Trend** (autocorrelation of returns):

| Label | Threshold | Effect |
|-------|-----------|--------|
| TRENDING | > 0.15 | Momentum works — trade |
| NEUTRAL | -0.15 to 0.15 | Trade with caution |
| MEAN_REVERTING | < -0.15 | Momentum fails — **skip** |

Mean-reverting markets lost $1,533 paper money in backtesting. The regime gate is the single most important filter.

### Stage 3: Streak Detection

Count consecutive 5-minute candles closing in the same direction. If the streak is >= 3 candles, the signal fires. **We ride the streak** — UP streak means predict UP. DOWN streak means predict DOWN. The 5m candle is the atomic unit — all pipelines (including 15m and Bybit) use 5m candle data for streak detection.

The estimate is computed dynamically, not hardcoded:
```
strength = log(|streak|) / log(baseline_streak) × magnitude_factor
edge = max_edge × strength
estimate = 0.50 ± edge     (range: ~0.36 to ~0.64)
```

### Stage 4: Gate Filters

Three gates can skip a prediction. Each gate has an **extreme estimate override** — if the signal is strong enough (estimate > 0.65 or < 0.35), it bypasses the gate and gets stored as a conv=2 shadow for forward validation.

| Gate | Condition | Normal Action | Extreme Override |
|------|-----------|--------------|-----------------|
| **Dead Hour** | Current UTC hour has < 50% WR on 30+ historical bets | Skip (conv=0) | Shadow (conv=2) |
| **Price Gate** | Market price > 85% or < 15% | Skip (conv=0) | Shadow (conv=2) |
| **MR Regime** | Autocorrelation below threshold | Skip (conv=0) | Shadow (conv=2) |

Dead hours are **data-driven** — computed from the last 90 days of resolved predictions, with a fallback to {3, 16, 21} UTC when the DB has insufficient data.

### Stage 5: Conviction Scoring

Conviction determines whether a prediction becomes a real bet.

| Tier | Bet Size | Assignment Logic |
|------|----------|-----------------|
| **conv=0** | $0 (skip) | No signal, gated out, or extreme skip |
| **conv=2** | $0 (shadow) | DOWN+NEUTRAL regime, extreme estimate override, or shadow-only |
| **conv=3** | $25 | Base tradeable — medium confidence in valid regime |
| **conv=4** | $25 | UP direction + market price in sweet spot (20%–70%) |
| **conv=5** | $25 | Conv 4 + cross-exchange consensus or 5m confirmation boost |

Two independent boosts can increase conviction by +1 each (capped at 5):
- **Cross-exchange consensus:** Kraken and Coinbase both detect the same streak (score=2)
- **5m confirmation boost:** The 5m pipeline has 2+ recent predictions in the same direction (15m pipeline only)

All tiers bet the same $25 in production (Phase 1 flat grind). Tiers exist to track whether higher conviction predicts better outcomes.

**Key filter:** DOWN + NEUTRAL regime is demoted to conv=2. It has 52% WR — coin-flip territory. UP + NEUTRAL stays at conv >= 3 (82% WR on 90 bets).

### Stage 6: Trade Execution

Predictions with conv >= 3 hit the trade execution pipeline (`src/trade.py`). Four circuit breakers must pass before an order is placed:

| Breaker | Threshold | Resets |
|---------|-----------|--------|
| **Conviction gate** | conv < 3 | Per-prediction |
| **Edge threshold** | \|estimate - 0.50\| < 5% | Per-prediction |
| **Daily loss limit** | $300 cumulative losses today | UTC midnight |
| **Consecutive loss breaker** | 5 losses in a row | Next win |

If all gates pass, the order is constructed:

```
price_limit = estimate + 0.02 (fill priority spread)
max_price = market_price + 0.05 (slippage cap) + 0.02 (fill priority)
size = $25 (BTC) or conviction-tiered (ETH: $25/$50/$75)
```

**Book depth guard:** If CLOB liquidity data is available, size is capped at 90% of max bet at 2% slippage. Orders below $5 are rejected.

**Two modes:**
- `TRADING_ENABLED=true`: Submit GTC limit order to Polymarket CLOB via `py-clob-client` on Polygon
- `TRADING_ENABLED=false` (default): Log what would have been placed (paper mode)

**Kill switch:** `data/KILL_SWITCH` file or `KILL_SWITCH=true` env var halts all trading instantly, no code change needed.

### Stage 7: Settlement & P&L

After markets resolve (5-minute window closes):

1. **Auto-resolve:** Query Polymarket Gamma API for closed markets, snap outcome from final price
2. **Match fills:** Check CLOB trade history for our order IDs
3. **Compute P&L:**
   - Win: `pnl = size × (1/fill_price - 1) × 0.985` (fee-adjusted)
   - Loss: `pnl = -size`
4. **Update status:** submitted → filled → settled (with pnl)

Expired orders (never filled before market resolved) get status "expired" — tracked separately for fill rate analysis.

---

## Bybit Perpetual Futures Pipeline

The Bybit pipeline trades BTCUSDT perpetual futures instead of Polymarket binary options. Same momentum signal, different execution.

| Setting | Value |
|---------|-------|
| Position size | 0.005 BTC (~$420 at $84k) |
| Leverage | None (1x) |
| Stop-loss | Entry ± 1.5 × ATR(14) |
| Max hold time | 6 cycles (30 minutes) |
| Daily loss limit | $50 |
| Kill switch | `data/KILL_SWITCH_BYBIT` or env var |
| Fee | 0.055% taker / 0.02% maker |

**Position lifecycle:** Open (limit order + server-side stop) → Hold (check exit each cycle) → Close (market order on streak break, time ceiling, or stop-loss).

Key difference from Polymarket: positions can be held across multiple cycles. Polymarket bets are one-shot per 5-minute market.

---

## Shadow Systems

Three observational systems run alongside production. They never place bets or modify conviction — they log data for forward validation.

### Shadow Conviction Scorer (`shadow_conviction_scorer.py`)

A parameterized scoring engine that computes a continuous strength signal for every prediction. Each pipeline has its own config (streak baseline, edge caps, tier thresholds). The shadow tier is logged alongside the production conviction for comparison.

```
shadow_strength = log_curve(streak) × magnitude(price_move / volatility)
shadow_edge = max_edge × shadow_strength
shadow_tier = map_to_tier(shadow_edge, conv_thresholds)
```

### Shadow Indicators (`shadow_indicators.py`)

Three technical indicators attached to every prediction's reasoning JSON:

| Indicator | What It Measures | When Attached |
|-----------|-----------------|---------------|
| **RSI(14)** | Momentum oscillator (0-100) | Always |
| **OBV Slope** | Volume-price divergence | Market price in 50%-70% |
| **VWAP Z-Score** | Deviation from volume-weighted average | Mean-reverting regime only |

### VWAP Mean-Reversion Shadow

When the regime is mean-reverting and VWAP z-score exceeds thresholds, a separate `vwap_meanrev` agent stores shadow predictions at conv=2. These are tracked but never traded — the VWAP strategy was reverted after actual WR came in at 29.4% (initial stat was misread).

---

## Circuit Breakers — All of Them

Every dashboard shows a circuit breaker panel with live status. Here's the complete inventory:

### Prediction-Level Gates

| Gate | Config Key | Value | Scope |
|------|-----------|-------|-------|
| Min streak | `SHADOW_CONFIGS[pipeline].min_streak` | 3 (all pipelines) | Per-signal |
| Dead hour | `compute_dead_hours()` | Data-driven, fallback {3,16,21} UTC | Per-market |
| Price gate | `PRICE_GATE_UPPER/LOWER` | 85% / 15% | Per-market |
| MR regime | `AUTOCORR_MEAN_REVERTING_5M` | -0.15 | Per-cycle |
| Extreme override | `EXTREME_ESTIMATE_UPPER/LOWER` | 0.65 / 0.35 | Per-market |
| DOWN+NEUTRAL | Hardcoded in `store_prediction` | Demotes to conv=2 | Per-prediction |

### Trade-Level Breakers

| Breaker | Config Key | Value | Resets |
|---------|-----------|-------|--------|
| Conviction floor | `MIN_CONVICTION` | 3 | Per-prediction |
| Edge threshold | `EDGE_THRESHOLD` | 0.05 (5%) | Per-prediction |
| Daily loss limit | `DAILY_LOSS_LIMIT` | $300 (Polymarket) / $50 (Bybit) | UTC midnight |
| Consecutive losses | `CONSECUTIVE_LOSS_MAX` | 5 in a row | Next win |
| Kill switch | File or env var | `data/KILL_SWITCH` | Manual removal |
| Thin book guard | `BOOK_DEPTH_SAFETY_MARGIN` | 90% of max@2% slippage | Per-order |
| Min bet size | `MIN_BET_SIZE` | $5 | Per-order |

### Bybit-Specific

| Breaker | Config Key | Value |
|---------|-----------|-------|
| Max hold time | `BYBIT_MAX_HOLD_CYCLES` | 6 cycles (30 min) |
| Stop-loss | `BYBIT_STOP_ATR_MULT` | 1.5 × ATR |
| Same-direction skip | Code check | Can't open same-way twice |

All config values live in `src/config.py` and are env-overridable where noted. The dashboard reads them at generation time — no hardcoded values in the display layer.

---

## Repository Map

### Core Pipeline (`src/`)

| File | Role |
|------|------|
| `ci_run.py` | BTC 5m orchestrator. Fetch → predict → trade → score → dashboard. |
| `ci_run_15m.py` | BTC 15m orchestrator. Uses 5m candles + 5m confirmation boost. |
| `ci_run_eth.py` | ETH 5m orchestrator. Same flow, ETH-specific vol thresholds. |
| `ci_run_bybit.py` | Bybit orchestrator. Perpetual futures lifecycle. |
| `ci_run_kalshi.py` | Kalshi orchestrator. Phase 0, mock mode. |
| `predict.py` | **BTC brain.** Regime, streaks, gates, conviction, shadow scoring. **FROZEN.** |
| `predict_eth.py` | ETH brain. Same momentum logic, separate DB. |
| `btc_data.py` | BTC candles from Kraken + Coinbase. **FROZEN.** |
| `eth_data.py` | ETH candles from Coinbase. |
| `trade.py` | Polymarket order execution. Circuit breakers, sizing, CLOB submission. |
| `bybit_trade.py` | Bybit position lifecycle. Open/close/stop-loss. |
| `score.py` | Market resolution and Brier score computation. **FROZEN.** |
| `fetch_markets.py` | Active Polymarket markets via Gamma API. |
| `kalshi_markets.py` | Active Kalshi markets via REST API (HMAC auth). |
| `dashboard.py` | Static HTML dashboard generator. Breaker panels, shadow labels, P&L. |
| `config.py` | **All thresholds, gates, and sizing constants.** Single source of truth. |
| `shadow_conviction_scorer.py` | Parameterized shadow scoring engine. |
| `shadow_indicators.py` | RSI, OBV, VWAP shadow indicator logging. |
| `clob_depth.py` | Polymarket CLOB liquidity queries. **FROZEN.** |
| `daily_report.py` | Daily performance report with alerts and optimization monitoring. |
| `optimization_tracker.py` | Registers, monitors, and flags active optimizations. |
| `generate_dashboard.py` | Regenerate BTC 5m dashboard locally. |
| `pipeline_control.py` | Pipeline mode control (live/paused). |

### Data (`data/`)

| File | Contents |
|------|----------|
| `predictions.db` | BTC 5m — predictions, markets, orders. CI auto-commits. |
| `predictions_15m.db` | BTC 15m. Isolated. |
| `predictions_eth.db` | ETH 5m. Isolated. |
| `predictions_bybit.db` | Bybit BTCUSDT. Has `positions` table. |
| `predictions_kalshi.db` | Kalshi BTC. Phase 0 data. |
| `KILL_SWITCH` | If this file exists, all Polymarket trading halts. |
| `KILL_SWITCH_BYBIT` | If this file exists, all Bybit trading halts. |

### CI/CD (`.github/workflows/`)

| Workflow | Schedule | Entry Point |
|----------|----------|-------------|
| `predict-and-score.yml` | Self-scheduling ~5 min | `ci_run.py` |
| `predict-15m.yml` | Self-scheduling ~15 min | `ci_run_15m.py` |
| `predict-eth-5m.yml` | Self-scheduling ~5 min | `ci_run_eth.py` |
| `predict-bybit.yml` | Self-scheduling ~5 min | `ci_run_bybit.py` |
| `predict-kalshi.yml` | Self-scheduling ~15 min | `ci_run_kalshi.py` |
| `daily-report.yml` | 06:00 CST daily | `daily_report.py` |

Each workflow has a `*/30 * * * *` cron fallback. The primary mechanism is `repository_dispatch` — each successful run schedules its own next run. Max 300 dispatches/day guard prevents runaway loops.

**CI auto-commits constantly.** Always `git pull --rebase` before pushing. If DB conflicts, your code changes win — CI regenerates the DB next cycle.

### Tests (`tests/`)

**338 tests** across 14 files. Runtime: ~60 seconds. Must pass before every commit.

| File | Tests | What It Covers |
|------|-------|---------------|
| `test_smoke.py` | Imports | Broken imports, syntax errors |
| `test_momentum.py` | BTC signal | Streak detection, direction, confidence |
| `test_eth_signal.py` | ETH signal | ETH momentum matches BTC logic |
| `test_regime.py` | Regime | Trending/MR/neutral classification |
| `test_pnl.py` | P&L math | Win/loss calculation, conviction tiers |
| `test_trade.py` | Execution | Sizing, circuit breakers, kill switch, CLOB |
| `test_btc_data.py` | Candles | Parsing, summary stats, null handling |
| `test_15m.py` | 15m pipeline | 5m atomic unit, sibling boost, loose mode |
| `test_regression.py` | Incidents | One test per past production incident |
| `test_shadow_conviction.py` | Shadow scorer | Tier mapping, production isolation |
| `test_shadow_indicators.py` | Indicators | RSI/OBV/VWAP logging |
| `test_vwap_strategy.py` | VWAP | Mean-reversion shadow strategy |
| `test_activity_digest.py` | Digest | Session log generation |
| `test_pipeline_e2e.py` | **E2E lifecycle** | Full predict-trade-settle-score chain |

The E2E tests exercise the complete lifecycle on an in-memory DB with real functions (no mocks). They caught the cold-start drawdown breaker bug that halted trading for 36 hours.

### Docs (`docs/`)

| Directory | Contents |
|-----------|----------|
| `core/` | PRIMER (this file), strategy, ROADMAP, decisions, TESTING |
| `ops/` | BREAK_FIX_LOG, ENGINEERING_LESSONS |
| `plans/` | Kalshi integration, multi-asset expansion |
| `reference/` | Kelly sizing, liquidity probes |
| `research/` | Backtest findings, outcome analysis (BTC/ETH/SOL), pattern mining |
| `specs/` | Unimplemented feature designs (RSI gate, OBV filter, volatility breakout, etc.) |
| `analysis/` | Postmortems, theses, one-off investigations |
| `pipelines/` | ETH acceptance criteria, model training spec |
| `daily/` | Auto-generated daily reports |
| `sessions/` | Working session logs |
| `archive/` | Superseded docs (V3 contrarian, old plans) |
| `*.html` | Dashboard pages (auto-generated, do not edit) |

---

## Frozen Files

The BTC 5m pipeline is the money-maker. These files must have **zero lines changed** unless explicitly approved:

`src/ci_run.py`, `src/btc_data.py`, `src/predict.py`, `src/score.py`, `src/clob_depth.py`, `.github/workflows/predict-and-score.yml`, `data/predictions.db`

Run `git diff --name-only` before committing and verify none of these appear.

---

## Validation Principles

1. **Baseline before shipping.** Snapshot WR, P&L, bet count before every change.
2. **Revert criteria before shipping.** Decide what "failure" looks like while you're still objective.
3. **50-bet minimum.** Anything less is noise.
4. **Forward validation only.** The data that found the edge can't confirm it.
5. **Track the counterfactual.** Filtered predictions stored at conv=2 for comparison.
6. **One change at a time.** Can't attribute results to stacked changes.
7. **Paper trade first.** 200+ resolved predictions before risking real capital.

---

## Production Sizing Philosophy

Production sizing is a grind, not a gamble.

| Phase | Bet Size | Advance Trigger | Stop Trigger |
|-------|----------|-----------------|-------------|
| **Phase 1 (CURRENT)** | $25 flat | Bankroll +$500 | WR < 52% over 50 bets, or -$300 daily |
| **Phase 2** | $50 flat | Bankroll +$1,500 cumulative | WR < 52% over 50 bets, or -$500 daily |
| **Phase 3** | Kelly fractional | Bankroll +$3,000 cumulative | Drawdown > 30% of peak |

Conviction gates which bets fire (conv >= 3), not how much. All bets are the same dollar amount within a phase. Kelly sizing in Phase 3 is capped by CLOB book depth, not just bankroll math.

---

## Key Principles

- **This is MOMENTUM.** We ride streaks. V3 faded streaks and lost at 37% WR (BTC) and 33% WR (ETH). This is non-negotiable.
- **No LLMs at runtime.** V1/V2 cost $15-50/day for marginal signal. The current system runs for $0.
- **No agent bias.** All directional bias comes from price data, not prompts or code.
- **Config is the source of truth.** Every threshold that affects money lives in `src/config.py`.
- **GitHub is the source of truth.** Always pull before reading data. Always push after making changes.

---

## Quick Commands

```bash
# Run tests (always before committing)
python3 -m pytest tests/ -v

# Generate BTC 5m dashboard locally
python3 src/generate_dashboard.py

# Check optimization status
python3 src/optimization_tracker.py summary

# Check project health
git pull && cat docs/daily/$(ls -t docs/daily/ | head -1)

# Full health check
git pull
python3 -m pytest tests/ -v
python3 src/optimization_tracker.py summary
```

---

## Giving Back

A portion of this project's profits will be donated to **[GiveDirectly](https://www.givedirectly.org/)** — direct cash transfers to people in extreme poverty. Amount and frequency TBD once the pipeline has a steady track record.
