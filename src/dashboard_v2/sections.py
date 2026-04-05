"""HTML section builders. Each function returns an HTML string."""

from . import colors as C
from .charts import prepare_cumulative_pnl, prepare_waterfall, prepare_rolling_accuracy, to_json


def _pnl_class(val):
    if val > 0:
        return "hero-positive"
    elif val < 0:
        return "hero-negative"
    return "hero-zero"


def _pnl_sign(val):
    return f"+${val:,.2f}" if val >= 0 else f"-${abs(val):,.2f}"


def _provenance_html(prov):
    if not prov:
        return ""
    src = prov.get("source", "")
    ts = prov.get("fetched_at", "")[:16].replace("T", " ")
    return f'<div class="provenance"><span class="provenance-tag">{src}</span>{ts} UTC</div>'


def _metric(label, value, color=None):
    style = f' style="color:{color}"' if color else ""
    return f"""<div class="metric">
    <div class="metric-label">{label}</div>
    <div class="metric-value"{style}>{value}</div>
</div>"""


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def header_section(pipeline_name, mode, summary, integrity=None):
    badge_cls = "badge-live" if mode == "live" else "badge-paper"
    badge_label = "LIVE" if mode == "live" else "PAPER"
    status = summary["status"]
    status_color = C.PROFIT if status == "Active" else (C.LOSS if status == "Stale" else C.NEUTRAL)

    # Integrity indicator
    integrity_dot = ""
    integrity_detail = ""
    if integrity:
        int_status = integrity.get("status", "green")
        warnings = integrity.get("warnings_24h", 0)
        failures = integrity.get("failures_24h", 0)
        issues = integrity.get("recent_issues", [])
        if int_status == "red":
            integrity_dot = f'&nbsp;&middot;&nbsp; <span style="color:#ef4444">&#9679; {failures} failure(s)</span>'
        elif int_status == "yellow":
            integrity_dot = f'&nbsp;&middot;&nbsp; <span style="color:#eab308">&#9679; {warnings} warning(s)</span>'
        else:
            integrity_dot = '&nbsp;&middot;&nbsp; <span style="color:#22c55e">&#9679; Integrity OK</span>'
        # Show issues as visible list if any
        if issues:
            items = "".join(f'<li>{_esc(i)}</li>' for i in issues[:8])
            integrity_detail = f'<ul style="margin:6px 0 0 18px;padding:0;font-size:11px;color:{C.TEXT_DIM};list-style:disc">{items}</ul>'

    return f"""<div class="header">
    <h1>{pipeline_name} <span class="badge {badge_cls}">{badge_label}</span></h1>
    <div class="header-meta">
        <span style="color:{status_color}">&#9679; {status}</span>
        &nbsp;&middot;&nbsp; Last cycle: {summary["last_prediction"]}
        &nbsp;&middot;&nbsp; {summary["resolved_markets"]}/{summary["total_markets"]} resolved
        &nbsp;&middot;&nbsp; Health: {summary["health_pct"]}%{integrity_dot}
    </div>{integrity_detail}
</div>"""


def _esc(text):
    """Escape HTML special chars."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ---------------------------------------------------------------------------
# Live P&L (Polymarket Data API)
# ---------------------------------------------------------------------------

def live_pnl_section(live_data):
    if not live_data:
        return ""

    pnl = live_data["total_pnl"]
    chart_data = to_json(prepare_cumulative_pnl(
        _build_live_pnl_series(live_data)
    ))

    wr = (live_data["num_wins"] / live_data["num_bets"] * 100) if live_data["num_bets"] > 0 else 0

    metrics_html = "".join([
        _metric("Win Rate", f"{wr:.1f}%", C.PROFIT if wr > 50 else C.LOSS),
        _metric("ROI", f"{live_data['roi']}%", C.PROFIT if live_data['roi'] > 0 else C.LOSS),
        _metric("Record", f"{live_data['num_wins']}W-{live_data['num_losses']}L"),
        _metric("Max DD", f"${live_data['max_drawdown']:.2f}", C.LOSS if live_data['max_drawdown'] > 0 else None),
        _metric("Avg Win", f"${live_data['avg_win']:.2f}", C.PROFIT),
        _metric("Avg Loss", f"${live_data['avg_loss']:.2f}", C.LOSS),
    ])

    return f"""<div class="section section-live">
    <div class="section-title">Live P&L</div>
    <div class="hero {_pnl_class(pnl)}">{_pnl_sign(pnl)}</div>
    {_provenance_html(live_data.get("_provenance"))}
    <div class="chart-container d3-chart" data-chart-type="cumulative_pnl" data-chart-data='{chart_data}'></div>
    <div class="metrics">{metrics_html}</div>
