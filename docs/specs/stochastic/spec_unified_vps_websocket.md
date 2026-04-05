# Spec: Unified VPS + Websocket Architecture

**Status:** Proposed
**Replaces:** `spec_bybit_vps_migration.md`, `spec_fill_diagnostic.md`
**Goal:** Consolidate all execution onto one VPS, replace polling with websockets, and instrument the diagnostics that resolve the fill-problem debate — in three sequential phases over ~10 days.

---

## Why One Spec

These three efforts are interdependent:

- Migrating Bybit/Kalshi to the VPS is a prerequisite for the websocket rewrite (no point rewriting if half the pipelines are still on GitHub Actions).
- The websocket rewrite eliminates the stale price snapshot, which is the core of Tension 2 from the fill-problem analysis.
- The fill diagnostics (snapshot age, conviction-vs-drift) should run during the transition to validate the architectural decision with data.

Doing them as separate specs creates ordering ambiguity. This spec makes the sequence explicit.

---

## Phase 1: Consolidate (Days 1-2) — COMPLETE

> Deployed: commit `e2d07f13` (2026-04-05). All 5 pipelines on VPS, GitHub Actions disabled.

Move all pipelines to the VPS. Kill GitHub Actions as an execution environment.

### Changes

**`vps-loop.sh`** — add Bybit and Kalshi to the existing loop:

```bash
# After existing BTC 5m / ETH 5m / BTC 15m blocks:

# Bybit BTC Perps — every cycle
python src/predict.py --pipeline bybit_btc_perps
git add -A && git commit -m "bybit predict $(date -u +%H:%M)" && git push || true

# Kalshi BTC — every cycle
python src/predict.py --pipeline kalshi_btc
git add -A && git commit -m "kalshi predict $(date -u +%H:%M)" && git push || true
```

**VPS `.env`** — add Bybit and Kalshi API keys. Remove from GitHub Secrets after validation.

**GitHub Actions** — disable all `repository_dispatch` and cron workflows. Keep `workflow_dispatch` as manual emergency fallback.

**Timing guard** — add cycle timing to the loop:

```bash
CYCLE_START=$(date +%s)
# ... all pipelines ...
CYCLE_END=$(date +%s)
ELAPSED=$((CYCLE_END - CYCLE_START))
echo "DIAG|cycle_seconds=$ELAPSED"
if [ $ELAPSED -gt 240 ]; then
  echo "WARN: cycle exceeded 4 min, consider parallelizing"
fi
```

If total cycle time exceeds 4 min, parallelize pipelines with `&` and `wait`.

### Validation

| Check | Method |
|-------|--------|
| All 5 pipelines producing predictions every 5 min | `git log --oneline --since="1 hour ago"` |
| GitHub Actions idle | Actions tab shows zero triggered runs |
| API keys working | First cycle logs for Bybit/Kalshi show successful responses |
| Cycle time within budget | `DIAG|cycle_seconds` stays under 240 |

### Exit Criteria

All pipelines running on VPS for 24 hours with no missed cycles. Then proceed to Phase 2.

---

## Phase 2: Instrument (Days 2-3, overlaps with Phase 1) — LIVE

> Deployed: commit `57b0f9ea` (2026-04-05). DIAG log lines active, `fill_diagnostic.py` ready. Awaiting 24-48h of data accumulation.

Deploy the fill diagnostics to collect the data that resolves Tension 1 and Tension 2. This runs in parallel with Phase 1 — four log lines, zero execution changes.

### Changes

**`src/trade.py`** — add to `compute_order()`:

```python
# Diagnostic A: Snapshot staleness (Tension 2)
snapshot_age_ms = (datetime.utcnow() - market_row["updated_at"]).total_seconds() * 1000
log.info(f"DIAG|snapshot_age_ms={snapshot_age_ms:.0f}|market={market_row['market_id']}")

# Diagnostic B: Conviction vs. price drift (Tension 1)
live_price = fetch_live_mid(market_row["market_id"])
price_drift = abs(live_price - market_price_yes)
conviction = prediction_row.get("conviction_score", 0)
log.info(f"DIAG|conv={conviction}|drift={price_drift:.4f}|snapshot_age_ms={snapshot_age_ms:.0f}")

# Diagnostic C: Order submission RTT (cancel-replace feasibility)
t0 = time.monotonic()
response = submit_order(...)
rtt_ms = (time.monotonic() - t0) * 1000
log.info(f"DIAG|order_rtt_ms={rtt_ms:.0f}|status={response.status}")
```

