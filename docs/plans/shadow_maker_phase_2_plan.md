# Shadow Maker Phase 2 — Implementation Plan

**Date:** 2026-04-21
**Status:** Design ready (no code yet)
**References:** `docs/specs/spec_maker_mode.md` (Phase 2 section 5)

## Why now (and why maybe not)

Phase 1 data (2026-04-18 to 2026-04-21) shows:
- BTC 5m shadow maker EHR: **+0.023** on 19 filled
- BTC 5m live taker EHR: **−0.149 lifetime, −0.082 7d** on 71 bets
- ETH 5m shadow maker EHR: **−0.099** on 36 filled
- **Gap on BTC (shadow > taker): 17¢/$** — structural case for maker mode

Today's FAK pilot confirmed that execution improvement alone cannot rescue a negative-EHR signal. **Phase 2 only makes sense if the underlying signal recovers to EHR ≥ 0.** This is now a precondition enforced by the signal-EHR live gate (shipped 2026-04-21).

**Ship Phase 2 when:**
1. BTC 5m 7d signal EHR recovers to ≥ 0 on 50+ bets (gate allows live)
2. Shadow maker has ≥ 200 resolved fills showing shadow_ehr > taker_ehr with statistical confidence
3. All Phase 2 code is behind a `maker_mode: true` pipeline config flag (so shipping ≠ activating)