</div>"""


def _build_live_pnl_series(live_data):
    """Convert flat pnl_series + bet_results into timestamped series.

    polymarket_pnl returns pnl_series as bare floats and bet_results
    with per-bet detail. We need to combine them.
    """
    bet_results = live_data.get("bet_results", [])
    pnl_series = live_data.get("pnl_series", [])

    # If bet_results have timestamps already (they don't in polymarket_pnl),
    # just use them. Otherwise, we generate sequential points.
    # polymarket_pnl.compute_real_pnl builds bets_chronological with timestamps
    # but bet_results in the portfolio dict are stripped of timestamps.
    # We'll use indexed points as a fallback.
    if not pnl_series:
        return []

    # The live pnl module doesn't carry dates through to the portfolio dict.
    # We re-derive from the activity data. For now, use sequential indices
    # wrapped as synthetic timestamps based on the API fetch time.
    # This is a known limitation — the Polymarket Data API returns epoch
    # timestamps that get lost in the portfolio rollup.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    # Space the bets out evenly over the period for visual representation
    if len(pnl_series) <= 1:
        return [{"date": now.isoformat(), "value": pnl_series[0]}] if pnl_series else []

    # Approximate: assume bets span from 2026-04-01 to now
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    step = (now - start) / max(len(pnl_series) - 1, 1)
    return [
        {"date": (start + step * i).strftime("%Y-%m-%dT%H:%M:%SZ"), "value": round(v, 2)}
        for i, v in enumerate(pnl_series)
    ]


# ---------------------------------------------------------------------------
# Signal P&L (conviction simulation)
# ---------------------------------------------------------------------------

def signal_pnl_section(signal_data, mode):
    if not signal_data or signal_data["num_bets"] == 0:
        return ""

    pnl = signal_data["total_pnl"]
    section_cls = "section-live" if mode == "live" else "section-paper"
    chart_data = to_json(prepare_cumulative_pnl(signal_data["pnl_series"]))
    waterfall_data = to_json(prepare_waterfall(signal_data["bet_results"]))

    metrics_html = "".join([
        _metric("Win Rate", f"{signal_data['win_rate']}%",
                C.PROFIT if signal_data['win_rate'] > 50 else C.LOSS),
        _metric("ROI", f"{signal_data['roi']}%",
                C.PROFIT if signal_data['roi'] > 0 else C.LOSS),
        _metric("Record", f"{signal_data['num_wins']}W-{signal_data['num_losses']}L"),
        _metric("Streak", signal_data["streak"]),
        _metric("EV/Bet", f"${signal_data['ev_per_bet']:.2f}",
                C.PROFIT if signal_data['ev_per_bet'] > 0 else C.LOSS),
        _metric("Edge", f"{signal_data['edge']}pp",
                C.PROFIT if signal_data['edge'] > 0 else C.LOSS),
    ])

    return f"""<div class="section {section_cls}">
    <div class="section-title">Signal P&L</div>
    <div class="hero {_pnl_class(pnl)}">{_pnl_sign(pnl)}</div>
    {_provenance_html(signal_data.get("_provenance"))}
    <div class="chart-container d3-chart" data-chart-type="cumulative_pnl" data-chart-data='{chart_data}'></div>
    <div class="metrics">{metrics_html}</div>
    <div style="margin-top:16px">
        <div class="section-title" style="margin-bottom:8px">Per-Bet Waterfall</div>
        <div class="chart-container d3-chart" data-chart-type="waterfall" data-chart-data='{waterfall_data}'></div>
    </div>
