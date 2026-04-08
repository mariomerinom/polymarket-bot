"""
diag.py — Local Streamlit diagnostic dashboard for polymarket-bot.

Purpose: see what's happening across all pipelines without committing for
each chart iteration. Replaces the retired GH Pages dashboards with a
local-only tool you spin up when you need it and kill when you don't.

Usage:
    source venv/bin/activate
    streamlit run tools/diag.py

Tabs:
    1. P&L Overlay      — counterfactual (signal) vs actual P&L per pipeline.
                          The visual gap IS the execution loss.
    2. Rolling WR       — 50-bet rolling window per pipeline with 55% line.
    3. Regime Heatmap   — day_type x direction WR/$/bet (asset_daily join).
    4. Fill Diagnostic  — fill_diagnostic.result codes per day, fill rate.
    5. Raw Query        — SQL escape hatch.

Reads after `git pull`. No writes. No network calls.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Repo path setup
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

# Reuse the counterfactual P&L logic from signal_pnl.py
from signal_pnl import hypothetical_pnl  # noqa: E402
# Pipeline-internal modules reused for diagnostic surface
from system_state import get_system_state  # noqa: E402
from pnl_legacy import compute_pnl, compute_ev_breakeven  # noqa: E402
from pipeline_integrity import get_recent_integrity  # noqa: E402
import json  # noqa: E402

# ── Pipeline registry ──────────────────────────────────────────────────────

PIPELINES = {
    "BTC 5m":  {"db": "data/predictions.db",       "asset": "BTC", "name": "btc_5m"},
    "BTC 15m": {"db": "data/predictions_15m.db",   "asset": "BTC", "name": "btc_15m"},
    "ETH 5m":  {"db": "data/predictions_eth.db",   "asset": "ETH", "name": "eth_5m"},
    "Bybit BTC": {"db": "data/predictions_bybit.db", "asset": "BTC", "name": "bybit_btc"},
}

ASSET_DAILY_DB = "data/asset_daily.db"


# ── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="polymarket-bot diag",
    page_icon="📊",
    layout="wide",
)

st.title("polymarket-bot diagnostic")
st.caption(
    "Local view across all pipelines. Reads from `data/*.db` after the most "
    "recent `git pull`. Run `git pull` from the repo root before relaunching "
    "for fresh data."
)

# ── Sidebar ────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    days = st.slider("Lookback (days)", 1, 90, 30)
    min_conviction = st.slider("Min conviction", 0, 5, 3)

    enabled_pipelines = st.multiselect(
        "Pipelines",
        options=list(PIPELINES.keys()),
        default=["BTC 5m", "ETH 5m"],
    )

    bet_size = st.number_input("Bet size $ (counterfactual)", value=25.0, step=5.0)

    st.divider()
    st.caption(f"Repo: `{REPO_ROOT}`")
    st.caption(f"Asset daily: `{ASSET_DAILY_DB}`")


# ── Data loaders ───────────────────────────────────────────────────────────


@st.cache_data(ttl=60)
def load_predictions(db_path: str, days: int, min_conviction: int,
                     asset: str | None) -> pd.DataFrame:
    """Pull resolved predictions joined to markets, orders count, and asset_daily."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    has_ad = False
    if asset and Path(ASSET_DAILY_DB).exists():
        try:
            db.execute("ATTACH DATABASE ? AS ad", (ASSET_DAILY_DB,))
            has_ad = True
        except sqlite3.Error:
            has_ad = False

    if has_ad:
        sql = """
            SELECT p.id, p.market_id, p.agent, p.estimate, p.regime,
                   p.conviction_score, p.predicted_at,
                   m.price_yes, m.price_no, m.outcome, m.resolved,
                   (SELECT COUNT(*) FROM orders o WHERE o.prediction_id = p.id) AS placed,
                   (SELECT COALESCE(SUM(pnl),0) FROM orders o
                       WHERE o.prediction_id = p.id
                         AND o.status IN ('settled','paper_settled')) AS actual_pnl,
                   ad.trend_label AS day_trend_label,
                   ad.realized_vol AS day_realized_vol
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            LEFT JOIN ad.asset_daily ad
                ON ad.asset = ?
               AND ad.date  = substr(p.predicted_at, 1, 10)
            WHERE p.predicted_at >= ?
              AND p.conviction_score >= ?
              AND m.resolved = 1
              AND m.outcome IS NOT NULL
        """
        rows = db.execute(sql, (asset, cutoff, min_conviction)).fetchall()
    else:
        sql = """
            SELECT p.id, p.market_id, p.agent, p.estimate, p.regime,
                   p.conviction_score, p.predicted_at,
                   m.price_yes, m.price_no, m.outcome, m.resolved,
                   (SELECT COUNT(*) FROM orders o WHERE o.prediction_id = p.id) AS placed,
                   (SELECT COALESCE(SUM(pnl),0) FROM orders o
                       WHERE o.prediction_id = p.id
                         AND o.status IN ('settled','paper_settled')) AS actual_pnl,
                   NULL AS day_trend_label,
                   NULL AS day_realized_vol
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE p.predicted_at >= ?
              AND p.conviction_score >= ?
              AND m.resolved = 1
              AND m.outcome IS NOT NULL
        """
        rows = db.execute(sql, (cutoff, min_conviction)).fetchall()
    db.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(r) for r in rows])
    # direction from estimate
    df["direction"] = df["estimate"].apply(lambda e: "UP" if e > 0.5 else "DOWN")
    # date
    df["date"] = df["predicted_at"].str.slice(0, 10)
    df["predicted_at_dt"] = pd.to_datetime(df["predicted_at"], errors="coerce")
    # counterfactual P&L
    df["counterfactual_pnl"] = df.apply(
        lambda r: hypothetical_pnl(
            r["direction"], r["estimate"], int(r["outcome"]),
            r["price_yes"], r["price_no"], bet_size,
        ),
        axis=1,
    )
    return df


