# Streamlit Adoption Plan

**Date:** 2026-04-08
**Status:** Active
**Trigger:** GH Pages dashboards retired earlier today (commits `5245932a` ship + `acd0df1d` retirement). Streamlit diag shipped at `tools/diag.py`. Need a written habit so the morning glance has a new home, and a list of charts the dashboard had that diag.py is missing so we can prioritize what to add next.

## Context

The retired dashboards were the unconscious morning ritual: `git pull` → open the GH Pages tab → eyeball WR / P&L / orders / breaker. That ritual is now gone. Without a written replacement, the failure mode is "forget to look until something breaks." The 48-hour WR cliff (65% → 38%) we just diagnosed today would have been spotted ~24 hours sooner under the old habit. We need:

1. A 60-second daily workflow that produces the same situational awareness the dashboards used to.
2. An audit of what diag.py is missing vs. what the dashboards displayed, so we know what to build before we can fully kill the old habit.

This is documentation only — no code in this plan.

## Critical files (read-only references)

- `tools/diag.py` — current Streamlit app, 5 tabs (P&L Overlay, Rolling WR, Regime Heatmap, Fill Diagnostic, Raw Query). 486 lines.
- `tools/signal_pnl.py` — counterfactual engine, reused via `hypothetical_pnl`.
- `src/asset_daily.py` — regime metrics (trend_label, vol terciles).
- `src/fill_diagnostic.py` — fill_rate / fill_outcome_correlation.
- `src/daily_report.py` — auto-generated `docs/daily/YYYY-MM-DD.md` (00:05 UTC); the only piece of the old reporting habit that survived. Streamlit complements this — does not replace it.
- `CLAUDE.md` § Diagnostic Tooling — already points at `streamlit run tools/diag.py`. This doc is the canonical workflow it links to.

---

## Section 1 — Daily workflow (the 60-second glance)

A literal step-by-step ritual replacing the GH Pages habit.

### 1. Launch (terminal, every morning)

```
cd ~/polymarket-bot && git pull && source venv/bin/activate && streamlit run tools/diag.py
```

Same command, every day. Memorize it. The `git pull` is non-negotiable — the VPS engine commits every ~5 minutes and stale local DBs will lie to you.

### 2. Sidebar defaults to set on first open of the day

