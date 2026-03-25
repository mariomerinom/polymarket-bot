"""
dashboard.py — Web dashboard for the Polymarket autoresearch bot.

Run: python dashboard.py (from src/ directory)
Serves on http://localhost:5050
"""

import sqlite3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from flask import Flask, Response
    app = Flask(__name__)
except ImportError:
    app = None

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"
EVOLUTION_LOG = None  # Legacy — evolution system removed in V3

AGENT_COLORS = {
    "momentum_rule": "#3fb950",    # V4: regime-filtered momentum (ride streaks)
    "contrarian_rule": "#3fb950",  # Legacy V3 (same color, old DB rows)
    "contrarian": "#f0883e",       # Legacy V2
    "volume_wick": "#58a6ff",      # Legacy V2
}
AGENT_COLOR_LIST = ["#d2a8ff", "#58a6ff", "#f0883e", "#3fb950", "#f778ba"]


def get_db(db_path=None):
    path = db_path or DB_PATH
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def load_evolution_log():
    """Legacy — evolution system removed in V3."""
    return []


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_status(db):
    """Get bot status info for the header."""
    now = datetime.now(timezone.utc)
    row = db.execute("SELECT MAX(predicted_at) FROM predictions").fetchone()
    last_prediction = row[0] if row and row[0] else None

    total = db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1").fetchone()[0]

    now_iso = now.isoformat()
    row = db.execute(
        "SELECT end_date FROM markets WHERE resolved = 0 AND end_date > ? ORDER BY end_date ASC LIMIT 1",
        (now_iso,)
    ).fetchone()
    next_market_end = row[0] if row else None

    status = "Idle"
    if last_prediction:
        try:
            last_dt = datetime.fromisoformat(last_prediction.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            diff_min = (now - last_dt).total_seconds() / 60
            status = "Active" if diff_min <= 10 else "Stale"
        except ValueError:
            status = "Unknown"

    evolutions = len(load_evolution_log())
    return {
        "last_prediction": last_prediction[:16].replace("T", " ") if last_prediction else "Never",
        "total_markets": total,
        "resolved_markets": resolved,
        "next_market_end": next_market_end,
        "status": status,
        "evolutions": evolutions,
    }


def get_pipeline_health(db):
    """Compute pipeline health: how many of the last N cycles ran on time."""
    now = datetime.now(timezone.utc)

    # Get distinct cycle timestamps (one per cycle = one prediction batch)
    rows = db.execute("""
        SELECT cycle, MIN(predicted_at) as cycle_time
        FROM predictions
        GROUP BY cycle
        ORDER BY cycle DESC
        LIMIT 50
    """).fetchall()

    if len(rows) < 2:
        return {"total_cycles": len(rows), "on_time": len(rows), "gaps": 0, "health_pct": 100, "avg_gap_min": 0}

    # Compute gaps between consecutive cycles
    timestamps = []
    for r in rows:
        ts_str = r[1]
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamps.append(dt)
        except (ValueError, TypeError):
            continue

    timestamps.sort()
    gaps_min = []
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
        gaps_min.append(gap)

    # "On time" = gap <= 15 min (generous for GitHub Actions cron)
    on_time = sum(1 for g in gaps_min if g <= 15)
    total = len(gaps_min)
    health_pct = (on_time / total * 100) if total > 0 else 100
    avg_gap = sum(gaps_min) / len(gaps_min) if gaps_min else 0

    return {
        "total_cycles": len(timestamps),
        "on_time": on_time,
        "gaps": total - on_time,
        "health_pct": health_pct,
        "avg_gap_min": avg_gap,
    }


def get_live_context(db):
    """Get last resolved market result, current open prediction, and BTC price."""
    # Last resolved market with per-agent predictions
    last_resolved_rows = db.execute("""
        SELECT m.question, m.outcome, m.price_yes, m.end_date,
               p.agent, p.estimate
        FROM markets m
        JOIN predictions p ON p.market_id = m.id
        WHERE m.resolved = 1
        ORDER BY m.end_date DESC, p.agent ASC
        LIMIT 10
    """).fetchall()
    last_resolved = None
    if last_resolved_rows:
        first = last_resolved_rows[0]
        outcome = first["outcome"]
        agent_results = []
        for r in last_resolved_rows:
            if r["question"] != first["question"]:
                break
            est = r["estimate"]
            correct = (est >= 0.5 and outcome == 1) or (est < 0.5 and outcome == 0)
            agent_results.append({
                "agent": r["agent"],
                "estimate": est,
                "correct": correct,
            })
        hits = sum(1 for a in agent_results if a["correct"])
        total_agents = len(agent_results)
        last_resolved = {
            "question": first["question"],
            "outcome": outcome,
            "price_yes": first["price_yes"],
            "agent_results": agent_results,
            "hits": hits,
            "total_agents": total_agents,
        }

    # Current open prediction (unresolved, most recent)
    current_pred = db.execute("""
        SELECT m.question, m.price_yes, m.end_date,
               GROUP_CONCAT(p.agent || ':' || printf('%.0f', p.estimate * 100) || '%(' || COALESCE(p.confidence, 'low') || ')', ' | ') as predictions
        FROM markets m
        JOIN predictions p ON p.market_id = m.id
        WHERE m.resolved = 0
        GROUP BY m.id
        ORDER BY m.end_date ASC
        LIMIT 1
    """).fetchone()

    # BTC price from btc_data module (try import, gracefully fail)
    btc_price = None
    btc_change = None
    btc_trend = None
    try:
        from btc_data import fetch_btc_candles
        data = fetch_btc_candles(limit=6)
        if data:
            btc_price = data["current_price"]
            btc_change = data["1h_change_pct"]
            btc_trend = data["trend"]
    except Exception:
        pass

    return {
        "last_resolved": dict(last_resolved) if last_resolved else None,
        "current_pred": dict(current_pred) if current_pred else None,
        "btc_price": btc_price,
        "btc_change": btc_change,
        "btc_trend": btc_trend,
    }


def get_resolved_predictions(db):
    """Get all resolved predictions ordered chronologically. Used by multiple sections."""
    # Try v2 schema first (with conviction_score)
    try:
        rows = db.execute("""
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
                   p.conviction_score, m.outcome, m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
            ORDER BY p.predicted_at ASC
        """).fetchall()
    except sqlite3.OperationalError:
        rows = db.execute("""
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
                   NULL as conviction_score, m.outcome, m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
            ORDER BY p.predicted_at ASC
        """).fetchall()
    return [dict(r) for r in rows]


def is_correct(estimate, outcome):
    """Did the agent call the direction right?"""
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def compute_agent_stats(resolved):
    """Compute per-agent stats: W/L, accuracy, streaks, rolling, market comparison."""
    agents = defaultdict(lambda: {
        "wins": 0, "losses": 0, "total": 0,
        "current_streak_type": None, "current_streak": 0,
        "best_w_streak": 0, "worst_l_streak": 0,
        "results": [],  # list of bools (correct or not), chronological
        "market_correct": 0,
    })

    for row in resolved:
        agent = row["agent"]
        a = agents[agent]
        correct = is_correct(row["estimate"], row["outcome"])
        market_right = is_correct(row["price_yes"], row["outcome"])

        a["total"] += 1
        a["results"].append(correct)
        if correct:
            a["wins"] += 1
        else:
            a["losses"] += 1
        if market_right:
            a["market_correct"] += 1

        # Streak tracking
        if a["current_streak_type"] is None:
            a["current_streak_type"] = "W" if correct else "L"
            a["current_streak"] = 1
        elif (correct and a["current_streak_type"] == "W") or (not correct and a["current_streak_type"] == "L"):
            a["current_streak"] += 1
        else:
            a["current_streak_type"] = "W" if correct else "L"
            a["current_streak"] = 1

        if a["current_streak_type"] == "W":
            a["best_w_streak"] = max(a["best_w_streak"], a["current_streak"])
        else:
            a["worst_l_streak"] = max(a["worst_l_streak"], a["current_streak"])

    # Compute rolling last-10
    for a in agents.values():
        last10 = a["results"][-10:]
        a["last10_acc"] = sum(last10) / len(last10) * 100 if last10 else 0
        a["accuracy"] = a["wins"] / a["total"] * 100 if a["total"] > 0 else 0
        a["market_accuracy"] = a["market_correct"] / a["total"] * 100 if a["total"] > 0 else 0

    return dict(agents)


def compute_ensemble(resolved):
    """Majority vote ensemble across agents per market."""
    # Group predictions by market
    market_preds = defaultdict(list)
    market_outcomes = {}
    for row in resolved:
        market_preds[row["market_id"]].append(row["estimate"])
        market_outcomes[row["market_id"]] = row["outcome"]

    wins = 0
    total = 0
    results = []
    for mid, estimates in market_preds.items():
        outcome = market_outcomes[mid]
        # Majority vote: average the estimates
        avg = sum(estimates) / len(estimates)
        correct = is_correct(avg, outcome)
        results.append(correct)
        total += 1
        if correct:
            wins += 1

    accuracy = wins / total * 100 if total > 0 else 0

    # Streak
    streak_type = None
    streak = 0
    for c in results:
        if streak_type is None:
            streak_type = "W" if c else "L"
            streak = 1
        elif (c and streak_type == "W") or (not c and streak_type == "L"):
            streak += 1
        else:
            streak_type = "W" if c else "L"
            streak = 1

    return {
        "wins": wins, "losses": total - wins, "total": total,
        "accuracy": accuracy,
        "current_streak_type": streak_type or "W",
        "current_streak": streak,
    }


def compute_pnl(resolved, unit_bet=100):
    """Simulate P&L using conviction-tier bet sizing.

    Conviction tiers determine bet size:
    - MEDIUM (score 3): $75
    - HIGH (score 4+): $200
    - Everything else: $0 (skip)

    Tracks per-bet detail to show the asymmetry:
    - Wins are variable: profit = bet × (1/price - 1)
    - Losses are fixed: always exactly -bet_size
    """
    CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 200}

    agents = defaultdict(lambda: {
        "total_pnl": 0.0,
        "total_wagered": 0.0,
        "num_bets": 0,
        "skipped": 0,
        "pnl_series": [],
        # New: per-bet breakdown for asymmetry visualization
        "gross_wins": 0.0,      # sum of all winning bet profits
        "gross_losses": 0.0,    # sum of all losing bet losses (negative)
        "num_wins": 0,
        "num_losses": 0,
        "bet_results": [],      # list of {profit, bet_size, price, won}
        "max_drawdown": 0.0,    # worst peak-to-trough in cumulative P&L
    })

    for row in resolved:
        agent = row["agent"]
        a = agents[agent]
        estimate = row["estimate"]
        outcome = row["outcome"]
        price_yes = row["price_yes"]
        conv = row.get("conviction_score") or 0
        bet_size = CONVICTION_BETS.get(conv, 0)

        if bet_size == 0:
            a["skipped"] += 1
            a["pnl_series"].append(a["total_pnl"])
            continue

        if estimate >= 0.5:
            if price_yes > 0 and price_yes < 1:
                profit = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                profit = 0
        else:
            price_no = 1.0 - price_yes
            if price_no > 0 and price_no < 1:
                profit = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size
            else:
                profit = 0

        a["total_pnl"] += profit
        a["total_wagered"] += bet_size
        a["num_bets"] += 1
        a["pnl_series"].append(a["total_pnl"])

        # Track win/loss detail
        won = profit > 0
        if won:
            a["gross_wins"] += profit
            a["num_wins"] += 1
        else:
            a["gross_losses"] += profit  # negative number
            a["num_losses"] += 1
        a["bet_results"].append({
            "profit": round(profit, 2),
            "bet_size": bet_size,
            "price": price_yes,
            "won": won,
        })

    for a in agents.values():
        a["roi"] = (a["total_pnl"] / a["total_wagered"] * 100) if a["total_wagered"] > 0 else 0
        a["avg_win"] = (a["gross_wins"] / a["num_wins"]) if a["num_wins"] > 0 else 0
        a["avg_loss"] = (a["gross_losses"] / a["num_losses"]) if a["num_losses"] > 0 else 0  # negative
        # Max drawdown: worst peak-to-trough drop in cumulative P&L
        peak = 0.0
        max_dd = 0.0
        for val in a["pnl_series"]:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        a["max_drawdown"] = max_dd

    return dict(agents)