**Do NOT ship Phase 2 while:**
- Signal EHR is negative (gate already blocks this)
- Shadow maker fill rate < 30% (maker orders would rarely fill, same as Phase 1's safety gate)
- Shadow EHR is near zero (no signal to capture)

Estimated implementation: **2-3 days of focused work** once activation conditions are met.

---

## The shape of Phase 2

Phase 2 is NOT a replacement for the taker path. Both live side-by-side:

```
prediction (conv≥4 + edge qualifies)
      │
      ├─► MAKER PATH (new)                   ─► GTD limit at best_bid + 0.01
      │     if signal healthy AND spread ≥ 2¢      90s lifetime, no escalation
      │
      └─► TAKER PATH (existing, FAK)         ─► IOC at mid + cushion
            if edge clears FAK min + cushion       immediate, partial OK
```

Which path fires depends on `maker_mode_enabled` pipeline flag and runtime conditions. A prediction can route to EITHER maker OR taker, never both.

---

## File-level implementation

### New files (3)

| File | Purpose |
|------|---------|
| `src/maker_execution.py` | Phase 2 order submission, lifetime management, rebate tracking |
| `src/maker_fills_tracker.py` | Schema + helpers for the `maker_orders` table (posted, canceled, filled, expired states) |
| `tests/test_maker_execution.py` | Contract tests covering all AC-LM-1 through AC-LM-11 |

### Modified files (4)

| File | Change |
|------|--------|
| `src/trade.py::execute_trades` | After `should_trade()` passes, branch: maker vs taker based on pipeline config flag + conditions |
| `src/trade.py::compute_order` | Factor out "taker path" so maker path can reuse edge/cushion helpers |
| `config/pipelines.json` | Add `maker_mode: bool` field per-pipeline (default `false`) |
| `src/daily_report.py` | Add `analyze_maker(db, date_str)` section rendering AC-LM-10 metrics |
| `src/consolidated_report.py` | Add maker subsection under the Shadow Maker row when any pipeline has `maker_mode: true` |

### No changes needed

- `src/system_state.py` — the signal-EHR gate already protects maker live (it's a pipeline-level live-mode check, agnostic to execution strategy)
- `src/predict.py` / `src/predict_eth.py` — prediction path is unchanged; maker vs taker is an execution-layer concern
- `src/shadow_maker.py` — keeps running in parallel even when Phase 2 is live; becomes the "what if we stayed passive" counterfactual

---

## Database schema: `maker_orders`

```sql
CREATE TABLE IF NOT EXISTS maker_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER,
    market_id TEXT NOT NULL,
    pipeline TEXT NOT NULL,
    cycle INTEGER,
    posted_at TEXT NOT NULL,

    -- Order
    direction TEXT,           -- UP | DOWN
    side TEXT,                -- BUY | SELL (buy YES or buy NO)
    size REAL,
    maker_price REAL,         -- our limit price
    best_bid_at_post REAL,
    best_ask_at_post REAL,
    spread_at_post REAL,
    edge_at_post REAL,

    -- Lifecycle
    status TEXT,              -- posted | canceled | filled_partial | filled | expired
    canceled_at TEXT,
    filled_at TEXT,
    filled_size REAL,
    filled_avg_price REAL,
    fill_latency_ms INTEGER,

    -- Resolution (post-market)
    outcome INTEGER,          -- 1 YES, 0 NO
    resolved_at TEXT,
    pnl REAL,                 -- includes maker rebate
    rebate_earned REAL,
    adverse INTEGER,          -- 1 if fill moved underwater within 30s

    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    FOREIGN KEY (market_id) REFERENCES markets(id)
);
```

One row per posted maker order. `status` transitions: `posted` → (`canceled` | `filled_partial` | `filled` | `expired`). Resolution fields populated post-market.

---

## Execution logic (pseudocode)

### In `src/maker_execution.py`

```python
def execute_maker(db, prediction, market_row, cycle, pipeline_name):
    """AC-LM-1/2/3: entry criteria + price selection + edge floor."""

    if prediction["conviction_score"] < 4:
        return None  # maker path only fires at conv>=4

    direction = "UP" if prediction["estimate"] >= 0.5 else "DOWN"
    best_bid = market_row.get("_yes_best_bid")
    best_ask = market_row.get("_yes_best_ask")
    spread = market_row.get("_yes_spread")

    if spread is None or spread < 0.02:
        _log_skip(db, prediction, "spread_too_thin")
        return None

    TICK = 0.01
    if direction == "UP":
        maker_price = best_bid + TICK
        maker_edge = prediction["estimate"] - maker_price
    else:
        # For DOWN, we post on NO side
        maker_price = 1 - (best_ask - TICK)  # i.e., NO bid one tick inside
        maker_edge = (1 - prediction["estimate"]) - maker_price

    MIN_EDGE = 0.03  # from config
    if maker_edge < MIN_EDGE + TICK:
        _log_skip(db, prediction, "edge_below_maker_floor")
        return None

    # Submit as GTD with 90-second lifetime
    order_id = _post_maker_gtd(
        market_id=market_row["id"],
        direction=direction,
        price=maker_price,
        size=25 if prediction["conviction_score"] == 4 else 50,
        lifetime_seconds=90,
    )

    _record_maker_order(db, prediction, market_row, maker_price, order_id, cycle)
    return order_id


def tick_maker_lifetime(db):
    """Called every cycle. Cancels or re-prices expired/stale maker orders.

    AC-LM-5: max 90s lifetime, recompute on each cycle,
    AC-LM-6: NEVER escalate to taker.
    """
    for row in db.execute(
        "SELECT * FROM maker_orders WHERE status = 'posted'"
    ):
        age_s = _now_seconds() - _parse_ts(row["posted_at"])
        if age_s >= 90:
            _cancel_order(row["order_id"])
            db.execute(
                "UPDATE maker_orders SET status='expired', "
                "canceled_at=? WHERE id=?",
                (_now(), row["id"]),
            )
        # Also cancel if market has resolved
        market = db.execute(
            "SELECT resolved FROM markets WHERE id=?", (row["market_id"],)
        ).fetchone()
        if market and market[0] == 1:
            _cancel_order(row["order_id"])
            db.execute(
                "UPDATE maker_orders SET status='canceled', "
                "canceled_at=? WHERE id=?",
                (_now(), row["id"]),
            )
```

### Integration in `src/trade.py::execute_trades`

```python
# Inside the for pred in predictions loop:
pipe_cfg = load_pipeline_config(pipeline_name)
use_maker = pipe_cfg.get("maker_mode", False) and should_trade_ok

if use_maker:
    maker_order_id = execute_maker(
        db, pred, market_row, cycle, pipeline_name
    )
    if maker_order_id:
        continue  # maker path took it; skip taker path

# Existing taker path (unchanged)
order_params, order_reason = compute_order(pred, market_row, liquidity)
...
```

---

## Kill switches & guardrails

Phase 2 adds three new protections on top of the existing taker rails:

1. **Per-pipeline toggle** — `config/pipelines.json::maker_mode: false` default; must be explicitly set to true. Revert = flip to false.
2. **Dedicated kill switch file** — `data/KILL_SWITCH_MAKER` halts only the maker path. Taker unaffected.
3. **Rolling maker-EHR gate** (AC-LM-11) — compute 20-fill rolling maker EHR every cycle; if < −0.03, auto-disable maker for the day.

Existing rails apply to the combined live path:
- $300 daily loss cap (counts maker + taker pnl)
- 5 consecutive loss breaker (counts all live orders)
- Signal-EHR live gate (blocks all live if 7d EHR < 0)

---

## Testing strategy

### Unit tests (`tests/test_maker_execution.py`)

Covers every AC in spec section 5:

1. **AC-LM-1 entry criteria**: conv<4 skips, edge below floor skips, spread<2¢ skips, pipeline paper skips
2. **AC-LM-2 price selection**: BUY posts at `best_bid + 0.01`, SELL at `best_ask - 0.01`
3. **AC-LM-3 edge floor**: rejects if maker_edge < min_edge + 0.01
4. **AC-LM-4 order type**: GTD with correct expiration timestamp
5. **AC-LM-5 lifetime**: cancel + re-price after 90s, cancel if market resolves
6. **AC-LM-6 no escalation**: failed maker order does NOT call execute_taker
7. **AC-LM-7 sizing**: conv=4 → $25, conv=5 → $50, conv=3 → skip
8. **AC-LM-8 daily cap**: 7th maker order refused after $150 exposure
9. **AC-LM-9 rebate math**: correct formula applied, logged in P&L
10. **AC-LM-10 metrics present**: daily_report.analyze_maker() returns all 7 fields
11. **AC-LM-11 kill switch**: 20-fill rolling EHR < −0.03 disables maker for day

### Integration tests

- Full execute_trades() cycle with maker_mode=true and mocked book
- Verify `orders` table unchanged; `maker_orders` populated
- Daily report renders maker section
- Consolidated report aggregates maker across pipelines

---

## Rollout plan

**Stage A — Ship behind flag (default off)**
- All code lands; `maker_mode: false` in pipelines.json for every pipeline
- Zero production impact
- Verified: tests pass, daily report renders empty maker section

**Stage B — Single-pipeline pilot**
- Flip `maker_mode: true` on btc_5m only (assuming signal EHR has recovered)
- Run alongside FAK taker for the same signals
- Monitor: fill latency, fill rate, maker_ehr, adverse_pct
- Duration: 48-72 hours, min 30 maker orders

**Stage C — Expand or revert**
- If Stage B maker_ehr > shadow_ehr > taker_ehr: expand to eth_5m (if ETH signal EHR also recovers)
- If Stage B maker_ehr < 0 on 30+ fills: revert, close the Phase 2 experiment, update optimizations.json

**Stage D — Deprecate Phase 1 shadow maker**
- Once Phase 2 is validated and stable, the Phase 1 shadow maker becomes redundant — real maker data replaces hypothetical
- Wind-down: stop logging shadow rows but retain the table for historical analysis

---

## What this plan does NOT cover

- **Two-sided market making** (posting on both YES and NO simultaneously): out of scope. The spec (AC-LM section 5) is explicit: single-sided informed liquidity only.
- **Maker on perps** (Bybit/Hyperliquid): spec currently targets Polymarket CLOB. Perp-venue maker is a separate design.
- **Cross-venue routing** (best venue per signal): deferred until maker mode stabilizes on a single venue.
- **Queue priority metrics**: we post at `best_bid + 0.01` (one-tick inside), giving queue priority. We don't explicitly track our queue position — that would require venue-specific instrumentation.

---

## Open design questions (resolve before Stage A)

1. **Rebate calculation source.** Polymarket CLOB may report rebates explicitly via API, or we may need to compute them client-side using Akey's formula. Worth a 30-min API test before committing.
2. **Order modification vs cancel-and-repost.** Polymarket CLOB supports both. Modification is cheaper (no queue reset) but requires an additional API call path. Choose one before implementation.
3. **GTD expiry granularity.** Polymarket market resolution is at a specific UTC timestamp; GTD expiration must be 120s before that (AC-LM-4). Verify the API accepts second-precision GTD.
4. **Partial fill continuation.** If we get 50% filled then expire, do we post the remaining 50% in the next cycle, or drop it? Spec doesn't say. Recommendation: drop — don't chase.

---

## Checklist for activation

Before shipping Phase 2 to production:

- [ ] BTC 5m 7d signal EHR ≥ 0 on 50+ bets (checked via `system_state.signal_ehr_7d`)
- [ ] Shadow maker has ≥ 200 resolved fills with shadow_ehr > taker_ehr (from daily reports)
- [ ] All open design questions (§above) resolved
- [ ] 12+ new unit tests passing (one per AC)
- [ ] Integration tests pass with mocked Polymarket CLOB responses
- [ ] Daily report and consolidated report render maker section correctly
- [ ] `data/KILL_SWITCH_MAKER` tested in staging — flipping it halts maker within 1 cycle
- [ ] `maker_mode` flag defaults to `false` for all pipelines in committed `pipelines.json`

Once all checked, Phase 2 is activatable by flipping a single pipeline's `maker_mode: true`.

## Summary

Phase 2 is a bounded, behind-a-flag feature ready to ship when the underlying signal is healthy. Design reuses: signal-EHR gate (today), shadow_maker resolve patterns (Apr 16), fill_diagnostic schema (Apr 11), `_store_prediction` and execute_trades orchestration. No infrastructure invention; pure execution-layer addition.

The expected answer from Phase 2: **does being the liquidity we come to (maker) actually outperform chasing liquidity (FAK taker) on the same signal?** Phase 1 shadow says "probably yes for BTC." Phase 2 says "let's verify with real orders when conditions allow."