- **Lookback:** 7 days (yesterday's daily report covers 1d; 7d shows the trend)
- **Min conviction:** 3
- **Pipelines:** BTC 5m + ETH 5m (the two we actually trade/paper-grade)
- **Bet size:** $25

### 3. The 5 things to look at, in order, with a stop rule for each

| Order | Where | What | Stop rule |
|-------|-------|------|-----------|
| 1 | KPI strip (top of page) | 7d WR, counterfactual $, actual $, gap $ | If WR < 55% → go to step 2 immediately |
| 2 | **Rolling WR** tab | 50-bet rolling line vs 55% threshold | If line < 52% → file incident card, halt re-arm conversation |
| 3 | **P&L Overlay** tab | Counterfactual vs actual gap per pipeline | If gap widening → execution problem (Lever B); if both falling → signal problem |
| 4 | **Regime Heatmap** tab | day_trend × direction; vol_bucket × direction | Note any cell that flipped sign vs 30d baseline |
| 5 | **Fill Diagnostic** tab | Fill rate trend, result code mix | Confirm fill rate ≥70% if BTC 5m has ≥10 attempts in window |

### 4. Write one line in `docs/sessions/YYYY-MM-DD.md`

Capture:
- 50-bet rolling WR
- 7d gap $
- Anything in step 3 that crossed a stop rule

### 5. Kill Streamlit (`Ctrl+C`)

It's not meant to run all day. Open it again only when you have a question.

**Total time:** 60–90 seconds when nothing is wrong, up to 5 minutes when something is.

---

## Section 2 — Decision triggers (cross-reference)

Streamlit views → kanban actions:

| Streamlit signal | Action |
|------------------|--------|
| Rolling WR < 52% (50 bets) | Create `incident,<pipeline>` issue. Block re-arm. |
| Rolling WR ≥ 55% on 100+ bets after a dip | Move re-arm decision card to "Ready" |
| P&L Overlay gap > $200 over 50 bets, signal positive | Execution failure — Lever A/C eval per Lever B plan |
| P&L Overlay both lines down | Signal failure — open regime investigation |
| Fill rate < 70% on ≥30 attempts | Lever B DoD failed; classify codes |
| Heatmap cell flips sign vs 30d | Note in session log; revisit after 50 more bets |

---

## Section 3 — Missing features (audit vs. retired dashboards)

What the old `dashboard_v2` displayed that diag.py does NOT yet show. Each item gets a priority and the source code path that produced it (so a future builder can port the logic, not redesign it):

| Missing view | Priority | What it was | Source | Current diag gap |
|---|---|---|---|---|
| Per-agent scorecard (Brier, WR, EV, breakeven WR) | **P1** | Top-of-page tile in `dashboard.py` showing each agent's contract status | `pnl_legacy.compute_pnl` + `compute_ev_breakeven` (rescued, importable) | No agent dimension surfaced anywhere |
| Trade execution status panel | **P1** | live/paper mode, kill switch, daily loss vs limit, breaker streak | `system_state.get_system_state()` (still alive) | Diag has zero `system_state` integration |
| Conviction tier histogram | **P2** | Distribution of conv 0/1/2/3/4/5 over window | `dashboard_v2.charts` (deleted; trivial to recreate) | Only filterable, never visualized |
| Predicted-at vs settled-at lag chart | **P2** | How long markets take to resolve, surfaced market-stuckness | `dashboard.py` time-delta chart | Not present |
| Engine health (WS feeds, dispatch latency, reconnects) | **P2** | `data/ws_metrics.json` parsed via `dashboard_v2.data.get_engine_health` | Deleted; raw json still on VPS at `~/polymarket-bot/data/ws_metrics.json` | Diag has no engine pane |
| Daily P&L bars (calendar view) | **P3** | One bar per day, color by sign | `dashboard_v2.charts` (deleted) | Only cumulative line in P&L Overlay |
| Open positions / pending orders snapshot | **P3** | Bybit perp + any unfilled Polymarket orders | `bybit_markets.get_open_position` + `orders` table | Not present — would need a new tab |
| Optimization timeline (deploy markers) | **P3** | Vertical lines on charts at `optimizations.json` entries | Embedded in dashboard.py chart code | Spec'd in original diag plan, not implemented |
| Recent integrity_log warnings/fails | **P3** | Bottom-of-page WARN/FAIL bar from `pipeline_integrity.get_recent_integrity` | Function still alive | Not surfaced |
| Per-market deep-link / question text | **P4** | Click a row, see the market question | Static HTML rendering | Streamlit row-click would need st.dataframe selection wiring |

**P1 items are required** before we can claim the dashboard habit is fully replaced. Without the agent scorecard and the trade-execution panel, the morning glance is missing the two questions an operator most needs answered: "are agents earning their keep?" and "did the bot trade today and is it allowed to?". P2/P3/P4 are nice-to-haves staged after.

---

## Section 4 — Build order for missing features

Recommended ship sequence, single commit per item, each ~30–60 lines added to `tools/diag.py`:

1. **Trade Execution panel** (top-of-page strip, above tabs). Reuses `system_state.get_system_state(db, pipeline_name)` — already does the heavy lifting. Surfaces: mode, kill switch, daily loss vs $300 limit, consecutive losses, last settled, blockers list.
2. **Agent scorecard tab.** Group `all_df` by `agent`, run `compute_pnl` from `pnl_legacy`, show contract table + EV/breakeven from `compute_ev_breakeven`.
3. **Conviction histogram.** One Plotly bar chart over `conviction_score` from `all_df`. ~10 lines.
4. **Engine health pane.** Parse `data/ws_metrics.json` directly. Match the deleted `dashboard_v2.data.get_engine_health` shape.
5. **Daily P&L bars.** `all_df.groupby('date').agg(...).plot.bar`. One chart.
6. **Integrity log warnings strip.** Bottom of page, calls `pipeline_integrity.get_recent_integrity(db)`.
7. **Open positions / Optimization markers / Per-market click.** Defer until items 1–6 land and we know if we still want them.

Each ships as its own commit with a one-line addition to the existing CLAUDE.md Diagnostic Tooling section if it materially changes the morning workflow.

---

## Section 5 — Verification

How we know the habit + features replaced the dashboards:

1. **One full week of session logs** (`docs/sessions/`) showing the 60-second glance ritual was performed daily.
2. **At least one decision driven by Streamlit alone** — a kanban card moved (incident filed, re-arm blocked, optimization reverted) where the supporting evidence points to a Streamlit screenshot or a `signal_pnl.py` output, not a dashboard URL.
3. **P1 features shipped** — both Trade Execution panel and Agent scorecard live in `tools/diag.py`.
4. **Zero references to dashboard.py / dashboard_v2 / GH Pages dashboards** in any new doc, plan, or session log going forward.

---

## What this plan does NOT do

- Does not change `tools/diag.py` (no code in this plan)
- Does not modify the daily report generator (already fixed)
- Does not affect VPS systemd, engine, or trade path
- Does not address the WR nosedive itself — that's a separate incident, tracked separately
- Does not propose hosting Streamlit on the VPS (local-only by design)
