# Shadow Experiments — Framework

> Canonical reference for the shadow-logging pattern used throughout BOTSY.
> Read this before adding any new "what if we did X instead" experiment.

## 1. The pattern

Shadow logging is the system's dominant low-risk experimentation pattern. Instead of changing production behavior to test a hypothesis, you **log what the alternative WOULD have done** alongside the real decision. Accumulate N observations. Compare the shadow series against the live series. Promote, revert, or extend — based on data.

```
live path  ─► decision ─► outcome  ─┐
                                     ├─► compare at report/analysis time
shadow    ─► alt-decision ─► outcome ┘
```

### Why it works

- **Zero risk.** Shadows never change money flows. Promotion is a separate, explicit step with its own revert criteria.
- **Apples-to-apples.** Shadow and live fire on the same cycle against the same market state. Eliminates the "different days, different conditions" confound.
- **Cheap.** One try/except wrapper, a column or table, and a daily report section. Nothing heavier.
- **Data-driven promotion.** We learned the hard way that hunches and small samples lie (§6). Shadows force a quantified comparison before any behavior change.

---

## 2. When to use

### ✅ Good fits

- **Comparing two paths on the same signal** — passive maker vs aggressive taker (`shadow_maker`)
- **Measuring the counterfactual impact of a gate** — "what if we didn't gate HIGH_VOL?" (`shadow_regime_relative`)
- **Validating a new classifier/signal pre-promotion** — alt conviction scorer (`shadow_conviction_scorer`)
- **Collecting indicator data for post-hoc optimization** — RSI/OBV/VWAP snapshots (`shadow_indicators`)
- **Expanding a filter's coverage** — "if we relax rule X for Y observations, what WR do we get?" Shadow the Y first.

### ❌ Bad fits

- **Full replacement proposals** — "let's ship VWAP to replace momentum." Use Strategy Lab (always-fire) + graduation flow instead. Shadow is for observing an alternative that runs *alongside* the primary path.
- **Non-comparable metrics** — if the shadow and live metrics aren't directly compared at the end, the shadow is just noise. Decide the comparison function before implementing.
- **Hot-path-breaking logic** — shadows must not slow or block trading. If the observation requires a network call, it doesn't belong in the cycle path. Move it to daily-report time.

---

## 3. Storage decision

Three storage shapes cover every existing shadow. Pick one at design time.

### A. Dedicated table

**Use when:** the shadow needs post-market resolution (fills, outcomes, settlement) that aren't known at logging time.

**Example:** `shadow_maker.init_table()` creates a 17-column table including `fill_candle_low`, `fill_candle_high`, `adverse`, `outcome`, `resolved_at`. Rows logged at prediction time, updated after markets resolve.

**Template to copy:** `src/shadow_maker.py` — `init_table`, `record`, `resolve_shadow_fills_polymarket`, `shadow_stats`.

**Tradeoffs:** Clean SQL joins, indexable, supports post-market updates. Costs: schema migration if fields change.

### B. JSON blob in `predictions.reasoning`

**Use when:** observation is synchronous at cycle time — no market-resolution update needed.

**Example:** `shadow_regime_relative` computed from candles + asset_daily.db at prediction time, embedded as `reasoning_data["shadow_regime_relative"] = {...}`.

**Template to copy:** `src/ci_run_perp.py::_store_prediction` (lines ~644–655) — how to inject a shadow field into `reasoning` without affecting production behavior.

**Tradeoffs:** No schema change, zero migration. Cost: JSON extraction in SQL is slower than indexed columns; comparison queries must use `json_extract(reasoning, '$.shadow_*')`.

### C. Conviction-demotion row

**Use when:** the shadow is an alternative-signal variant that you want to surface through the existing daily WR/EHR tracking (i.e., it IS a prediction, just downgraded to shadow status).

**Example (reverted):** `mr_shadow_extreme_estimate` — stored as conv=2 row instead of conv=3/4, bypasses trade execution but appears in prediction history.

**Template:** `INSERT INTO predictions (...conviction_score=2...)` followed by diagnostic print.