def compute_ensemble_pnl(resolved, unit_bet=100):
    """Ensemble P&L using conviction-tier bet sizing. Only bets on MEDIUM+ conviction."""
    CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 200}
    WEIGHTS = {"momentum_rule": 1.0, "contrarian_rule": 1.0, "contrarian": 0.55, "volume_wick": 0.45}

    market_data = defaultdict(lambda: {"agents": [], "outcome": None, "price_yes": None, "conviction": 0})
    for row in resolved:
        md = market_data[row["market_id"]]
        md["agents"].append({"agent": row["agent"], "estimate": row["estimate"]})
        md["outcome"] = row["outcome"]
        md["price_yes"] = row["price_yes"]
        if row.get("conviction_score") is not None:
            md["conviction"] = row["conviction_score"]

    total_pnl = 0.0
    total_wagered = 0.0
    num_bets = 0
    num_skipped = 0
    pnl_series = []

    for mid, md in market_data.items():
        conv = md["conviction"] or 0
        bet_size = CONVICTION_BETS.get(conv, 0)

        # Weighted ensemble estimate
        total_w = 0
        weighted_sum = 0
        for p in md["agents"]:
            w = WEIGHTS.get(p["agent"], 0.5)
            weighted_sum += w * p["estimate"]
            total_w += w
        ens_est = weighted_sum / total_w if total_w > 0 else 0.5

        if bet_size == 0:
            num_skipped += 1
            pnl_series.append(total_pnl)
            continue

        outcome = md["outcome"]
        price_yes = md["price_yes"]

        if ens_est >= 0.5:
            if 0 < price_yes < 1:
                profit = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                profit = 0
        else:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                profit = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size
            else:
                profit = 0

        total_pnl += profit
        total_wagered += bet_size
        num_bets += 1
        pnl_series.append(total_pnl)

    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0
    return {
        "total_pnl": total_pnl, "total_wagered": total_wagered,
        "num_bets": num_bets, "num_skipped": num_skipped,
        "roi": roi, "pnl_series": pnl_series,
    }


def compute_conviction_breakdown(resolved):
    """Compute accuracy and P&L by conviction tier. v2 feature."""
    # Group by market, get conviction score per market
    market_data = defaultdict(lambda: {"estimates": [], "outcome": None, "price_yes": None, "conviction": None})
    for row in resolved:
        md = market_data[row["market_id"]]
        md["estimates"].append({"agent": row["agent"], "estimate": row["estimate"]})
        md["outcome"] = row["outcome"]
        md["price_yes"] = row["price_yes"]
        if row.get("conviction_score") is not None:
            md["conviction"] = row["conviction_score"]

    def score_to_tier(score):
        if score is None:
            return "UNKNOWN"
        if score <= 1:
            return "NO_BET"
        elif score == 2:
            return "LOW"
        elif score == 3:
            return "MEDIUM"
        else:
            return "HIGH"

    bet_sizes = {"NO_BET": 0, "LOW": 0, "MEDIUM": 75, "HIGH": 200, "UNKNOWN": 0}
    weights = {"momentum_rule": 1.0, "contrarian_rule": 1.0, "contrarian": 0.55, "volume_wick": 0.45}

    tiers = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0, "wagered": 0.0})

    for mid, md in market_data.items():
        tier = score_to_tier(md["conviction"])
        outcome = md["outcome"]
        price_yes = md["price_yes"]

        # Weighted ensemble
        total_w = 0
        weighted_sum = 0
        for p in md["estimates"]:
            w = weights.get(p["agent"], 1.0 / len(md["estimates"]))
            weighted_sum += w * p["estimate"]
            total_w += w
        ens_est = weighted_sum / total_w if total_w > 0 else 0.5

        correct = is_correct(ens_est, outcome)
        ts = tiers[tier]
        ts["total"] += 1
        if correct:
            ts["wins"] += 1
        else:
            ts["losses"] += 1

        bet_size = bet_sizes.get(tier, 0)
        if bet_size > 0:
            ts["wagered"] += bet_size
            if ens_est >= 0.5:
                if 0 < price_yes < 1:
                    ts["pnl"] += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                if 0 < price_no < 1:
                    ts["pnl"] += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

    # Compute ROI per tier
    for ts in tiers.values():
        ts["accuracy"] = ts["wins"] / ts["total"] * 100 if ts["total"] > 0 else 0
        ts["roi"] = ts["pnl"] / ts["wagered"] * 100 if ts["wagered"] > 0 else 0

    return dict(tiers)


def build_pnl_svg(agent_pnl, ensemble_pnl):
    """Build SVG chart of cumulative P&L over time."""
    all_series = {}
    for agent, data in agent_pnl.items():
        if data["pnl_series"]:
            all_series[agent] = data["pnl_series"]
    if ensemble_pnl["pnl_series"]:
        all_series["ENSEMBLE"] = ensemble_pnl["pnl_series"]

    if not all_series:
        return '<p class="empty">No P&L data yet.</p>'

    W, H = 800, 300
    ml, mr, mt, mb = 60, 20, 20, 40
    cw = W - ml - mr
    ch = H - mt - mb

    max_len = max(len(s) for s in all_series.values())
    if max_len < 2:
        return '<p class="empty">Not enough data for P&L chart.</p>'

    all_vals = [v for s in all_series.values() for v in s]
    y_min = min(min(all_vals), 0)
    y_max = max(max(all_vals), 0)
    y_range = y_max - y_min if y_max != y_min else 1

    svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;height:auto;background:#161b22;border-radius:8px;">'

    # Zero line
    zero_y = mt + ch - ((0 - y_min) / y_range * ch)
    svg += f'<line x1="{ml}" y1="{zero_y}" x2="{W-mr}" y2="{zero_y}" stroke="#484f58" stroke-width="1" stroke-dasharray="6,4" />'
    svg += f'<text x="{ml-8}" y="{zero_y+4}" fill="#8b949e" font-size="11" text-anchor="end">$0</text>'

    # Y axis labels
    for pct in [0.25, 0.5, 0.75, 1.0]:
        for val in [y_min + pct * y_range]:
            if abs(val) < 0.01:
                continue
            y = mt + ch - ((val - y_min) / y_range * ch)
            svg += f'<line x1="{ml}" y1="{y}" x2="{W-mr}" y2="{y}" stroke="#21262d" stroke-width="1" />'
            svg += f'<text x="{ml-8}" y="{y+4}" fill="#8b949e" font-size="10" text-anchor="end">${val:,.0f}</text>'

    # Lines
    ens_colors = {**AGENT_COLORS, "ENSEMBLE": "#f0883e"}
    agents_sorted = sorted(all_series.keys())
    for idx, agent in enumerate(agents_sorted):
        pts = all_series[agent]
        color = ens_colors.get(agent, AGENT_COLOR_LIST[idx % len(AGENT_COLOR_LIST)])
        points = []
        for i, val in enumerate(pts):
            x = ml + (i / (max_len - 1)) * cw if max_len > 1 else ml
            y = mt + ch - ((val - y_min) / y_range * ch)
            points.append(f"{x:.1f},{y:.1f}")
        sw = "3" if agent == "ENSEMBLE" else "2"
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="{sw}" />'

    svg += '</svg>'

    # Legend
    legend = '<div class="chart-legend">'
    for idx, agent in enumerate(agents_sorted):
        color = ens_colors.get(agent, AGENT_COLOR_LIST[idx % len(AGENT_COLOR_LIST)])
        legend += f'<span class="legend-item"><span class="legend-dot" style="background:{color}"></span>{agent}</span>'
    legend += '</div>'

    return svg + legend