@st.cache_data(ttl=60)
def load_fill_diagnostic(db_path: str, days: int) -> pd.DataFrame:
    if not Path(db_path).exists():
        return pd.DataFrame()
    db = sqlite3.connect(db_path)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = db.execute(
            "SELECT timestamp, pipeline, result, cushion, filled_size, "
            "requested_size, outcome FROM fill_diagnostic WHERE timestamp >= ?",
            (cutoff,),
        ).fetchall()
    except sqlite3.Error:
        rows = []
    db.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "timestamp", "pipeline", "result", "cushion",
        "filled_size", "requested_size", "outcome",
    ])
    df["date"] = df["timestamp"].str.slice(0, 10)
    return df


def vol_bucket(v, low_hi, mid_hi):
    if v is None or pd.isna(v):
        return "—"
    if v <= low_hi:
        return "vol_low"
    if v <= mid_hi:
        return "vol_mid"
    return "vol_hi"


# ── Build combined frames ──────────────────────────────────────────────────

if not enabled_pipelines:
    st.warning("Select at least one pipeline in the sidebar.")
    st.stop()

frames = []
for label in enabled_pipelines:
    spec = PIPELINES[label]
    df = load_predictions(spec["db"], days, min_conviction, spec["asset"])
    if df.empty:
        continue
    df["pipeline"] = label
    frames.append(df)

if not frames:
    st.warning("No resolved predictions in the selected window.")
    st.stop()

all_df = pd.concat(frames, ignore_index=True)
all_df = all_df.sort_values("predicted_at_dt")