**⚠️ Warning:** This shape was the failure mode of the four April-2026 reverts (§6). It couples the shadow's lifecycle to conviction semantics, and the daily report can't always distinguish "shadow conv=2" from "gated conv=2." Prefer A or B unless you specifically need the prediction-table surface.

---

## 4. The five-step template

### Step 1 — Define the alternative

Write one sentence before writing any code.

> "If we computed regime using a z-score against each asset's own 30-day distribution (instead of an absolute BTC-calibrated threshold), SOL/DOGE would be classified as MEDIUM or LOW in the cycles they're currently marked HIGH_VOL."

The sentence must name:
- What rule/path is being shadowed ("regime classification")
- The alternative ("z-score vs asset's own distribution")
- The expected observable difference ("SOL/DOGE reclassification rate")

### Step 2 — Pick storage

Apply §3's decision:
- Need post-market resolution? → **A (dedicated table)**
- Synchronous observation only? → **B (JSON blob)**
- Need daily-report WR/EHR visibility via existing prediction queries? → **C (conviction-demotion)** — but see warning

### Step 3 — Implement the logger

Always wrap in try/except. Never let a shadow failure break the hot path.

```python
try:
    shadow_result = compute_shadow(...)
    reasoning_data["my_shadow"] = shadow_result
except Exception as _e:
    reasoning_data["my_shadow"] = {"error": str(_e)}
```

For table-backed shadows:

```python
try:
    shadow_module.record(db, prediction_id=pred["id"], cycle=cycle, ...)
except Exception as _e:
    print(f"    [shadow_X] error: {_e}")  # log, don't raise
```

### Step 4 — Register in `docs/optimizations.json`

Single source of truth for experiment lifecycle:

```json
{
  "name": "shadow_regime_relative_perps",
  "description": "Brief what + why.",
  "registered_at": "2026-04-19T18:40:00+00:00",
  "pipeline": "perps",
  "status": "shadow",
  "min_sample": 200,
  "revert_condition": "explicit data condition that triggers revert",
  "baseline": { "...pre-shadow measurements..." },
  "latest_check": null,
  "post_stats": null,
  "closed_at": null,
  "close_reason": null
}
```

Required fields:
- `name` — snake_case, prefix with `shadow_` for clarity
- `description` — one paragraph: what's shadowed, why, what we expect to measure
- `registered_at` — ISO-8601 UTC
- `status` — `"shadow"` for new experiments (other values: `"active"`, `"monitoring"`, `"validated"`, `"reverted"`, `"closed"`)
- `min_sample` — number of observations before any decision (**50+ is the floor**; 200+ for conviction changes)
- `revert_condition` — the specific data rule that triggers revert (e.g., `"post_wr < 48 on 50+ forward bets"`)
- `baseline` — dict with any pre-shadow numbers that make the comparison meaningful

### Step 5 — Add the comparison surface

Every shadow must have an eventual comparison. Pick one:

- **Daily report section** — add an `analyze_my_shadow(db, date_str)` function in `daily_report.py`, render in `format_report`. Shadow maker and conviction scorer use this.
- **Consolidated report section** — aggregate across pipelines in `consolidated_report.py` if cross-pipeline comparison matters.
- **Ad-hoc SQL at decision time** — if the shadow only matters at the promotion/revert decision, a committed SQL query in `docs/analysis/...md` is enough.
- **MCP tool** — expose via Botsy MCP for repeated querying.

No comparison surface = noise. Delete the shadow or add the comparison before shipping.

---

## 5. Promotion criteria

**Do not promote a shadow without all four:**

1. **min_sample reached.** 50-bet floor, 200+ for conviction-structure changes. A 30-bet WR of 80% is noise; April-2026 proved this.
2. **Baseline pre-registered.** Know what you're beating. `baseline` field in `optimizations.json` at registration time.
3. **Revert condition pre-registered.** The data rule that triggers revert is written *before* the shadow goes live. No "let's see how it does and decide later." Define failure while still objective.
4. **One-week minimum.** Even with N=200, if the shadow only ran for 2 days, reject promotion. Market conditions rotate; a week gives at least one regime shift.