</div>"""


# ---------------------------------------------------------------------------
# EV / Breakeven gauge
# ---------------------------------------------------------------------------

def ev_gauge_section(signal_data):
    if not signal_data or signal_data["num_bets"] == 0:
        return ""

    wr = signal_data["win_rate"]
    be_wr = signal_data["breakeven_wr"]
    edge = signal_data["edge"]
    ev = signal_data["ev_per_bet"]
    avg_win = signal_data["avg_win"]
    avg_loss = signal_data["avg_loss"]
    dd = signal_data["max_drawdown"]

    metrics_html = "".join([
        _metric("Breakeven WR", f"{be_wr}%"),
        _metric("Current WR", f"{wr}%", C.PROFIT if wr > be_wr else C.LOSS),
        _metric("Edge Margin", f"{edge}pp", C.PROFIT if edge > 0 else C.LOSS),
        _metric("Avg Win", f"${avg_win:.2f}", C.PROFIT),
        _metric("Avg Loss", f"${avg_loss:.2f}", C.LOSS),
        _metric("Max Drawdown", f"${dd:.2f}", C.LOSS if dd > 0 else None),
    ])

    return f"""<div class="section">
    <div class="section-title">EV &amp; Risk</div>
    <div class="metrics">{metrics_html}</div>
</div>"""


# ---------------------------------------------------------------------------
# Conviction scoreboard
# ---------------------------------------------------------------------------

def conviction_section(breakdown):
    if not breakdown:
        return ""

    tier_order = ["HIGH", "MEDIUM", "LOW", "NO_BET", "UNKNOWN"]
    tier_labels = {"HIGH": "High (4-5)", "MEDIUM": "Medium (3)", "LOW": "Low (2)", "NO_BET": "No Bet (0-1)", "UNKNOWN": "Unknown"}

    rows = ""
    for tier in tier_order:
        if tier not in breakdown:
            continue
        ts = breakdown[tier]
        wr_color = C.PROFIT if ts["accuracy"] > 50 else (C.LOSS if ts["accuracy"] < 45 else C.NEUTRAL)
        pnl_color = C.PROFIT if ts["pnl"] > 0 else (C.LOSS if ts["pnl"] < 0 else C.NEUTRAL)
        rows += f"""<tr>
    <td>{tier_labels.get(tier, tier)}</td>
    <td>{ts["total"]}</td>
    <td style="color:{wr_color}">{ts["accuracy"]}%</td>
    <td>{ts["wins"]}W-{ts["losses"]}L</td>
    <td style="color:{pnl_color}">${ts["pnl"]:,.2f}</td>
    <td>${ts["wagered"]:,.0f}</td>
    <td style="color:{pnl_color}">{ts["roi"]}%</td>
</tr>"""

    return f"""<div class="section">
    <div class="section-title">Conviction Breakdown</div>
    <table class="conv-table">
        <thead><tr>
            <th>Tier</th><th>Bets</th><th>WR</th><th>Record</th><th>P&L</th><th>Wagered</th><th>ROI</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
</div>"""


# ---------------------------------------------------------------------------
# Rolling accuracy chart
# ---------------------------------------------------------------------------

def rolling_accuracy_section(rolling_data):
    if not rolling_data or len(rolling_data) < 3:
        return ""

    chart_data = to_json(prepare_rolling_accuracy(rolling_data))

    return f"""<div class="section">
    <div class="section-title">Rolling Accuracy (10-bet window)</div>
    <div class="chart-container d3-chart" data-chart-type="rolling_accuracy" data-chart-data='{chart_data}'></div>
