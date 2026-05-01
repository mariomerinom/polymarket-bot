# Multi-Poll Predict — Empirically Learn the In-Cycle Information Curve

**Date:** 2026-04-28
**Status:** Plan ready for approval
**Triggered by:** Signal-rehab investigation findings (`docs/analysis/signal_rehab_2026-04-28.md`). Commit `f79e56f21` (2026-04-05) retired GitHub Actions and moved dispatch from "GHA cron with ~2:30 of natural delay" to "VPS WS event with ~6s latency." Both BTC and ETH lab WR dropped from ~60% to ~50% the same week. The lost ~10pp of WR was the in-flight price information that had been accumulating during the GHA delay.

**Replaces (rejected) prior framing:** "Add a fixed 2:30 timer to recover the edge." That hard-codes an accidental number into the architecture. The principled question is *when* during a 5-minute cycle does the prediction signal have the most edge — that's a learnable empirical question, not a magic constant.

---

## Backward — what could break

- The current immediate-dispatch path is what feeds production conviction-gated bets, the arb_divergence logger, daily reports, and the shadow framework. **None of those change in this plan.** Multi-poll runs as pure shadow alongside.
- New high-frequency writes to a new table. Disk and DB-locking risk: small (rows are small, WAL handles concurrency). Modeled below.
- 9 polls per cycle could create CPU spikes on a 1 GB droplet that recently crashlooped from disk-full. The poll function must be cheap (read WS-cached price + run `predict()`); no REST calls, no synchronous network.
- The capture retention bug last week was a perfect example of "unbounded writer + no rotation." Multi-poll table needs an explicit retention policy from day 1.

**Rollback:** if multi-poll causes any engine instability or anomaly, comment out the scheduling call in `botsy_engine.py::bybit_spot_feed` (single-line change). Engine restart via deploy hook. No data loss in main predictions table.

---

## Present — what changes

### Phase A — Instrument the cycle (work: ~2-3h, observation: 7-14 days)

Multi-poll runs **in parallel with** the existing immediate-dispatch. The immediate dispatch keeps doing what it does today — feeding predictions to live/paper, the shadow scorer, arb_divergence. Multi-poll fires *additional* predictions at offsets T+30s through T+270s after each candle close, into a separate table. Pure observation, zero behavior change for capital.

**New module:** `src/multi_poll_predict.py`

```python
POLL_OFFSETS_S = [30, 60, 90, 120, 150, 180, 210, 240, 270]

async def schedule_polls(engine, cycle_close_at, source, symbol, interval):
    """Fire predict() at each offset after the candle close, log to
    multi_poll_predictions. Each poll is a fresh predict call against
    the live WS-cached price at that moment.

    Polls run concurrently with normal pipeline dispatch. Failures
    in any single poll are logged + swallowed — must not break the
    hot path."""
```

Each poll:
1. Awaits `asyncio.sleep(offset_s - elapsed)` precisely
2. Reads current price from `candle_buffer` (no REST)
3. Calls `predict.run_predictions()` against the same active markets
4. Writes to `multi_poll_predictions` with `offset_seconds=offset_s`
5. Wraps everything in try/except; failures log warning, continue

**New table:** `multi_poll_predictions` in `data/predictions.db`

```sql
CREATE TABLE IF NOT EXISTS multi_poll_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle INTEGER,
    cycle_close_at TEXT NOT NULL,
    offset_seconds INTEGER NOT NULL,
    predicted_at TEXT NOT NULL,
    market_id TEXT NOT NULL,
    asset TEXT,
    estimate REAL,
    conviction_score INTEGER,
    regime TEXT,
    daily_regime_label TEXT,
    spot_at_poll REAL,
    in_flight_return_pct REAL,    -- (spot_at_poll - cycle_open_spot) / cycle_open_spot
    poll_succeeded INTEGER DEFAULT 1,
    -- Resolution back-fill (NULL until the underlying market resolves)
    market_resolved INTEGER,
    market_outcome INTEGER,
    won INTEGER,                   -- nullable; 1 if estimate side matched outcome
    FOREIGN KEY (market_id) REFERENCES markets(id)
);

CREATE INDEX IF NOT EXISTS idx_mpp_cycle ON multi_poll_predictions(cycle);
CREATE INDEX IF NOT EXISTS idx_mpp_offset ON multi_poll_predictions(offset_seconds);
CREATE INDEX IF NOT EXISTS idx_mpp_market ON multi_poll_predictions(market_id, predicted_at);
```