Only after all four hold: write a "Promote" commit that (a) changes behavior in the production path, (b) flips the `status` to `"active"` in `optimizations.json`, (c) files a GitHub issue with baseline snapshot and monitoring plan.

---

## 6. Anti-patterns (learning from failures)

### Thin-sample over-promotion

Three reverts in April 2026 (`mr_shadow_extreme`, `eth_mr_shadow_extreme`, `unified_extreme_estimate_shadow`, `shadow_vwap_meanrev`) all promoted at high WR on fewer than 30 bets, then collapsed to ~52% on forward data.

**Rule:** 200+ bets before any conviction-structure change. 50+ for everything else.

### Contaminated metrics

`shadow_vwap_meanrev` tracked "aggregate conv≥3 WR" (77.9%) rather than VWAP-specific WR (40% on 20 bets). The comparison didn't isolate the shadow — it measured the entire production path including the shadow.

**Rule:** Comparison function must query shadow-specific rows only. Write the SQL at registration time.

### Promotion without revert plan

`15m_loose_mode` was promoted based on early WR but the revert criteria were vague ("if it stops working"). It took weeks to diagnose what "stops working" meant.

**Rule:** `revert_condition` must be a single data expression a reader can evaluate in <1 minute. "WR < 48% on 50+ bets" — yes. "If performance degrades" — no.

### Skipping registration

Three existing shadows (`shadow_maker`, `shadow_conviction_scorer`, `shadow_indicators`) ran for weeks without `optimizations.json` entries. The framework couldn't see them; the daily board didn't list them; promotion conversations happened in chat instead of against a pre-registered baseline.

**Rule:** Register *at the time of the first commit* that adds the shadow. The entry can be thin; it just needs to exist.

### Coupling shadow lifecycle to conviction semantics

The conviction-demotion storage shape (§3C) caused the April reverts: as the shadow scaled, the conv=2 rows mixed with legitimate gated conv=2 predictions, confusing downstream WR/EHR analyses.

**Rule:** Prefer storage A (table) or B (JSON blob) unless you specifically need existing predictions-table queries to surface the shadow. If you do use C, tag with an explicit `reason` string matching the shadow name so filters can separate it.

---

## 7. Catalog of current shadows

As of 2026-04-19. Update this table when shadows are added / promoted / reverted.

| Name | File | Storage | Status | Since |
|------|------|---------|--------|-------|
| `shadow_maker_phase_1` | `src/shadow_maker.py` | Table | shadow | 2026-04-16 |
| `shadow_conviction_scorer` | `src/shadow_conviction_scorer.py` | JSON blob | shadow | ~2026-03-30 |
| `shadow_indicators_rsi_obv_vwap` | `src/shadow_indicators.py` | JSON blob | shadow | ~2026-03-30 |
| `shadow_regime_relative_perps` | `src/relative_regime.py` | JSON blob | shadow | 2026-04-19 |
| `mr_shadow_extreme` | inline in `src/predict.py` | conv=2 row | reverted | 2026-04-09 |
| `eth_mr_shadow_extreme` | inline in `src/predict_eth.py` | conv=2 row | reverted | 2026-04-09 |
| `unified_extreme_estimate_shadow` | inline in predict + predict_eth | conv=2 row | reverted | 2026-04-09 |

Full records (baseline, revert criteria, close reason) live in `docs/optimizations.json`. That file is the source of truth; this catalog is the reading-optimized index.

---

## Reference sources

- Storage templates: `src/shadow_maker.py` (table), `src/relative_regime.py` + `src/ci_run_perp.py::_store_prediction` (JSON blob)
- Comparison examples: `src/daily_report.py::analyze_shadow_maker`, `::analyze_shadow_conviction`, `::analyze_shadow_indicators`
- Registered experiments: `docs/optimizations.json` (all entries with `status: "shadow"`)
- Validation principles that shadows enforce: `CLAUDE.md::"Validation Principles"`
- Reverted case studies: `docs/optimizations.json` — search for `"status": "reverted"` and read their `close_reason`

## Changelog

- **2026-04-19** — Initial framework documentation. Cataloged 7 existing shadows. Registered 3 previously-unregistered shadows in `docs/optimizations.json`.
