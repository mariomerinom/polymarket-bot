"""
consolidated_report.py — Cross-pipeline daily aggregation.

Produces two outputs:
  1. An inline "Consolidated Overview" block prepended to the existing
     per-pipeline daily at docs/daily/YYYY-MM-DD.md.
  2. A standalone detail file at docs/daily/consolidated-YYYY-MM-DD.md
     covering all 12 pipelines (the existing daily only hardcodes 5).

Consumes per-pipeline data from daily_report.analyze_pipeline() and
pipeline metadata from pipeline_control. Honors the "always use MCP
tools" rule by iterating pipeline_control.discover_pipelines() which
mirrors tools/botsy_mcp.py discovery logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pipeline_control


# ── Aggregation ──────────────────────────────────────────────────────


def _summary_of(result: dict) -> Optional[dict]:
    """Safely extract the summary dict from a per-pipeline result."""
    if not isinstance(result, dict):
        return None
    if "error" in result:
        return None
    return result.get("summary")


def compute_portfolio_totals(per_pipeline_results: list) -> dict:
    """Aggregate P&L, bets, WR across all pipelines for the day."""
    total_bets = 0
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    total_wagered = 0.0
    pipelines_with_bets = 0

    for result in per_pipeline_results:
        summary = _summary_of(result)
        if not summary:
            continue
        bets = summary.get("resolved_bets") or 0
        if bets > 0:
            pipelines_with_bets += 1
        total_bets += bets
        total_wins += summary.get("wins") or 0
        total_losses += summary.get("losses") or 0
        total_pnl += summary.get("pnl") or 0.0
        total_wagered += summary.get("wagered") or 0.0

    wr = round(total_wins / total_bets * 100, 1) if total_bets > 0 else 0.0

    return {
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "aggregate_wr_pct": wr,
        "total_pnl_usd": round(total_pnl, 2),
        "total_wagered_usd": round(total_wagered, 2),
        "active_pipelines": pipelines_with_bets,
        "pipelines_with_resolved_bets": pipelines_with_bets,
        "total_pipelines": len(per_pipeline_results),
    }


def compute_asset_rollup(per_pipeline_results: list) -> dict:
    """Group per-pipeline P&L by underlying asset (BTC / ETH / SOL / DOGE).

    An asset is only included if at least one of its pipelines had a bet.
    """
    rollup: dict[str, dict] = {}
    for result in per_pipeline_results:
        summary = _summary_of(result)
        if not summary:
            continue
        bets = summary.get("resolved_bets") or 0
        if bets <= 0:
            continue
        pipeline = result.get("pipeline", "")
        asset = pipeline_control.pipeline_to_asset(pipeline)
        bucket = rollup.setdefault(asset, {
            "bets": 0, "wins": 0, "losses": 0,
            "pnl": 0.0, "wagered": 0.0, "pipelines": [],
        })
        bucket["bets"] += bets
        bucket["wins"] += summary.get("wins") or 0
        bucket["losses"] += summary.get("losses") or 0
        bucket["pnl"] += summary.get("pnl") or 0.0
        bucket["wagered"] += summary.get("wagered") or 0.0
        bucket["pipelines"].append(pipeline)

    # Compute WR per bucket
    for asset, b in rollup.items():
        b["wr"] = round(b["wins"] / b["bets"] * 100, 1) if b["bets"] else 0.0
        b["pnl"] = round(b["pnl"], 2)
        b["wagered"] = round(b["wagered"], 2)

    return rollup


# ── Formatting helpers ───────────────────────────────────────────────


def _fmt_pnl(pnl: float) -> str:
    """Format P&L with sign: +$100.00 / -$50.00 / $0.00."""
    sign = "+" if pnl > 0 else ("-" if pnl < 0 else "")
    return f"{sign}${abs(pnl):,.2f}"


def _fmt_pnl_bold(pnl: float) -> str:
    """Bold version for emphasis: **+$100.00**."""
    return f"**{_fmt_pnl(pnl)}**"


# ── Rendering: inline overview block ─────────────────────────────────


def render_overview_block(per_pipeline_results: list, date_str: str) -> str:
    """Short overview block to prepend to the existing daily report."""
    totals = compute_portfolio_totals(per_pipeline_results)
    rollup = compute_asset_rollup(per_pipeline_results)

    lines = [
        "## Consolidated Overview (All 12 Pipelines)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total bets | {totals['total_bets']} |",
    ]
    if totals["total_bets"] > 0:
        lines.append(
            f"| Aggregate WR | {totals['aggregate_wr_pct']}% "
            f"({totals['total_wins']}W-{totals['total_losses']}L) |"
        )
    else:
        lines.append("| Aggregate WR | — (no resolved bets) |")
    lines.extend([
        f"| Total P&L | {_fmt_pnl_bold(totals['total_pnl_usd'])} |",
        f"| Total wagered | ${totals['total_wagered_usd']:,.2f} |",
        f"| Pipelines with resolved bets | {totals['pipelines_with_resolved_bets']} of {totals['total_pipelines']} |",
        f"| Detail | [Full breakdown →](./consolidated-{date_str}.md) |",
        "",
    ])

    if rollup:
        lines.extend([
            "### By Asset",
            "",
            "| Asset | Bets | WR | P&L |",
            "|-------|------|-----|-----|",
        ])
        for asset in ("BTC", "ETH", "SOL", "DOGE"):
            if asset not in rollup:
                continue
            b = rollup[asset]
            lines.append(
                f"| {asset} | {b['bets']} | {b['wr']}% | {_fmt_pnl(b['pnl'])} |"
            )
        lines.append("")

    return "\n".join(lines)


# ── Rendering: detail file ───────────────────────────────────────────


def _render_portfolio_totals_section(totals: dict) -> list:
    return [
        "## 1. Portfolio Totals",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total bets | {totals['total_bets']} |",
        f"| Total wins | {totals['total_wins']} |",
        f"| Total losses | {totals['total_losses']} |",
        f"| Aggregate WR | {totals['aggregate_wr_pct']}% |",
        f"| Total P&L | {_fmt_pnl_bold(totals['total_pnl_usd'])} |",
        f"| Total wagered | ${totals['total_wagered_usd']:,.2f} |",
        f"| Pipelines with resolved bets | {totals['pipelines_with_resolved_bets']} of {totals['total_pipelines']} |",
        "",
    ]


def _render_leaderboard_section(per_pipeline_results: list) -> list:
    lines = [
        "## 2. Pipeline Leaderboard",
        "",
        "All pipelines, sorted by today's P&L (descending).",
        "",
        "| Pipeline | Asset | Mode | Bets | WR | P&L | Signal EHR | Exec EHR | Wagered |",
        "|----------|-------|------|-----:|----|-----|-----------:|---------:|--------:|",
    ]

    # Sort: pipelines with bets first (by P&L desc), then zero-bet pipelines alphabetical,
    # then errored pipelines at the bottom
    def sort_key(r):
        if r.get("error"):
            return (2, r.get("pipeline", ""))
        summary = _summary_of(r)
        if not summary or (summary.get("resolved_bets") or 0) == 0:
            return (1, r.get("pipeline", ""))
        return (0, -(summary.get("pnl") or 0.0))

    for result in sorted(per_pipeline_results, key=sort_key):
        name = result.get("pipeline", "?")
        asset = pipeline_control.pipeline_to_asset(name)
        cfg = pipeline_control.load_pipeline_config(name)
        mode = cfg.get("mode", "?")

        if result.get("error"):
            lines.append(
                f"| {name} | {asset} | {mode} | — | — | ⚠️ error | — | — | — |"
            )
            continue

        summary = _summary_of(result)
        if not summary:
            lines.append(
                f"| {name} | {asset} | {mode} | 0 | — | $0.00 | — | — | — |"
            )
            continue

        bets = summary.get("resolved_bets") or 0
        wr = f"{summary.get('wr')}%" if bets > 0 else "—"
        pnl = _fmt_pnl(summary.get("pnl") or 0.0)
        wagered = f"${summary.get('wagered') or 0:,.2f}"

        ehr = result.get("ehr") or {}
        # Prefer rolling 7d values — single-day is often null for low-activity pipes
        signal_ehr = ehr.get("rolling_signal")
        exec_ehr = ehr.get("rolling_execution")
        signal_ehr_str = f"{signal_ehr:+.3f}" if signal_ehr is not None else "—"
        exec_ehr_str = f"{exec_ehr:+.3f}" if exec_ehr is not None else "—"

        lines.append(
            f"| {name} | {asset} | {mode} | {bets} | {wr} | {pnl} "
            f"| {signal_ehr_str} | {exec_ehr_str} | {wagered} |"
        )
    lines.append("")
    return lines


def _render_asset_rollup_section(rollup: dict) -> list:
    lines = ["## 3. Per-Asset Roll-up", ""]
    if not rollup:
        lines.extend(["_No bets across any asset today._", ""])
        return lines
    lines.extend([
        "| Asset | Pipelines | Bets | WR | P&L | Wagered |",
        "|-------|-----------|-----:|----|-----|--------:|",
    ])
    for asset in ("BTC", "ETH", "SOL", "DOGE"):
        if asset not in rollup:
            continue
        b = rollup[asset]
        pipes = ", ".join(sorted(b["pipelines"]))
        lines.append(
            f"| **{asset}** | {pipes} | {b['bets']} | {b['wr']}% "
            f"| {_fmt_pnl(b['pnl'])} | ${b['wagered']:,.2f} |"
        )
    lines.append("")
    return lines


def _render_ehr_section(per_pipeline_results: list) -> list:
    """Signal vs Execution EHR per pipeline — surfaces the execution gap.

    The analyze_ehr() dict uses keys: signal, execution (today's),
    rolling_signal, rolling_execution, rolling_n. We prefer rolling
    values since single-day EHR is often None for low-activity pipelines.
    """
    lines = [
        "## 4. Signal vs Execution EHR (7-day rolling)",
        "",
        "Gap = signal EHR − execution EHR. The edge that execution destroys.",
        "",
        "| Pipeline | Signal EHR | Exec EHR | n | Gap |",
        "|----------|-----------:|---------:|--:|----:|",
    ]
    any_ehr = False
    for result in per_pipeline_results:
        if not isinstance(result, dict) or result.get("error"):
            continue
        name = result.get("pipeline", "?")
        ehr = result.get("ehr") or {}
        signal_ehr = ehr.get("rolling_signal")
        exec_ehr = ehr.get("rolling_execution")
        n = ehr.get("rolling_n") or 0
        if signal_ehr is None and exec_ehr is None:
            continue
        any_ehr = True
        gap = None
        if signal_ehr is not None and exec_ehr is not None:
            gap = signal_ehr - exec_ehr
        gap_str = f"{gap*100:+.1f}¢/$" if gap is not None else "—"
        s_str = f"{signal_ehr:+.4f}" if signal_ehr is not None else "—"
        e_str = f"{exec_ehr:+.4f}" if exec_ehr is not None else "—"
        lines.append(f"| {name} | {s_str} | {e_str} | {n} | {gap_str} |")
    if not any_ehr:
        lines.append("| _no EHR data_ |  |  |  |  |")
    lines.append("")
    return lines


def _render_shadow_maker_section(per_pipeline_results: list) -> list:
    """Shadow maker aggregate across all pipelines logging shadows."""
    lines = [
        "## 5. Shadow Maker (Phase 1)",
        "",
        "Hypothetical maker fills — what would have filled if we posted passively.",
        "",
        "| Pipeline | Logged | Filled | Fill Rate | Adverse % | Shadow EHR |",
        "|----------|-------:|-------:|----------:|----------:|-----------:|",
    ]
    any_shadow = False
    total_logged = 0
    total_filled = 0
    for result in per_pipeline_results:
        if result.get("error"):
            continue
        sm = result.get("shadow_maker")
        if not sm:
            continue
        name = result.get("pipeline", "?")
        n_logged = sm.get("n_logged") or 0
        n_filled = sm.get("n_filled") or 0
        fill_rate = sm.get("fill_rate")
        adverse = sm.get("adverse_pct")
        shadow_ehr = sm.get("shadow_ehr")
        if n_logged == 0:
            continue
        any_shadow = True
        total_logged += n_logged
        total_filled += n_filled
        fr_str = f"{fill_rate*100:.1f}%" if fill_rate is not None else "—"
        ad_str = f"{adverse*100:.1f}%" if adverse is not None else "—"
        ehr_str = f"{shadow_ehr:+.4f}" if shadow_ehr is not None else "—"
        lines.append(
            f"| {name} | {n_logged} | {n_filled} | {fr_str} | {ad_str} | {ehr_str} |"
        )
    if not any_shadow:
        lines.append("| _no shadow data today_ |  |  |  |  |  |")
    lines.append("")
    return lines


def _render_alerts_section(per_pipeline_results: list) -> list:
    lines = ["## 6. Alerts (All Pipelines)", ""]
    any_alerts = False
    for result in per_pipeline_results:
        if result.get("error"):
            continue
        alerts = result.get("alerts") or []
        if not alerts:
            continue
        any_alerts = True
        name = result.get("pipeline", "?")
        lines.append(f"### {name}")
        for alert in alerts:
            if isinstance(alert, dict):
                sev = alert.get("severity", "info")
                msg = alert.get("message", str(alert))
                lines.append(f"- **[{sev}]** {msg}")
            else:
                lines.append(f"- {alert}")
        lines.append("")
    if not any_alerts:
        lines.append("_No alerts across any pipeline today._")
        lines.append("")
    return lines


def _render_engine_health_section() -> list:
    """Engine health from data/ws_metrics.json (if present)."""
    lines = ["## 7. Engine Health", ""]
    metrics_path = Path(__file__).parent.parent / "data" / "ws_metrics.json"
    if not metrics_path.exists():
        lines.append("_ws_metrics.json not found — engine may not be running._")
        lines.append("")
        return lines
    try:
        m = json.loads(metrics_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        lines.append(f"_Could not read engine metrics: {e}_")
        lines.append("")
        return lines

    lines.extend([
        "| Feed | Status | Reconnects (24h) |",
        "|------|--------|-----------------:|",
    ])
    for feed in ("bybit_spot", "bybit_linear", "polymarket"):
        f = m.get(feed, {})
        status = f.get("status", "?")
        reconnects = f.get("reconnects_24h", 0)
        lines.append(f"| {feed} | {status} | {reconnects} |")
    lines.append("")

    dispatch = m.get("dispatch_latency_ms", {})
    event_lag = m.get("event_lag_ms", {})
    ta_build = m.get("ta_build_ms", {})
    fanout = m.get("pipeline_fanout_ms", {})
    lab = m.get("strategy_lab_ms", {})
    total_wall = m.get("total_dispatch_wall_ms", {})
    slowest = m.get("slowest_pipeline_runtime_ms", {})
    orderbook = m.get("orderbook_age_ms", {})
    lines.extend([
        "| Metric | p50 | p95 | Samples |",
        "|--------|----:|----:|--------:|",
        f"| Production dispatch latency (ms) | {dispatch.get('p50','?')} | {dispatch.get('p95','?')} | {dispatch.get('samples',0)} |",
        f"| Bybit event lag (ms) | {event_lag.get('p50','?')} | {event_lag.get('p95','?')} | {event_lag.get('samples',0)} |",
        f"| TA build (ms) | {ta_build.get('p50','?')} | {ta_build.get('p95','?')} | {ta_build.get('samples',0)} |",
        f"| Pipeline fanout (ms) | {fanout.get('p50','?')} | {fanout.get('p95','?')} | {fanout.get('samples',0)} |",
        f"| Strategy Lab runtime (ms) | {lab.get('p50','?')} | {lab.get('p95','?')} | {lab.get('samples',0)} |",
        f"| Total dispatch wall time (ms) | {total_wall.get('p50','?')} | {total_wall.get('p95','?')} | {total_wall.get('samples',0)} |",
        f"| True orderbook age (ms) | {orderbook.get('p50','?')} | {orderbook.get('p95','?')} | {orderbook.get('samples',0)} |",
        "",
        f"- Slowest pipeline runtime: {slowest.get('pipeline') or 'N/A'} p95={slowest.get('p95', 0)}ms ({slowest.get('samples', 0)} samples)",
        f"- Orderbook cache: {(m.get('orderbook_cache') or {}).get('tokens', 0)} tokens, {(m.get('orderbook_cache') or {}).get('token_set_changes_24h', 0)} token-set changes (24h)",
        f"- Cycles: {m.get('cycles', 0)}",
        f"- Fallback fires (24h): {m.get('fallback_fires_24h', 0)}",
        f"- Engine start: {m.get('engine_start', '?')}",
        "",
    ])
    lines.extend(_orderbook_diagnostic_lines(m))
    lines.append("")
    lines.extend(_render_btc5m_readiness_section())
    lines.append("")

    # Kill switch status
    kill_file = Path(__file__).parent.parent / "data" / "KILL_SWITCH"
    if kill_file.exists():
        lines.append("⚠️ **KILL_SWITCH file is PRESENT** — trading is halted.")
    else:
        lines.append("✅ Kill switch clear (no `data/KILL_SWITCH` file).")
    lines.append("")
    return lines


def _render_btc5m_readiness_section() -> list[str]:
    try:
        import sqlite3
        from canary_readiness import (
            btc5m_delayed_policy_blockers,
            btc5m_live_canary_blockers,
        )
        db_path = pipeline_control.discover_pipelines()["btc_5m"]
        db = sqlite3.connect(str(db_path))
        try:
            live_blockers = btc5m_live_canary_blockers(db)
            delayed_blockers = btc5m_delayed_policy_blockers(db)
        finally:
            db.close()
    except Exception as exc:
        live_blockers = [f"canary_readiness_unavailable ({exc})"]
        delayed_blockers = []

    blockers = live_blockers + delayed_blockers
    lines = [
        "### BTC 5m Production Readiness",
        "",
        f"- Verdict: {'READY' if not blockers else 'BLOCKED'}",
    ]
    if live_blockers:
        lines.append(
            "- Live canary blockers: " + "; ".join(str(b) for b in live_blockers)
        )
    if delayed_blockers:
        lines.append(
            "- Delayed FAK blockers: " + "; ".join(str(b) for b in delayed_blockers)
        )
    if not blockers:
        lines.append("- No live-canary or delayed-policy blockers.")
    return lines


def _dominant_orderbook_cause(metrics: dict) -> str | None:
    cache = metrics.get("orderbook_cache") or {}
    orderbook = metrics.get("orderbook_age_ms") or metrics.get("orderbook_age") or {}
    p95 = orderbook.get("p95") or 0
    if p95 < 2_000:
        return None
    if (cache.get("book_events_24h", 0) + cache.get("price_change_events_24h", 0)) == 0:
        return "no websocket book/price_change events"
    if cache.get("price_change_missing_snapshot", 0) > cache.get("price_change_invalid_bbo", 0):
        return "missing snapshots before price_change"
    if cache.get("price_change_invalid_bbo", 0):
        return "invalid BBO from price_change"
    stale_reasons = cache.get("stale_reasons") or {}
    if stale_reasons:
        reason, _ = max(stale_reasons.items(), key=lambda kv: kv[1])
        if reason == "missing_cache_entry":
            return "token not subscribed or not cached"
        if reason == "stale_updated_at":
            return "no recent websocket deltas"
        return reason.replace("_", " ")
    if cache.get("resubscribe_debounced", 0) or cache.get("resubscribe_executed", 0):
        return "subscription reconnect churn"
    return "unknown orderbook freshness cause"


def _orderbook_diagnostic_lines(metrics: dict) -> list[str]:
    cache = metrics.get("orderbook_cache") or {}
    ignored = cache.get("ignored_event_types") or {}
    stale_reasons = cache.get("stale_reasons") or {}
    attempts = cache.get("rest_snapshot_seed_attempts", 0)
    successes = cache.get("rest_snapshot_seed_success", 0)
    cause = _dominant_orderbook_cause(metrics)
    lines = [
        (
            "- Polymarket events: "
            f"book={cache.get('book_events_24h', 0)}, "
            f"price_change={cache.get('price_change_events_24h', 0)}, "
            f"ignored={ignored}"
        ),
        (
            "- Orderbook freshness detail: "
            f"fresh/stale tokens: {cache.get('fresh_tokens_now', 0)}/"
            f"{cache.get('stale_tokens_now', 0)}, "
            f"updated last 60s/5m: {cache.get('tokens_updated_last_60s', 0)}/"
            f"{cache.get('tokens_updated_last_5m', 0)}, "
            f"stale reasons: {stale_reasons}"
        ),
        (
            "- REST snapshot seed: "
            f"{successes}/{attempts} successful "
            f"(missing={cache.get('rest_snapshot_seed_missing', 0)}, "
            f"invalid_bbo={cache.get('rest_snapshot_seed_invalid_bbo', 0)})"
        ),
        (
            "- Polymarket resubscribe: "
            f"resubscribe debounced/executed: {cache.get('resubscribe_debounced', 0)}/"
            f"{cache.get('resubscribe_executed', 0)}, "
            f"added/removed tokens: {cache.get('token_set_added', 0)}/"
            f"{cache.get('token_set_removed', 0)}"
        ),
    ]
    if cause:
        lines.append(f"- Orderbook freshness decision: dominant cause: {cause}")
    return lines


def _render_circuit_breaker_section(per_pipeline_results: list) -> list:
    lines = [
        "## 8. Circuit Breaker Status",
        "",
        "Daily loss vs $300 per-pipeline limit.",
        "",
        "| Pipeline | Daily Loss | Breaker Limit | Tripped? |",
        "|----------|-----------:|--------------:|:--------:|",
    ]
    any_data = False
    for result in per_pipeline_results:
        if result.get("error"):
            continue
        orders = result.get("orders")
        if not orders:
            continue
        name = result.get("pipeline", "?")
        daily_loss = orders.get("daily_loss")
        breaker_limit = orders.get("breaker_limit")
        tripped = orders.get("breaker_tripped")
        if daily_loss is None and breaker_limit is None:
            continue
        any_data = True
        loss_str = f"${daily_loss:.2f}" if daily_loss is not None else "—"
        lim_str = f"${breaker_limit}" if breaker_limit is not None else "—"
        trip_str = "YES" if tripped else "No"
        lines.append(f"| {name} | {loss_str} | {lim_str} | {trip_str} |")
    if not any_data:
        lines.append("| _no order data today_ |  |  |  |")
    lines.append("")
    return lines


def _render_config_snapshot_section() -> list:
    """Pipeline config snapshot — mode, bet size for all 12."""
    lines = [
        "## 9. Pipeline Config Snapshot",
        "",
        "| Pipeline | Mode | Bet Size | Asset |",
        "|----------|------|---------:|-------|",
    ]
    try:
        cfg_path = Path(__file__).parent.parent / "config" / "pipelines.json"
        cfg = json.loads(cfg_path.read_text())
        for name, spec in sorted(cfg.get("pipelines", {}).items()):
            mode = spec.get("mode", "?")
            bet = spec.get("bet_size")
            bet_str = str(bet) if bet is not None else "default"
            asset = pipeline_control.pipeline_to_asset(name)
            lines.append(f"| {name} | {mode} | {bet_str} | {asset} |")
    except (OSError, json.JSONDecodeError):
        lines.append("| _could not load pipelines.json_ |  |  |  |")
    lines.append("")
    return lines


def render_consolidated_detail(per_pipeline_results: list, date_str: str) -> str:
    """Render the full consolidated detail markdown file."""
    totals = compute_portfolio_totals(per_pipeline_results)
    rollup = compute_asset_rollup(per_pipeline_results)

    lines = [
        f"# Consolidated Daily Report — {date_str}",
        "",
        "Cross-pipeline aggregation across all 12 BOTSY pipelines. "
        "Per-pipeline drill-down is in the companion "
        f"[{date_str}.md]({date_str}.md) file.",
        "",
    ]

    lines.extend(_render_portfolio_totals_section(totals))
    lines.extend(_render_leaderboard_section(per_pipeline_results))
    lines.extend(_render_asset_rollup_section(rollup))
    lines.extend(_render_ehr_section(per_pipeline_results))
    lines.extend(_render_shadow_maker_section(per_pipeline_results))
    lines.extend(_render_alerts_section(per_pipeline_results))
    lines.extend(_render_engine_health_section())
    lines.extend(_render_circuit_breaker_section(per_pipeline_results))
    lines.extend(_render_config_snapshot_section())

    return "\n".join(lines)


# ── Orchestration ────────────────────────────────────────────────────


def analyze_all_pipelines(date_str: str, analyze_fn=None) -> list:
    """Run analyze_pipeline for every pipeline in config/pipelines.json.

    Uses pipeline_control.discover_pipelines() which mirrors the MCP's
    discovery logic — single source of truth for pipeline→DB mapping.

    analyze_fn: optional injection for testing; defaults to daily_report.analyze_pipeline.
    """
    if analyze_fn is None:
        # Lazy import to avoid circular dep at module load time
        from daily_report import analyze_pipeline
        analyze_fn = analyze_pipeline

    results = []
    for name, db_path in sorted(pipeline_control.discover_pipelines().items()):
        try:
            data = analyze_fn(str(db_path), date_str)
            if data is None:
                # No predictions for this date — still include with empty summary
                results.append({
                    "pipeline": name,
                    "summary": None,
                })
            else:
                results.append({"pipeline": name, **data})
        except Exception as e:
            results.append({"pipeline": name, "error": str(e)})
    return results


def write_consolidated_detail(per_pipeline_results: list, date_str: str,
                              daily_dir: Path) -> Path:
    """Write the consolidated detail markdown file. Returns its path."""
    md = render_consolidated_detail(per_pipeline_results, date_str)
    out_path = daily_dir / f"consolidated-{date_str}.md"
    out_path.write_text(md)
    return out_path
