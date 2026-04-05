"""Data layer: all SQLite queries and Polymarket API integration.

Every function returns dicts with a _provenance key for display.
Time series always pair values with ISO timestamps.
"""

import sqlite3
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import (
    PAPER_BTC_CONVICTION_BETS, PAPER_ETH_CONVICTION_BETS,
    LIVE_BTC_CONVICTION_BETS, LIVE_ETH_CONVICTION_BETS,
    LIVE_START_DATE, DAILY_LOSS_LIMIT, CONSECUTIVE_LOSS_MAX,
    MIN_CONVICTION, EDGE_THRESHOLD, PRICE_GATE_UPPER, PRICE_GATE_LOWER,
    EXTREME_ESTIMATE_UPPER, EXTREME_ESTIMATE_LOWER,
    BYBIT_DAILY_LOSS_LIMIT, BYBIT_MIN_CONVICTION,
    LIVE_KALSHI_CONVICTION_BETS,
)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "predictions.db"


def get_db(db_path=None):
    path = db_path or DB_PATH
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db


def _now_utc():
    return datetime.now(timezone.utc)


def _clean_ts(ts_str):
    """Truncate to second precision + Z suffix for cross-browser D3 compat.

    Python's datetime.isoformat() produces '2026-03-25T22:46:44.855951+00:00'
    which causes NaN in new Date() on some browsers due to microseconds + offset.
    """
    if not ts_str or len(ts_str) <= 20:
        return ts_str
    # Strip microseconds and timezone offset, append Z
    return ts_str[:19] + "Z"


def _provenance(source, ts=None):
    return {"source": source, "fetched_at": (ts or _now_utc()).isoformat(timespec="seconds")}


# ---------------------------------------------------------------------------
# Pipeline summary
# ---------------------------------------------------------------------------