**Retention policy (built in from day 1):**
- 30-day rolling window. `_purge_old_polls()` runs at engine startup and once per day.
- Lessons from the 2026-04-24 disk-full incident applied: retention is in code, not in a never-wired cron.

**Resolution back-fill:**
- Reuse the existing `_auto_resolve()` mechanism that already runs against `predictions` — extend it to also resolve `multi_poll_predictions` rows where `market_resolved IS NULL`.

**Engine wiring** in `src/botsy_engine.py::bybit_spot_feed`:

```python
# After confirmed kline candle close — existing dispatch fires immediately
await self.dispatch("bybit_spot", symbol, interval, candle_ts)

# NEW: schedule the multi-poll shadow run as a non-awaiting background task
if interval in ("5", "15") and symbol in ("BTCUSDT", "ETHUSDT"):
    asyncio.create_task(
        multi_poll_predict.schedule_polls(
            self, candle_ts, "bybit_spot", symbol, interval
        )
    )
```

`asyncio.create_task` so the polls run independently — the WS feed loop continues processing other events while polls fire over the next 4.5 minutes.

**Pipeline scope (initial):**
- BTC 5m + ETH 5m only. These are where the strong-era edge existed and where we have ground truth from prior data.
- Perps and 15m can be added in Phase D if the BTC/ETH result is positive.

**Tests** (`tests/test_multi_poll_predict.py`):
- Schedule fires N polls at correct offsets
- Each poll writes a row with the right metadata
- Failure in one poll doesn't kill the others
- Retention purge deletes rows >30d old, idempotent
- Init table is idempotent

**Observation period:** 7-14 days minimum. Sample-size floor: ≥100 resolved polls per (offset × regime) cell on at least 4 cells. Earliest decision: 2026-05-05; realistic: 2026-05-10/12.

### Phase B — Analysis (work: ~2h, runs once at observation gate)

New tool: `tools/multi_poll_analysis.py` (sibling to `tools/signal_rehab_analysis.py`).

For each `(offset_seconds × regime × asset)` cell:
- Resolved N
- WR (using same formula as the rest of the codebase: `(estimate>0.5 AND outcome=1) OR (estimate<0.5 AND outcome=0)`)
- Confidence interval at 95%
- WR vs offset=0 baseline (immediate dispatch comparison)

Three possible findings:

| Finding | Action |
|---|---|
| **Single offset clearly best** across all regimes (e.g., T+150 wins by ≥3pp on N≥100) | Ship that offset as the new dispatch policy in Phase C |
| **Regime-adaptive optimum** (different offsets win in different regimes) | Ship a small policy table `OFFSET_BY_REGIME = {"MEDIUM_VOL/NEUTRAL": 150, "HIGH_VOL/TRENDING": 60, ...}` in Phase C |
| **No offset shows edge** above immediate-dispatch baseline | V4 chapter closes cleanly. Pivot to arb / longer-duration / Kalshi proceeds with confidence — the "we shot ourselves" hypothesis is ruled out by data |

Output: `docs/analysis/multi_poll_result_<date>.md` + HTML render.

### Phase C — Ship validated policy (work: ~1h, conditional on Phase B finding edge)

If Phase B identifies an exploitable offset (or per-regime offset table):

1. Modify `botsy_engine.py::dispatch` to use the validated offset
2. Register optimization in `docs/optimizations.json` with:
   - Pre-shipping baseline: current immediate-dispatch WR per regime
   - Pre-registered revert: if forward-WR drops below pre-shipping baseline by ≥3pp on 50+ bets, revert
3. Keep multi-poll instrumentation running (now as ongoing calibration, not experiment)
4. After 50 forward bets, validate against the pre-registered baseline

If Phase B finds no edge, no Phase C — `multi_poll_predict` stays as ongoing observation, optimization is registered as `reverted`.

---

## Future — where this surfaces

- **Daily report:** add a "multi-poll snapshot" section showing today's per-offset WR distribution (just the latest day)
- **Consolidated report:** roll up weekly per-(offset × regime) cells
- **Optimization registry:** Phase A registered as `multi_poll_predict_logger` with status `shadow`. Phase C (if reached) registered as `multi_poll_dispatch_<offset>` with status `active`
- **Documentation:** if Phase C ships, update `docs/core/strategy.md` to document the offset choice as an explicit design decision (not an accident this time)
- **Revisit trigger:** the multi-poll table itself becomes a permanent calibration substrate. If WR-per-offset drifts over time (regime change, market microstructure evolution), Phase B can be re-run to re-tune. Quarterly cadence reasonable.