# vol terciles for grouping
vols = sorted(v for v in all_df["day_realized_vol"].dropna().tolist())
if len(vols) >= 3:
    vol_low_hi = vols[len(vols) // 3]
    vol_mid_hi = vols[(2 * len(vols)) // 3]
else:
    vol_low_hi = float("inf")
    vol_mid_hi = float("inf")
all_df["vol_bucket"] = all_df["day_realized_vol"].apply(
    lambda v: vol_bucket(v, vol_low_hi, vol_mid_hi)
)

# top-line KPIs
col1, col2, col3, col4 = st.columns(4)
n = len(all_df)
wins = int(((all_df["direction"] == "UP") & (all_df["outcome"] == 1)).sum() +
           ((all_df["direction"] == "DOWN") & (all_df["outcome"] == 0)).sum())
wr = wins / n if n else 0
counter_total = all_df["counterfactual_pnl"].sum()
actual_total = all_df["actual_pnl"].sum()
col1.metric("Resolved predictions", f"{n}")
col2.metric("Win rate", f"{wr*100:.1f}%")
col3.metric("Counterfactual P&L", f"${counter_total:,.0f}")
col4.metric("Actual P&L", f"${actual_total:,.0f}",
            delta=f"${actual_total - counter_total:,.0f} gap")

# ── Trade Execution strip (P1 #1) ──────────────────────────────────────────

st.divider()
st.subheader("Trade execution status")
st.caption(
    "Per-pipeline runtime state from `system_state.get_system_state`. "
    "Answers: 'did the bot trade today and is it allowed to?'"
)


@st.cache_data(ttl=30)
def load_system_state(db_path: str, pipeline_name: str) -> dict | None:
    if not Path(db_path).exists():
        return None
    try:
        db = sqlite3.connect(db_path)
        s = get_system_state(db, pipeline_name)
        db.close()
        return {
            "pipeline": pipeline_name,
            "mode": s.mode,
            "kill_switch": s.kill_switch,
            "can_trade": s.can_trade,
            "blockers": "; ".join(s.blockers) or "—",
            "daily_loss": s.daily_loss,
            "daily_loss_limit": s.daily_loss_limit,
            "consec_losses": s.consecutive_losses,
            "consec_max": s.consecutive_loss_max,
            "orders_today": s.orders_today,
            "qual_signals_today": s.qualifying_signals_today,
            "last_settled": s.last_settled_at.isoformat() if s.last_settled_at else "—",
            "is_healthy": s.is_healthy,
            "warnings": "; ".join(s.health_warnings) or "—",
        }
    except Exception as e:
        return {"pipeline": pipeline_name, "error": str(e)}


state_rows = []
for label in enabled_pipelines:
    spec = PIPELINES[label]
    s = load_system_state(spec["db"], spec["name"])
    if s:
        s["label"] = label
        state_rows.append(s)

if state_rows:
    cols = st.columns(len(state_rows))
    for col, s in zip(cols, state_rows):
        with col:
            mode_emoji = "🟢" if s.get("can_trade") else "🔴"
            healthy_emoji = "✅" if s.get("is_healthy") else "⚠️"
            st.markdown(f"**{mode_emoji} {s['label']}** — {s.get('mode','?')}")
            st.markdown(
                f"- Can trade: **{s.get('can_trade')}**  \n"
                f"- Kill switch: {s.get('kill_switch')}  \n"
                f"- Daily loss: **${s.get('daily_loss',0):.0f}** / "
                f"${s.get('daily_loss_limit',0):.0f}  \n"
                f"- Streak: {s.get('consec_losses',0)} / {s.get('consec_max',0)}  \n"
                f"- Orders today: {s.get('orders_today',0)}  \n"
                f"- Qualifying signals: {s.get('qual_signals_today',0)}  \n"
                f"- Last settled: `{s.get('last_settled','—')[:19]}`  \n"
                f"- {healthy_emoji} {s.get('warnings','—')}"
            )
            if s.get("blockers", "—") != "—":
                st.error(f"Blockers: {s['blockers']}")

# ── Engine Health strip (P2 #4) ────────────────────────────────────────────

WS_METRICS_PATH = REPO_ROOT / "data" / "ws_metrics.json"
if WS_METRICS_PATH.exists():
    with st.expander("Engine health (WS feeds, dispatch latency)"):
        try:
            metrics = json.loads(WS_METRICS_PATH.read_text())
            ec1, ec2, ec3, ec4 = st.columns(4)
            for col, key, label in [
                (ec1, "bybit_spot", "Bybit Spot"),
                (ec2, "bybit_linear", "Bybit Linear"),
                (ec3, "polymarket", "Polymarket"),
            ]:
                feed = metrics.get(key, {}) or {}
                status = feed.get("status", "unknown")
                emoji = "🟢" if status == "connected" else "🔴"
                col.markdown(
                    f"**{emoji} {label}**  \n"
                    f"status: {status}  \n"
                    f"reconnects 24h: {feed.get('reconnects_24h', 0)}  \n"
                    f"last: `{(feed.get('last_event') or '—')[:19]}`"
                )
            with ec4:
                disp = metrics.get("dispatch_latency_ms", {}) or {}
                ob = metrics.get("orderbook_age_ms", {}) or {}
                st.markdown(
                    f"**⏱ Latency**  \n"
                    f"dispatch p50/p95: {disp.get('p50',0)}/{disp.get('p95',0)}ms  \n"
                    f"orderbook p50/p95: {ob.get('p50',0)}/{ob.get('p95',0)}ms  \n"
                    f"cycles: {metrics.get('cycles', 0)}  \n"
                    f"fallback fires 24h: {metrics.get('fallback_fires_24h', 0)}"
                )
            st.caption(
                f"Source: `data/ws_metrics.json` (engine_start: "
                f"{metrics.get('engine_start','?')}). Local file — pull for fresh."
            )
        except Exception as e:
            st.warning(f"ws_metrics.json parse error: {e}")
else:
    st.caption("ℹ️ `data/ws_metrics.json` not found locally — git pull to fetch.")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────

tab_pnl, tab_wr, tab_heat, tab_agents, tab_fill, tab_raw = st.tabs([
    "P&L Overlay", "Rolling WR", "Regime Heatmap",
    "Agents", "Fill Diagnostic", "Raw Query",
])

# ── Tab 1: P&L Overlay ─────────────────────────────────────────────────────

with tab_pnl:
    st.subheader("Cumulative P&L: counterfactual vs actual")
    st.caption(
        "Counterfactual = what we'd have made if every signal converted into "
        "a perfect fill at the listed price. Actual = real settled P&L "
        "(paper_settled and live settled). The gap is execution loss."
    )

    fig = go.Figure()
    for pipeline in enabled_pipelines:
        sub = all_df[all_df["pipeline"] == pipeline].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("predicted_at_dt")
        sub["counter_cum"] = sub["counterfactual_pnl"].cumsum()
        sub["actual_cum"] = sub["actual_pnl"].cumsum()
        fig.add_trace(go.Scatter(
            x=sub["predicted_at_dt"], y=sub["counter_cum"],
            name=f"{pipeline} counterfactual", mode="lines",
            line=dict(dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=sub["predicted_at_dt"], y=sub["actual_cum"],
            name=f"{pipeline} actual", mode="lines",
        ))
    fig.update_layout(
        height=500, hovermode="x unified",
        xaxis_title="time", yaxis_title="cumulative P&L $",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Per-pipeline gap**")
    gap_rows = []
    for pipeline in enabled_pipelines:
        sub = all_df[all_df["pipeline"] == pipeline]
        if sub.empty:
            continue
        gap_rows.append({
            "pipeline": pipeline,
            "n": len(sub),
            "counterfactual_$": round(sub["counterfactual_pnl"].sum(), 2),
            "actual_$": round(sub["actual_pnl"].sum(), 2),
            "gap_$": round(sub["counterfactual_pnl"].sum() - sub["actual_pnl"].sum(), 2),
            "gap_per_bet": round(
                (sub["counterfactual_pnl"].sum() - sub["actual_pnl"].sum()) / max(len(sub), 1),
                2,
            ),
        })
    if gap_rows:
        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True)

    # Daily P&L bars (P3 #5)
    st.markdown("**Daily P&L (counterfactual + actual)**")
    daily = (
        all_df.assign(
            counter=all_df["counterfactual_pnl"], actual=all_df["actual_pnl"],
        )
        .groupby("date")[["counter", "actual"]].sum().reset_index()
        .melt(id_vars="date", var_name="kind", value_name="pnl")
    )
    if not daily.empty:
        bar = px.bar(
            daily, x="date", y="pnl", color="kind", barmode="group",
            color_discrete_map={"counter": "#1f77b4", "actual": "#ff7f0e"},
        )
        bar.update_layout(height=300, xaxis_title="", yaxis_title="$ per day")
        st.plotly_chart(bar, use_container_width=True)

# ── Tab 2: Rolling WR ──────────────────────────────────────────────────────

with tab_wr:
    st.subheader("Rolling 50-bet win rate per pipeline")
    st.caption("Reference line at 55%. Drops below = signal degradation or fill issues.")

    window = st.slider("Window size", 10, 100, 50, key="rwr_window")

    fig = go.Figure()
    for pipeline in enabled_pipelines:
        sub = all_df[all_df["pipeline"] == pipeline].copy()
        if len(sub) < window:
            continue
        sub = sub.sort_values("predicted_at_dt")
        sub["won"] = (
            ((sub["direction"] == "UP") & (sub["outcome"] == 1)) |
            ((sub["direction"] == "DOWN") & (sub["outcome"] == 0))
        ).astype(int)
        sub["rolling_wr"] = sub["won"].rolling(window).mean() * 100
        fig.add_trace(go.Scatter(
            x=sub["predicted_at_dt"], y=sub["rolling_wr"],
            name=pipeline, mode="lines",
        ))
    fig.add_hline(y=55, line_dash="dot", line_color="red",
                  annotation_text="55% threshold")
    fig.update_layout(
        height=500, hovermode="x unified",
        xaxis_title="time", yaxis_title="rolling WR %",
        yaxis_range=[30, 90],
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Tab 3: Regime Heatmap ──────────────────────────────────────────────────

with tab_heat:
    st.subheader("WR by regime cell")
    group_dim = st.selectbox(
        "Row dimension",
        ["day_trend_label", "vol_bucket", "regime", "agent"],
        index=0,
    )
    col_dim = st.selectbox("Column dimension", ["direction", "pipeline"], index=0)

    if group_dim not in all_df.columns or col_dim not in all_df.columns:
        st.warning("Selected dimension not present.")
    else:
        all_df["won"] = (
            ((all_df["direction"] == "UP") & (all_df["outcome"] == 1)) |
            ((all_df["direction"] == "DOWN") & (all_df["outcome"] == 0))
        ).astype(int)
        agg = all_df.groupby([group_dim, col_dim]).agg(
            n=("id", "count"),
            wr=("won", "mean"),
            counter=("counterfactual_pnl", "sum"),
            actual=("actual_pnl", "sum"),
        ).reset_index()
        agg["wr_pct"] = (agg["wr"] * 100).round(1)
        agg["per_bet"] = (agg["counter"] / agg["n"]).round(2)

        wr_pivot = agg.pivot(index=group_dim, columns=col_dim, values="wr_pct")
        n_pivot = agg.pivot(index=group_dim, columns=col_dim, values="n")
        counter_pivot = agg.pivot(index=group_dim, columns=col_dim, values="counter")

        st.markdown("**Win rate %**")
        fig = px.imshow(
            wr_pivot, text_auto=".1f", aspect="auto",
            color_continuous_scale="RdYlGn", zmin=40, zmax=80,
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Sample size (n)**")
        st.dataframe(n_pivot.fillna(0).astype(int), use_container_width=True)

        st.markdown("**Counterfactual $ per cell**")
        st.dataframe(counter_pivot.round(0).fillna(0), use_container_width=True)

# ── Tab: Agents (P1 #2 + P2 conviction histogram) ─────────────────────────

with tab_agents:
    st.subheader("Per-agent scorecard")
    st.caption(
        "Reuses `pnl_legacy.compute_pnl` + `compute_ev_breakeven` — same "
        "P&L contract the retired dashboards used."
    )

    # Build resolved-row dicts in the shape pnl_legacy expects
    resolved = []
    for r in all_df.itertuples():
        resolved.append({
            "agent": r.agent,
            "estimate": r.estimate,
            "outcome": int(r.outcome),
            "price_yes": r.price_yes,
            "market_id": r.market_id,
            "predicted_at": r.predicted_at,
            "conviction_score": r.conviction_score,
        })

    # Per-pipeline asset routing — use first pipeline's asset (simple)
    asset = PIPELINES[enabled_pipelines[0]]["asset"]
    try:
        agent_pnl = compute_pnl(resolved, asset=asset)
    except Exception as e:
        st.error(f"compute_pnl failed: {e}")
        agent_pnl = {}

    if agent_pnl:
        rows = []
        for agent, d in agent_pnl.items():
            rows.append({
                "agent": agent,
                "n_bets": d.get("num_bets", 0),
                "wins": d.get("num_wins", 0),
                "wr_%": round(
                    (d.get("num_wins", 0) / d.get("num_bets", 1) * 100)
                    if d.get("num_bets", 0) else 0, 1),
                "pnl_$": round(d.get("total_pnl", 0), 2),
                "wagered_$": round(d.get("total_wagered", 0), 2),
                "roi_%": round(d.get("roi", 0), 2),
                "avg_win": round(d.get("avg_win", 0), 2),
                "avg_loss": round(d.get("avg_loss", 0), 2),
                "max_dd": round(d.get("max_drawdown", 0), 2),
                "skipped": d.get("skipped", 0),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

        ev = compute_ev_breakeven(agent_pnl)
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Total bets", ev["total_bets"])
        ec2.metric("Current WR", f"{ev['current_wr']*100:.1f}%")
        ec3.metric("Breakeven WR", f"{ev['breakeven_wr']*100:.1f}%")
        ec4.metric("Margin", f"{ev['margin']*100:+.1f}%",
                   delta=f"EV ${ev['ev']:.2f}/bet")
    else:
        st.info("No bet rows fed bet sizes (check conviction filter / asset routing).")

    st.divider()
    st.subheader("Conviction tier histogram")
    if "conviction_score" in all_df.columns and not all_df.empty:
        conv = (
            all_df.groupby(["pipeline", "conviction_score"])
            .size().reset_index(name="n")
        )
        cf = px.bar(
            conv, x="conviction_score", y="n", color="pipeline", barmode="group",
        )
        cf.update_layout(height=300, xaxis_title="conviction", yaxis_title="count")
        st.plotly_chart(cf, use_container_width=True)

# ── Tab 4: Fill Diagnostic ─────────────────────────────────────────────────

with tab_fill:
    st.subheader("Fill diagnostic")
    st.caption(
        "Source: `fill_diagnostic` table. Validates Lever B (FAK + dynamic "
        "cushion). DoD: fill rate ≥ 70%, corr(filled, won) ≥ 0."
    )

    fill_frames = []
    for label in enabled_pipelines:
        spec = PIPELINES[label]
        fdf = load_fill_diagnostic(spec["db"], days)
        if fdf.empty:
            continue
        fdf["pipeline_label"] = label
        fill_frames.append(fdf)

    if not fill_frames:
        st.info("No fill_diagnostic rows in window.")
    else:
        fdf_all = pd.concat(fill_frames, ignore_index=True)
        st.markdown(f"**{len(fdf_all)} fill_diagnostic rows in window**")

        # Result code stacked bar by date
        counts = fdf_all.groupby(["date", "result"]).size().reset_index(name="n")
        fig = px.bar(counts, x="date", y="n", color="result", barmode="stack")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        # Result summary table
        summary = (
            fdf_all.groupby(["pipeline_label", "result"]).size()
            .reset_index(name="n")
            .pivot(index="result", columns="pipeline_label", values="n")
            .fillna(0).astype(int)
        )
        st.markdown("**Result code counts**")
        st.dataframe(summary, use_container_width=True)

        # Fill rate per pipeline
        rates = []
        FILLED_CODES = {"filled_full", "filled_partial"}
        TERMINAL_CODES = FILLED_CODES | {"killed_fok", "cancelled_ioc_residual"}
        for label in enabled_pipelines:
            sub = fdf_all[fdf_all["pipeline_label"] == label]
            terminal = sub[sub["result"].isin(TERMINAL_CODES)]
            filled = terminal[terminal["result"].isin(FILLED_CODES)]
            n = len(terminal)
            rate = (len(filled) / n * 100) if n else 0
            rates.append({
                "pipeline": label,
                "terminal_n": n,
                "filled_n": len(filled),
                "fill_rate_%": round(rate, 1),
            })
        if rates:
            st.markdown("**Fill rate (terminal attempts only)**")
            st.dataframe(pd.DataFrame(rates), use_container_width=True)

# ── Tab 5: Raw Query ───────────────────────────────────────────────────────

with tab_raw:
    st.subheader("Raw SQL")
    st.caption(
        "Read-only escape hatch. Enter a query against any pipeline DB. "
        "Asset_daily is attached as `ad`. No writes allowed."
    )
    db_choice = st.selectbox(
        "Database",
        list(PIPELINES.keys()),
        format_func=lambda k: f"{k} → {PIPELINES[k]['db']}",
    )
    default_sql = (
        "SELECT date, asset, trend_label, body_pct, realized_vol\n"
        "FROM ad.asset_daily\n"
        "ORDER BY date DESC LIMIT 20;"
    )
    sql = st.text_area("SQL", value=default_sql, height=150)
    if st.button("Run"):
        if not sql.strip().lower().startswith(("select", "with")):
            st.error("Only SELECT / WITH queries allowed.")
        else:
            try:
                db = sqlite3.connect(PIPELINES[db_choice]["db"])
                if Path(ASSET_DAILY_DB).exists():
                    db.execute("ATTACH DATABASE ? AS ad", (ASSET_DAILY_DB,))
                df = pd.read_sql_query(sql, db)
                db.close()
                st.dataframe(df, use_container_width=True)
                st.caption(f"{len(df)} rows")
            except Exception as e:
                st.error(f"Query error: {e}")

# ── Bottom: Integrity log strip (P3 #6) ────────────────────────────────────

st.divider()
st.subheader("Recent integrity warnings (24h)")
st.caption("Source: `pipeline_integrity.get_recent_integrity` per pipeline DB.")

integrity_rows = []
for label in enabled_pipelines:
    spec = PIPELINES[label]
    if not Path(spec["db"]).exists():
        continue
    try:
        db = sqlite3.connect(spec["db"])
        for row in get_recent_integrity(db, hours=24):
            row["pipeline_label"] = label
            integrity_rows.append(row)
        db.close()
    except Exception as e:
        st.warning(f"{label}: integrity read failed: {e}")

if integrity_rows:
    idf = pd.DataFrame(integrity_rows)
    cols = ["timestamp", "pipeline_label", "check_name", "status", "detail"]
    cols = [c for c in cols if c in idf.columns]
    st.dataframe(idf[cols].sort_values("timestamp", ascending=False),
                 use_container_width=True)
else:
    st.success("No WARN/FAIL integrity entries in the last 24h.")