def build_waterfall_svg(agent_pnl):
    """Build SVG waterfall chart showing each discrete bet as a bar.

    Green bars go UP (variable win amounts), red bars go DOWN (fixed loss).
    This makes the asymmetry visible: losses are uniform, wins vary by price.
    """
    # Collect all bet results from the first agent (primary view)
    all_bets = []
    for agent, data in agent_pnl.items():
        for bet in data.get("bet_results", []):
            all_bets.append(bet)

    if len(all_bets) < 1:
        return '<p class="empty">No bet data for waterfall chart.</p>'

    W, H = 800, 280
    ml, mr, mt, mb = 60, 20, 20, 50
    cw = W - ml - mr
    ch = H - mt - mb

    # Compute cumulative running total for bar positioning
    running = 0.0
    bars = []
    for bet in all_bets:
        start = running
        running += bet["profit"]
        bars.append({"start": start, "end": running, "profit": bet["profit"],
                      "won": bet["won"], "bet_size": bet["bet_size"], "price": bet["price"]})

    all_vals = [0.0] + [b["end"] for b in bars]
    y_min = min(all_vals)
    y_max = max(all_vals)
    y_pad = max(abs(y_max - y_min) * 0.1, 10)
    y_min -= y_pad
    y_max += y_pad
    y_range = y_max - y_min if y_max != y_min else 1

    num_bars = len(bars)
    bar_w = max(2, min(20, cw / num_bars - 1))
    gap = max(0.5, (cw - bar_w * num_bars) / max(num_bars, 1))

    svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;height:auto;background:#161b22;border-radius:8px;">'

    # Zero line
    zero_y = mt + ch - ((0 - y_min) / y_range * ch)
    svg += f'<line x1="{ml}" y1="{zero_y}" x2="{W-mr}" y2="{zero_y}" stroke="#484f58" stroke-width="1" stroke-dasharray="6,4" />'
    svg += f'<text x="{ml-8}" y="{zero_y+4}" fill="#8b949e" font-size="11" text-anchor="end">$0</text>'

    # Y axis labels
    for pct in [0.25, 0.5, 0.75, 1.0]:
        val = y_min + pct * y_range
        if abs(val) < 0.01:
            continue
        y = mt + ch - ((val - y_min) / y_range * ch)
        svg += f'<line x1="{ml}" y1="{y}" x2="{W-mr}" y2="{y}" stroke="#21262d" stroke-width="1" />'
        svg += f'<text x="{ml-8}" y="{y+4}" fill="#8b949e" font-size="10" text-anchor="end">${val:,.0f}</text>'

    # Bars
    for i, b in enumerate(bars):
        x = ml + i * (bar_w + gap)
        y_start = mt + ch - ((b["start"] - y_min) / y_range * ch)
        y_end = mt + ch - ((b["end"] - y_min) / y_range * ch)
        bar_top = min(y_start, y_end)
        bar_h = max(abs(y_end - y_start), 1)
        color = "#3fb950" if b["won"] else "#f44336"
        opacity = "0.85"
        svg += f'<rect x="{x:.1f}" y="{bar_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="{opacity}" rx="1">'
        svg += f'<title>Bet #{i+1}: {"WIN" if b["won"] else "LOSS"} ${b["profit"]:+,.0f} (price: {b["price"]:.2f})</title>'
        svg += '</rect>'
        # Price annotations on winning bars (when not too crowded)
        if b["won"] and num_bars <= 30:
            label_y = bar_top - 4
            if label_y < mt + 8:
                label_y = bar_top + bar_h + 10
            svg += f'<text x="{x + bar_w/2:.1f}" y="{label_y:.1f}" fill="#8b949e" font-size="8" text-anchor="middle">@{b["price"]:.2f}</text>'

    # Running total line overlay
    points = []
    for i, b in enumerate(bars):
        x = ml + i * (bar_w + gap) + bar_w / 2
        y = mt + ch - ((b["end"] - y_min) / y_range * ch)
        points.append(f"{x:.1f},{y:.1f}")
    if points:
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="#c9d1d9" stroke-width="1.5" stroke-dasharray="3,2" opacity="0.6" />'

    # X axis label
    svg += f'<text x="{ml + cw/2}" y="{H-8}" fill="#8b949e" font-size="10" text-anchor="middle">{num_bars} bets (green = variable win, red = fixed loss)</text>'

    svg += '</svg>'
    return svg


def compute_ev_breakeven(agent_pnl):
    """Compute expected value per bet and breakeven win rate.

    EV = win_rate × avg_win + loss_rate × avg_loss
    Breakeven WR = |avg_loss| / (avg_win + |avg_loss|)
    """
    total_wins = sum(p["num_wins"] for p in agent_pnl.values())
    total_losses = sum(p["num_losses"] for p in agent_pnl.values())
    total_bets = total_wins + total_losses
    if total_bets == 0:
        return {"ev": 0, "breakeven_wr": 0.5, "current_wr": 0, "margin": 0, "total_bets": 0}

    gross_wins = sum(p["gross_wins"] for p in agent_pnl.values())
    gross_losses = sum(p["gross_losses"] for p in agent_pnl.values())
    avg_win = gross_wins / total_wins if total_wins > 0 else 0
    avg_loss = gross_losses / total_losses if total_losses > 0 else 0  # negative

    win_rate = total_wins / total_bets
    ev = win_rate * avg_win + (1 - win_rate) * avg_loss

    # Breakeven: WR where EV = 0 → WR × avg_win + (1-WR) × avg_loss = 0
    denom = avg_win + abs(avg_loss)
    breakeven_wr = abs(avg_loss) / denom if denom > 0 else 0.5

    return {
        "ev": ev,
        "breakeven_wr": breakeven_wr,
        "current_wr": win_rate,
        "margin": win_rate - breakeven_wr,
        "total_bets": total_bets,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }


def build_distribution_svg(agent_pnl):
    """Build SVG histogram showing win/loss amount distribution.

    Wins spread across many buckets (variable), losses cluster at 1-2 values (fixed).
    This makes the binary options asymmetry visually obvious.
    """
    all_profits = []
    for data in agent_pnl.values():
        for bet in data.get("bet_results", []):
            all_profits.append(bet["profit"])

    if len(all_profits) < 2:
        return '<p class="empty">Need more bets for distribution chart.</p>'

    wins = [p for p in all_profits if p > 0]
    losses = [p for p in all_profits if p <= 0]

    # Build buckets
    p_min = min(all_profits)
    p_max = max(all_profits)
    spread = p_max - p_min
    if spread == 0:
        spread = 100
    num_buckets = min(20, max(6, len(all_profits) // 2))
    bucket_width = spread / num_buckets

    buckets = []
    for i in range(num_buckets):
        lo = p_min + i * bucket_width
        hi = lo + bucket_width
        w_count = sum(1 for p in wins if lo <= p < hi or (i == num_buckets - 1 and p == hi))
        l_count = sum(1 for p in losses if lo <= p < hi or (i == num_buckets - 1 and p == hi))
        buckets.append({"lo": lo, "hi": hi, "wins": w_count, "losses": l_count})

    max_count = max((b["wins"] + b["losses"] for b in buckets), default=1) or 1

    W, H = 800, 220
    ml, mr, mt, mb = 60, 20, 20, 50
    cw = W - ml - mr
    ch = H - mt - mb
    bar_w = cw / num_buckets - 1

    svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;height:auto;background:#161b22;border-radius:8px;">'

    # Zero line (where $0 falls)
    zero_bucket_x = ml + ((0 - p_min) / spread) * cw
    if ml < zero_bucket_x < W - mr:
        svg += f'<line x1="{zero_bucket_x:.1f}" y1="{mt}" x2="{zero_bucket_x:.1f}" y2="{H-mb}" stroke="#c9d1d9" stroke-width="1" stroke-dasharray="6,3" opacity="0.5" />'
        svg += f'<text x="{zero_bucket_x:.1f}" y="{mt - 4}" fill="#c9d1d9" font-size="10" text-anchor="middle">$0</text>'

    # Draw stacked bars
    for i, b in enumerate(buckets):
        x = ml + i * (bar_w + 1)
        total = b["wins"] + b["losses"]
        if total == 0:
            continue

        # Losses on bottom, wins on top (stacked)
        loss_h = (b["losses"] / max_count) * ch
        win_h = (b["wins"] / max_count) * ch

        if b["losses"] > 0:
            y_loss = mt + ch - loss_h
            svg += f'<rect x="{x:.1f}" y="{y_loss:.1f}" width="{bar_w:.1f}" height="{loss_h:.1f}" fill="#f44336" opacity="0.85" rx="1">'
            svg += f'<title>${b["lo"]:+,.0f} to ${b["hi"]:+,.0f}: {b["losses"]} loss(es)</title></rect>'

        if b["wins"] > 0:
            y_win = mt + ch - loss_h - win_h
            svg += f'<rect x="{x:.1f}" y="{y_win:.1f}" width="{bar_w:.1f}" height="{win_h:.1f}" fill="#3fb950" opacity="0.85" rx="1">'
            svg += f'<title>${b["lo"]:+,.0f} to ${b["hi"]:+,.0f}: {b["wins"]} win(s)</title></rect>'

    # X-axis labels (a few key bucket boundaries)
    label_indices = [0, num_buckets // 4, num_buckets // 2, 3 * num_buckets // 4, num_buckets - 1]
    for idx in label_indices:
        if idx < len(buckets):
            x = ml + idx * (bar_w + 1) + bar_w / 2
            val = buckets[idx]["lo"]
            svg += f'<text x="{x:.1f}" y="{H-mb+14}" fill="#8b949e" font-size="9" text-anchor="middle">${val:+,.0f}</text>'

    # Annotation
    svg += f'<text x="{ml + cw/2}" y="{H-8}" fill="#8b949e" font-size="10" text-anchor="middle">Losses cluster at fixed bet sizes. Wins spread based on entry price.</text>'

    # Y-axis label
    svg += f'<text x="{ml-8}" y="{mt + ch/2}" fill="#8b949e" font-size="10" text-anchor="end" transform="rotate(-90,{ml-8},{mt+ch/2})">Count</text>'

    svg += '</svg>'
    return svg


def compute_confidence_calibration(resolved):
    """Accuracy broken down by confidence level per agent."""
    cal = defaultdict(lambda: defaultdict(lambda: {"correct": 0, "total": 0}))
    for row in resolved:
        conf = (row["confidence"] or "unknown").lower()
        correct = is_correct(row["estimate"], row["outcome"])
        cal[row["agent"]][conf]["total"] += 1
        if correct:
            cal[row["agent"]][conf]["correct"] += 1
    return dict(cal)


def compute_rolling_accuracy(resolved, window=10):
    """Compute rolling accuracy time series per agent."""
    agent_results = defaultdict(list)
    for row in resolved:
        correct = is_correct(row["estimate"], row["outcome"])
        agent_results[row["agent"]].append(correct)

    series = {}
    for agent, results in agent_results.items():
        if len(results) < window:
            continue
        points = []
        for i in range(window - 1, len(results)):
            chunk = results[i - window + 1:i + 1]
            acc = sum(chunk) / len(chunk) * 100
            points.append(acc)
        series[agent] = points
    return series


def get_agent_scorecard(db):
    rows = db.execute("""
        SELECT p.agent,
               COUNT(*) AS num_markets,
               AVG((p.estimate - m.outcome) * (p.estimate - m.outcome)) AS avg_brier,
               AVG((p.estimate - m.outcome) * (p.estimate - m.outcome))
                 - AVG((m.price_yes - m.outcome) * (m.price_yes - m.outcome)) AS vs_market
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1
        GROUP BY p.agent
        ORDER BY avg_brier ASC
    """).fetchall()
    return rows


def get_recent_predictions(db, limit=50):
    rows = db.execute("""
        SELECT p.agent, p.estimate, p.edge, p.confidence, p.predicted_at, p.cycle,
               m.question, m.price_yes, m.resolved, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        ORDER BY p.predicted_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return rows


def get_markets(db):
    rows = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes, price_no,
               resolved, outcome
        FROM markets
        ORDER BY resolved ASC, end_date ASC
    """).fetchall()
    return rows


# ---------------------------------------------------------------------------
# SVG Chart Builder
# ---------------------------------------------------------------------------

def build_time_series_svg(rolling_series):
    """Build an SVG line chart of rolling accuracy per agent."""
    if not rolling_series:
        return '<p class="empty">Not enough data for time series (need 10+ resolved predictions per agent).</p>'

    W, H = 800, 300
    ml, mr, mt, mb = 50, 20, 20, 40  # margins
    cw = W - ml - mr
    ch = H - mt - mb

    max_len = max(len(pts) for pts in rolling_series.values())
    if max_len < 2:
        return '<p class="empty">Not enough data for time series.</p>'

    svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;height:auto;background:#161b22;border-radius:8px;">'

    # Grid lines and Y labels
    for pct in [0, 25, 50, 75, 100]:
        y = mt + ch - (pct / 100 * ch)
        color = "#484f58"
        dash = ""
        if pct == 50:
            color = "#da3633"
            dash = 'stroke-dasharray="6,4"'
        svg += f'<line x1="{ml}" y1="{y}" x2="{W-mr}" y2="{y}" stroke="{color}" stroke-width="1" {dash} />'
        svg += f'<text x="{ml-8}" y="{y+4}" fill="#8b949e" font-size="11" text-anchor="end">{pct}%</text>'

    # X axis labels
    for i in range(0, max_len, max(1, max_len // 6)):
        x = ml + (i / (max_len - 1)) * cw if max_len > 1 else ml
        svg += f'<text x="{x}" y="{H-8}" fill="#8b949e" font-size="10" text-anchor="middle">#{i+1}</text>'

    # Agent lines
    agents_sorted = sorted(rolling_series.keys())
    for idx, agent in enumerate(agents_sorted):
        pts = rolling_series[agent]
        color = AGENT_COLORS.get(agent, AGENT_COLOR_LIST[idx % len(AGENT_COLOR_LIST)])
        points = []
        for i, acc in enumerate(pts):
            x = ml + (i / (max_len - 1)) * cw if max_len > 1 else ml
            y = mt + ch - (acc / 100 * ch)
            points.append(f"{x:.1f},{y:.1f}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2" />'

    svg += '</svg>'

    # Legend
    legend = '<div class="chart-legend">'
    for idx, agent in enumerate(agents_sorted):
        color = AGENT_COLORS.get(agent, AGENT_COLOR_LIST[idx % len(AGENT_COLOR_LIST)])
        legend += f'<span class="legend-item"><span class="legend-dot" style="background:{color}"></span>{agent}</span>'
    legend += '<span class="legend-item"><span class="legend-line" style="border-color:#da3633"></span>50% (coin flip)</span>'
    legend += '</div>'

    return svg + legend


# ---------------------------------------------------------------------------
# HTML Builder
# ---------------------------------------------------------------------------

def accuracy_color(pct):
    if pct > 55:
        return "#3fb950"
    if pct > 52:
        return "#4caf50"
    if pct >= 48:
        return "#ffc107"
    return "#f44336"


def streak_badge(stype, count):
    if stype == "W":
        return f'<span class="streak streak-w">W{count}</span>'
    else:
        return f'<span class="streak streak-l">L{count}</span>'


def brier_color(score):
    if score is None:
        return "#888"
    if score < 0.1:
        return "#4caf50"
    if score < 0.2:
        return "#8bc34a"
    if score < 0.3:
        return "#ffc107"
    if score < 0.5:
        return "#ff9800"
    return "#f44336"


def vs_market_color(vs):
    if vs is None:
        return "#888"
    return "#4caf50" if vs < 0 else "#f44336"


def build_html():
    db = get_db()
    try:
        status = get_status(db)
        pipeline = get_pipeline_health(db)
        live_ctx = get_live_context(db)
        resolved = get_resolved_predictions(db)
        agent_stats = compute_agent_stats(resolved)
        ensemble = compute_ensemble(resolved)
        agent_pnl = compute_pnl(resolved)
        ensemble_pnl = compute_ensemble_pnl(resolved)
        calibration = compute_confidence_calibration(resolved)
        conviction_tiers = compute_conviction_breakdown(resolved)
        rolling = compute_rolling_accuracy(resolved)
        scorecard = get_agent_scorecard(db)
        predictions = get_recent_predictions(db)
        markets = get_markets(db)
        evolution = load_evolution_log()
    finally:
        db.close()

    has_data = len(resolved) > 0

    # -- Status Header --
    status_color = {
        "Active": "#238636", "Idle": "#8b949e", "Stale": "#da3633", "Unknown": "#484f58"
    }.get(status["status"], "#484f58")

    next_market_js = ""
    if status["next_market_end"]:
        next_market_js = f'data-next-market="{status["next_market_end"]}"'

    status_html = f"""<div class="status-bar">
        <div class="status-item">
            <span class="status-label">Status</span>
            <span class="status-value" style="color:{status_color}">{status["status"]}</span>
        </div>
        <div class="status-item">
            <span class="status-label">Last Cycle</span>
            <span class="status-value">{status["last_prediction"]} UTC</span>
        </div>
        <div class="status-item">
            <span class="status-label">Markets</span>
            <span class="status-value">{status["resolved_markets"]} / {status["total_markets"]} resolved</span>
        </div>
        <div class="status-item">
            <span class="status-label">Next Market</span>
            <span class="status-value" id="countdown" {next_market_js}>--</span>
        </div>
        <div class="status-item">
            <span class="status-label">Evolutions</span>
            <span class="status-value">{status["evolutions"]}</span>
        </div>
    </div>"""

    # -- Observation Mode Banner --
    observation_html = """<div style="background:rgba(88,166,255,0.12);border:1px solid #1f6feb;border-radius:8px;padding:16px 20px;margin-bottom:16px;text-align:center">
        <div style="font-size:18px;font-weight:700;color:#58a6ff;letter-spacing:1px">📋 PAPER TRADING — V4 MOMENTUM</div>
        <div style="color:#8b949e;font-size:13px;margin-top:4px">Inverted contrarian: ride the streak. V3 contrarian lost at 37% WR / -$962. Validating momentum before going live.</div>
    </div>"""

    # -- Pipeline Health Banner --
    health_pct = pipeline["health_pct"]
    on_time = pipeline["on_time"]
    total_gaps = pipeline["on_time"] + pipeline["gaps"]
    if health_pct >= 80:
        health_color = "#3fb950"
        health_bg = "rgba(63,185,80,0.08)"
        health_border = "#238636"
        health_status = "HEALTHY"
    elif health_pct >= 50:
        health_color = "#ffc107"
        health_bg = "rgba(255,193,7,0.08)"
        health_border = "#9e6a03"
        health_status = "DEGRADED"
    else:
        health_color = "#f44336"
        health_bg = "rgba(244,67,54,0.08)"
        health_border = "#da3633"
        health_status = "DOWN"

    # Time since last cycle
    last_cycle_ago = ""
    if status["last_prediction"] and status["last_prediction"] != "Never":
        try:
            lp = status["last_prediction"].replace(" ", "T") + ":00+00:00"
            lp_dt = datetime.fromisoformat(lp)
            ago_min = (datetime.now(timezone.utc) - lp_dt).total_seconds() / 60
            if ago_min < 60:
                last_cycle_ago = f"{ago_min:.0f}m ago"
            else:
                last_cycle_ago = f"{ago_min/60:.1f}h ago"
        except (ValueError, TypeError):
            last_cycle_ago = ""

    pipeline_html = f"""<div class="pipeline-banner" style="background:{health_bg};border-color:{health_border}">
        <div class="pipeline-main">
            <div class="pipeline-fraction" style="color:{health_color}">
                <span class="pipeline-big">{on_time}</span><span class="pipeline-slash">/{total_gaps}</span>
            </div>
            <div class="pipeline-labels">
                <span class="pipeline-status" style="color:{health_color}">{health_status}</span>
                <span class="pipeline-desc">cycles on time ({health_pct:.0f}%)</span>
            </div>
        </div>
        <div class="pipeline-meta">
            <div class="pipeline-detail">Avg gap: {pipeline["avg_gap_min"]:.0f}min &middot; {pipeline["total_cycles"]} total &middot; {pipeline["gaps"]} missed</div>
            {"<div class='pipeline-ago'>Last cycle: " + last_cycle_ago + "</div>" if last_cycle_ago else ""}
        </div>
    </div>"""

    # -- Live Context Banner --
    live_parts = []

    # BTC Price
    if live_ctx["btc_price"]:
        btc_chg = live_ctx["btc_change"] or 0
        btc_color = "#3fb950" if btc_chg >= 0 else "#f44336"
        btc_sign = "+" if btc_chg >= 0 else ""
        btc_trend_label = (live_ctx["btc_trend"] or "").upper()
        live_parts.append(f"""<div class="live-card">
            <div class="live-label">BTC Price</div>
            <div class="live-value">${live_ctx["btc_price"]:,.0f}</div>
            <div class="live-detail" style="color:{btc_color}">{btc_sign}{btc_chg:.3f}% &middot; {btc_trend_label}</div>
        </div>""")

    # Last Resolved
    lr = live_ctx.get("last_resolved")
    if lr:
        outcome_str = "UP &#9650;" if lr["outcome"] == 1 else "DOWN &#9660;"
        outcome_color = "#3fb950" if lr["outcome"] == 1 else "#f44336"
        hits = lr["hits"]
        total_a = lr["total_agents"]
        if hits == total_a:
            verdict = "&#10003; ALL HIT"
            verdict_color = "#3fb950"
            verdict_bg = "rgba(63,185,80,0.15)"
            verdict_border = "#238636"
        elif hits == 0:
            verdict = "&#10007; ALL MISS"
            verdict_color = "#f44336"
            verdict_bg = "rgba(244,67,54,0.15)"
            verdict_border = "#da3633"
        elif hits >= total_a / 2:
            verdict = f"&#10003; {hits}/{total_a} HIT"
            verdict_color = "#3fb950"
            verdict_bg = "rgba(63,185,80,0.10)"
            verdict_border = "#238636"
        else:
            verdict = f"&#10007; {hits}/{total_a} HIT"
            verdict_color = "#ffc107"
            verdict_bg = "rgba(255,193,7,0.10)"
            verdict_border = "#9e6a03"

        # Per-agent breakdown with check/cross
        agent_chips = ""
        for a in lr["agent_results"]:
            chip_color = "#238636" if a["correct"] else "#da3633"
            chip_bg = "rgba(63,185,80,0.15)" if a["correct"] else "rgba(244,67,54,0.15)"
            chip_icon = "&#10003;" if a["correct"] else "&#10007;"
            agent_chips += (
                f'<span class="result-chip" style="background:{chip_bg};border:1px solid {chip_color};color:{chip_color}">'
                f'{chip_icon} {a["agent"]} {a["estimate"]*100:.0f}%</span> '
            )

        q_short = lr["question"][:40] + "..." if len(lr["question"]) > 40 else lr["question"]
        live_parts.append(f"""<div class="live-card live-result" style="background:{verdict_bg};border-color:{verdict_border}">
            <div class="live-label">Last Result</div>
            <div class="live-verdict" style="color:{verdict_color}">{verdict}</div>
            <div class="live-outcome">Resolved <span style="color:{outcome_color};font-weight:700">{outcome_str}</span></div>
            <div class="live-detail">{q_short}</div>
            <div class="result-chips">{agent_chips}</div>
        </div>""")

    # Current Prediction
    cp = live_ctx.get("current_pred")
    if cp:
        q_short = cp["question"][:45] + "..." if len(cp["question"]) > 45 else cp["question"]
        live_parts.append(f"""<div class="live-card">
            <div class="live-label">Current Prediction</div>
            <div class="live-value" style="color:#58a6ff">Mkt {cp["price_yes"]:.0%}</div>
            <div class="live-detail">{q_short}</div>
            <div class="live-sub">{cp["predictions"]}</div>
        </div>""")

    live_banner_html = ""
    if live_parts:
        live_banner_html = f"""<div class="live-banner">{"".join(live_parts)}</div>"""

    # -- Aggregate Performance Banner --
    if has_data:
        perf_cards = ""
        # Agent cards
        for agent in sorted(agent_stats.keys()):
            a = agent_stats[agent]
            acc = a["accuracy"]
            ac = accuracy_color(acc)
            vs_flip = acc - 50
            vs_sign = "+" if vs_flip >= 0 else ""
            vs_color = "#3fb950" if vs_flip > 0 else ("#ffc107" if vs_flip == 0 else "#f44336")
            color = AGENT_COLORS.get(agent, "#c9d1d9")
            perf_cards += f"""<div class="perf-card">
                <div class="perf-agent" style="color:{color}">{agent}</div>
                <div class="perf-record">{a["wins"]}W - {a["losses"]}L</div>
                <div class="perf-accuracy" style="color:{ac}">{acc:.1f}%</div>
                <div class="perf-vs" style="color:{vs_color}">{vs_sign}{vs_flip:.1f}pp vs coin flip</div>
                <div class="perf-streak">{streak_badge(a["current_streak_type"], a["current_streak"])}</div>
            </div>"""

        # Ensemble card
        e_acc = ensemble["accuracy"]
        e_ac = accuracy_color(e_acc)
        e_vs = e_acc - 50
        e_sign = "+" if e_vs >= 0 else ""
        e_vs_color = "#3fb950" if e_vs > 0 else ("#ffc107" if e_vs == 0 else "#f44336")
        perf_cards += f"""<div class="perf-card perf-ensemble">
            <div class="perf-agent" style="color:#f0883e">ENSEMBLE</div>
            <div class="perf-record">{ensemble["wins"]}W - {ensemble["losses"]}L</div>
            <div class="perf-accuracy" style="color:{e_ac}">{e_acc:.1f}%</div>
            <div class="perf-vs" style="color:{e_vs_color}">{e_sign}{e_vs:.1f}pp vs coin flip</div>
            <div class="perf-streak">{streak_badge(ensemble["current_streak_type"], ensemble["current_streak"])}</div>
        </div>"""

        performance_html = f"""<h2>Performance</h2>
        <div class="perf-grid">{perf_cards}</div>"""
    else:
        performance_html = """<h2>Performance</h2>
        <p class="empty">No resolved markets yet. Waiting for first results...</p>"""

    # -- P&L Section --
    if has_data and agent_pnl:
        # Consolidated P&L across all agents
        total_pnl_all = sum(p["total_pnl"] for p in agent_pnl.values())
        total_wagered_all = sum(p["total_wagered"] for p in agent_pnl.values())
        total_bets_all = sum(p["num_bets"] for p in agent_pnl.values())
        total_wins_all = sum(p["num_wins"] for p in agent_pnl.values())
        total_losses_all = sum(p["num_losses"] for p in agent_pnl.values())
        gross_wins_all = sum(p["gross_wins"] for p in agent_pnl.values())
        gross_losses_all = sum(p["gross_losses"] for p in agent_pnl.values())
        max_dd_all = max((p["max_drawdown"] for p in agent_pnl.values()), default=0)
        roi_all = (total_pnl_all / total_wagered_all * 100) if total_wagered_all > 0 else 0
        all_color = "#3fb950" if total_pnl_all >= 0 else "#f44336"
        all_sign = "+" if total_pnl_all >= 0 else ""
        avg_win_all = (gross_wins_all / total_wins_all) if total_wins_all > 0 else 0
        avg_loss_all = (gross_losses_all / total_losses_all) if total_losses_all > 0 else 0

        consolidated_html = f"""<div class="consolidated-pnl">
            <div class="consolidated-label">TOTAL PORTFOLIO</div>
            <div class="consolidated-return" style="color:{all_color}">{all_sign}${total_pnl_all:,.0f}</div>
            <div class="consolidated-detail">{total_bets_all} discrete bets &middot; {roi_all:+.0f}% ROI</div>
            <div class="pnl-asymmetry">
                <div class="pnl-asym-row">
                    <span class="pnl-asym-label" style="color:#3fb950">{total_wins_all}W</span>
                    <span class="pnl-asym-bar-wrap"><span class="pnl-asym-bar" style="background:#3fb950;width:{max(5, gross_wins_all / max(gross_wins_all, abs(gross_losses_all), 1) * 100):.0f}%"></span></span>
                    <span class="pnl-asym-val" style="color:#3fb950">+${gross_wins_all:,.0f}</span>
                    <span class="pnl-asym-avg">avg +${avg_win_all:,.0f}/win</span>
                </div>
                <div class="pnl-asym-row">
                    <span class="pnl-asym-label" style="color:#f44336">{total_losses_all}L</span>
                    <span class="pnl-asym-bar-wrap"><span class="pnl-asym-bar" style="background:#f44336;width:{max(5, abs(gross_losses_all) / max(gross_wins_all, abs(gross_losses_all), 1) * 100):.0f}%"></span></span>
                    <span class="pnl-asym-val" style="color:#f44336">${gross_losses_all:,.0f}</span>
                    <span class="pnl-asym-avg">fixed ${avg_loss_all:,.0f}/loss</span>
                </div>
            </div>
            <div class="consolidated-detail" style="margin-top:8px;font-size:0.75rem;color:#8b949e">
                Max drawdown: <span style="color:#f44336">${max_dd_all:,.0f}</span>
                &middot; Cumulative risked: ${total_wagered_all:,.0f} (sequential, not simultaneous)
            </div>
        </div>"""

        pnl_cards = ""
        for agent in sorted(agent_pnl.keys()):
            p = agent_pnl[agent]
            color = AGENT_COLORS.get(agent, "#c9d1d9")
            pnl_color = "#3fb950" if p["total_pnl"] >= 0 else "#f44336"
            pnl_sign = "+" if p["total_pnl"] >= 0 else ""
            roi_sign = "+" if p["roi"] >= 0 else ""
            wr = (p["num_wins"] / p["num_bets"] * 100) if p["num_bets"] > 0 else 0
            pnl_cards += f"""<div class="perf-card">
                <div class="perf-agent" style="color:{color}">{agent}</div>
                <div class="perf-accuracy" style="color:{pnl_color}">{pnl_sign}${p["total_pnl"]:,.0f}</div>
                <div class="perf-record">{p["num_wins"]}W-{p["num_losses"]}L ({wr:.0f}% WR)</div>
                <div class="perf-vs" style="color:#3fb950">+${p["gross_wins"]:,.0f} won (avg +${p["avg_win"]:,.0f})</div>
                <div class="perf-vs" style="color:#f44336">${p["gross_losses"]:,.0f} lost (fixed ${p["avg_loss"]:,.0f})</div>
                <div class="perf-vs" style="color:#8b949e">Max DD: ${p["max_drawdown"]:,.0f} &middot; {roi_sign}{p["roi"]:.0f}% ROI</div>
            </div>"""

        # Ensemble P&L card
        ep = ensemble_pnl
        ep_color = "#3fb950" if ep["total_pnl"] >= 0 else "#f44336"
        ep_sign = "+" if ep["total_pnl"] >= 0 else ""
        ep_roi_sign = "+" if ep["roi"] >= 0 else ""
        pnl_cards += f"""<div class="perf-card perf-ensemble">
            <div class="perf-agent" style="color:#f0883e">ENSEMBLE</div>
            <div class="perf-accuracy" style="color:{ep_color}">{ep_sign}${ep["total_pnl"]:,.0f}</div>
            <div class="perf-record">{ep["num_bets"]} bets &middot; {ep_roi_sign}{ep["roi"]:.0f}% ROI</div>
            <div class="perf-vs">from ${ep["total_wagered"]:,.0f} cumulative ({ep["num_skipped"]} skipped)</div>
        </div>"""

        # EV & Breakeven analysis
        ev_data = compute_ev_breakeven(agent_pnl)
        ev_html = ""
        if ev_data["total_bets"] >= 2:
            ev = ev_data["ev"]
            be_wr = ev_data["breakeven_wr"]
            cur_wr = ev_data["current_wr"]
            margin = ev_data["margin"]
            ev_color = "#3fb950" if ev >= 0 else "#f44336"
            ev_sign = "+" if ev >= 0 else ""
            margin_color = "#3fb950" if margin >= 0 else "#f44336"
            margin_sign = "+" if margin >= 0 else ""
            # Gauge: bar from 0% to 100%, marker at breakeven, fill to current WR
            gauge_fill_pct = min(100, max(0, cur_wr * 100))
            gauge_be_pct = min(100, max(0, be_wr * 100))
            ev_html = f"""<div class="ev-box">
                <div class="ev-row">
                    <div class="ev-metric">
                        <div class="ev-label">EV per bet</div>
                        <div class="ev-value" style="color:{ev_color}">{ev_sign}${ev:,.1f}</div>
                    </div>
                    <div class="ev-metric">
                        <div class="ev-label">Breakeven WR</div>
                        <div class="ev-value">{be_wr*100:.1f}%</div>
                    </div>
                    <div class="ev-metric">
                        <div class="ev-label">Current WR</div>
                        <div class="ev-value" style="color:{margin_color}">{cur_wr*100:.1f}%</div>
                    </div>
                    <div class="ev-metric">
                        <div class="ev-label">Edge</div>
                        <div class="ev-value" style="color:{margin_color}">{margin_sign}{margin*100:.1f}pp</div>
                    </div>
                </div>
                <div class="ev-gauge-wrap">
                    <div class="ev-gauge-bg">
                        <div class="ev-gauge-fill" style="width:{gauge_fill_pct:.0f}%;background:{margin_color}"></div>
                        <div class="ev-gauge-marker" style="left:{gauge_be_pct:.0f}%" title="Breakeven: {be_wr*100:.1f}%"></div>
                    </div>
                    <div class="ev-gauge-labels">
                        <span>0%</span>
                        <span style="position:absolute;left:{gauge_be_pct:.0f}%;transform:translateX(-50%);color:#c9d1d9;font-weight:700">BE</span>
                        <span>100%</span>
                    </div>
                </div>
            </div>"""

        pnl_html = f"""<h2>Simulated P&amp;L</h2>
        <p class="section-desc">Binary options: wins are variable (depends on entry price), losses are fixed ($75 or $200). Bets are discrete and sequential.</p>
        {consolidated_html}
        {ev_html}
        <div class="perf-grid">{pnl_cards}</div>
        <div class="chart-container" style="margin-top:16px">
            <h3 style="color:#8b949e;font-size:0.9rem;margin-bottom:8px">Per-Bet Waterfall</h3>
            {build_waterfall_svg(agent_pnl)}
        </div>
        <div class="chart-container" style="margin-top:16px">
            <h3 style="color:#8b949e;font-size:0.9rem;margin-bottom:8px">Win/Loss Distribution</h3>
            {build_distribution_svg(agent_pnl)}
        </div>
        <div class="chart-container" style="margin-top:16px">
            <h3 style="color:#8b949e;font-size:0.9rem;margin-bottom:8px">Cumulative P&amp;L</h3>
            {build_pnl_svg(agent_pnl, ensemble_pnl)}
        </div>"""
    else:
        pnl_html = ""

    # -- Conviction Breakdown (v2) --
    conviction_html = ""
    if has_data and conviction_tiers:
        has_conviction_data = any(t != "UNKNOWN" for t in conviction_tiers.keys())
        if has_conviction_data:
            tier_colors = {
                "HIGH": "#3fb950", "MEDIUM": "#58a6ff",
                "LOW": "#ffc107", "NO_BET": "#8b949e", "UNKNOWN": "#484f58",
            }
            tier_labels = {
                "HIGH": "HIGH (4-5)", "MEDIUM": "MEDIUM (3)",
                "LOW": "LOW (2)", "NO_BET": "NO BET (0-1)", "UNKNOWN": "N/A",
            }
            tier_bets = {"NO_BET": "$0", "LOW": "$25", "MEDIUM": "$75", "HIGH": "$200", "UNKNOWN": "$0"}

            conv_rows = ""
            total_conv_pnl = 0.0
            total_conv_wagered = 0.0
            for tier_name in ["HIGH", "MEDIUM", "LOW", "NO_BET"]:
                ts = conviction_tiers.get(tier_name)
                if ts is None or ts["total"] == 0:
                    continue
                tc = tier_colors.get(tier_name, "#8b949e")
                acc = ts["accuracy"]
                acc_c = accuracy_color(acc)
                pnl_str = f"${ts['pnl']:+,.0f}" if ts["wagered"] > 0 else "—"
                pnl_c = "#3fb950" if ts["pnl"] >= 0 else "#f44336"
                roi_str = f"{ts['roi']:+.0f}%" if ts["wagered"] > 0 else "—"
                total_conv_pnl += ts["pnl"]
                total_conv_wagered += ts["wagered"]
                conv_rows += f"""<tr>
                    <td style="color:{tc};font-weight:700">{tier_labels.get(tier_name, tier_name)}</td>
                    <td>{ts["total"]}</td>
                    <td style="color:{acc_c}">{acc:.1f}%</td>
                    <td>{ts["wins"]}</td>
                    <td>{ts["losses"]}</td>
                    <td>{tier_bets.get(tier_name, '$0')}</td>
                    <td style="color:{pnl_c}">{pnl_str}</td>
                    <td>{roi_str}</td>
                </tr>"""

            total_roi = total_conv_pnl / total_conv_wagered * 100 if total_conv_wagered > 0 else 0
            total_c = "#3fb950" if total_conv_pnl >= 0 else "#f44336"

            conviction_html = f"""<h2>Conviction Scoreboard</h2>
            <p class="section-desc">Conviction measures agreement across 5 independent signal layers. Higher conviction = bigger bet. Only bet when conviction &ge; 2.</p>
            <div class="table-wrap"><table>
                <thead><tr>
                    <th>Tier</th><th>Markets</th><th>Accuracy</th><th>W</th><th>L</th><th>Bet Size</th><th>P&amp;L</th><th>ROI</th>
                </tr></thead>
                <tbody>{conv_rows}
                <tr style="border-top:2px solid #30363d">
                    <td style="font-weight:700;color:#f0883e">TOTAL (bets only)</td>
                    <td></td><td></td><td></td><td></td>
                    <td></td>
                    <td style="color:{total_c};font-weight:700">${total_conv_pnl:+,.0f}</td>
                    <td style="font-weight:700">{total_roi:+.0f}%</td>
                </tr></tbody>
            </table></div>"""

    # -- Time Series Chart --
    chart_html = f"""<h2>Rolling Accuracy (last 10 predictions)</h2>
    <div class="chart-container">{build_time_series_svg(rolling)}</div>"""

    # -- Hit Rate Table --
    if has_data:
        hitrate_rows = ""
        for agent in sorted(agent_stats.keys()):
            a = agent_stats[agent]
            color = AGENT_COLORS.get(agent, "#c9d1d9")
            last10_color = accuracy_color(a["last10_acc"])
            hitrate_rows += f"""<tr>
                <td class="agent-name" style="color:{color}">{agent}</td>
                <td>{a["wins"]}-{a["losses"]}</td>
                <td style="color:{accuracy_color(a["accuracy"])}">{a["accuracy"]:.1f}%</td>
                <td style="color:{last10_color}">{a["last10_acc"]:.1f}%</td>
                <td>{streak_badge(a["current_streak_type"], a["current_streak"])}</td>
                <td>{streak_badge("W", a["best_w_streak"])}</td>
                <td>{streak_badge("L", a["worst_l_streak"])}</td>
            </tr>"""
        hitrate_html = f"""<h2>Win/Loss &amp; Hit Rate</h2>
        <div class="table-wrap"><table>
            <thead><tr>
                <th>Agent</th><th>Record</th><th>Accuracy</th><th>Last 10</th>
                <th>Streak</th><th>Best W</th><th>Worst L</th>
            </tr></thead>
            <tbody>{hitrate_rows}</tbody>
        </table></div>"""
    else:
        hitrate_html = ""

    # -- Agent vs Coin Flip Comparison (CSS bar chart) --
    if has_data:
        bars_html = ""
        for agent in sorted(agent_stats.keys()):
            a = agent_stats[agent]
            color = AGENT_COLORS.get(agent, "#c9d1d9")
            agent_acc = a["accuracy"]
            market_acc = a["market_accuracy"]
            agent_bar_color = "#3fb950" if agent_acc > market_acc else "#f44336"
            bars_html += f"""<div class="bar-group">
                <div class="bar-label" style="color:{color}">{agent}</div>
                <div class="bar-row">
                    <span class="bar-tag">Agent</span>
                    <div class="bar-track"><div class="bar-fill" style="width:{agent_acc}%;background:{agent_bar_color}">{agent_acc:.1f}%</div></div>
                </div>
                <div class="bar-row">
                    <span class="bar-tag">Market</span>
                    <div class="bar-track"><div class="bar-fill" style="width:{market_acc}%;background:#58a6ff">{market_acc:.1f}%</div></div>
                </div>
                <div class="bar-row">
                    <span class="bar-tag">Coin Flip</span>
                    <div class="bar-track"><div class="bar-fill" style="width:50%;background:#484f58">50.0%</div></div>
                </div>
            </div>"""
        comparison_html = f"""<h2>Agent vs Market vs Coin Flip</h2>
        <div class="bar-chart">{bars_html}</div>"""
    else:
        comparison_html = ""

    # -- Confidence Calibration --
    if has_data and calibration:
        conf_levels = ["low", "medium", "high"]
        cal_rows = ""
        for agent in sorted(calibration.keys()):
            color = AGENT_COLORS.get(agent, "#c9d1d9")
            cal_rows += f'<tr><td class="agent-name" style="color:{color}">{agent}</td>'
            agent_cal = calibration[agent]
            for level in conf_levels:
                data = agent_cal.get(level, {"correct": 0, "total": 0})
                if data["total"] > 0:
                    acc = data["correct"] / data["total"] * 100
                    cell_color = accuracy_color(acc)
                    cal_rows += f'<td style="color:{cell_color}">{acc:.0f}% <span style="color:#484f58">({data["total"]})</span></td>'
                else:
                    cal_rows += '<td style="color:#484f58">-- (0)</td>'
            cal_rows += "</tr>"

        calibration_html = f"""<h2>Confidence Calibration</h2>
        <p class="section-desc">When an agent says "high confidence", are they right more often?</p>
        <div class="table-wrap"><table>
            <thead><tr>
                <th>Agent</th><th>Low</th><th>Medium</th><th>High</th>
            </tr></thead>
            <tbody>{cal_rows}</tbody>
        </table></div>"""
    else:
        calibration_html = ""

    # -- Recent Predictions --
    prediction_rows = ""
    if predictions:
        for row in predictions:
            if row["resolved"]:
                correct = is_correct(row["estimate"], row["outcome"])
                outcome_str = '<span class="badge badge-yes">UP</span>' if row["outcome"] == 1 else '<span class="badge badge-no">DOWN</span>'
                result_icon = '<span style="color:#3fb950">&#10003;</span>' if correct else '<span style="color:#f44336">&#10007;</span>'
                outcome_str = f"{result_icon} {outcome_str}"
            else:
                outcome_str = '<span class="badge badge-pending">Pending</span>'
            question = row["question"]
            if len(question) > 80:
                question = question[:77] + "..."
            prediction_rows += f"""<tr>
                <td class="agent-name">{row["agent"]}</td>
                <td title="{row["question"]}">{question}</td>
                <td>{row["estimate"]:.1%}</td>
                <td>{row["price_yes"]:.1%}</td>
                <td>{row["edge"]:+.1%}</td>
                <td>{row["confidence"]}</td>
                <td>{outcome_str}</td>
                <td>C{row["cycle"]}</td>
            </tr>"""
    else:
        prediction_rows = '<tr><td colspan="8" class="empty">No predictions yet.</td></tr>'

    # -- Technical Metrics (Brier) --
    scorecard_rows = ""
    if scorecard:
        for row in scorecard:
            agent = row["agent"]
            avg_brier = row["avg_brier"]
            num = row["num_markets"]
            vs = row["vs_market"]
            bc = brier_color(avg_brier)
            vc = vs_market_color(vs)
            beating = "BEATING" if vs < 0 else "LOSING TO"
            scorecard_rows += f"""<tr>
                <td class="agent-name">{agent}</td>
                <td style="color:{bc};font-weight:600">{avg_brier:.4f}</td>
                <td>{num}</td>
                <td style="color:{vc}">{vs:+.4f} ({beating} market)</td>
            </tr>"""
    else:
        scorecard_rows = '<tr><td colspan="4" class="empty">No resolved markets yet.</td></tr>'

    # -- Markets --
    market_rows = ""
    if markets:
        for row in markets:
            if row["resolved"]:
                mstatus = '<span class="badge badge-yes">UP</span>' if row["outcome"] == 1 else '<span class="badge badge-no">DOWN</span>'
            else:
                mstatus = '<span class="badge badge-pending">Pending</span>'
            question = row["question"]
            if len(question) > 90:
                question = question[:87] + "..."
            vol = row["volume"]
            vol_str = f"${vol:,.0f}" if vol else "$0"
            market_rows += f"""<tr>
                <td title="{row["question"]}">{question}</td>
                <td>{row["category"] or "N/A"}</td>
                <td>{row["price_yes"]:.1%}</td>
                <td>{vol_str}</td>
                <td>{row["end_date"][:10] if row["end_date"] else "N/A"}</td>
                <td>{mstatus}</td>
            </tr>"""
    else:
        market_rows = '<tr><td colspan="6" class="empty">No markets tracked yet.</td></tr>'

    # -- Evolution History --
    evolution_items = ""
    if evolution:
        for entry in reversed(evolution):
            cycle = entry.get("cycle", "?")
            ts = entry.get("timestamp", "?")
            if isinstance(ts, str) and len(ts) > 16:
                ts = ts[:16].replace("T", " ")
            agent = entry.get("agent", "?")
            brier_before = entry.get("brier_before")
            brier_after = entry.get("brier_after")
            kept = entry.get("kept")
            mod = entry.get("modification", "")
            diagnosis = "N/A"
            expected = ""
            if isinstance(mod, dict):
                diagnosis = mod.get("diagnosis", "N/A")
                expected = mod.get("expected_effect", "")
            elif isinstance(mod, str):
                for line in mod.split("\n"):
                    if line.startswith("Diagnosis: "):
                        diagnosis = line[len("Diagnosis: "):]
                    elif line.startswith("Expected effect: "):
                        expected = line[len("Expected effect: "):]

            kept_badge = ""
            if kept is True:
                kept_badge = '<span class="badge badge-yes">Kept</span>'
            elif kept is False:
                kept_badge = '<span class="badge badge-no">Reverted</span>'
            else:
                kept_badge = '<span class="badge badge-pending">Pending</span>'

            brier_before_str = f"{brier_before:.4f}" if brier_before is not None else "N/A"
            brier_after_str = f"{brier_after:.4f}" if brier_after is not None else "N/A"

            evolution_items += f"""<div class="evo-card">
                <div class="evo-header">
                    <span class="evo-cycle">Cycle {cycle}</span>
                    <span class="evo-agent agent-name">{agent}</span>
                    <span class="evo-time">{ts}</span>
                    {kept_badge}
                </div>
                <div class="evo-body">
                    <p><strong>Diagnosis:</strong> {diagnosis}</p>
                    {"<p><strong>Expected effect:</strong> " + expected + "</p>" if expected else ""}
                    <p class="evo-scores">Brier: {brier_before_str} &rarr; {brier_after_str}</p>
                </div>
            </div>"""
    else:
        evolution_items = '<p class="empty">No evolution history yet.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Polymarket Bot Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    line-height: 1.5;
    padding: 20px;
}}
h1 {{
    color: #58a6ff;
    font-size: 1.8rem;
    margin-bottom: 8px;
}}
.subtitle {{
    color: #8b949e;
    margin-bottom: 28px;
    font-size: 0.95rem;
}}
h2 {{
    color: #58a6ff;
    font-size: 1.25rem;
    margin: 32px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #21262d;
}}
.section-desc {{
    color: #8b949e;
    font-size: 0.85rem;
    margin-bottom: 12px;
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-size: 0.9rem;
}}
th {{
    background: #161b22;
    color: #58a6ff;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid #21262d;
    white-space: nowrap;
}}
td {{
    padding: 8px 12px;
    border-bottom: 1px solid #21262d;
    vertical-align: middle;
    max-width: 320px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}}
tr:hover {{
    background: #161b22;
}}
.agent-name {{
    color: #d2a8ff;
    font-weight: 600;
}}
.badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
}}
.badge-yes {{
    background: #238636;
    color: #fff;
}}
.badge-no {{
    background: #da3633;
    color: #fff;
}}
.badge-pending {{
    background: #30363d;
    color: #8b949e;
    border: 1px solid #484f58;
}}
.empty {{
    text-align: center;
    color: #484f58;
    padding: 24px;
    font-style: italic;
}}

/* Performance Cards */
.perf-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
}}
.perf-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
}}
.perf-ensemble {{
    border-color: #f0883e;
    border-width: 2px;
}}
.consolidated-pnl {{
    background: #161b22;
    border: 2px solid #3fb950;
    border-radius: 10px;
    padding: 24px;
    text-align: center;
    margin-bottom: 16px;
}}
.consolidated-label {{
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #8b949e;
    margin-bottom: 4px;
}}
.consolidated-return {{
    font-size: 3rem;
    font-weight: 800;
    line-height: 1.1;
}}
.consolidated-detail {{
    color: #8b949e;
    font-size: 0.9rem;
    margin: 4px 0;
}}
.consolidated-profit {{
    font-size: 1.1rem;
    font-weight: 700;
}}
.pnl-asymmetry {{
    margin-top: 12px;
    text-align: left;
    max-width: 500px;
    margin-left: auto;
    margin-right: auto;
}}
.pnl-asym-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 4px 0;
    font-size: 0.85rem;
}}
.pnl-asym-label {{
    width: 30px;
    font-weight: 700;
    text-align: right;
    flex-shrink: 0;
}}
.pnl-asym-bar-wrap {{
    flex: 1;
    background: #21262d;
    border-radius: 4px;
    height: 18px;
    overflow: hidden;
}}
.pnl-asym-bar {{
    display: block;
    height: 100%;
    border-radius: 4px;
    min-width: 4px;
}}
.pnl-asym-val {{
    width: 80px;
    font-weight: 700;
    text-align: right;
    flex-shrink: 0;
}}
.pnl-asym-avg {{
    color: #8b949e;
    font-size: 0.75rem;
    width: 110px;
    flex-shrink: 0;
}}
/* EV & Breakeven Box */
.ev-box {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 16px;
}}
.ev-row {{
    display: flex;
    justify-content: space-around;
    gap: 16px;
    margin-bottom: 12px;
}}
.ev-metric {{
    text-align: center;
}}
.ev-label {{
    font-size: 0.7rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}}