---

## Critical files

**New:**
- `src/multi_poll_predict.py` — orchestrator + schema + retention
- `tools/multi_poll_analysis.py` — Phase B analysis (Phase A doesn't need it)
- `tests/test_multi_poll_predict.py` — TDD-first

**Modified:**
- `src/botsy_engine.py` — one `asyncio.create_task` call inside `bybit_spot_feed`'s 5m close branch
- `src/predict.py` — extract a callable that takes `(symbol, interval, price_now, candle_buffer)` and returns predictions, so multi-poll can call it directly without going through the full pipeline lifecycle. **Or** wrap the existing `run_predictions()` if it already accepts injected price data (it does per the search above).
- `docs/optimizations.json` — register `multi_poll_predict_logger` (shadow)
- *(Later, conditional)* `docs/optimizations.json` again, for the Phase C policy registration

**Reuse (no modification):**
- `src/predict.py::run_predictions()` already accepts `btc_data=` injection — multi-poll feeds the live WS-cached candle into this hook
- `src/candle_buffer.py::get_candles()` for cached price reads
- `src/auto_resolve.py` (or wherever resolution lives) — extend to cover the new table
- Shadow framework template from `docs/core/SHADOW_FRAMEWORK.md`

---

## Verification

**End of Phase A (after first 24h of observation):**
- `pytest tests/test_multi_poll_predict.py` → green
- `sqlite3 data/predictions.db "SELECT offset_seconds, COUNT(*) FROM multi_poll_predictions WHERE predicted_at > datetime('now','-1 day') GROUP BY offset_seconds ORDER BY offset_seconds"` → all 9 offsets producing rows, roughly equal counts per offset
- No errors in `logs/loop.log` mentioning `multi_poll`
- Disk usage stable (no runaway growth)

**End of Phase A (decision gate, ~2026-05-10):**
- Per-cell sample sizes: ≥100 resolved polls in ≥4 cells minimum
- Run `tools/multi_poll_analysis.py` → Phase B output

**End of Phase C (if shipped):**
- 50 forward bets at the new offset
- Forward WR ≥ baseline-WR − 3pp (revert criterion not tripped)

---

## Sequencing summary

```
Today:        Work Phase A  (~2-3h)        →  Ship (pure shadow, zero capital risk)
~7-14 days:   Observe Phase A — gated on N≥100 in ≥4 cells
                                            →  Run Phase B analysis

If edge:      Work Phase C  (~1h)          →  Ship (gated dispatch policy)
                                            →  50-bet forward validation gate
                                            →  promote or revert

If no edge:   No Phase C. Result registered. Pivot decision proceeds.
```

**Work total: ~3-5 hours of implementation across all three phases.**

**Calendar total: ~2-3 weeks** including the observation window and forward-validation period.

---

## Trade-offs explicitly acknowledged

- **Cost:** 9× the prediction writes per cycle. ~50-200 KB/day of new DB rows. Negligible at current scale.
- **Risk:** the polling task could leak coroutines if not properly bounded. Mitigation: each `schedule_polls` task runs for a known finite duration (270s) and explicitly returns. No long-lived state.
- **Cycle interaction:** polls from cycle N are still running when cycle N+1 fires (cycles overlap by ~30s). Means up to ~18 polls in flight simultaneously. No issue — each is an independent async task.
- **Information asymmetry concerns:** if T+270 turns out to be the optimal offset, that's "wait 4.5 minutes after candle close." A market mover during that window would exit our window. Acceptable — the bet sizes are small and the markets are 5m, so the universe of "things that resolve faster than we can act" is small.

## Out of scope

- Order-flow-based stopping rules (e.g., "fire when book imbalance exceeds X"). That's a Phase 2 design once we know whether time-based offset alone has edge.
- Per-market-class poll schedules. All markets in scope are 5m direction binaries.
- Live capital exposure increase. Phase A is shadow only. Phase C ships behind the existing signal-EHR gate, so even if we activate a new dispatch policy, the gate still must clear before live trades can fire.