def get_pipeline_summary(db):
    """Status, last cycle, markets count, health."""
    now = _now_utc()
    row = db.execute("SELECT MAX(predicted_at) FROM predictions").fetchone()
    last_prediction = row[0] if row and row[0] else None

    total = db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1").fetchone()[0]

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

    # Pipeline health from cycle gaps
    rows = db.execute("""
        SELECT cycle, MIN(predicted_at) as cycle_time
        FROM predictions GROUP BY cycle
        ORDER BY cycle DESC LIMIT 50
    """).fetchall()
    timestamps = []
    for r in rows:
        try:
            dt = datetime.fromisoformat(r[1].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamps.append(dt)
        except (ValueError, TypeError):
            continue
    timestamps.sort()
    on_time = 0
    total_gaps = 0
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
        total_gaps += 1
        if gap <= 15:
            on_time += 1
    health_pct = (on_time / total_gaps * 100) if total_gaps > 0 else 100

    return {
        "status": status,
        "last_prediction": last_prediction[:16].replace("T", " ") if last_prediction else "Never",
        "total_markets": total,
        "resolved_markets": resolved,
        "health_pct": round(health_pct, 1),
        "on_time": on_time,
        "total_cycles": len(timestamps),
        "_provenance": _provenance("SQLite"),
    }


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def detect_mode(db):
    """Detect pipeline mode from orders table."""
    try:
        tbl = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()
        if tbl:
            row = db.execute("SELECT COUNT(*) FROM orders WHERE mode='live'").fetchone()
            if row and row[0] > 0:
                return "live"
    except Exception:
        pass
    return "paper"


# ---------------------------------------------------------------------------
# Trade execution status (order fill tracking)
# ---------------------------------------------------------------------------

def get_trade_execution(db):
    """Order execution stats: filled, pending, expired, fill rate."""
    try:
        tbl = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()
        if not tbl:
            return None

        # All-time live order stats by status
        rows = db.execute("""
            SELECT status, COUNT(*) as cnt
            FROM orders WHERE mode='live'
            GROUP BY status
        """).fetchall()
        status_counts = {r[0]: r[1] for r in rows}

        filled = status_counts.get("filled", 0) + status_counts.get("settled", 0)
        pending = status_counts.get("pending", 0) + status_counts.get("submitted", 0)
        expired = status_counts.get("expired", 0)
        failed = status_counts.get("failed", 0)
        total = filled + pending + expired + failed

        fill_rate = (filled / (filled + expired) * 100) if (filled + expired) > 0 else 0

        # Today's orders
        today = _now_utc().strftime("%Y-%m-%d")
        today_row = db.execute("""
            SELECT COUNT(*), COALESCE(SUM(size), 0)
            FROM orders WHERE mode='live' AND placed_at LIKE ?
        """, (f"{today}%",)).fetchone()

        # Last order time
        last_row = db.execute(
            "SELECT placed_at FROM orders WHERE mode='live' ORDER BY placed_at DESC LIMIT 1"
        ).fetchone()
        last_order = last_row[0][:16].replace("T", " ") if last_row and last_row[0] else None

        return {
            "filled": filled,
            "pending": pending,
            "expired": expired,
            "failed": failed,
            "total": total,
            "fill_rate": round(fill_rate, 1),
            "today_count": today_row[0],
            "today_wagered": round(today_row[1], 2),
            "last_order": last_order,
            "_provenance": _provenance("SQLite (orders)"),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Recent bets (last N orders with resolution status)
# ---------------------------------------------------------------------------

def _fetch_onchain_fills():
    """Fetch on-chain activity and build a lookup by market title.

    Returns dict: {market_title: {"cost": float, "payout": float, "filled": bool}}
    """
    try:
        from polymarket_pnl import fetch_activity
        activities = fetch_activity()
        if not activities:
            return {}
        from collections import defaultdict
        markets = defaultdict(lambda: {"cost": 0, "payout": 0, "filled": False})
        for a in activities:
            title = a.get("title", "")
            if not title:
                continue
            if a.get("type") == "TRADE":
                markets[title]["cost"] += a.get("usdcSize", 0)
                markets[title]["filled"] = True
            elif a.get("type") == "REDEEM":
                markets[title]["payout"] += a.get("usdcSize", 0)
        return dict(markets)
    except Exception:
        return {}


def get_recent_bets(db, limit=10):
    """Last N orders with market resolution data. Works for both paper and live.

    Cross-references Polymarket Data API to detect orders that filled
    on-chain but are stuck as 'submitted' in the orders table.
    """
    import re

    try:
        tbl = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()
        if not tbl:
            return None

        rows = db.execute(f"""
            SELECT o.direction, o.size, o.price_limit, o.price_filled,
                   o.status, o.mode, o.placed_at, o.pnl, o.settled_at,
                   o.reason,
                   m.question, m.outcome, m.resolved
            FROM orders o
            LEFT JOIN markets m ON o.market_id = m.id
            ORDER BY o.placed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

        # Fetch on-chain fills for cross-referencing
        onchain = _fetch_onchain_fills()

        bets = []
        for r in rows:
            question = r["question"] or ""
            time_match = re.search(r'(\w+ \d+, \d+:\d+(?:AM|PM)-\d+:\d+(?:AM|PM) ET)', question)
            time_label = time_match.group(1) if time_match else (r["placed_at"] or "")[:16].replace("T", " ")

            status = r["status"]
            outcome = r["outcome"]
            resolved = r["resolved"]
            direction = r["direction"]

            # Check if this order actually filled on-chain despite orders table status
            chain_data = onchain.get(question)
            chain_filled = chain_data["filled"] if chain_data else False

            if status == "failed":
                result = "FAILED"
                result_detail = (r["reason"] or "")[:40] if r["reason"] else "API error"
            elif status in ("submitted", "pending"):
                if chain_filled and resolved and outcome is not None:
                    # Order filled on-chain! Compute real P&L from chain data
                    cost = chain_data["cost"]
                    payout = chain_data["payout"]
                    profit = payout - cost
                    won = payout > 0
                    result = "WIN" if won else "LOSS"
                    result_detail = f"${profit:+.2f} (on-chain)"
                elif resolved and outcome is not None:
                    would_win = (direction == "UP" and outcome == 1) or (direction == "DOWN" and outcome == 0)
                    result = "EXPIRED (would have won)" if would_win else "EXPIRED (would have lost)"
                    result_detail = ""
                else:
                    result = "PENDING"
                    result_detail = ""
            elif status == "settled":
                if r["pnl"] is not None and r["pnl"] > 0:
                    result = "WIN"
                elif r["pnl"] is not None and r["pnl"] < 0:
                    result = "LOSS"
                else:
                    result = "SETTLED"
                result_detail = f"${r['pnl']:+.2f}" if r["pnl"] is not None else ""
            elif status == "filled":
                if resolved and outcome is not None:
                    would_win = (direction == "UP" and outcome == 1) or (direction == "DOWN" and outcome == 0)
                    result = "WIN (unsettled)" if would_win else "LOSS (unsettled)"
                else:
                    result = "FILLED (open)"
                result_detail = ""
            elif status == "paper":
                if resolved and outcome is not None:
                    would_win = (direction == "UP" and outcome == 1) or (direction == "DOWN" and outcome == 0)
                    result = "WIN" if would_win else "LOSS"
                else:
                    result = "OPEN"
                result_detail = f"${r['pnl']:+.2f}" if r["pnl"] is not None else ""
            else:
                result = status.upper()
                result_detail = ""

            bets.append({
                "time": time_label,
                "direction": direction,
                "size": r["size"],
                "mode": r["mode"],
                "status": status,
                "result": result,
                "result_detail": result_detail,
                "filled_price": r["price_filled"],
                "limit_price": r["price_limit"],
            })

        return bets
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Live P&L (Polymarket Data API — source of truth)
# ---------------------------------------------------------------------------

def get_live_pnl(db):
    """Fetch real P&L from Polymarket Data API. Returns None if unavailable."""
    try:
        from polymarket_pnl import fetch_real_pnl
        result = fetch_real_pnl(db)
        if result is None:
            return None
        p = result["portfolio"]
        # Build timestamped series from bets_chronological
        ts = _now_utc()
        return {
            "total_pnl": p["total_pnl"],
            "total_wagered": p["total_wagered"],
            "num_bets": p["num_bets"],
            "num_wins": p["num_wins"],
            "num_losses": p["num_losses"],
            "roi": p["roi"],
            "max_drawdown": p["max_drawdown"],
            "avg_win": p["avg_win"],
            "avg_loss": p["avg_loss"],
            "pnl_series": p["pnl_series"],
            "bet_results": p["bet_results"],
            "_provenance": _provenance("Polymarket Data API", ts),
        }
    except Exception as e:
        print(f"  [DASHBOARD_V2] Live P&L fetch: {e}")
        return None


# ---------------------------------------------------------------------------
# Signal P&L (conviction-based simulation)
# ---------------------------------------------------------------------------

def _get_bet_size(conv, predicted_at, asset="BTC"):
    date_str = (predicted_at or "")[:10]
    if asset == "ETH":
        tiers = LIVE_ETH_CONVICTION_BETS if date_str >= LIVE_START_DATE else PAPER_ETH_CONVICTION_BETS
    elif asset == "KALSHI":
        tiers = LIVE_KALSHI_CONVICTION_BETS if date_str >= LIVE_START_DATE else PAPER_BTC_CONVICTION_BETS
    else:
        tiers = LIVE_BTC_CONVICTION_BETS if date_str >= LIVE_START_DATE else PAPER_BTC_CONVICTION_BETS
    return tiers.get(conv, 0)


def _is_correct(estimate, outcome):
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def get_resolved_predictions(db):
    """Get all resolved predictions ordered chronologically."""
    try:
        rows = db.execute("""
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
                   p.conviction_score, m.outcome, m.price_yes, m.end_date
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
            ORDER BY p.predicted_at ASC
        """).fetchall()
    except sqlite3.OperationalError:
        rows = db.execute("""
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
                   NULL as conviction_score, m.outcome, m.price_yes, m.end_date
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1
            ORDER BY p.predicted_at ASC
        """).fetchall()
    return [dict(r) for r in rows]


def get_signal_pnl(db, asset="BTC"):
    """Conviction-based simulated P&L with timestamped series.

    Returns per-agent and ensemble stats.
    """
    resolved = get_resolved_predictions(db)

    # Filter to active agents (predicted in last 7 days)
    cutoff_7d = (_now_utc() - timedelta(days=7)).isoformat()
    active_agents = set()
    for r in resolved:
        if (r.get("predicted_at") or "") >= cutoff_7d:
            active_agents.add(r["agent"])
    active = [r for r in resolved if r["agent"] in active_agents]
    if not active:
        active = resolved

    # Detect shadow agents (never produced conv >= 3)
    agent_max_conv = defaultdict(int)
    for r in active:
        cs = r.get("conviction_score") or 0
        agent_max_conv[r["agent"]] = max(agent_max_conv[r["agent"]], cs)
    shadow_agents = {a for a, mc in agent_max_conv.items() if mc < 3}
    production = [r for r in active if r["agent"] not in shadow_agents]
    if not production:
        production = active

    # Per-market ensemble with timestamped P&L
    market_data = defaultdict(lambda: {
        "estimates": [], "outcome": None, "price_yes": None,
        "conviction": 0, "predicted_at": "", "end_date": "",
    })
    for row in production:
        md = market_data[row["market_id"]]
        md["estimates"].append(row["estimate"])
        md["outcome"] = row["outcome"]
        md["price_yes"] = row["price_yes"]
        if row.get("conviction_score") is not None:
            md["conviction"] = row["conviction_score"]
        if row.get("predicted_at"):
            md["predicted_at"] = row["predicted_at"]
        if row.get("end_date"):
            md["end_date"] = row["end_date"]

    total_pnl = 0.0
    total_wagered = 0.0
    num_bets = 0
    num_wins = 0
    num_losses = 0
    num_skipped = 0
    gross_wins = 0.0
    gross_losses = 0.0
    pnl_series = []  # [{date, value}]
    bet_results = []  # [{date, profit, bet_size, price, won}]
    max_dd = 0.0
    peak = 0.0

    # Sort by predicted_at for chronological series
    sorted_markets = sorted(market_data.items(), key=lambda x: x[1]["predicted_at"])

    # Streak tracking
    streak_type = None
    streak_count = 0

    for mid, md in sorted_markets:
        conv = md["conviction"] or 0
        bet_size = _get_bet_size(conv, md["predicted_at"], asset)
        avg_est = sum(md["estimates"]) / len(md["estimates"])

        if bet_size == 0:
            num_skipped += 1
            continue

        outcome = md["outcome"]
        price_yes = md["price_yes"]

        if avg_est >= 0.5:
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
        won = profit > 0

        if won:
            num_wins += 1
            gross_wins += profit
        else:
            num_losses += 1
            gross_losses += profit

        # Streak
        if streak_type is None:
            streak_type = "W" if won else "L"
            streak_count = 1
        elif (won and streak_type == "W") or (not won and streak_type == "L"):
            streak_count += 1
        else:
            streak_type = "W" if won else "L"
            streak_count = 1

        ts = _clean_ts(md["predicted_at"] or md["end_date"])
        pnl_series.append({"date": ts, "value": round(total_pnl, 2)})
        bet_results.append({
            "date": ts,
            "profit": round(profit, 2),
            "bet_size": bet_size,
            "price": price_yes,
            "won": won,
        })

        if total_pnl > peak:
            peak = total_pnl
        dd = peak - total_pnl
        if dd > max_dd:
            max_dd = dd

    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0
    wr = (num_wins / num_bets * 100) if num_bets > 0 else 0
    avg_win = (gross_wins / num_wins) if num_wins > 0 else 0
    avg_loss = (gross_losses / num_losses) if num_losses > 0 else 0

    # EV metrics
    ev_per_bet = (total_pnl / num_bets) if num_bets > 0 else 0
    breakeven_wr = 0
    if avg_win > 0 and avg_loss < 0:
        breakeven_wr = abs(avg_loss) / (avg_win + abs(avg_loss)) * 100

    return {
        "total_pnl": round(total_pnl, 2),
        "total_wagered": round(total_wagered, 2),
        "num_bets": num_bets,
        "num_wins": num_wins,
        "num_losses": num_losses,
        "num_skipped": num_skipped,
        "win_rate": round(wr, 1),
        "roi": round(roi, 1),
        "max_drawdown": round(max_dd, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "ev_per_bet": round(ev_per_bet, 2),
        "breakeven_wr": round(breakeven_wr, 1),
        "edge": round(wr - breakeven_wr, 1) if breakeven_wr > 0 else 0,
        "streak": f"{streak_type}{streak_count}" if streak_type else "—",
        "pnl_series": pnl_series,
        "bet_results": bet_results,
        "_provenance": _provenance("Conviction simulation"),
    }


# ---------------------------------------------------------------------------
# Conviction breakdown
# ---------------------------------------------------------------------------

def get_conviction_breakdown(db, asset="BTC"):
    """Accuracy and P&L by conviction tier."""
    resolved = get_resolved_predictions(db)
    cutoff_7d = (_now_utc() - timedelta(days=7)).isoformat()
    active_agents = set()
    for r in resolved:
        if (r.get("predicted_at") or "") >= cutoff_7d:
            active_agents.add(r["agent"])
    active = [r for r in resolved if r["agent"] in active_agents]
    if not active:
        active = resolved

    market_data = defaultdict(lambda: {
        "estimates": [], "outcome": None, "price_yes": None,
        "conviction": None, "predicted_at": "",
    })
    for row in active:
        md = market_data[row["market_id"]]
        md["estimates"].append(row["estimate"])
        md["outcome"] = row["outcome"]
        md["price_yes"] = row["price_yes"]
        if row.get("conviction_score") is not None:
            md["conviction"] = row["conviction_score"]
        if row.get("predicted_at"):
            md["predicted_at"] = row["predicted_at"]

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

    tiers = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0, "wagered": 0.0})

    for mid, md in market_data.items():
        tier = score_to_tier(md["conviction"])
        outcome = md["outcome"]
        price_yes = md["price_yes"]
        avg_est = sum(md["estimates"]) / len(md["estimates"])
        correct = _is_correct(avg_est, outcome)

        ts = tiers[tier]
        ts["total"] += 1
        if correct:
            ts["wins"] += 1
        else:
            ts["losses"] += 1

        conv = md["conviction"] or 0
        bet_size = _get_bet_size(conv, md["predicted_at"], asset)
        if bet_size > 0:
            ts["wagered"] += bet_size
            if avg_est >= 0.5:
                if 0 < price_yes < 1:
                    ts["pnl"] += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                if 0 < price_no < 1:
                    ts["pnl"] += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

    for ts in tiers.values():
        ts["accuracy"] = round(ts["wins"] / ts["total"] * 100, 1) if ts["total"] > 0 else 0
        ts["roi"] = round(ts["pnl"] / ts["wagered"] * 100, 1) if ts["wagered"] > 0 else 0
        ts["pnl"] = round(ts["pnl"], 2)
        ts["wagered"] = round(ts["wagered"], 2)

    return dict(tiers)


# ---------------------------------------------------------------------------
# Pipeline integrity
# ---------------------------------------------------------------------------

def get_integrity_status(db):
    """Get pipeline integrity summary, or None if module unavailable."""
    try:
        from pipeline_integrity import get_integrity_summary
        return get_integrity_summary(db)
    except (ImportError, Exception):
        return None


# ---------------------------------------------------------------------------
# Circuit breakers
# ---------------------------------------------------------------------------

def get_breaker_status(db, asset="BTC", subtitle=""):
    """Current circuit breaker state."""
    is_bybit = "BYBIT" in (subtitle or "").upper()
    loss_limit = BYBIT_DAILY_LOSS_LIMIT if is_bybit else DAILY_LOSS_LIMIT
    min_conv = BYBIT_MIN_CONVICTION if is_bybit else MIN_CONVICTION
    ks_file = "KILL_SWITCH_BYBIT" if is_bybit else "KILL_SWITCH"
    ks_env = "KILL_SWITCH_BYBIT" if is_bybit else "KILL_SWITCH"

    kill_switch = (
        Path(__file__).parent.parent.parent.joinpath("data", ks_file).exists()
        or os.environ.get(ks_env, "").lower() == "true"
    )

    daily_loss = 0.0
    consecutive_losses = 0
    table_name = "positions" if is_bybit else "orders"
    date_col = "opened_at" if is_bybit else "placed_at"
    settled_col = "closed_at" if is_bybit else "settled_at"
    status_settled = "closed" if is_bybit else "settled"

    try:
        tbl = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        if tbl:
            today = _now_utc().strftime("%Y-%m-%d")
            row = db.execute(f"""
                SELECT COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0)
                FROM {table_name}
                WHERE {date_col} LIKE ? AND status IN ('filled', ?)
            """, (f"{today}%", status_settled)).fetchone()
            daily_loss = abs(row[0]) if row else 0.0

            rows = db.execute(f"""
                SELECT pnl FROM {table_name}
                WHERE status = ? AND pnl IS NOT NULL
                  AND {settled_col} LIKE ?
                ORDER BY {settled_col} DESC LIMIT 50
            """, (status_settled, f"{today}%")).fetchall()
            for r in rows:
                if r[0] < 0:
                    consecutive_losses += 1
                else:
                    break
    except Exception:
        pass

    daily_pct = (daily_loss / loss_limit * 100) if loss_limit > 0 else 0

    return {
        "kill_switch": kill_switch,
        "daily_loss": round(daily_loss, 2),
        "daily_loss_limit": loss_limit,
        "daily_loss_pct": min(round(daily_pct, 1), 100),
        "consecutive_losses": consecutive_losses,
        "consecutive_loss_max": CONSECUTIVE_LOSS_MAX,
        "min_conviction": min_conv,
        "edge_threshold": EDGE_THRESHOLD,
        "price_gate": (PRICE_GATE_LOWER, PRICE_GATE_UPPER),
        "extreme_estimate": (EXTREME_ESTIMATE_LOWER, EXTREME_ESTIMATE_UPPER),
    }


# ---------------------------------------------------------------------------
# Rolling accuracy (timestamped)
# ---------------------------------------------------------------------------

def get_rolling_accuracy(db, window=10):
    """Rolling win rate over a sliding window, with timestamps."""
    resolved = get_resolved_predictions(db)
    cutoff_7d = (_now_utc() - timedelta(days=7)).isoformat()
    active_agents = set()
    for r in resolved:
        if (r.get("predicted_at") or "") >= cutoff_7d:
            active_agents.add(r["agent"])

    # Deduplicate to one result per market (ensemble)
    market_data = {}
    for row in resolved:
        if row["agent"] not in active_agents:
            continue
        mid = row["market_id"]
        if mid not in market_data:
            market_data[mid] = {
                "estimates": [], "outcome": row["outcome"],
                "predicted_at": row["predicted_at"],
            }
        market_data[mid]["estimates"].append(row["estimate"])

    results = []
    for mid, md in sorted(market_data.items(), key=lambda x: x[1]["predicted_at"]):
        avg_est = sum(md["estimates"]) / len(md["estimates"])
        correct = _is_correct(avg_est, md["outcome"])
        results.append({"date": _clean_ts(md["predicted_at"]), "correct": correct})

    series = []
    for i in range(window - 1, len(results)):
        win_slice = results[i - window + 1:i + 1]
        wr = sum(1 for r in win_slice if r["correct"]) / window * 100
        series.append({"date": results[i]["date"], "value": round(wr, 1)})

    return series


# ---------------------------------------------------------------------------
# Engine health (websocket metrics from ws_metrics.json)
# ---------------------------------------------------------------------------

def get_engine_health():
    """Read ws_metrics.json written by botsy_engine.py.

    Returns dict with WS feed statuses, latency, reconnects, or None if
    the engine is not running (file missing or stale > 5 min).
    """
    import json
    metrics_path = Path(__file__).parent.parent.parent / "data" / "ws_metrics.json"
    if not metrics_path.exists():
        return None
    try:
        data = json.loads(metrics_path.read_text())
        # Check staleness — if engine hasn't written in 5 min, it's down
        engine_start = data.get("engine_start", "")

        return {
            "bybit_spot_status": (data.get("bybit_spot") or {}).get("status", "unknown"),
            "bybit_spot_last": (data.get("bybit_spot") or {}).get("last_event"),
            "bybit_spot_reconnects": (data.get("bybit_spot") or {}).get("reconnects_24h", 0),
            "bybit_linear_status": (data.get("bybit_linear") or {}).get("status", "unknown"),
            "bybit_linear_last": (data.get("bybit_linear") or {}).get("last_event"),
            "bybit_linear_reconnects": (data.get("bybit_linear") or {}).get("reconnects_24h", 0),
            "polymarket_status": (data.get("polymarket") or {}).get("status", "unknown"),
            "polymarket_last": (data.get("polymarket") or {}).get("last_event"),
            "polymarket_reconnects": (data.get("polymarket") or {}).get("reconnects_24h", 0),
            "dispatch_latency": data.get("dispatch_latency_ms", {}),
            "orderbook_age": data.get("orderbook_age_ms", {}),
            "fallback_fires": data.get("fallback_fires_24h", 0),
            "cycles": data.get("cycles", 0),
            "engine_start": engine_start,
        }
    except (json.JSONDecodeError, OSError):
        return None
