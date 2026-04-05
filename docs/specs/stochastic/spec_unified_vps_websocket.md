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

## Phase 1: Consolidate (Days 1-2)

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

## Phase 2: Instrument (Days 2-3, overlaps with Phase 1)

Deploy the fill diagnostics from `spec_fill_diagnostic.md` to collect the data that resolves Tension 1 and Tension 2. This runs in parallel with Phase 1 — four log lines, zero execution changes.

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
┌─────────────────────────────────────────────────┐
│  botsy_engine.py (single async process)         │
│                                                 │
│  ┌─────────────┐   ┌─────────────┐              │
│  │ WS: Binance │   │ WS: Bybit   │  ← candle   │
│  │ BTC + ETH   │   │ BTC Perps   │    close     │
│  │ 1m + 5m     │   │ 5m          │    events    │
│  └──────┬──────┘   └──────┬──────┘              │
│         │                 │                     │
│         ▼                 ▼                     │
│  ┌──────────────────────────────┐               │
│  │  Event Router                │               │
│  │  on_candle_close(symbol, tf) │               │
│  └──────┬───────────────────────┘               │
│         │                                       │
│         ▼                                       │
│  ┌──────────────────────────────┐               │
│  │  Pipeline Dispatcher         │               │
│  │  5m close → BTC 5m, ETH 5m  │               │
│  │  15m close → BTC 15m        │               │
│  │  5m close → Bybit perps     │               │
│  └──────┬───────────────────────┘               │
│         │                                       │
│         ▼                                       │
│  ┌──────────────────────────────┐               │
│  │  predict() → compute_order() │               │
│  │  live mid from WS orderbook  │  ← no stale  │
│  │  submit_order()              │    snapshot   │
│  └──────────────────────────────┘               │
│                                                 │
│  ┌──────────────┐                               │
│  │ WS: Polymarket│  ← live orderbook for        │
│  │ orderbook     │    compute_order() mid price  │
│  └──────────────┘                               │
│                                                 │
│  ┌──────────────┐                               │
│  │ Daily report  │  ← cron trigger at 12:00 UTC │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
```

### Core Components

**1. Websocket Manager** — maintains persistent connections with auto-reconnect:

```python
class WSManager:
    async def connect(self, exchange, symbols, timeframes):
        # Binance: wss://stream.binance.com/ws
        # Bybit: wss://stream.bybit.com/v5/public/linear
        # Polymarket: wss://ws-subscriptions-clob.polymarket.com/ws/market
        ...

    async def on_disconnect(self, exchange):
        # Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        # Alert after 3 consecutive failures
        ...
```

**2. Event Router** — maps candle-close events to pipeline runs:

```python
ROUTING = {
    ("binance", "BTCUSDT", "5m"):  ["btc_5m", "btc_15m_check"],
    ("binance", "ETHUSDT", "5m"):  ["eth_5m"],
    ("bybit",   "BTCUSDT", "5m"):  ["bybit_btc_perps"],
}

async def on_candle_close(exchange, symbol, timeframe, candle):
    pipelines = ROUTING.get((exchange, symbol, timeframe), [])
    for pipeline in pipelines:
        await dispatch(pipeline, candle)
```

**3. Live Price Feed** — `compute_order()` reads from the Polymarket websocket orderbook instead of a DB snapshot:

```python
# Before (stale):
market_price_yes = market_row["price"]  # from DB, unknown age

# After (live):
market_price_yes = orderbook.get_mid(market_id)  # from WS, sub-second
best_ask = orderbook.get_best_ask(market_id)      # for spread calc
```

This eliminates Tension 2 entirely. The snapshot age becomes ~0ms by construction.

**4. Resilience Layer:**

| Failure | Response |
|---------|----------|
| WS disconnect | Auto-reconnect with exponential backoff (1s → 30s max) |
| 3 consecutive reconnect failures | Alert via webhook (Telegram/Discord/email) |
| No candle event for 10 min | Fallback: run all pipelines once, log warning |
| Python process crash | systemd auto-restart with `Restart=always`, `RestartSec=5` |
| VPS reboot | systemd `enable` ensures process starts on boot |

**5. Git Commit** — unchanged. After each pipeline run, commit and push as before. The git history remains the audit trail.

### What Gets Deleted

| Gone | Replacement |
|------|-------------|
| `vps-loop.sh` | `botsy_engine.py` |
| `sleep 300` | Websocket candle-close events |
| All GitHub Actions workflows (Bybit, Kalshi) | VPS-native execution |
| `repository_dispatch` + cron fallback | Not needed |
| Stale DB price snapshot in `compute_order()` | Live WS orderbook mid |

### What Stays the Same

- `src/predict.py` — prediction logic unchanged
- `src/trade.py` — order logic unchanged (except price source)
- `src/daily_report.py` — triggered by cron inside the engine instead of vps-loop
- Git commit/push pattern — identical
- All API keys — already on VPS from Phase 1

### Dependencies

| Library | Purpose |
|---------|---------|
| `websockets` or `aiohttp` | WS connections |
| `asyncio` | Event loop |
| `systemd` unit file | Process management |

No new infrastructure. Same VPS, same Python environment.

### Latency Gains

| Metric | Before (sleep loop) | After (websocket) |
|--------|--------------------|--------------------|
| Signal-to-prediction latency | 0-300s (random within sleep window) | < 1s (fires on candle close) |
| Price snapshot age | Unknown (measured in Phase 2) | ~0ms (live WS feed) |
| Bybit cycle overhead | 2-3 min cold start | 0 (persistent process) |
| Missed cycles on failure | Up to 30 min (GH Actions cron) | 10 min max (fallback timer) |

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

## After Phase 3: Deploy the Fill Fix

With websockets live, the stale-snapshot problem is gone. Now deploy the dynamic slippage formula using whichever approach Phase 2's data selected:

- If conviction correlates with drift → microstructure-only formula
- If no correlation → microstructure base with conviction ceiling
- Cancel-replace cycle → add if RTT data supports it

This is a separate spec (`spec_dynamic_price_cap.md` or a revised version based on diagnostic results). It's a config + formula change on top of a now-solid execution foundation.

---

## Timeline

| Day | Phase | Work | Risk |
|-----|-------|------|------|
| 1 | 1 | Add Bybit + Kalshi to `vps-loop.sh`, move keys, disable GH Actions | Low |
| 2 | 1+2 | Validate 24h of VPS-only execution. Deploy diagnostic log lines. | Low |
| 3 | 2 | Collect diagnostic data. Run analysis. Populate decision table. | Zero |
| 4-6 | 3 | Build `botsy_engine.py`: WS manager, event router, live orderbook | Medium |
| 7-8 | 3 | Shadow mode: engine runs alongside loop | Low |
| 9 | 3 | Cutover: stop loop, engine takes over | Medium |
| 10 | 3 | 24h validation. Deploy dynamic slippage formula. | Low |