</div>"""


# ---------------------------------------------------------------------------
# Trade execution
# ---------------------------------------------------------------------------

def trade_execution_section(exec_data):
    if not exec_data:
        return ""

    fill_rate = exec_data["fill_rate"]
    fr_color = C.PROFIT if fill_rate >= 80 else (C.WARN if fill_rate >= 50 else C.LOSS)

    metrics_html = "".join([
        _metric("Fill Rate", f"{fill_rate}%", fr_color),
        _metric("Filled", str(exec_data["filled"])),
        _metric("Expired", str(exec_data["expired"]), C.WARN if exec_data["expired"] > 0 else None),
        _metric("Pending", str(exec_data["pending"]), C.CHART_LINE if exec_data["pending"] > 0 else None),
        _metric("Today", f"{exec_data['today_count']} (${exec_data['today_wagered']:.0f})"),
    ])

    last_order = exec_data.get("last_order") or "Never"

    return f"""<div class="section section-live">
    <div class="section-title">Trade Execution</div>
    <div class="metrics">{metrics_html}</div>
    <div class="provenance" style="margin-top:8px">Last order: {last_order} UTC</div>
</div>"""


# ---------------------------------------------------------------------------
# Recent bets
# ---------------------------------------------------------------------------

_RESULT_COLORS = {
    "WIN": C.PROFIT,
    "LOSS": C.LOSS,
    "FAILED": C.LOSS,
    "PENDING": C.CHART_LINE,
    "SETTLED": C.NEUTRAL,
}


def _result_color(result):
    for key, color in _RESULT_COLORS.items():
        if key in result:
            return color
    return C.NEUTRAL


def recent_bets_section(bets):
    if not bets:
        return ""

    rows = ""
    for b in bets:
        rc = _result_color(b["result"])
        mode_badge = f'<span style="color:{C.LIVE["accent"]};font-size:10px">LIVE</span>' if b["mode"] == "live" else f'<span style="color:{C.PAPER["accent"]};font-size:10px">PAPER</span>'
        price_str = f'@{b["filled_price"]:.2f}' if b["filled_price"] else (f'lim {b["limit_price"]:.2f}' if b["limit_price"] else "")
        detail = f' <span style="color:{C.TEXT_DIM}">{_esc(b["result_detail"])}</span>' if b["result_detail"] else ""

        rows += f"""<tr>
    <td style="white-space:nowrap">{_esc(b["time"])}</td>
    <td>{mode_badge}</td>
    <td>{b["direction"]}</td>
    <td>${b["size"]:.0f}</td>
    <td style="color:{C.TEXT_MUTED};font-size:12px">{price_str}</td>
    <td style="color:{rc};font-weight:600">{b["result"]}{detail}</td>
</tr>"""

    return f"""<div class="section">
    <div class="section-title">Recent Bets</div>
    <table class="conv-table">
        <thead><tr>
            <th>Time</th><th>Mode</th><th>Dir</th><th>Size</th><th>Price</th><th>Result</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