.ev-value {{
    font-size: 1.3rem;
    font-weight: 700;
    color: #c9d1d9;
}}
.ev-gauge-wrap {{
    max-width: 500px;
    margin: 0 auto;
}}
.ev-gauge-bg {{
    position: relative;
    height: 14px;
    background: #21262d;
    border-radius: 7px;
    overflow: visible;
}}
.ev-gauge-fill {{
    height: 100%;
    border-radius: 7px;
    opacity: 0.7;
    transition: width 0.3s;
}}
.ev-gauge-marker {{
    position: absolute;
    top: -4px;
    width: 3px;
    height: 22px;
    background: #c9d1d9;
    border-radius: 2px;
    transform: translateX(-50%);
}}
.ev-gauge-labels {{
    display: flex;
    justify-content: space-between;
    font-size: 0.7rem;
    color: #484f58;
    margin-top: 2px;
    position: relative;
}}
.perf-agent {{
    font-size: 0.85rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}}
.perf-record {{
    font-size: 1.6rem;
    font-weight: 700;
    color: #c9d1d9;
    margin-bottom: 4px;
}}
.perf-accuracy {{
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 4px;
}}
.perf-vs {{
    font-size: 0.85rem;
    margin-bottom: 8px;
}}
.perf-streak {{
    margin-top: 4px;
}}