### Decision Rules (after 24-48 hours of data)

**Tension 2 — Snapshot staleness:**

| p95 Snapshot Age | Conclusion |
|------------------|------------|
| < 500ms | Staleness is minor. Websocket rewrite is an optimization, not urgent. Deploy dynamic slippage formula now. |
| 500ms - 2s | Gray zone. Deploy formula now, accelerate Phase 3. |
| > 2s | Staleness is the root cause. Phase 3 is mandatory before the formula change matters. |

**Tension 1 — Conviction in the slippage formula:**

| Conv=5 vs Conv=3 Drift | Conclusion |
|-------------------------|------------|
| Conv=5 significantly larger (p < 0.05) | Exclude conviction from pricing. Use microstructure only. |
| No significant difference | Use conviction as ceiling/governor (Gemini approach). |
| Conv=5 significantly smaller | Conviction additive bonus is defensible (Grok approach). |

**Cancel-replace feasibility:**

| p95 Order RTT | Conclusion |
|---------------|------------|
| < 500ms | Cancel-replace cycles are viable. Build into Phase 3. |
| 500ms - 1s | Possible but tight. Limit to 2 cycles max. |
| > 1s | Cancel-replace is impractical on this API. Skip it. |

### Surfacing the Results

The diagnostic data must produce a concrete deliverable — not raw logs that require manual parsing.

**`src/fill_diagnostic.py`** — standalone analysis script:

```python
"""
Parse DIAG lines from logs, compute summary statistics, output decision table.
Run manually or from daily_report.py after 24h of collection.

Usage: python src/fill_diagnostic.py --log-file /var/log/botsy.log --min-samples 20
"""

# 1. Parse all DIAG lines from log file
# 2. Compute:
#    - snapshot_age_ms: p50, p95, p99
#    - order_rtt_ms: p50, p95, p99
#    - price_drift grouped by conviction tier: median, mean, std
#    - Mann-Whitney U test: conv=3 drift vs conv=5 drift (p-value)
# 3. Output: decision table (text + markdown)
```

**`src/daily_report.py`** — add a "Phase 2 Diagnostic" section that runs automatically once sufficient data exists (>= 20 samples per conviction tier). This appears in the same daily report already reviewed each morning:

```
## Fill Diagnostic (Phase 2)

| Metric | p50 | p95 | p99 |
|--------|-----|-----|-----|
| Snapshot age (ms) | 847 | 2340 | 4100 |
| Order RTT (ms) | 312 | 490 | 780 |

| Conv Tier | Median Drift | Samples |
|-----------|-------------|---------|
| 3 | 0.0031 | 24 |
| 4 | 0.0058 | 31 |
| 5 | 0.0092 | 22 |

Mann-Whitney U (conv=3 vs conv=5): p=0.003

### Decisions
- ⚠️ Snapshot staleness p95 > 2s → Phase 3 websocket rewrite is mandatory
- ✅ Conv=5 drift >> Conv=3 drift (p < 0.05) → Exclude conviction from slippage formula
- ✅ Order RTT p95 < 500ms → Cancel-replace cycles are viable in Phase 3
```

The "Decisions" lines are auto-generated by applying the decision rules to the computed statistics. No interpretation required — the report tells you what to do.

### Acceptance Criteria

Phase 2 is complete when all of the following are true:

- [ ] DIAG log lines are being emitted on every `compute_order()` invocation (verified by `grep DIAG /var/log/botsy.log | head`)
- [ ] Minimum 20 samples per conviction tier (3, 4, 5) have been collected
- [ ] `src/fill_diagnostic.py` exists and produces the decision table from raw logs
- [ ] Daily report includes the "Fill Diagnostic (Phase 2)" section with populated statistics
- [ ] All three decision rows (staleness, conviction, RTT) show a resolved verdict (not "insufficient data")
- [ ] The chosen slippage formula variant is documented in a one-line update to `spec_unified_vps_websocket.md`

Then proceed to Phase 3.

---

## Phase 3: Websocket Rewrite (Days 4-10)

