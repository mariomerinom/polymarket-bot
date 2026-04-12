#!/usr/bin/env python3
"""
botsy_mcp.py — MCP server for querying BOTSY trading pipeline databases.

Exposes purpose-built tools for the questions we actually ask:
  - Win rate, P&L, bet counts across pipelines
  - Judge shadow performance (accepted vs rejected)
  - Fill diagnostics
  - Regime analysis
  - Raw SQL escape hatch

Usage (via Claude Code settings.json):
  "command": "/path/to/mcp-venv/bin/python3",
  "args": ["/path/to/tools/botsy_mcp.py"]
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("botsy")

# ── Database paths ────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PIPELINES_JSON = ROOT_DIR / "config" / "pipelines.json"

ASSET_DAILY_DB = DATA_DIR / "asset_daily.db"

# Legacy name → DB path for pipelines that don't follow the convention
_LEGACY_DB_NAMES = {
    "btc_5m": "predictions.db",
    "btc_15m": "predictions_15m.db",
    "eth_5m": "predictions_eth.db",
    "kalshi": "predictions_kalshi.db",
    "bybit": "predictions_bybit.db",
}


def _pipeline_to_db_path(name: str) -> Path:
    """Map a pipeline name to its DB file path.

    Conventions:
      - Legacy pipelines: _LEGACY_DB_NAMES lookup
      - Perp pipelines ({asset}_{exchange}): predictions_{exchange}_{asset}.db
        e.g. eth_bybit -> predictions_bybit_eth.db
      - Simple pipelines: predictions_{name}.db
        e.g. hl -> predictions_hl.db
    """
    if name in _LEGACY_DB_NAMES:
        return DATA_DIR / _LEGACY_DB_NAMES[name]

    # Perp pipeline pattern: {asset}_{exchange} -> predictions_{exchange}_{asset}.db
    _EXCHANGES = {"bybit", "hl"}
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in _EXCHANGES:
        asset, exchange = parts
        return DATA_DIR / f"predictions_{exchange}_{asset}.db"

    return DATA_DIR / f"predictions_{name}.db"


def _discover_pipelines() -> dict[str, Path]:
    """Discover all pipelines from config/pipelines.json.

    Returns only pipelines whose DB file exists on disk.
    """
    pipelines = {}
    if PIPELINES_JSON.exists():
        cfg = json.loads(PIPELINES_JSON.read_text())
        for name in cfg.get("pipelines", {}):
            path = _pipeline_to_db_path(name)
            if path.exists():
                pipelines[name] = path
    return pipelines


def _connect(pipeline: str) -> sqlite3.Connection:
    """Get a read-only connection to a pipeline DB."""
    pipelines = _discover_pipelines()
    path = pipelines.get(pipeline)
    if not path:
        raise ValueError(f"Unknown or missing pipeline: {pipeline}. "
                         f"Available: {', '.join(sorted(pipelines.keys()))}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ── Tool: Win Rate ────────────────────────────────────────────────────────

@mcp.tool()
def win_rate(
    pipeline: str = "btc_5m",
    days: int = 7,
    min_conviction: int = 3,
) -> str:
    """Get win rate, P&L, and bet count for a pipeline.

    Args:
        pipeline: Pipeline name (auto-discovered from config/pipelines.json)
        days: Lookback period in days (default 7)
        min_conviction: Minimum conviction to count as a bet (default 3)

    Returns:
        JSON with total_bets, wins, losses, win_rate, estimated_pnl
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                p.estimate,
                p.conviction_score,
                m.outcome,
                m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
              AND p.conviction_score >= ?
              AND p.predicted_at >= datetime('now', ?)
        """, (min_conviction, f"-{days} days")).fetchall()

        wins = losses = 0
        pnl = 0.0
        for r in rows:
            direction_up = r["estimate"] >= 0.5
            won = (direction_up and r["outcome"] == 1) or \
                  (not direction_up and r["outcome"] == 0)
            if won:
                wins += 1
                # Approximate P&L: bet $25, win pays ~$25/price - $25
                price = r["price_yes"] if direction_up else (1 - r["price_yes"])
                pnl += 25 * (1 / max(price, 0.01) - 1) if price < 1 else 0
            else:
                losses += 1
                pnl -= 25

        total = wins + losses
        wr = round(wins / total * 100, 1) if total > 0 else 0

        return json.dumps({
            "pipeline": pipeline,
            "days": days,
            "min_conviction": min_conviction,
            "total_bets": total,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": wr,
            "estimated_pnl": round(pnl, 2),
        }, indent=2)
    finally:
        db.close()


# ── Tool: Recent Predictions ─────────────────────────────────────────────

@mcp.tool()
def recent_predictions(
    pipeline: str = "btc_5m",
    limit: int = 20,
    min_conviction: int = 0,
) -> str:
    """Get the most recent predictions with outcomes.

    Args:
        pipeline: Pipeline name
        limit: Number of predictions to return (default 20)
        min_conviction: Filter by minimum conviction (default 0 = all)

    Returns:
        JSON array of predictions with direction, conviction, outcome, judge verdict
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                p.predicted_at,
                p.estimate,
                p.conviction_score,
                p.regime,
                p.reasoning,
                m.outcome,
                m.resolved
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE p.conviction_score >= ?
            ORDER BY p.predicted_at DESC
            LIMIT ?
        """, (min_conviction, limit)).fetchall()

        results = []
        for r in rows:
            direction = "UP" if r["estimate"] >= 0.5 else "DOWN"
            reasoning = {}
            try:
                reasoning = json.loads(r["reasoning"]) if r["reasoning"] else {}
            except Exception:
                pass

            judge = reasoning.get("judge")
            outcome = None
            won = None
            if r["resolved"]:
                outcome = "UP" if r["outcome"] == 1 else "DOWN"
                won = (direction == outcome)

            entry = {
                "predicted_at": r["predicted_at"],
                "direction": direction,
                "conviction": r["conviction_score"],
                "regime": r["regime"],
                "resolved": bool(r["resolved"]),
                "outcome": outcome,
                "won": won,
            }
            if judge:
                entry["judge_p"] = judge.get("p_success")
                entry["judge_bet"] = judge.get("should_bet")
            results.append(entry)

        return json.dumps(results, indent=2)
    finally:
        db.close()


# ── Tool: Judge Shadow Performance ───────────────────────────────────────

@mcp.tool()
def judge_performance(
    pipeline: str = "btc_5m",
    days: int = 30,
) -> str:
    """Analyze ML Judge shadow performance — accepted vs rejected bets.

    Shows how the Judge would have filtered bets if it were live.
    Only counts resolved predictions where the Judge evaluated.

    Args:
        pipeline: Pipeline name (default btc_5m)
        days: Lookback period in days

    Returns:
        JSON with baseline, accepted, and rejected win rates + P&L
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                p.estimate,
                p.conviction_score,
                p.reasoning,
                m.outcome,
                m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
              AND p.conviction_score >= 3
              AND p.predicted_at >= datetime('now', ?)
        """, (f"-{days} days",)).fetchall()

        baseline = {"bets": 0, "wins": 0, "pnl": 0.0}
        accepted = {"bets": 0, "wins": 0, "pnl": 0.0}
        rejected = {"bets": 0, "wins": 0, "pnl": 0.0}
        no_judge = 0

        for r in rows:
            reasoning = {}
            try:
                reasoning = json.loads(r["reasoning"]) if r["reasoning"] else {}
            except Exception:
                pass

            direction_up = r["estimate"] >= 0.5
            won = (direction_up and r["outcome"] == 1) or \
                  (not direction_up and r["outcome"] == 0)
            price = r["price_yes"] if direction_up else (1 - r["price_yes"])
            bet_pnl = 25 * (1 / max(price, 0.01) - 1) if won and price < 1 else -25 if not won else 0

            baseline["bets"] += 1
            baseline["wins"] += int(won)
            baseline["pnl"] += bet_pnl

            judge = reasoning.get("judge")
            if judge and "p_success" in judge:
                bucket = accepted if judge.get("should_bet") else rejected
                bucket["bets"] += 1
                bucket["wins"] += int(won)
                bucket["pnl"] += bet_pnl
            else:
                no_judge += 1

        def _stats(d):
            wr = round(d["wins"] / d["bets"] * 100, 1) if d["bets"] > 0 else 0
            return {**d, "win_rate_pct": wr, "pnl": round(d["pnl"], 2)}

        return json.dumps({
            "pipeline": pipeline,
            "days": days,
            "baseline": _stats(baseline),
            "judge_accepted": _stats(accepted),
            "judge_rejected": _stats(rejected),
            "no_judge_score": no_judge,
            "judge_coverage_pct": round(
                (accepted["bets"] + rejected["bets"]) /
                max(baseline["bets"], 1) * 100, 1),
        }, indent=2)
    finally:
        db.close()


# ── Tool: P&L by Day ─────────────────────────────────────────────────────

@mcp.tool()
def pnl_by_day(
    pipeline: str = "btc_5m",
    days: int = 14,
) -> str:
    """Get daily P&L breakdown for a pipeline.

    Args:
        pipeline: Pipeline name
        days: Number of days to show

    Returns:
        JSON array of daily stats: date, bets, wins, losses, win_rate, pnl
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                date(p.predicted_at) as day,
                p.estimate,
                p.conviction_score,
                m.outcome,
                m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
              AND p.conviction_score >= 3
              AND p.predicted_at >= datetime('now', ?)
            ORDER BY p.predicted_at
        """, (f"-{days} days",)).fetchall()

        daily = {}
        for r in rows:
            day = r["day"]
            if day not in daily:
                daily[day] = {"date": day, "bets": 0, "wins": 0, "losses": 0, "pnl": 0.0}

            direction_up = r["estimate"] >= 0.5
            won = (direction_up and r["outcome"] == 1) or \
                  (not direction_up and r["outcome"] == 0)
            price = r["price_yes"] if direction_up else (1 - r["price_yes"])
            bet_pnl = 25 * (1 / max(price, 0.01) - 1) if won and price < 1 else -25 if not won else 0

            daily[day]["bets"] += 1
            if won:
                daily[day]["wins"] += 1
            else:
                daily[day]["losses"] += 1
            daily[day]["pnl"] += bet_pnl

        result = []
        for d in sorted(daily.values(), key=lambda x: x["date"]):
            d["win_rate_pct"] = round(d["wins"] / d["bets"] * 100, 1) if d["bets"] > 0 else 0
            d["pnl"] = round(d["pnl"], 2)
            result.append(d)

        return json.dumps(result, indent=2)
    finally:
        db.close()


# ── Tool: Orders & Fills ─────────────────────────────────────────────────

@mcp.tool()
def order_summary(
    pipeline: str = "btc_5m",
    days: int = 7,
) -> str:
    """Get order execution summary — fills, expirations, paper vs live.

    Args:
        pipeline: Pipeline name
        days: Lookback period

    Returns:
        JSON with order counts by status, fill rate, total P&L
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                status,
                mode,
                pnl,
                placed_at
            FROM orders
            WHERE placed_at >= datetime('now', ?)
        """, (f"-{days} days",)).fetchall()

        by_status = {}
        by_mode = {}
        total_pnl = 0.0
        settled = 0

        for r in rows:
            s = r["status"] or "unknown"
            m = r["mode"] or "unknown"
            by_status[s] = by_status.get(s, 0) + 1
            by_mode[m] = by_mode.get(m, 0) + 1
            if r["pnl"] is not None:
                total_pnl += r["pnl"]
                settled += 1

        return json.dumps({
            "pipeline": pipeline,
            "days": days,
            "total_orders": len(rows),
            "by_status": by_status,
            "by_mode": by_mode,
            "settled_orders": settled,
            "total_pnl": round(total_pnl, 2),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# ── Tool: Regime Breakdown ───────────────────────────────────────────────

@mcp.tool()
def regime_breakdown(
    pipeline: str = "btc_5m",
    days: int = 14,
) -> str:
    """Win rate broken down by regime (vol bucket × trend direction).

    Args:
        pipeline: Pipeline name
        days: Lookback period

    Returns:
        JSON with win rate per regime label
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                p.regime,
                p.estimate,
                m.outcome
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
              AND p.conviction_score >= 3
              AND p.predicted_at >= datetime('now', ?)
        """, (f"-{days} days",)).fetchall()

        regimes = {}
        for r in rows:
            regime = r["regime"] or "UNKNOWN"
            if regime not in regimes:
                regimes[regime] = {"bets": 0, "wins": 0}

            direction_up = r["estimate"] >= 0.5
            won = (direction_up and r["outcome"] == 1) or \
                  (not direction_up and r["outcome"] == 0)
            regimes[regime]["bets"] += 1
            regimes[regime]["wins"] += int(won)

        result = []
        for regime, stats in sorted(regimes.items(),
                                     key=lambda x: x[1]["bets"], reverse=True):
            wr = round(stats["wins"] / stats["bets"] * 100, 1) if stats["bets"] > 0 else 0
            result.append({
                "regime": regime,
                "bets": stats["bets"],
                "wins": stats["wins"],
                "win_rate_pct": wr,
            })

        return json.dumps(result, indent=2)
    finally:
        db.close()


# ── Tool: Pipeline Overview ──────────────────────────────────────────────

@mcp.tool()
def pipeline_overview() -> str:
    """Quick overview of all pipelines — last prediction time, total bets, recent WR.

    Returns:
        JSON array with status for each pipeline
    """
    results = []
    for name, path in sorted(_discover_pipelines().items()):
        if not path.exists():
            results.append({"pipeline": name, "status": "missing"})
            continue

        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row

            # Last prediction
            last = db.execute(
                "SELECT predicted_at, conviction_score FROM predictions "
                "ORDER BY predicted_at DESC LIMIT 1"
            ).fetchone()

            # Recent WR (7 days, conv >= 3)
            wr_rows = db.execute("""
                SELECT p.estimate, m.outcome
                FROM predictions p
                JOIN markets m ON p.market_id = m.id
                WHERE m.resolved = 1
                  AND p.conviction_score >= 3
                  AND p.predicted_at >= datetime('now', '-7 days')
            """).fetchall()

            wins = sum(1 for r in wr_rows
                       if (r["estimate"] >= 0.5 and r["outcome"] == 1) or
                          (r["estimate"] < 0.5 and r["outcome"] == 0))
            total = len(wr_rows)

            # Total resolved bets all time
            total_all = db.execute("""
                SELECT COUNT(*) FROM predictions p
                JOIN markets m ON p.market_id = m.id
                WHERE m.resolved = 1 AND p.conviction_score >= 3
            """).fetchone()[0]

            results.append({
                "pipeline": name,
                "last_prediction": last["predicted_at"] if last else None,
                "last_conviction": last["conviction_score"] if last else None,
                "bets_7d": total,
                "wins_7d": wins,
                "wr_7d_pct": round(wins / total * 100, 1) if total > 0 else None,
                "total_resolved_bets": total_all,
            })
            db.close()
        except Exception as e:
            results.append({"pipeline": name, "error": str(e)})

    return json.dumps(results, indent=2)


# ── Tool: Fill Diagnostics ───────────────────────────────────────────────

@mcp.tool()
def fill_diagnostics(
    pipeline: str = "btc_5m",
    days: int = 7,
) -> str:
    """Fill rate and adverse selection analysis from fill_diagnostic table.

    Args:
        pipeline: Pipeline name
        days: Lookback period

    Returns:
        JSON with fill counts by result code, adverse selection stats
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT result, outcome
            FROM fill_diagnostic
            WHERE pipeline = ?
              AND timestamp >= datetime('now', ?)
        """, (pipeline, f"-{days} days")).fetchall()

        by_result = {}
        filled_won = filled_lost = 0
        skipped_would_won = skipped_would_lost = 0

        for r in rows:
            result = r["result"]
            by_result[result] = by_result.get(result, 0) + 1

            if r["outcome"] is not None:
                won = r["outcome"] == 1
                if result in ("filled_full", "filled_partial"):
                    if won:
                        filled_won += 1
                    else:
                        filled_lost += 1
                elif result.startswith("skipped_") or result == "killed_fok":
                    if won:
                        skipped_would_won += 1
                    else:
                        skipped_would_lost += 1

        total_filled = filled_won + filled_lost
        total_skipped = skipped_would_won + skipped_would_lost

        return json.dumps({
            "pipeline": pipeline,
            "days": days,
            "total_records": len(rows),
            "by_result": by_result,
            "filled_wr_pct": round(filled_won / total_filled * 100, 1) if total_filled > 0 else None,
            "skipped_would_have_won_pct": round(
                skipped_would_won / total_skipped * 100, 1) if total_skipped > 0 else None,
            "adverse_selection": skipped_would_won > skipped_would_lost if total_skipped > 5 else None,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "note": "fill_diagnostic table may not exist"})
    finally:
        db.close()


# ── Tool: Daily Regime Data ──────────────────────────────────────────────

@mcp.tool()
def daily_regime(
    asset: str = "BTC",
    days: int = 7,
) -> str:
    """Get daily regime data from asset_daily.db.

    Args:
        asset: Asset name (BTC or ETH)
        days: Number of days

    Returns:
        JSON array with daily regime metrics
    """
    if not ASSET_DAILY_DB.exists():
        return json.dumps({"error": "asset_daily.db not found"})

    db = sqlite3.connect(f"file:{ASSET_DAILY_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute("""
            SELECT date, open, high, low, close,
                   range_pct, realized_vol, body_pct, velocity,
                   trend_label, range_zscore, velocity_zscore
            FROM asset_daily
            WHERE asset = ?
            ORDER BY date DESC
            LIMIT ?
        """, (asset.upper(), days)).fetchall()

        return json.dumps(_rows_to_dicts(rows), indent=2)
    finally:
        db.close()


# ── Tool: Raw SQL ─────────────────────────────────────────────────────────

@mcp.tool()
def query(
    pipeline: str,
    sql: str,
) -> str:
    """Execute a read-only SQL query against any pipeline database.

    Use this for ad-hoc analysis when the other tools don't cover your question.
    Only SELECT queries are allowed.

    Args:
        pipeline: Pipeline name (auto-discovered from config/pipelines.json)
                  or 'asset_daily' for the daily regime DB
        sql: SQL SELECT query to execute

    Returns:
        JSON array of result rows
    """
    sql_stripped = sql.strip().upper()
    if not sql_stripped.startswith("SELECT") and not sql_stripped.startswith("WITH"):
        return json.dumps({"error": "Only SELECT/WITH queries allowed"})

    if pipeline == "asset_daily":
        if not ASSET_DAILY_DB.exists():
            return json.dumps({"error": "asset_daily.db not found"})
        db = sqlite3.connect(f"file:{ASSET_DAILY_DB}?mode=ro", uri=True)
    else:
        db = _connect(pipeline)

    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(sql).fetchall()
        return json.dumps(_rows_to_dicts(rows), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        db.close()


# ── Tool: Streak Analysis ────────────────────────────────────────────────

@mcp.tool()
def streak_analysis(
    pipeline: str = "btc_5m",
    days: int = 7,
) -> str:
    """Analyze current win/loss streaks and direction patterns.

    Args:
        pipeline: Pipeline name
        days: Lookback period

    Returns:
        JSON with current streak, longest streaks, direction bias
    """
    db = _connect(pipeline)
    try:
        rows = db.execute("""
            SELECT
                p.predicted_at,
                p.estimate,
                m.outcome
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
              AND p.conviction_score >= 3
              AND p.predicted_at >= datetime('now', ?)
            ORDER BY p.predicted_at DESC
        """, (f"-{days} days",)).fetchall()

        if not rows:
            return json.dumps({"pipeline": pipeline, "bets": 0, "message": "No resolved bets"})

        # Build win/loss sequence
        results = []
        up_count = down_count = 0
        for r in rows:
            direction_up = r["estimate"] >= 0.5
            won = (direction_up and r["outcome"] == 1) or \
                  (not direction_up and r["outcome"] == 0)
            results.append({"won": won, "direction": "UP" if direction_up else "DOWN"})
            if direction_up:
                up_count += 1
            else:
                down_count += 1

        # Current streak (from most recent)
        current_type = results[0]["won"]
        current_streak = 0
        for r in results:
            if r["won"] == current_type:
                current_streak += 1
            else:
                break

        # Longest win and loss streaks
        max_win = max_loss = 0
        cur_win = cur_loss = 0
        for r in results:
            if r["won"]:
                cur_win += 1
                cur_loss = 0
                max_win = max(max_win, cur_win)
            else:
                cur_loss += 1
                cur_win = 0
                max_loss = max(max_loss, cur_loss)

        return json.dumps({
            "pipeline": pipeline,
            "days": days,
            "total_bets": len(results),
            "current_streak": current_streak,
            "current_streak_type": "WIN" if current_type else "LOSS",
            "longest_win_streak": max_win,
            "longest_loss_streak": max_loss,
            "direction_bias": {
                "up_bets": up_count,
                "down_bets": down_count,
                "pct_up": round(up_count / len(results) * 100, 1),
            },
        }, indent=2)
    finally:
        db.close()


# ── Tool: Strategy Lab Performance ──────────────────────────────────────

STRATEGY_LAB_DB = DATA_DIR / "strategy_lab.db"


@mcp.tool()
def lab_performance(
    strategy: str = "",
    pipeline: str = "",
    days: int = 7,
) -> str:
    """Strategy Lab results: WR, P&L, bet count per strategy.

    Args:
        strategy: Filter by strategy name (empty = all strategies)
        pipeline: Filter by pipeline name (empty = all pipelines)
        days: Lookback period in days (default 7)

    Returns:
        JSON array with per-strategy stats: bets, wins, WR, P&L, days to gate
    """
    if not STRATEGY_LAB_DB.exists():
        return json.dumps({"error": "strategy_lab.db not found — lab not running yet"})

    db = sqlite3.connect(f"file:{STRATEGY_LAB_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        where_clauses = ["outcome IS NOT NULL",
                         f"predicted_at >= datetime('now', '-{days} days')"]
        params = []
        if strategy:
            where_clauses.append("strategy = ?")
            params.append(strategy)
        if pipeline:
            where_clauses.append("pipeline = ?")
            params.append(pipeline)

        where = " AND ".join(where_clauses)

        rows = db.execute(f"""
            SELECT strategy, pipeline,
                   COUNT(*) as bets,
                   SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(pnl) as total_pnl
            FROM lab_predictions
            WHERE {where}
            GROUP BY strategy, pipeline
            ORDER BY strategy, pipeline
        """, params).fetchall()

        # Also get total predictions (including unresolved) for gate progress
        total_rows = db.execute(f"""
            SELECT strategy, COUNT(*) as total
            FROM lab_predictions
            WHERE predicted_at >= datetime('now', '-30 days')
            GROUP BY strategy
        """).fetchall()
        totals = {r["strategy"]: r["total"] for r in total_rows}

        results = []
        for r in rows:
            bets = r["bets"]
            wins = r["wins"]
            wr = round(wins / bets * 100, 1) if bets > 0 else 0
            total = totals.get(r["strategy"], bets)
            results.append({
                "strategy": r["strategy"],
                "pipeline": r["pipeline"],
                "bets": bets,
                "wins": wins,
                "losses": bets - wins,
                "win_rate_pct": wr,
                "pnl": round(r["total_pnl"] or 0, 2),
                "total_predictions": total,
                "gate_progress": f"{total}/200",
            })

        return json.dumps(results, indent=2)
    finally:
        db.close()


@mcp.tool()
def lab_param_sweep(
    strategy: str = "",
    param: str = "",
    buckets: int = 5,
    min_samples: int = 10,
    days: int = 7,
) -> str:
    """Parameter optimization: bucket WR by metadata parameter values.

    Finds which parameter ranges have edge by grouping resolved predictions
    by metadata values and computing WR per bucket.

    Args:
        strategy: Strategy to analyze (empty = all). Use 'candle_snapshot' for raw data.
        param: Metadata parameter to bucket (e.g. 'rsi_14', 'zscore', 'bb_bandwidth',
               'streak_length', 'rvol', 'z_score', 'expansion_ratio').
               Empty = show available params and their value ranges.
        buckets: Number of equal-width buckets for numeric params (default 5)
        min_samples: Minimum samples per bucket to show (default 10)
        days: Lookback period in days (default 7)

    Returns:
        JSON with per-bucket WR, count, and P&L. Sorted by WR descending.
    """
    if not STRATEGY_LAB_DB.exists():
        return json.dumps({"error": "strategy_lab.db not found — lab not running yet"})

    db = sqlite3.connect(f"file:{STRATEGY_LAB_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        # Build base query
        where = [f"predicted_at >= datetime('now', '-{days} days')",
                 "outcome IS NOT NULL", "metadata IS NOT NULL"]
        params_list = []
        if strategy:
            where.append("strategy = ?")
            params_list.append(strategy)

        where_sql = " AND ".join(where)

        # If no param specified, list available params with value ranges
        if not param:
            rows = db.execute(f"""
                SELECT metadata FROM lab_predictions
                WHERE {where_sql}
                LIMIT 100
            """, params_list).fetchall()

            if not rows:
                return json.dumps({"error": "No resolved predictions with metadata yet",
                                   "hint": "Strategies need time to fire and resolve. Check back in 10+ minutes."})

            # Collect all keys and sample values
            import collections
            key_stats = collections.defaultdict(lambda: {"count": 0, "numeric": True, "min": float("inf"), "max": float("-inf"), "samples": []})
            for r in rows:
                try:
                    meta = json.loads(r["metadata"])
                    for k, v in meta.items():
                        ks = key_stats[k]
                        ks["count"] += 1
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            ks["min"] = min(ks["min"], v)
                            ks["max"] = max(ks["max"], v)
                        else:
                            ks["numeric"] = False
                        if len(ks["samples"]) < 5:
                            ks["samples"].append(v)
                except (json.JSONDecodeError, TypeError):
                    pass

            available = []
            for k, stats in sorted(key_stats.items()):
                entry = {"param": k, "count": stats["count"]}
                if stats["numeric"] and stats["min"] != float("inf"):
                    entry["type"] = "numeric"
                    entry["min"] = round(stats["min"], 4)
                    entry["max"] = round(stats["max"], 4)
                else:
                    entry["type"] = "categorical"
                    entry["samples"] = stats["samples"][:5]
                available.append(entry)

            return json.dumps({"available_params": available,
                               "usage": "Call with param='rsi_14' to see WR bucketed by RSI"}, indent=2)

        # Fetch all resolved predictions with metadata
        rows = db.execute(f"""
            SELECT direction, outcome, pnl, metadata, strategy
            FROM lab_predictions
            WHERE {where_sql}
        """, params_list).fetchall()

        if not rows:
            return json.dumps({"error": f"No resolved predictions found for param '{param}'"})

        # Extract param values
        entries = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
                val = meta.get(param)
                if val is not None:
                    entries.append({
                        "val": val,
                        "outcome": r["outcome"],
                        "pnl": r["pnl"] or 0,
                        "direction": r["direction"],
                        "strategy": r["strategy"],
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        if not entries:
            return json.dumps({"error": f"Parameter '{param}' not found in metadata",
                               "hint": "Use lab_param_sweep with no param to see available parameters"})

        # Check if numeric or categorical
        numeric_values = [e["val"] for e in entries if isinstance(e["val"], (int, float)) and not isinstance(e["val"], bool)]

        if len(numeric_values) > len(entries) * 0.5:
            # Numeric bucketing
            min_val = min(numeric_values)
            max_val = max(numeric_values)

            if min_val == max_val:
                bucket_width = 1
            else:
                bucket_width = (max_val - min_val) / buckets

            results = []
            for i in range(buckets):
                lo = min_val + i * bucket_width
                hi = lo + bucket_width if i < buckets - 1 else max_val + 0.001
                bucket_entries = [e for e in entries
                                  if isinstance(e["val"], (int, float))
                                  and lo <= e["val"] < hi]
                if len(bucket_entries) < min_samples:
                    continue
                wins = sum(1 for e in bucket_entries if e["outcome"] == 1)
                total = len(bucket_entries)
                pnl = sum(e["pnl"] for e in bucket_entries)
                results.append({
                    "bucket": f"{lo:.4g} – {hi:.4g}",
                    "count": total,
                    "wins": wins,
                    "losses": total - wins,
                    "win_rate_pct": round(wins / total * 100, 1),
                    "pnl": round(pnl, 2),
                })

            results.sort(key=lambda x: x["win_rate_pct"], reverse=True)
            return json.dumps({
                "param": param,
                "type": "numeric",
                "total_samples": len(entries),
                "buckets": results,
                "insight": _param_insight(results, param),
            }, indent=2)
        else:
            # Categorical bucketing
            from collections import defaultdict
            cat_groups = defaultdict(list)
            for e in entries:
                cat_groups[str(e["val"])].append(e)

            results = []
            for cat_val, group in sorted(cat_groups.items()):
                if len(group) < min_samples:
                    continue
                wins = sum(1 for e in group if e["outcome"] == 1)
                total = len(group)
                pnl = sum(e["pnl"] for e in group)
                results.append({
                    "value": cat_val,
                    "count": total,
                    "wins": wins,
                    "losses": total - wins,
                    "win_rate_pct": round(wins / total * 100, 1),
                    "pnl": round(pnl, 2),
                })

            results.sort(key=lambda x: x["win_rate_pct"], reverse=True)
            return json.dumps({
                "param": param,
                "type": "categorical",
                "total_samples": len(entries),
                "buckets": results,
                "insight": _param_insight(results, param),
            }, indent=2)

    finally:
        db.close()


def _param_insight(results, param):
    """Generate a brief insight string from bucket results."""
    if not results:
        return "No buckets with enough samples."
    best = results[0]
    worst = results[-1] if len(results) > 1 else None
    insight = f"Best: {best.get('bucket', best.get('value', '?'))} → {best['win_rate_pct']}% WR ({best['count']} bets)"
    if worst and worst != best:
        insight += f" | Worst: {worst.get('bucket', worst.get('value', '?'))} → {worst['win_rate_pct']}% WR ({worst['count']} bets)"
    spread = best["win_rate_pct"] - (worst["win_rate_pct"] if worst else best["win_rate_pct"])
    if spread > 10:
        insight += f" | ⚡ {spread:.0f}pp spread — strong parameter signal"
    elif spread > 5:
        insight += f" | {spread:.0f}pp spread — moderate signal"
    return insight


@mcp.tool()
def lab_param_matrix(
    strategy: str = "candle_snapshot",
    param_x: str = "",
    param_y: str = "",
    buckets: int = 3,
    min_samples: int = 5,
    days: int = 7,
) -> str:
    """2D parameter matrix: WR by two parameters simultaneously.

    Cross-tabulates two metadata parameters to find interaction effects.
    E.g., param_x='rsi_14', param_y='streak_length' shows WR for each
    (RSI bucket × streak length) combination.

    Args:
        strategy: Strategy to analyze (default candle_snapshot)
        param_x: First parameter (rows)
        param_y: Second parameter (columns)
        buckets: Number of buckets per numeric param (default 3, keep low for readability)
        min_samples: Min samples per cell (default 5)
        days: Lookback period (default 7)
    """
    if not STRATEGY_LAB_DB.exists():
        return json.dumps({"error": "strategy_lab.db not found"})

    if not param_x or not param_y:
        return json.dumps({"error": "Both param_x and param_y required",
                           "hint": "Use lab_param_sweep with no param to see available parameters"})

    db = sqlite3.connect(f"file:{STRATEGY_LAB_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        where = [f"predicted_at >= datetime('now', '-{days} days')",
                 "outcome IS NOT NULL", "metadata IS NOT NULL"]
        params_list = []
        if strategy:
            where.append("strategy = ?")
            params_list.append(strategy)

        rows = db.execute(f"""
            SELECT outcome, pnl, metadata
            FROM lab_predictions
            WHERE {" AND ".join(where)}
        """, params_list).fetchall()

        if not rows:
            return json.dumps({"error": "No data yet"})

        # Extract both params
        entries = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"])
                vx = meta.get(param_x)
                vy = meta.get(param_y)
                if vx is not None and vy is not None:
                    entries.append({"x": vx, "y": vy,
                                    "outcome": r["outcome"],
                                    "pnl": r["pnl"] or 0})
            except (json.JSONDecodeError, TypeError):
                pass

        if not entries:
            return json.dumps({"error": f"Parameters '{param_x}' and/or '{param_y}' not found in metadata"})

        def _bucketize(values, n_buckets):
            nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) > len(values) * 0.5:
                mn, mx = min(nums), max(nums)
                w = (mx - mn) / n_buckets if mx != mn else 1
                def assign(v):
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        return str(v)
                    idx = min(int((v - mn) / w), n_buckets - 1)
                    lo = mn + idx * w
                    hi = lo + w
                    return f"{lo:.3g}–{hi:.3g}"
                return assign
            else:
                return str

        assign_x = _bucketize([e["x"] for e in entries], buckets)
        assign_y = _bucketize([e["y"] for e in entries], buckets)

        from collections import defaultdict
        cells = defaultdict(list)
        for e in entries:
            bx = assign_x(e["x"])
            by = assign_y(e["y"])
            cells[(bx, by)].append(e)

        matrix = []
        for (bx, by), group in sorted(cells.items()):
            if len(group) < min_samples:
                continue
            wins = sum(1 for e in group if e["outcome"] == 1)
            total = len(group)
            matrix.append({
                param_x: bx,
                param_y: by,
                "count": total,
                "win_rate_pct": round(wins / total * 100, 1),
                "pnl": round(sum(e["pnl"] for e in group), 2),
            })

        matrix.sort(key=lambda x: x["win_rate_pct"], reverse=True)
        return json.dumps({
            "param_x": param_x,
            "param_y": param_y,
            "total_samples": len(entries),
            "cells": matrix,
        }, indent=2)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