/* Streaks */
.streak {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
}}
.streak-w {{
    background: #238636;
    color: #fff;
}}
.streak-l {{
    background: #da3633;
    color: #fff;
}}

/* Bar Chart */
.bar-chart {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 20px;
}}
.bar-group {{
    margin-bottom: 20px;
}}
.bar-group:last-child {{
    margin-bottom: 0;
}}
.bar-label {{
    font-weight: 700;
    font-size: 0.9rem;
    margin-bottom: 6px;
}}
.bar-row {{
    display: flex;
    align-items: center;
    margin-bottom: 4px;
    gap: 8px;
}}
.bar-tag {{
    width: 55px;
    font-size: 0.75rem;
    color: #8b949e;
    text-align: right;
    flex-shrink: 0;
}}
.bar-track {{
    flex: 1;
    height: 22px;
    background: #0d1117;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}}
.bar-fill {{
    height: 100%;
    border-radius: 4px;
    display: flex;
    align-items: center;
    padding-left: 8px;
    font-size: 0.75rem;
    font-weight: 600;
    color: #fff;
    min-width: 45px;
    transition: width 0.3s ease;
}}

/* Chart */
.chart-container {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 8px;
}}
.chart-legend {{
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    justify-content: center;
    padding-top: 12px;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: #8b949e;
}}
.legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
}}
.legend-line {{
    width: 16px;
    height: 0;
    border-top: 2px dashed;
    display: inline-block;
}}