</div>"""


# ---------------------------------------------------------------------------
# Engine health (websocket feeds)
# ---------------------------------------------------------------------------

def _ws_status_html(status, last_event):
    """Format a WS feed status indicator."""
    if status == "connected":
        icon = f'<span style="color:{C.PROFIT}">&#x2714;</span>'
        label = "Connected"
    else:
        icon = f'<span style="color:{C.LOSS}">&#x2716;</span>'
        label = "Down"
    age_str = ""
    if last_event:
        try:
            from datetime import datetime, timezone
            last_dt = datetime.fromisoformat(last_event)
            now = datetime.now(timezone.utc)
            age_s = (now - last_dt).total_seconds()
            if age_s < 60:
                age_str = f" ({age_s:.0f}s ago)"
            elif age_s < 3600:
                age_str = f" ({age_s / 60:.0f}m ago)"
            else:
                age_str = f" ({age_s / 3600:.1f}h ago)"
        except (ValueError, TypeError):
            pass
    return f'{icon} {label}{age_str}'


def engine_health_section(health):
    if not health:
        return ""

    # Feed statuses
    polygon_html = _ws_status_html(health["polygon_status"], health["polygon_last"])
    bybit_html = _ws_status_html(health["bybit_status"], health["bybit_last"])
    polymarket_html = _ws_status_html(health["polymarket_status"], health["polymarket_last"])

    # Latency
    lat = health.get("dispatch_latency", {})
    lat_p50 = lat.get("p50", 0)
    lat_p95 = lat.get("p95", 0)
    lat_color = C.PROFIT if lat_p95 < 2000 else (C.WARN if lat_p95 < 5000 else C.LOSS)

    # Orderbook age
    ob = health.get("orderbook_age", {})
    ob_p50 = ob.get("p50", 0)
    ob_p95 = ob.get("p95", 0)

    # Reconnects
    recon_total = (health["polygon_reconnects"]
                   + health["bybit_reconnects"]
                   + health["polymarket_reconnects"])
    recon_color = C.PROFIT if recon_total == 0 else (C.WARN if recon_total < 5 else C.LOSS)

    # Fallback fires
    fb = health.get("fallback_fires", 0)
    fb_color = C.PROFIT if fb == 0 else C.WARN

    return f"""<div class="section">
    <div class="section-title">Engine Health</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:12px">
        <div class="metric">
            <div class="metric-label">Polygon.io</div>
            <div class="metric-value" style="font-size:13px">{polygon_html}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Bybit</div>
            <div class="metric-value" style="font-size:13px">{bybit_html}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Polymarket</div>
            <div class="metric-value" style="font-size:13px">{polymarket_html}</div>
        </div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:16px;font-size:11px;color:{C.TEXT_DIM};border-top:1px solid {C.BORDER};padding-top:8px">
        <span>Dispatch: <span style="color:{lat_color}">{lat_p50}ms p50 / {lat_p95}ms p95</span></span>
        <span>Orderbook: {ob_p50}ms p50 / {ob_p95}ms p95</span>
        <span>Reconnects (24h): <span style="color:{recon_color}">{recon_total}</span></span>
        <span>Fallback fires: <span style="color:{fb_color}">{fb}</span></span>
        <span>Cycles: {health.get('cycles', 0)}</span>
    </div>
</div>"""


# ---------------------------------------------------------------------------
# Circuit breakers
# ---------------------------------------------------------------------------

def breaker_section(status):
    if not status:
        return ""

    # Kill switch
    if status["kill_switch"]:
        ks_html = f'<span style="color:{C.LOSS};font-weight:700">&#x2716; ACTIVE</span>'
    else:
        ks_html = f'<span style="color:{C.PROFIT}">&#x2714; OFF</span>'

    # Daily loss bar
    pct = status["daily_loss_pct"]
    bar_color = C.LOSS if pct >= 100 else (C.WARN if pct >= 60 else C.PROFIT)
    loss_val = status["daily_loss"]
    loss_max = status["daily_loss_limit"]

    # Consecutive losses
    consec = status["consecutive_losses"]
    consec_max = status["consecutive_loss_max"]
    consec_color = C.LOSS if consec >= consec_max else (C.WARN if consec >= consec_max - 1 else C.TEXT)

    pg_lo, pg_hi = status["price_gate"]
    ee_lo, ee_hi = status["extreme_estimate"]

    return f"""<div class="section">
    <div class="section-title">Circuit Breakers</div>
    <div class="breaker-row">
        <div class="breaker-item"><span style="color:{C.NEUTRAL}">Kill Switch:</span> {ks_html}</div>
        <div class="breaker-item">
            <span style="color:{C.NEUTRAL}">Daily Loss:</span>
            <span class="loss-bar"><span class="loss-bar-fill" style="width:{pct:.0f}%;background:{bar_color}"></span></span>
            <span>${loss_val:.0f}/${loss_max:.0f}</span>
        </div>
        <div class="breaker-item"><span style="color:{C.NEUTRAL}">Consec Losses:</span> <span style="color:{consec_color};font-weight:600">{consec}/{consec_max}</span></div>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:16px;font-size:11px;color:{C.TEXT_DIM};margin-top:8px;border-top:1px solid {C.BORDER};padding-top:8px">
        <span>Min Conv: {status['min_conviction']}</span>
        <span>Edge: {status['edge_threshold']:.0%}</span>
        <span>Price Gate: {pg_lo:.0%}\u2013{pg_hi:.0%}</span>
        <span>Extreme: &lt;{ee_lo} / &gt;{ee_hi}</span>
    </div>
</div>"""