Replace `vps-loop.sh` (bash while-loop with `sleep 300`) with an async Python process driven by exchange websocket events.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  botsy_engine.py (single async process)                      │
│                                                              │
│  ┌──────────────────────────────┐                            │
│  │ WS: Bybit (single connection)│  ← candle close events    │
│  │ BTC: 1m, 5m, 15m            │    all pipelines           │
│  │ ETH: 1m, 5m                 │    validated 241ms RTT     │
│  └──────┬───────────────────────┘                            │
│         │                                                    │
│         ▼                 ▼                                  │
│  ┌──────────────────────────────┐                            │
│  │  Candle Buffer               │  ← rolling 100-candle     │
│  │  per symbol, per timeframe   │    ring buffer in memory   │
│  └──────┬───────────────────────┘                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────┐                            │
│  │  TA Engine (pandas-ta)       │  ← recomputes on each     │
│  │  RSI, BB, VWAP, OBV, Stoch  │    new candle from buffer  │
│  │  per symbol, per timeframe   │    sub-ms latency          │
│  └──────┬───────────────────────┘                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────┐                            │
│  │  Event Router                │                            │
│  │  on_candle_close(symbol, tf) │                            │
│  └──────┬───────────────────────┘                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────┐                            │
│  │  Pipeline Dispatcher         │                            │
│  │  5m close → BTC 5m, ETH 5m  │                            │
│  │  15m close → BTC 15m        │                            │
│  │  5m close → Bybit perps     │                            │
│  └──────┬───────────────────────┘                            │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────┐                            │
│  │  predict(candle, indicators) │  ← indicators from TA     │
│  │  compute_order()             │    engine, not external API│
│  │  live mid from WS orderbook  │  ← no stale snapshot      │
│  │  submit_order()              │                            │
│  └──────────────────────────────┘                            │
│                                                              │
│  ┌──────────────┐                                            │
│  │ WS: Polymarket│  ← live orderbook for                     │
│  │ orderbook     │    compute_order() mid price               │
│  └──────────────┘                                            │
│                                                              │
│  ┌──────────────┐                                            │
│  │ Daily report  │  ← cron trigger at 12:00 UTC              │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

### Core Components

**1. Websocket Manager** — one connection per exchange, multiple stream subscriptions:

```python
class WSManager:
    """
    One persistent connection per exchange.
    Multiple (symbol, timeframe) subscriptions per connection.
    """

    CONNECTIONS = {
        "bybit": {
            "url": "wss://stream.bybit.com/v5/public/linear",
            "streams": [
                # BTC: all timeframes (serves BTC 5m, BTC 15m, Bybit perps, Kalshi)
                "kline.1.BTCUSDT", "kline.5.BTCUSDT", "kline.15.BTCUSDT",
                # ETH: 1m + 5m
                "kline.1.ETHUSDT", "kline.5.ETHUSDT",
            ],
        },
        "polymarket": {
            "url": "wss://ws-subscriptions-clob.polymarket.com/ws/market",
            "streams": [],  # subscribed per active market_id
        },
    }

    async def connect(self, exchange):
        # Open one socket, subscribe to all streams for that exchange
        ...

    async def on_disconnect(self, exchange):
        # Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        # Alert after 3 consecutive failures
        ...
```

Total connections: 2 (Bybit for all candle data, Polymarket for live orderbook). All timeframe and symbol subscriptions are multiplexed on the Bybit socket. Validated RTT: 241ms.

**2. Candle Buffer + TA Engine** — rolling OHLCV storage and local indicator computation:

```python
import pandas_ta as ta
import numpy as np
from collections import deque

class CandleBuffer:
    """Rolling ring buffer of OHLCV candles per (symbol, timeframe)."""
    def __init__(self, maxlen=100):
        self.buffers = {}  # (symbol, tf) → deque of candle dicts
        self.maxlen = maxlen

    def append(self, symbol, timeframe, candle):
        key = (symbol, timeframe)
        if key not in self.buffers:
            self.buffers[key] = deque(maxlen=self.maxlen)
        self.buffers[key].append(candle)

    def get_df(self, symbol, timeframe):
        """Return buffer as a pandas DataFrame for TA computation."""
        key = (symbol, timeframe)
        return pd.DataFrame(list(self.buffers.get(key, [])))


class TAEngine:
    """Compute indicators from candle buffer. No external API calls."""
    def __init__(self, buffer: CandleBuffer):
        self.buffer = buffer

    def compute(self, symbol, timeframe):
        df = self.buffer.get_df(symbol, timeframe)
        if len(df) < 20:
            return None  # insufficient data for indicators

        sma_20 = ta.sma(df["close"], length=20).iloc[-1]
        std_20 = ta.stdev(df["close"], length=20).iloc[-1]
        vol_mean_20 = df["volume"].rolling(20).mean().iloc[-1]

        return {
            # Existing indicators
            "rsi_14":    ta.rsi(df["close"], length=14).iloc[-1],
            "bbands":    ta.bbands(df["close"], length=20, std=2).iloc[-1].to_dict(),
            "vwap":      ta.vwap(df["high"], df["low"], df["close"], df["volume"]).iloc[-1],
            "obv":       ta.obv(df["close"], df["volume"]).iloc[-1],
            "obv_slope": np.polyfit(range(5), ta.obv(df["close"], df["volume"]).iloc[-5:].values, 1)[0],
            "stoch":     ta.stoch(df["high"], df["low"], df["close"], k=5, d=3).iloc[-1].to_dict(),

            # New: RVOL — relative volume vs 20-period mean
            "rvol":      df["volume"].iloc[-1] / vol_mean_20 if vol_mean_20 > 0 else 1.0,

            # New: Z-Score — distance from 20-SMA in standard deviations
            "z_score":   (df["close"].iloc[-1] - sma_20) / std_20 if std_20 > 0 else 0.0,

            # New: EMA ribbon — 9/21 crossover for micro-trend confirmation
            "ema_9":     ta.ema(df["close"], length=9).iloc[-1],
            "ema_21":    ta.ema(df["close"], length=21).iloc[-1],

            # New: RSI(7) — faster momentum for 5m scalping
            "rsi_7":     ta.rsi(df["close"], length=7).iloc[-1],
        }
```

On every candle-close event, the buffer appends the new candle and the TA engine recomputes all indicators from the in-memory array. Sub-millisecond. No external API, no third-party dependency, no latency, no cost.