/* Evolution */
.evo-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}}
.evo-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}}
.evo-cycle {{
    color: #58a6ff;
    font-weight: 700;
    font-size: 0.95rem;
}}
.evo-time {{
    color: #484f58;
    font-size: 0.85rem;
    margin-left: auto;
}}
.evo-body p {{
    margin: 4px 0;
    font-size: 0.9rem;
}}
.evo-scores {{
    color: #8b949e;
    font-size: 0.85rem;
}}

/* Pipeline Health Banner */
.pipeline-banner {{
    background: #161b22;
    border: 2px solid #21262d;
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
}}
.pipeline-main {{
    display: flex;
    align-items: center;
    gap: 16px;
}}
.pipeline-fraction {{
    font-weight: 800;
}}
.pipeline-big {{
    font-size: 2.2rem;
    line-height: 1;
}}
.pipeline-slash {{
    font-size: 1.2rem;
    opacity: 0.6;
}}
.pipeline-labels {{
    display: flex;
    flex-direction: column;
}}
.pipeline-status {{
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.08em;
}}
.pipeline-desc {{
    color: #8b949e;
    font-size: 0.8rem;
}}
.pipeline-meta {{
    text-align: right;
}}
.pipeline-detail {{
    color: #8b949e;
    font-size: 0.8rem;
}}
.pipeline-ago {{
    color: #8b949e;
    font-size: 0.75rem;
    margin-top: 2px;
}}

/* Live Context Banner */
.live-banner {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
}}
.live-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 14px 18px;
}}
.live-label {{
    color: #484f58;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
}}
.live-value {{
    font-size: 1.5rem;
    font-weight: 800;
    color: #c9d1d9;
    margin-bottom: 2px;
}}
.live-detail {{
    font-size: 0.8rem;
    color: #8b949e;
}}
.live-sub {{
    font-size: 0.72rem;
    color: #484f58;
    margin-top: 4px;
    word-break: break-all;
}}
.live-result {{
    border-width: 2px;
}}
.live-verdict {{
    font-size: 1.8rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 4px;
}}
.live-outcome {{
    font-size: 0.85rem;
    color: #8b949e;
    margin-bottom: 4px;
}}
.result-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}}
.result-chip {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 14px;
    font-size: 0.72rem;
    font-weight: 700;
    white-space: nowrap;
}}

/* Status Bar */
.status-bar {{
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 24px;
}}
.status-item {{
    display: flex;
    flex-direction: column;
    gap: 2px;
}}
.status-label {{
    color: #484f58;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.status-value {{
    color: #c9d1d9;
    font-size: 1rem;
    font-weight: 600;
}}
.table-wrap {{
    overflow-x: auto;
}}
@media (max-width: 768px) {{
    body {{ padding: 10px; }}
    h1 {{ font-size: 1.4rem; }}
    td, th {{ padding: 6px 8px; font-size: 0.82rem; }}
    .perf-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .evo-header {{ flex-direction: column; align-items: flex-start; gap: 4px; }}
    .evo-time {{ margin-left: 0; }}
}}
</style>
</head>
<body>
<div class="container">
    <h1>Polymarket Autoresearch Bot</h1>
    <p class="subtitle">BTC 5-minute candle prediction &mdash; autoresearch loop</p>

    {status_html}

    {observation_html}

    {pipeline_html}

    {live_banner_html}

    {performance_html}

    {pnl_html}

    {conviction_html}

    {chart_html}

    {hitrate_html}

    {comparison_html}

    {calibration_html}

    <h2>Recent Predictions</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Agent</th>
            <th>Market</th>
            <th>Estimate</th>
            <th>Market Price</th>
            <th>Edge</th>
            <th>Confidence</th>
            <th>Outcome</th>
            <th>Cycle</th>
        </tr></thead>
        <tbody>{prediction_rows}</tbody>
    </table>
    </div>

    <h2>Technical Metrics (Brier Scores)</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Agent</th>
            <th>Avg Brier Score</th>
            <th>Resolved Markets</th>
            <th>vs Market</th>
        </tr></thead>
        <tbody>{scorecard_rows}</tbody>
    </table>
    </div>

    <h2>Markets</h2>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Question</th>
            <th>Category</th>
            <th>Price (UP)</th>
            <th>Volume</th>
            <th>End Date</th>
            <th>Status</th>
        </tr></thead>
        <tbody>{market_rows}</tbody>
    </table>
    </div>

    <h2>Evolution History</h2>
    {evolution_items}
</div>
<script>
(function() {{
    var el = document.getElementById('countdown');
    if (!el) return;
    var endStr = el.getAttribute('data-next-market');
    if (!endStr) {{ el.textContent = 'No upcoming market'; return; }}
    var end = new Date(endStr.replace('Z','+00:00'));
    function update() {{
        var now = new Date();
        var diff = Math.floor((end - now) / 1000);
        if (diff <= 0) {{ el.textContent = 'Resolving...'; return; }}
        var h = Math.floor(diff / 3600);
        var m = Math.floor((diff % 3600) / 60);
        var s = diff % 60;
        if (h > 0) {{
            el.textContent = h + 'h ' + m + 'm';
        }} else {{
            el.textContent = m + 'm ' + (s < 10 ? '0' : '') + s + 's';
        }}
    }}
    update();
    setInterval(update, 1000);
}})();
</script>
</body>
</html>"""


if app:
    @app.route("/")
    def index():
        html = build_html()
        return Response(html, mimetype="text/html")


if __name__ == "__main__":
    if app is None:
        print("Flask not installed. Use generate_dashboard.py instead.")
    else:
        print(f"Dashboard: http://localhost:5050")
        print(f"Database:  {DB_PATH}")
        app.run(host="0.0.0.0", port=5050, debug=True)