The indicator dict is passed directly to `predict()` and is available to `compute_order()` for execution-time decisions (e.g., Stochastic entry timing if that's enabled later).

**What this replaces:**

| Before | After |
|--------|-------|
| RSI from external API or shadow log | `ta.rsi()` on candle buffer |
| OBV slope from separate calculation | `ta.obv()` + `np.polyfit()` on buffer |
| VWAP from external source | `ta.vwap()` on buffer |
| Stochastic not available at execution time | `ta.stoch()` ready for Phase 2 timing if needed |
| Bollinger Bands not used | Available for future signal work |

**Indicator availability by timeframe:**

All timeframes are native websocket subscriptions — no derived/aggregated candles. Each pipeline gets data from the exchange it trades on.

| Pipeline | Exchange WS | Subscriptions | Indicators Available |
|----------|------------|---------------|---------------------|
| BTC 5m (Polymarket) | Bybit | 1m, 5m, 15m | All (RSI, BB, VWAP, OBV, EMA, Stoch, Z-Score, RVOL) |
| ETH 5m (Polymarket) | Bybit | 1m, 5m | All |
| Bybit BTC Perps | Bybit | 1m, 5m | All |
| Kalshi BTC | Bybit | 1m, 5m | All |

> **Design note (exchange choice):** An earlier version of this spec used Binance for spot candle feeds. The deployed engine uses Bybit (validated at 241ms RTT, free tier). Since all pipelines already connect to Bybit for the perps pipeline, consolidating candle feeds on a single Bybit connection reduces connections from 3 to 2 (Bybit + Polymarket) and eliminates cross-exchange basis risk for the perps pipeline.

> **Settlement reference:** Polymarket settles crypto price markets against **Chainlink Data Streams** — a decentralized oracle that aggregates price data from multiple exchanges via consensus median pricing. Neither Binance nor Bybit is the direct reference; basis risk is symmetric regardless of candle source. Chainlink's median typically tracks within <10bps of both exchanges at 5m resolution, with divergence possible during flash crashes or exchange-specific outages.

Each subscription is a stream filter on an already-open socket — not a new connection. The WSManager opens one connection to Bybit (all candle data) and one to Polymarket (live orderbook).

> **Design note:** An earlier version of this spec derived 15m candles from the 5m buffer. This was changed because (a) the exchange already computes authoritative 15m candles, (b) derivation introduces aggregation bugs and correlated failure modes, and (c) subscribing to a native 15m stream costs zero additional connections. The same principle applies to all timeframes — always prefer native exchange data over self-aggregated data.

> **Bias audit (TODO):** The existing codebase may contain 15m logic that derives from or depends on 5m candle data rather than treating 15m as an independent timeframe. This must be audited before Phase 3 cutover. Any code that aggregates 5m candles into 15m windows should be refactored to consume native 15m candle-close events from the buffer.

### Signal Logic Improvements (Integrated with TA Engine)

The following changes upgrade the prediction logic from naive streak counting to a weighted confluence model. All indicators are computed locally by the TA Engine — no new data sources required.

**A. RVOL-Weighted Momentum**

Replace the binary +1/-1 candle count with volume-weighted scoring:

```python
# Current (naive): each green candle = +1
streak_score = sum(1 for c in last_5_candles if c.close > c.open)

# New (weighted): high-volume candles count more
def weighted_momentum(candles, indicators):
    score = 0
    for c, ind in zip(candles, indicators):
        direction = 1 if c.close > c.open else -1
        weight = 1.5 if ind["rvol"] > 1.5 else 1.0
        score += direction * weight
    return score
```

A green candle on 1.5x average volume scores +1.5 instead of +1. Low-volume candles (noise) stay at +1. The conviction threshold (`>= 3`) remains the same, but now it takes fewer high-volume candles to trigger — or more low-volume candles, which is the correct behavior.

**B. Z-Score Inhibition (Mean Reversion Guard)**

Suppress entries when price is statistically overextended:

```python
def should_inhibit(direction, z_score):
    if direction == "UP" and z_score > 2.0:
        return True   # price already overextended upward
    if direction == "DOWN" and z_score < -2.0:
        return True   # price already overextended downward
    return False
```

This is the mean-reversion filter that's been difficult to integrate. It doesn't generate trades — it prevents bad ones. Placed after the momentum check but before order submission.

**C. EMA Ribbon Trend Confirmation**

Require the 9/21 EMA relationship to agree with the trade direction:

```python
def ema_confirms(direction, ema_9, ema_21):
    if direction == "UP":
        return ema_9 > ema_21   # short-term trend is up
    if direction == "DOWN":
        return ema_9 < ema_21   # short-term trend is down
    return False
```

This filters out signals where short-term price action contradicts the broader micro-trend.

**D. Revised Pipeline Flow**

```
candle close
  → TA Engine computes indicators (sub-ms)
  → weighted_momentum() replaces naive streak count
  → if score >= 3.0:
      → Z-Score inhibition check (suppress if overextended)
      → EMA ribbon confirmation (suppress if trend disagrees)
      → existing filters (regime, price gate, ride streak, etc.)
      → compute_order() with live WS orderbook mid
      → submit_order()
```

**E. Shadow Mode First**

All three signal changes (RVOL weighting, Z-Score inhibition, EMA confirmation) run in shadow mode initially — log what they would have done alongside the existing logic. Promote to production after 100+ bets of counterfactual data shows improvement.

| Shadow Metric | Compare Against |
|---------------|----------------|
| Weighted momentum score | Naive streak count |
| Z-Score inhibited trades | Did they actually lose? |
| EMA-filtered trades | Did they actually lose? |

---

**4. Event Router** — maps candle-close events to pipeline runs:

```python
ROUTING = {
    ("bybit", "BTCUSDT", "5m"):   ["btc_5m", "bybit_btc_perps", "kalshi_btc"],
    ("bybit", "BTCUSDT", "15m"):  ["btc_15m"],      # native 15m, not derived
    ("bybit", "ETHUSDT", "5m"):   ["eth_5m"],
}

async def on_candle_close(exchange, symbol, timeframe, candle):
    # Buffer receives ALL candle events (1m, 5m, 15m)
    buffer.append(symbol, timeframe, candle)
    ta_indicators = ta_engine.compute(symbol, timeframe)

    # Only dispatch pipelines on their specific timeframe triggers
    pipelines = ROUTING.get((exchange, symbol, timeframe), [])
    for pipeline in pipelines:
        await dispatch(pipeline, candle, ta_indicators)
```

Note: 1m candle events update the buffer and TA engine (for Stochastic, fast RSI) but don't trigger any pipeline dispatch. They're data inputs, not execution triggers.

**5. Live Price Feed** — `compute_order()` reads from the Polymarket websocket orderbook instead of a DB snapshot:

```python
# Before (stale):
market_price_yes = market_row["price"]  # from DB, unknown age

# After (live):
market_price_yes = orderbook.get_mid(market_id)  # from WS, sub-second
best_ask = orderbook.get_best_ask(market_id)      # for spread calc
```

This eliminates Tension 2 entirely. The snapshot age becomes ~0ms by construction.

**6. Resilience Layer:**

| Failure | Response |
|---------|----------|
| WS disconnect | Auto-reconnect with exponential backoff (1s → 30s max) |
| 3 consecutive reconnect failures | Alert via webhook (Telegram/Discord/email) |
| No candle event for 10 min | Fallback: run all pipelines once, log warning |
| Python process crash | systemd auto-restart with `Restart=always`, `RestartSec=5` |
| VPS reboot | systemd `enable` ensures process starts on boot |

**7. Git Commit** — unchanged. After each pipeline run, commit and push as before. The git history remains the audit trail.

### What Gets Deleted

| Gone | Replacement |
|------|-------------|
| `vps-loop.sh` | `botsy_engine.py` |
| `sleep 300` | Websocket candle-close events |
| All GitHub Actions workflows (Bybit, Kalshi) | VPS-native execution |
| `repository_dispatch` + cron fallback | Not needed |
| Stale DB price snapshot in `compute_order()` | Live WS orderbook mid |

### What Stays the Same

- `src/predict.py` — prediction logic unchanged, but now receives an `indicators` dict from the TA engine instead of computing or fetching its own
- `src/trade.py` — order logic unchanged (except price source from WS orderbook)
- `src/daily_report.py` — triggered by cron inside the engine instead of vps-loop
- Git commit/push pattern — identical
- All API keys — already on VPS from Phase 1

### Dependencies

| Library | Purpose |
|---------|---------|
| `websockets` or `aiohttp` | WS connections |
| `asyncio` | Event loop |
| `pandas-ta` | Local indicator computation (RSI, BB, VWAP, OBV, Stochastic) |
| `numpy` + `pandas` | Buffer math (likely already installed) |
| `systemd` unit file | Process management |

No new infrastructure. Same VPS, same Python environment. `pandas-ta` is a pure Python library with no C compilation step — `pip install pandas-ta`.

### Latency Gains

| Metric | Before (sleep loop) | After (websocket) |
|--------|--------------------|--------------------|
| Signal-to-prediction latency | 0-300s (random within sleep window) | < 1s (fires on candle close) |
| Price snapshot age | Unknown (measured in Phase 2) | ~0ms (live WS feed) |
| Indicator computation | External API call or shadow log parse | < 1ms (pandas-ta on in-memory buffer) |
| Indicator staleness | Varies by source | 0 (recomputed on each candle close) |
| Bybit cycle overhead | 2-3 min cold start | 0 (persistent process) |
| Missed cycles on failure | Up to 30 min (GH Actions cron) | 10 min max (fallback timer) |
| Third-party indicator dependency | Yes (external API, rate limits, downtime) | None (self-contained) |

---

## Validation Plan (Phase 3)

### Shadow Mode (Days 7-8)

Run `botsy_engine.py` alongside `vps-loop.sh` for 24 hours. Both produce predictions; only the loop's predictions are live. Compare:

- Prediction timestamps: engine should fire within 1-2s of candle close; loop fires 0-300s later
- Prediction count: engine should produce >= loop count (no missed cycles)
- Price freshness: log snapshot age from both paths

### Cutover (Day 9)

Stop `vps-loop.sh`. Engine takes over. Monitor for 24 hours.

### Success Criteria

| Metric | Target |
|--------|--------|
| All pipelines firing within 2s of candle close | 100% of cycles |
| Zero missed cycles in 24 hours | 0 |
| WS reconnects without manual intervention | Tested by killing connection |
| Process survives VPS reboot | Tested with `sudo reboot` |
| Snapshot age in `compute_order()` | < 100ms p95 |

### Revert

Restart `vps-loop.sh`. It's still on disk, still works, picks up immediately. The engine is a drop-in replacement, not a migration that burns bridges.

---

## After Phase 3: Execution & Sizing Upgrades

With websockets live, the stale-snapshot problem is gone. Four upgrades become available, each gated by Phase 2 diagnostic data or Phase 3 infrastructure.

### A. Fill Fix — Dynamic Slippage or Simple Limit

Deploy the fill strategy using whichever approach Phase 2's data selected:

- If conviction correlates with drift → microstructure-only formula
- If no correlation → microstructure base with conviction ceiling
- Cancel-replace cycle → add if RTT data supports it
- Alternatively: `price_limit = min(estimate, 0.95)` if the data shows the simpler approach is sufficient

This is a config + formula change on top of the now-solid execution foundation.

### B. Maker Logic (Gated by Phase 2 RTT data)

Flip from taker (crossing the spread, paying ~1.12% fee) to maker (posting inside the spread, earning ~1.12% rebate). On 41 bets/day at $25, the taker-to-maker swing is ~$23/day in fee alpha.

```python
# Maker: post at best bid + 1 tick, let the market come to you
price_limit = best_bid + min_tick_size

# Escalation: if not filled in 30-45s, move up one tick
# After 2-3 cycles: cross the spread (fallback to taker) or walk away
```

**Prerequisite:** Phase 2 RTT data must show p95 < 500ms for cancel-replace to be viable. If RTT > 1s, maker-with-escalation is impractical — stay taker with dynamic slippage.

**Interaction with fill fix:** Maker logic and the dynamic slippage formula are alternative approaches to the same problem. Maker logic avoids the spread entirely; dynamic slippage pays through it more aggressively. They can be combined (start as maker, escalate to aggressive taker) or run as an A/B test.

### C. EV Calculation Per Trade

The current pipeline does not compute explicit expected value at trade time. Adding this:

```python
# At signal time, compute EV before submitting
p_win = estimate  # model's predicted probability
profit = (1 - price) / price  # binary market payout ratio
EV = (p_win * profit) - ((1 - p_win) * 1)  # stake = 1 unit

if EV <= 0:
    skip("negative EV")
```

This gates every trade on positive expected value, not just conviction thresholds. Requires the model's `estimate` to be a calibrated probability (not just a directional signal).

### D. Kelly Criterion Bet Sizing

Replace flat $25 with mathematically optimal sizing:

```python
# Kelly fraction: optimal bet size as % of bankroll
b = (1 - price) / price   # payout odds
p = estimate               # win probability
q = 1 - p                  # loss probability
f = (p * b - q) / b        # Kelly fraction

# Half-Kelly for safety (standard practice)
bet_size = bankroll * f * 0.5
bet_size = max(min(bet_size, MAX_BET), MIN_BET)  # clamp
```

**Prerequisite:** EV calculation (step C) must be live first. Kelly sizing on uncalibrated probabilities is worse than flat sizing.

**Expected impact:** Conv=5 signals with high WR get larger bets; conv=3 signals near breakeven get smaller bets. Capital efficiency increases without changing total risk exposure.

---

## Timeline

| Day | Phase | Work | Status |
|-----|-------|------|--------|
| 1 | 1 | Add Bybit + Kalshi to `vps-loop.sh`, move keys, disable GH Actions | **DONE** (`e2d07f13`) |
| 2 | 1+2 | Validate 24h of VPS-only execution. Deploy diagnostic log lines. | **DONE** (`57b0f9ea`) |
| 3 | 2 | Collect diagnostic data. Run analysis. Populate decision table. | **IN PROGRESS** |
| 4-6 | 3 | Build `botsy_engine.py`: WS manager, event router, TA engine, live orderbook | Pending |
| 7-8 | 3 | Shadow mode: engine runs alongside loop | Pending |
| 9 | 3 | Cutover: stop loop, engine takes over | Pending |
| 10 | Post | Deploy fill fix (A), evaluate maker logic (B) based on Phase 2 RTT | Pending |
| 11+ | Post | EV calculation (C), then Kelly sizing (D) — sequential, shadow first | Pending |
