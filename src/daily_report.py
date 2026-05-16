"""
daily_report.py — Daily morning analysis report.

Generates a markdown report analyzing the previous day's predictions.
Covers all 5 pipelines (BTC 5m, BTC 15m, ETH 5m, Kalshi, Bybit). Designed to run via GitHub Actions cron
at 06:00 CST (12:00 UTC) daily, or on-demand.

Output: docs/daily/YYYY-MM-DD.md
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Database paths
DB_5M = Path(__file__).parent.parent / "data" / "predictions.db"
DB_15M = Path(__file__).parent.parent / "data" / "predictions_15m.db"
DB_ETH = Path(__file__).parent.parent / "data" / "predictions_eth.db"
DB_KALSHI = Path(__file__).parent.parent / "data" / "predictions_kalshi.db"
DB_BYBIT = Path(__file__).parent.parent / "data" / "predictions_bybit.db"
DB_STRATEGY_LAB = Path(__file__).parent.parent / "data" / "strategy_lab.db"
DB_ASSET_DAILY = Path(__file__).parent.parent / "data" / "asset_daily.db"
DAILY_DIR = Path(__file__).parent.parent / "docs" / "daily"

# Date-aware sizing: imported from centralized config.py
from config import (
    PAPER_BTC_CONVICTION_BETS, PAPER_ETH_CONVICTION_BETS,
    LIVE_BTC_CONVICTION_BETS, LIVE_ETH_CONVICTION_BETS,
    LIVE_KALSHI_CONVICTION_BETS, LIVE_BYBIT_CONVICTION_BETS,
    LIVE_START_DATE,
)
BTC_CONVICTION_BETS = LIVE_BTC_CONVICTION_BETS
ETH_CONVICTION_BETS = LIVE_ETH_CONVICTION_BETS
CONVICTION_BETS = BTC_CONVICTION_BETS  # default for backward compat


def _get_bet_size_dr(conv, predicted_at, asset="BTC"):
    """Return bet size based on date: paper tiers before LIVE_START_DATE, flat $25 after."""
    date_str = (predicted_at or "")[:10]
    if asset == "KALSHI":
        return LIVE_KALSHI_CONVICTION_BETS.get(conv, 0)
    if asset == "BYBIT":
        # Bybit signal simulation uses $25 flat (same as BTC production)
        # for comparable P&L across pipelines. Actual execution uses BTC sizing.
        return LIVE_BTC_CONVICTION_BETS.get(conv, 0)
    if date_str >= LIVE_START_DATE:
        tiers = LIVE_BTC_CONVICTION_BETS if asset == "BTC" else LIVE_ETH_CONVICTION_BETS
    else:
        tiers = PAPER_BTC_CONVICTION_BETS if asset == "BTC" else PAPER_ETH_CONVICTION_BETS
    return tiers.get(conv, 0)

# Trade execution constants (safe import from trade.py)
try:
    from trade import DAILY_LOSS_LIMIT, BET_SIZE
except ImportError:
    DAILY_LOSS_LIMIT = 300
    BET_SIZE = 25


def is_correct(estimate, outcome):
    """Did the prediction call the direction right?"""
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def get_daily_predictions(db, date_str):
    """Get all predictions made on a specific date (resolved or not)."""
    try:
        rows = db.execute("""
            SELECT p.rowid as id, p.agent, p.estimate, p.confidence,
                   p.predicted_at, p.market_id,
                   p.conviction_score, p.regime, p.reasoning,
                   m.outcome, m.price_yes, m.resolved
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE date(p.predicted_at) = ?
            ORDER BY p.predicted_at ASC
        """, (date_str,)).fetchall()
    except sqlite3.OperationalError:
        # Fallback without regime column
        rows = db.execute("""
            SELECT p.rowid as id, p.agent, p.estimate, p.confidence,
                   p.predicted_at, p.market_id,
                   p.conviction_score, NULL as regime, p.reasoning,
                   m.outcome, m.price_yes, m.resolved
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE date(p.predicted_at) = ?
            ORDER BY p.predicted_at ASC
        """, (date_str,)).fetchall()
    return [dict(r) for r in rows]


def get_daily_resolved(db, date_str):
    """Get resolved predictions from a specific date."""
    all_preds = get_daily_predictions(db, date_str)
    return [p for p in all_preds if p["resolved"] == 1]


def analyze_summary(predictions, resolved):
    """Daily summary: counts, WR, P&L."""
    total = len(predictions)
    bets = [p for p in predictions if (p.get("conviction_score") or 0) >= 3]
    skips = total - len(bets)

    wins = sum(1 for r in resolved if is_correct(r["estimate"], r["outcome"])
               and (r.get("conviction_score") or 0) >= 3)
    losses = sum(1 for r in resolved if not is_correct(r["estimate"], r["outcome"])
                 and (r.get("conviction_score") or 0) >= 3)
    resolved_bets = wins + losses

    wr = (wins / resolved_bets * 100) if resolved_bets > 0 else 0

    # P&L (date-aware sizing)
    total_pnl = 0.0
    total_wagered = 0.0
    for r in resolved:
        conv = r.get("conviction_score") or 0
        bet_size = _get_bet_size_dr(conv, r.get("predicted_at"))
        if bet_size == 0:
            continue
        estimate = r["estimate"]
        outcome = r["outcome"]
        price_yes = r["price_yes"]

        if estimate >= 0.5:
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

    return {
        "total_predictions": total,
        "bets": len(bets),
        "skips": skips,
        "resolved_bets": resolved_bets,
        "wins": wins,
        "losses": losses,
        "wr": round(wr, 1),
        "pnl": round(total_pnl, 2),
        "wagered": round(total_wagered, 2),
    }


def analyze_regime_distribution(predictions):
    """Count predictions per regime label."""
    regimes = defaultdict(lambda: {"total": 0, "bets": 0, "skips": 0})
    for p in predictions:
        regime = p.get("regime") or "UNKNOWN"
        conv = p.get("conviction_score") or 0
        regimes[regime]["total"] += 1
        if conv >= 3:
            regimes[regime]["bets"] += 1
        else:
            regimes[regime]["skips"] += 1
    return dict(regimes)


def analyze_direction(resolved):
    """WR by UP vs DOWN predictions."""
    directions = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0})
    for r in resolved:
        conv = r.get("conviction_score") or 0
        if conv < 3:
            continue
        direction = "UP" if r["estimate"] >= 0.5 else "DOWN"
        d = directions[direction]
        d["total"] += 1
        correct = is_correct(r["estimate"], r["outcome"])
        if correct:
            d["wins"] += 1
        else:
            d["losses"] += 1

        bet_size = _get_bet_size_dr(conv, r.get("predicted_at"))
        if r["estimate"] >= 0.5:
            if 0 < r["price_yes"] < 1:
                d["pnl"] += bet_size * (1.0 / r["price_yes"] - 1.0) if r["outcome"] == 1 else -bet_size
        else:
            price_no = 1.0 - r["price_yes"]
            if 0 < price_no < 1:
                d["pnl"] += bet_size * (1.0 / price_no - 1.0) if r["outcome"] == 0 else -bet_size

    for d in directions.values():
        d["wr"] = round(d["wins"] / d["total"] * 100, 1) if d["total"] > 0 else 0
        d["pnl"] = round(d["pnl"], 2)
    return dict(directions)


def analyze_side_regime_cohorts(resolved):
    """Performance by direction × regime for promotion guardrails."""
    cohorts = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0})
    for r in resolved:
        conv = r.get("conviction_score") or 0
        if conv < 3:
            continue

        direction = "UP" if r["estimate"] >= 0.5 else "DOWN"
        regime = r.get("regime") or "UNKNOWN"
        key = f"{direction} / {regime}"
        c = cohorts[key]
        c["direction"] = direction
        c["regime"] = regime
        c["total"] += 1

        correct = is_correct(r["estimate"], r["outcome"])
        if correct:
            c["wins"] += 1
        else:
            c["losses"] += 1

        bet_size = _get_bet_size_dr(conv, r.get("predicted_at"))
        if r["estimate"] >= 0.5:
            if 0 < r["price_yes"] < 1:
                c["pnl"] += bet_size * (1.0 / r["price_yes"] - 1.0) if r["outcome"] == 1 else -bet_size
        else:
            price_no = 1.0 - r["price_yes"]
            if 0 < price_no < 1:
                c["pnl"] += bet_size * (1.0 / price_no - 1.0) if r["outcome"] == 0 else -bet_size

    for c in cohorts.values():
        c["wr"] = round(c["wins"] / c["total"] * 100, 1) if c["total"] > 0 else 0
        c["pnl"] = round(c["pnl"], 2)
    return dict(cohorts)


def analyze_price_buckets(resolved):
    """WR and P&L by market price range."""
    buckets = {
        "0.15-0.30": {"range": (0.15, 0.30), "wins": 0, "losses": 0, "total": 0, "pnl": 0.0},
        "0.30-0.50": {"range": (0.30, 0.50), "wins": 0, "losses": 0, "total": 0, "pnl": 0.0},
        "0.50-0.70": {"range": (0.50, 0.70), "wins": 0, "losses": 0, "total": 0, "pnl": 0.0},
        "0.70-0.85": {"range": (0.70, 0.85), "wins": 0, "losses": 0, "total": 0, "pnl": 0.0},
    }

    for r in resolved:
        conv = r.get("conviction_score") or 0
        if conv < 3:
            continue
        price = r["price_yes"]
        bet_size = _get_bet_size_dr(conv, r.get("predicted_at"))

        for label, b in buckets.items():
            lo, hi = b["range"]
            if lo <= price < hi:
                b["total"] += 1
                correct = is_correct(r["estimate"], r["outcome"])
                if correct:
                    b["wins"] += 1
                else:
                    b["losses"] += 1

                if r["estimate"] >= 0.5:
                    if 0 < price < 1:
                        b["pnl"] += bet_size * (1.0 / price - 1.0) if r["outcome"] == 1 else -bet_size
                else:
                    price_no = 1.0 - price
                    if 0 < price_no < 1:
                        b["pnl"] += bet_size * (1.0 / price_no - 1.0) if r["outcome"] == 0 else -bet_size
                break

    result = {}
    for label, b in buckets.items():
        result[label] = {
            "wins": b["wins"],
            "losses": b["losses"],
            "total": b["total"],
            "wr": round(b["wins"] / b["total"] * 100, 1) if b["total"] > 0 else 0,
            "pnl": round(b["pnl"], 2),
        }
    return result


def analyze_conviction_tiers(resolved):
    """Performance by conviction tier for the day."""
    tiers = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "pnl": 0.0, "wagered": 0.0})
    for r in resolved:
        conv = r.get("conviction_score") or 0
        bet_size = _get_bet_size_dr(conv, r.get("predicted_at"))
        label = f"conv={conv} (${bet_size})"

        correct = is_correct(r["estimate"], r["outcome"])
        t = tiers[label]
        t["total"] += 1
        if correct:
            t["wins"] += 1
        else:
            t["losses"] += 1

        if bet_size > 0:
            t["wagered"] += bet_size
            if r["estimate"] >= 0.5:
                if 0 < r["price_yes"] < 1:
                    t["pnl"] += bet_size * (1.0 / r["price_yes"] - 1.0) if r["outcome"] == 1 else -bet_size
            else:
                price_no = 1.0 - r["price_yes"]
                if 0 < price_no < 1:
                    t["pnl"] += bet_size * (1.0 / price_no - 1.0) if r["outcome"] == 0 else -bet_size

    for t in tiers.values():
        t["wr"] = round(t["wins"] / t["total"] * 100, 1) if t["total"] > 0 else 0
        t["pnl"] = round(t["pnl"], 2)
        t["wagered"] = round(t["wagered"], 2)
    return dict(tiers)


def analyze_filter_breakdown(predictions, resolved):
    """Analyze skip reasons and counterfactual WR for filtered predictions.

    Extracts the 'reason' field from prediction reasoning JSON to show
    which filters are blocking bets and whether they're helping or hurting.
    """
    skip_reasons = defaultdict(lambda: {"count": 0, "resolved": 0, "would_win": 0})

    for p in predictions:
        conv = p.get("conviction_score") or 0
        if conv >= 3:
            continue  # not a skip

        reasoning = p.get("reasoning")
        if not reasoning:
            continue
        try:
            data = json.loads(reasoning) if isinstance(reasoning, str) else reasoning
        except (json.JSONDecodeError, TypeError):
            continue

        signal = data.get("signal", {})
        if isinstance(signal, str):
            reason = signal
        elif isinstance(signal, dict):
            reason = signal.get("reason", "unknown")
        else:
            continue

        # Bucket similar reasons
        if reason.startswith("streak_too_short"):
            bucket = "streak_too_short"
        elif reason.startswith("no_exhaustion"):
            bucket = "no_exhaustion"
        elif reason.startswith("cooldown_flip"):
            bucket = "cooldown_flip"
        elif reason.startswith("price_gate"):
            bucket = "price_gate"
        elif reason.startswith("time_gate"):
            bucket = "time_gate"
        elif reason.startswith("regime_skip"):
            bucket = "regime_skip"
        else:
            bucket = reason

        skip_reasons[bucket]["count"] += 1

        # Counterfactual: if we had bet momentum, would it have won?
        if p.get("resolved") == 1 and p.get("outcome") is not None:
            streak_str = reason.split("streak=")[-1].rstrip(")") if "streak=" in reason else ""
            try:
                streak = int(streak_str)
            except (ValueError, TypeError):
                streak = 0

            if abs(streak) >= 3:
                skip_reasons[bucket]["resolved"] += 1
                would_est = 0.62 if streak > 0 else 0.38
                if is_correct(would_est, p["outcome"]):
                    skip_reasons[bucket]["would_win"] += 1

    return dict(skip_reasons)


def analyze_regime_gate(predictions, resolved):
    """Summarize the BTC daily-regime gate (`src/regime_gate.py`).

    Reads `reasoning_data.regime_gate` and `pre_gate_conviction` written
    by `predict.store_prediction` and reports:
      - how many would-be conv>=3 cycles were downgraded by the gate
      - the gate state at evaluation time (asof_date, r_z, threshold)
      - counterfactual: of the gated bets that have since resolved,
        how many would have been correct as live bets

    Returns None if the gate field isn't populated yet (predictions
    written before commit e5e323c9 don't have it).
    """
    resolved_by_id = {p["id"]: p for p in resolved if p.get("id")}
    gated = []
    kept = []
    last_state = None
    for p in predictions:
        reasoning = p.get("reasoning")
        if not reasoning:
            continue
        try:
            data = json.loads(reasoning) if isinstance(reasoning, str) else reasoning
        except (json.JSONDecodeError, TypeError):
            continue
        gate_state = data.get("regime_gate")
        if gate_state is None:
            continue
        last_state = gate_state
        pre_conv = data.get("pre_gate_conviction") or 0
        if pre_conv < 3:
            continue  # gate only matters for would-be live bets
        if gate_state.get("gated"):
            gated.append(p)
        else:
            kept.append(p)
    if not gated and not kept:
        return None

    def _resolved_correct(group):
        n_resolved = 0
        n_correct = 0
        for p in group:
            r = resolved_by_id.get(p.get("id"))
            if not r:
                continue
            outcome = r.get("outcome")
            if outcome is None:
                continue
            n_resolved += 1
            if is_correct(p["estimate"], outcome):
                n_correct += 1
        return n_resolved, n_correct

    gr_n, gr_c = _resolved_correct(gated)
    kp_n, kp_c = _resolved_correct(kept)

    return {
        "gated_count": len(gated),
        "kept_count": len(kept),
        "gated_resolved": gr_n,
        "gated_correct": gr_c,
        "kept_resolved": kp_n,
        "kept_correct": kp_c,
        "last_state": last_state,
    }


def analyze_liquidity(predictions):
    """Analyze CLOB liquidity data from prediction reasoning JSON.

    Extracts liquidity.* fields stored by Phase 6a and computes:
    - Average spread %
    - Average max_bet_2pct
    - Distribution of spread ranges
    - Spread by direction (UP vs DOWN)
    """
    spreads = []
    max_bets_2pct = []
    max_bets_5pct = []
    depth_levels_list = []
    by_direction = defaultdict(lambda: {"spreads": [], "max_bets": []})
    slip_at_200 = []

    for p in predictions:
        reasoning_raw = p.get("reasoning")
        if not reasoning_raw:
            continue
        try:
            reasoning = json.loads(reasoning_raw) if isinstance(reasoning_raw, str) else reasoning_raw
        except (json.JSONDecodeError, TypeError):
            continue

        liq = reasoning.get("liquidity")
        if not liq or "error" in liq:
            continue

        spread_pct = liq.get("spread_pct")
        max_bet = liq.get("max_bet_2pct")
        max_bet_5 = liq.get("max_bet_5pct")
        depth = liq.get("depth_levels")
        token = liq.get("token", "?")

        if spread_pct is not None:
            spreads.append(spread_pct)
            by_direction[token]["spreads"].append(spread_pct)
        if max_bet is not None:
            max_bets_2pct.append(max_bet)
            by_direction[token]["max_bets"].append(max_bet)
        if max_bet_5 is not None:
            max_bets_5pct.append(max_bet_5)
        if depth is not None:
            depth_levels_list.append(depth)

        s200 = liq.get("slippage_at_200", {})
        if s200 and s200.get("slippage_pct") is not None:
            slip_at_200.append(s200["slippage_pct"])

    if not spreads:
        return None  # No liquidity data yet — skip section entirely

    avg_spread = sum(spreads) / len(spreads)
    avg_max_bet = sum(max_bets_2pct) / len(max_bets_2pct) if max_bets_2pct else 0
    avg_max_bet_5 = sum(max_bets_5pct) / len(max_bets_5pct) if max_bets_5pct else 0
    avg_depth = sum(depth_levels_list) / len(depth_levels_list) if depth_levels_list else 0
    avg_slip_200 = sum(slip_at_200) / len(slip_at_200) if slip_at_200 else 0

    # Spread distribution
    tight = sum(1 for s in spreads if s < 1.0)
    medium = sum(1 for s in spreads if 1.0 <= s < 3.0)
    wide = sum(1 for s in spreads if s >= 3.0)

    # Check how many bets would have exceeded max_bet_2pct
    exceeded_count = 0
    for p in predictions:
        conv = p.get("conviction_score") or 0
        bet_size = _get_bet_size_dr(conv, p.get("predicted_at"))
        if bet_size == 0:
            continue
        reasoning_raw = p.get("reasoning")
        if not reasoning_raw:
            continue
        try:
            reasoning = json.loads(reasoning_raw) if isinstance(reasoning_raw, str) else reasoning_raw
        except (json.JSONDecodeError, TypeError):
            continue
        liq = reasoning.get("liquidity")
        if liq and liq.get("max_bet_2pct") is not None:
            if bet_size > liq["max_bet_2pct"]:
                exceeded_count += 1

    # Per-direction breakdown
    direction_stats = {}
    for token, data in by_direction.items():
        direction_stats[token] = {
            "count": len(data["spreads"]),
            "avg_spread": round(sum(data["spreads"]) / len(data["spreads"]), 2) if data["spreads"] else 0,
            "avg_max_bet": round(sum(data["max_bets"]) / len(data["max_bets"]), 2) if data["max_bets"] else 0,
        }

    return {
        "count": len(spreads),
        "avg_spread": round(avg_spread, 2),
        "avg_max_bet_2pct": round(avg_max_bet, 2),
        "avg_max_bet_5pct": round(avg_max_bet_5, 2),
        "avg_depth_levels": round(avg_depth, 1),
        "avg_slip_200": round(avg_slip_200, 2),
        "spread_tight": tight,
        "spread_medium": medium,
        "spread_wide": wide,
        "exceeded_2pct": exceeded_count,
        "by_direction": direction_stats,
    }


def rolling_trend(db, date_str, window=7):
    """WR and P&L for each of the last N days."""
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    days = []

    for i in range(window):
        d = target - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        resolved = get_daily_resolved(db, d_str)

        if not resolved:
            days.append({"date": d_str, "bets": 0, "wr": 0, "pnl": 0})
            continue

        summary = analyze_summary(get_daily_predictions(db, d_str), resolved)
        days.append({
            "date": d_str,
            "bets": summary["resolved_bets"],
            "wr": summary["wr"],
            "pnl": summary["pnl"],
        })

    days.reverse()  # chronological order
    return days


def analyze_orders(db_path, date_str):
    """Analyze trade execution orders for a specific date.

    Returns None if the orders table doesn't exist or no orders were placed.
    """
    try:
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row

        # Check if orders table exists
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()
        if not table_check:
            db.close()
            return None

        # Day's orders
        rows = db.execute("""
            SELECT direction, size, status, mode, pnl
            FROM orders
            WHERE date(placed_at) = ?
        """, (date_str,)).fetchall()

        if not rows:
            db.close()
            return None

        rows = [dict(r) for r in rows]
        count = len(rows)
        total_wagered = sum(r["size"] for r in rows if r["size"])
        settled = [r for r in rows if r["pnl"] is not None]
        total_pnl = sum(r["pnl"] for r in settled)
        wins = sum(1 for r in settled if r["pnl"] > 0)
        losses = sum(1 for r in settled if r["pnl"] < 0)

        # Mode from most recent order
        mode = rows[-1]["mode"].upper() if rows[-1].get("mode") else "PAPER"

        # Circuit breaker: cumulative daily losses (same formula as trade.py)
        daily_loss = abs(sum(r["pnl"] for r in settled if r["pnl"] and r["pnl"] < 0))
        breaker_pct = (daily_loss / DAILY_LOSS_LIMIT * 100) if DAILY_LOSS_LIMIT > 0 else 0
        breaker_tripped = daily_loss >= DAILY_LOSS_LIMIT

        # Direction breakdown
        by_direction = {}
        for direction in ("UP", "DOWN"):
            d_rows = [r for r in rows if r["direction"] == direction]
            d_settled = [r for r in d_rows if r["pnl"] is not None]
            if d_rows:
                by_direction[direction] = {
                    "count": len(d_rows),
                    "pnl": sum(r["pnl"] for r in d_settled) if d_settled else 0,
                }

        # Fill rate: submitted orders that actually filled vs expired
        # Excludes paper and failed (API bugs) — only counts orders that reached CLOB
        submitted_statuses = ("submitted", "filled", "settled", "expired")
        submitted = [r for r in rows if r["status"] in submitted_statuses]
        filled = [r for r in rows if r["status"] in ("filled", "settled")]
        expired = [r for r in rows if r["status"] == "expired"]
        fill_rate = len(filled) / len(submitted) * 100 if submitted else 0

        # Also check expired orders: would they have won? (missed profit indicator)
        # This requires market outcome data, so query separately
        expired_would_win = 0
        try:
            expired_rows = db.execute("""
                SELECT o.direction, m.outcome
                FROM orders o JOIN markets m ON o.market_id = m.id
                WHERE date(o.placed_at) = ? AND o.status = 'expired' AND m.resolved = 1
            """, (date_str,)).fetchall()
            for er in expired_rows:
                dirn, outcome = er
                if (dirn == "UP" and outcome == 1) or (dirn == "DOWN" and outcome == 0):
                    expired_would_win += 1
        except Exception:
            pass

        db.close()

        return {
            "count": count,
            "total_wagered": total_wagered,
            "total_pnl": total_pnl,
            "wins": wins,
            "losses": losses,
            "mode": mode,
            "daily_loss": daily_loss,
            "breaker_limit": DAILY_LOSS_LIMIT,
            "breaker_pct": breaker_pct,
            "breaker_tripped": breaker_tripped,
            "by_direction": by_direction,
            "bet_size": BET_SIZE,
            "fill_rate": fill_rate,
            "submitted_count": len(submitted),
            "filled_count": len(filled),
            "expired_count": len(expired),
            "expired_would_win": expired_would_win,
        }
    except Exception:
        return None


def analyze_bybit_positions(db_path, date_str):
    """Analyze Bybit positions opened or closed on a given date.

    Bybit trades live in the `positions` table, not `orders`, so the
    standard analyze_orders returns None. This function provides the
    equivalent for the Bybit pipeline: lifecycle, close reasons,
    funding cost, pnl.
    """
    try:
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row

        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='positions'"
        ).fetchone()
        if not table_check:
            db.close()
            return None

        # Positions touched today (opened or closed). funding_cost column
        # may not exist on older DBs — guard via PRAGMA check.
        cols = {r[1] for r in db.execute("PRAGMA table_info(positions)").fetchall()}
        fc_expr = "COALESCE(funding_cost, 0)" if "funding_cost" in cols else "0"
        rows = db.execute(f"""
            SELECT side, size, entry_price, status, stop_loss, close_price,
                   pnl, close_reason, cycles_held, opened_at, closed_at,
                   {fc_expr} AS funding_cost
            FROM positions
            WHERE date(opened_at) = ? OR date(closed_at) = ?
        """, (date_str, date_str)).fetchall()
        db.close()

        if not rows:
            return None

        rows = [dict(r) for r in rows]
        opened = [r for r in rows if (r["opened_at"] or "")[:10] == date_str]
        closed = [r for r in rows if (r["closed_at"] or "")[:10] == date_str]
        settled = [r for r in closed if r["pnl"] is not None]
        total_pnl = sum(r["pnl"] for r in settled)
        total_funding = sum(r["funding_cost"] or 0 for r in settled)
        wins = sum(1 for r in settled if r["pnl"] > 0)
        losses = sum(1 for r in settled if r["pnl"] < 0)

        # Close-reason breakdown
        reasons: dict[str, dict] = {}
        for r in settled:
            k = r.get("close_reason") or "unknown"
            b = reasons.setdefault(k, {"n": 0, "pnl": 0.0, "wins": 0})
            b["n"] += 1
            b["pnl"] += r["pnl"] or 0
            if (r["pnl"] or 0) > 0:
                b["wins"] += 1

        # Side breakdown
        by_side: dict[str, dict] = {}
        for r in settled:
            k = r["side"]
            b = by_side.setdefault(k, {"n": 0, "pnl": 0.0, "wins": 0})
            b["n"] += 1
            b["pnl"] += r["pnl"] or 0
            if (r["pnl"] or 0) > 0:
                b["wins"] += 1

        avg_cycles_held = (
            sum(r["cycles_held"] or 0 for r in settled) / len(settled)
            if settled else 0
        )

        return {
            "opened": len(opened),
            "closed": len(closed),
            "settled_count": len(settled),
            "wins": wins,
            "losses": losses,
            "total_pnl": round(total_pnl, 2),
            "total_funding": round(total_funding, 4),
            "avg_cycles_held": round(avg_cycles_held, 1),
            "reasons": reasons,
            "by_side": by_side,
        }
    except Exception:
        return None


def generate_alerts(summary, rolling, orders=None, integrity_issues=None, ehr=None,
                    side_regime_cohorts=None, side_regime_guardrail=True):
    """Flag concerning patterns."""
    alerts = []

    # Daily WR below 55% with enough bets to be meaningful
    if summary["resolved_bets"] >= 5 and summary["wr"] < 55:
        alerts.append(f"⚠️ Daily WR {summary['wr']}% below 55% threshold ({summary['resolved_bets']} bets)")

    # Daily P&L negative
    if summary["pnl"] < -100:
        alerts.append(f"⚠️ Daily P&L ${summary['pnl']:+.2f} — significant loss")

    # Rolling: 3+ consecutive negative P&L days
    negative_streak = 0
    for day in reversed(rolling):
        if day["bets"] > 0 and day["pnl"] < 0:
            negative_streak += 1
        elif day["bets"] > 0:
            break
    if negative_streak >= 3:
        alerts.append(f"🚨 {negative_streak} consecutive losing days")

    # Rolling: WR trending down
    active_days = [d for d in rolling if d["bets"] > 0]
    if len(active_days) >= 4:
        first_half = active_days[:len(active_days)//2]
        second_half = active_days[len(active_days)//2:]
        avg_first = sum(d["wr"] for d in first_half) / len(first_half)
        avg_second = sum(d["wr"] for d in second_half) / len(second_half)
        if avg_second < avg_first - 10:
            alerts.append(f"📉 WR declining: {avg_first:.0f}% → {avg_second:.0f}% over 7 days")

    # No bets placed
    if summary["bets"] == 0:
        alerts.append("ℹ️ No bets placed today — all predictions skipped")

    # Circuit breaker alerts (from trade execution)
    if orders:
        if orders["breaker_tripped"]:
            alerts.append(
                f"🚨 Circuit breaker TRIPPED — daily loss "
                f"${orders['daily_loss']:.0f} >= ${orders['breaker_limit']:.0f} limit"
            )
        elif orders["breaker_pct"] >= 60:
            alerts.append(
                f"⚠️ Circuit breaker at {orders['breaker_pct']:.0f}% "
                f"(${orders['daily_loss']:.0f} / ${orders['breaker_limit']:.0f})"
            )

    # Integrity alerts
    if integrity_issues:
        fail_count = sum(1 for i in integrity_issues if i["status"] == "FAIL")
        warn_count = sum(1 for i in integrity_issues if i["status"] == "WARN")
        if fail_count:
            alerts.append(f"🚨 {fail_count} integrity check failure(s) today")
        # Surface specific high-value alerts, grouped by check so repeated
        # orphan rows don't drown out the actual operator signal.
        grouped = {}
        for issue in integrity_issues:
            check_name = issue["check_name"]
            if check_name not in ("orphaned_predictions", "expired_would_win", "failed_orders"):
                continue
            grouped.setdefault(check_name, []).append(issue["detail"])
        for check_name, details in list(grouped.items())[:3]:
            unique_details = []
            seen = set()
            for detail in details:
                if detail in seen:
                    continue
                seen.add(detail)
                unique_details.append(detail)
            sample = "; ".join(unique_details[:3])
            more = len(unique_details) - 3
            suffix = f"; +{more} more" if more > 0 else ""
            alerts.append(
                f"⚠️ {check_name}: {len(details)} issue(s) - {sample}{suffix}"
            )

    # AC-EHR-2: Rolling 7d signal EHR < 0 on 50+ bets
    if ehr and ehr.get("alert"):
        alerts.append(
            f"🚨 Signal EHR negative: {ehr['rolling_signal']:+.4f} "
            f"over {ehr['rolling_n']} bets (7-day) — model may be buying overpriced contracts"
        )

    # Promotion guardrail: weak side/regime cells should be visible before
    # any pipeline is considered healthy. Kalshi is excluded by caller because
    # its strike-aware parser has separate validation gates.
    if side_regime_guardrail and side_regime_cohorts:
        weak = [
            c for c in side_regime_cohorts.values()
            if c["total"] >= 5 and c["wr"] < 45
        ]
        if weak:
            weak.sort(key=lambda c: (c["wr"], -c["total"], c["pnl"]))
            c = weak[0]
            alerts.append(
                f"🧯 side/regime promotion guardrail: {c['direction']} in "
                f"{c['regime']} is {c['wr']}% WR on {c['total']} bets "
                f"(${c['pnl']:+.2f}); require cohort review before promotion"
            )

    return alerts


# ── Decision alert system ─────────────────────────────────────────────
# Each decision has an id matching docs/core/decisions.md, a check function,
# and a human-readable description generator.

def compute_decision_stats(db):
    """Query aggregate stats needed by decision checks."""
    stats = {
        "conv4_bets": 0, "conv4_wins": 0, "conv4_wr": 0,
        "conv3_bets": 0, "conv3_wins": 0, "conv3_wr": 0,
        "bucket_50_70_bets": 0, "bucket_50_70_wins": 0, "bucket_50_70_wr": 0,
        "bucket_15_30_bets": 0, "bucket_15_30_wins": 0, "bucket_15_30_wr": 0,
        "up_bets": 0, "up_wins": 0, "up_wr": 0,
        "down_bets": 0, "down_wins": 0, "down_wr": 0,
        "total_bets": 0, "total_pnl": 0.0, "total_wagered": 0.0,
        "days_active": 0,
    }

    try:
        rows = db.execute("""
            SELECT p.estimate, p.conviction_score, p.regime, p.predicted_at,
                   m.outcome, m.price_yes, m.resolved
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1 AND p.conviction_score >= 3
        """).fetchall()
    except sqlite3.OperationalError:
        return stats

    for r in rows:
        estimate, conv, regime, predicted_at, outcome, price_yes, resolved = r
        correct = is_correct(estimate, outcome)
        bet_size = _get_bet_size_dr(conv, predicted_at)
        direction = "UP" if estimate >= 0.5 else "DOWN"

        stats["total_bets"] += 1
        stats["total_wagered"] += bet_size

        # P&L
        if estimate >= 0.5 and 0 < price_yes < 1:
            stats["total_pnl"] += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
        elif estimate < 0.5:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                stats["total_pnl"] += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

        # Conviction tiers
        if conv == 4:
            stats["conv4_bets"] += 1
            if correct:
                stats["conv4_wins"] += 1
        elif conv == 3:
            stats["conv3_bets"] += 1
            if correct:
                stats["conv3_wins"] += 1

        # Price buckets
        if 0.50 <= price_yes < 0.70:
            stats["bucket_50_70_bets"] += 1
            if correct:
                stats["bucket_50_70_wins"] += 1
        elif 0.15 <= price_yes < 0.30:
            stats["bucket_15_30_bets"] += 1
            if correct:
                stats["bucket_15_30_wins"] += 1

        # Direction
        if direction == "UP":
            stats["up_bets"] += 1
            if correct:
                stats["up_wins"] += 1
        else:
            stats["down_bets"] += 1
            if correct:
                stats["down_wins"] += 1

    # Compute WR percentages
    for key in ["conv4", "conv3", "bucket_50_70", "bucket_15_30", "up", "down"]:
        bets = stats[f"{key}_bets"]
        wins = stats[f"{key}_wins"]
        stats[f"{key}_wr"] = round(wins / bets * 100, 1) if bets > 0 else 0

    # Days active
    try:
        days_row = db.execute("""
            SELECT COUNT(DISTINCT date(predicted_at)) FROM predictions
            WHERE conviction_score >= 3
        """).fetchone()
        stats["days_active"] = days_row[0] if days_row else 0
    except sqlite3.OperationalError:
        pass

    return stats


DECISIONS = [
    # Decision #1 closed 2026-04-19 as OBSOLETE. The decision text said
    # "demote conv=4 to flat $75," but by the time it triggered the live
    # sizing was already flat $25 across all tiers (config.py::
    # LIVE_BTC_CONVICTION_BETS = {3:25, 4:25, 5:25}). There is nothing to
    # demote. If tiered live sizing is ever reinstated, re-activate this
    # check. See GitHub decision #1 issue for context.
    # {
    #     "id": 1,
    #     "decision": "Demote conv=4 to flat $75 (5m)",
    #     "check": lambda s: s["conv4_bets"] >= 50 and s["conv4_wr"] < 60,
    #     "describe": lambda s: (
    #         f"conv=4 WR is {s['conv4_wr']}% over {s['conv4_bets']} bets "
    #         f"(threshold: <60% at 50+)"
    #     ),
    # },
    {
        "id": 2,
        "decision": "Tighten 0.50-0.70 price bucket",
        "check": lambda s: s["bucket_50_70_bets"] >= 20 and s["bucket_50_70_wr"] < 55,
        "describe": lambda s: (
            f"0.50-0.70 WR is {s['bucket_50_70_wr']}% over {s['bucket_50_70_bets']} bets "
            f"(threshold: <55% at 20+)"
        ),
    },
    {
        "id": 6,
        "decision": "Explore 0.15-0.30 bucket expansion",
        "check": lambda s: s["bucket_15_30_bets"] >= 20 and s["bucket_15_30_wr"] > 65,
        "describe": lambda s: (
            f"0.15-0.30 WR is {s['bucket_15_30_wr']}% over {s['bucket_15_30_bets']} bets "
            f"(attention threshold: >65% at 20+; promotion threshold: >65% at 50+)"
        ),
        "alert": lambda s, d: (
            f"\U0001f4ca Decision #{d['id']} MONITORING TRIGGERED: {d['decision']} — "
            f"{d['describe'](s)}; keep collecting ({s['bucket_15_30_bets']}/50)"
            if s["bucket_15_30_bets"] < 50
            else f"\U0001f514 Decision #{d['id']} READY: {d['decision']} — {d['describe'](s)}"
        ),
    },
]

# 15m-specific decisions (checked against 15m DB)
DECISIONS_15M = [
    {
        "id": 4,
        "decision": "Filter 15m RIDE UP signals",
        "check": lambda s: s["up_bets"] >= 30 and s["up_wr"] < 55,
        "describe": lambda s: (
            f"15m UP WR is {s['up_wr']}% over {s['up_bets']} bets "
            f"(threshold: <55% at 30+)"
        ),
    },
    {
        "id": 5,
        "decision": "Sunset or retrain 15m pipeline",
        "check": lambda s: (
            s["days_active"] >= 14
            and s["total_bets"] > 0
            and (s["total_bets"] / max(s["days_active"], 1)) < 5
            and s["total_wagered"] > 0
            and (s["total_pnl"] / s["total_wagered"] * 100) < 5
        ),
        "describe": lambda s: (
            f"15m avg {s['total_bets']/max(s['days_active'],1):.1f} bets/day over "
            f"{s['days_active']} days, ROI {s['total_pnl']/max(s['total_wagered'],1)*100:.1f}% "
            f"(threshold: <5 bets/day AND <5% ROI over 14+ days)"
        ),
    },
    {
        "id": 7,
        "decision": "Demote conv=4 to flat $75 (15m)",
        "check": lambda s: s["conv4_bets"] >= 20 and s["conv4_wr"] < 60,
        "describe": lambda s: (
            f"15m conv=4 WR is {s['conv4_wr']}% over {s['conv4_bets']} bets "
            f"(threshold: <60% at 20+)"
        ),
    },
]


def check_decisions(db_5m_path, db_15m_path):
    """Check all decision triggers against current data. Returns list of fired alerts."""
    alerts = []

    # 5m decisions
    if Path(db_5m_path).exists():
        db = sqlite3.connect(db_5m_path)
        db.row_factory = sqlite3.Row
        stats = compute_decision_stats(db)
        db.close()
        for d in DECISIONS:
            try:
                if d["check"](stats):
                    alerts.append(
                        d.get("alert", _format_ready_decision_alert)(stats, d)
                    )
            except (KeyError, ZeroDivisionError):
                pass

    # 15m decisions
    if Path(db_15m_path).exists():
        db = sqlite3.connect(db_15m_path)
        db.row_factory = sqlite3.Row
        stats = compute_decision_stats(db)
        db.close()
        for d in DECISIONS_15M:
            try:
                if d["check"](stats):
                    alerts.append(
                        d.get("alert", _format_ready_decision_alert)(stats, d)
                    )
            except (KeyError, ZeroDivisionError):
                pass

    return alerts


def _format_ready_decision_alert(stats, decision):
    return (
        f"\U0001f514 Decision #{decision['id']} READY: {decision['decision']} — "
        f"{decision['describe'](stats)}"
    )


def _generate_fill_diagnostic_section(min_samples=20):
    """Generate Phase 2 fill diagnostic section from VPS log DIAG lines.

    Returns markdown string or None if log file doesn't exist.
    """
    log_path = Path(__file__).parent.parent / "logs" / "loop.log"
    if not log_path.exists():
        return None

    from fill_diagnostic import parse_diag_lines, generate_report as diag_report
    decision_delays, orderbook_ages, rtt_values, drift_by_conv = parse_diag_lines(log_path)

    total = (
        len(decision_delays)
        + len(orderbook_ages)
        + len(rtt_values)
        + sum(len(v) for v in drift_by_conv.values())
    )
    if total == 0:
        return None

    return "\n" + diag_report(
        decision_delays, orderbook_ages, rtt_values, drift_by_conv, min_samples
    )


def _get_engine_metrics():
    """Read ws_metrics.json for engine health data. Returns dict or None."""
    metrics_path = Path(__file__).parent.parent / "data" / "ws_metrics.json"
    if not metrics_path.exists():
        return None
    try:
        import json as _json
        data = _json.loads(metrics_path.read_text())
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
            "event_lag": data.get("event_lag_ms", {}),
            "ta_build": data.get("ta_build_ms", {}),
            "pipeline_fanout": data.get("pipeline_fanout_ms", {}),
            "strategy_lab": data.get("strategy_lab_ms", {}),
            "total_dispatch_wall": data.get("total_dispatch_wall_ms", {}),
            "slowest_pipeline_runtime": data.get("slowest_pipeline_runtime_ms", {}),
            "pipeline_runtime": data.get("pipeline_runtime_ms", {}),
            "orderbook_age": data.get("orderbook_age_ms", {}),
            "orderbook_cache": data.get("orderbook_cache", {}),
            "fallback_fires": data.get("fallback_fires_24h", 0),
            "cycles": data.get("cycles", 0),
        }
    except (ValueError, OSError):
        return None


def _dominant_orderbook_cause(metrics: dict) -> str | None:
    cache = metrics.get("orderbook_cache") or {}
    orderbook = metrics.get("orderbook_age") or metrics.get("orderbook_age_ms") or {}
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
            "- **Polymarket events:** "
            f"book={cache.get('book_events_24h', 0)}, "
            f"price_change={cache.get('price_change_events_24h', 0)}, "
            f"ignored={ignored}"
        ),
        (
            "- **Orderbook freshness detail:** "
            f"fresh/stale tokens: {cache.get('fresh_tokens_now', 0)}/"
            f"{cache.get('stale_tokens_now', 0)}, "
            f"updated last 60s/5m: {cache.get('tokens_updated_last_60s', 0)}/"
            f"{cache.get('tokens_updated_last_5m', 0)}, "
            f"stale reasons: {stale_reasons}"
        ),
        (
            "- **REST snapshot seed:** "
            f"{successes}/{attempts} successful "
            f"(missing={cache.get('rest_snapshot_seed_missing', 0)}, "
            f"invalid_bbo={cache.get('rest_snapshot_seed_invalid_bbo', 0)})"
        ),
        (
            "- **Polymarket resubscribe:** "
            f"debounced/executed: {cache.get('resubscribe_debounced', 0)}/"
            f"{cache.get('resubscribe_executed', 0)}, "
            f"added/removed tokens: {cache.get('token_set_added', 0)}/"
            f"{cache.get('token_set_removed', 0)}"
        ),
    ]
    if cause:
        lines.append(f"- **Orderbook freshness decision:** dominant cause: {cause}")
    return lines


def _analyze_strategy_lab(db_path=None):
    """Analyze Strategy Lab predictions for the daily report.

    Returns a dict with leaderboard, gate tracker, kill/graduation candidates,
    or None if the DB doesn't exist or has no data.
    """
    db_path = db_path or DB_STRATEGY_LAB
    if not Path(db_path).exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cols = [r[1] for r in conn.execute("PRAGMA table_info(lab_predictions)").fetchall()]
        pnl_expr = "COALESCE(synthetic_pnl, pnl, 0)" if "synthetic_pnl" in cols else "COALESCE(pnl, 0)"

        # All-time stats per strategy (only resolved predictions)
        rows = conn.execute(f"""
            SELECT strategy,
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome = 0 THEN 1 ELSE 0 END) as losses,
                   COALESCE(SUM({pnl_expr}), 0) as synthetic_pnl
            FROM lab_predictions
            WHERE outcome IS NOT NULL
            GROUP BY strategy
            ORDER BY COUNT(*) DESC
        """).fetchall()

        if not rows:
            conn.close()
            return None

        strategies = []
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            wr = round(wins / total * 100, 1) if total > 0 else 0.0
            strategies.append({
                "strategy": r["strategy"],
                "total": total,
                "wins": wins,
                "losses": r["losses"],
                "wr": wr,
                "synthetic_pnl": r["synthetic_pnl"],
            })

        # Leaderboard: only strategies with 10+ resolved
        leaderboard = sorted(
            [s for s in strategies if s["total"] >= 10],
            key=lambda x: -x["wr"],
        )

        # Gate tracker: progress toward 200-bet graduation gate
        gate_tracker = []
        for s in strategies:
            # Estimate days to gate based on current throughput
            pending_count = conn.execute(
                "SELECT COUNT(*) FROM lab_predictions WHERE strategy = ? AND outcome IS NULL",
                (s["strategy"],),
            ).fetchone()[0]
            remaining = max(0, 200 - s["total"])
            # Rough estimate: bets per day based on total / days active
            first_row = conn.execute(
                "SELECT MIN(predicted_at) FROM lab_predictions WHERE strategy = ?",
                (s["strategy"],),
            ).fetchone()
            first_at = first_row[0] if first_row else None
            days_to_gate = None
            if first_at and remaining > 0:
                try:
                    first_dt = datetime.fromisoformat(first_at.replace("Z", "+00:00"))
                    days_active = max(1, (datetime.now(timezone.utc) - first_dt).total_seconds() / 86400)
                    bets_per_day = s["total"] / days_active
                    if bets_per_day > 0:
                        days_to_gate = round(remaining / bets_per_day, 1)
                except (ValueError, TypeError):
                    pass

            gate_tracker.append({
                "strategy": s["strategy"],
                "total": s["total"],
                "wr": s["wr"],
                "remaining": remaining,
                "days_to_gate": days_to_gate,
            })

        # Kill candidates: below 48% WR on 50+ bets
        kill_candidates = [s for s in strategies if s["total"] >= 50 and s["wr"] < 48.0]

        # Graduation candidates: above 52% WR on 200+ bets
        graduation_candidates = [s for s in strategies if s["total"] >= 200 and s["wr"] > 52.0]

        conn.close()

        return {
            "strategies": strategies,
            "leaderboard": leaderboard,
            "gate_tracker": gate_tracker,
            "kill_candidates": kill_candidates,
            "graduation_candidates": graduation_candidates,
            "pnl_metric": "synthetic_candle_pnl",
            "caveat": "Strategy Lab is discovery-only; WR and synthetic P&L are candle-score metrics, not executable trading edge.",
        }
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        print(f"  Strategy Lab DB error: {e}")
        return None


def _get_daily_regime(date_str):
    """Fetch daily macro context from asset_daily.db for the report date.

    Returns dict keyed by asset (BTC, ETH, SOL) with OHLCV, trend, vol metrics.
    Returns empty dict if DB missing or no data for that date.
    """
    if not DB_ASSET_DAILY.exists():
        return {}
    try:
        db = sqlite3.connect(str(DB_ASSET_DAILY))
        rows = db.execute(
            "SELECT asset, open, high, low, close, "
            "range_pct, realized_vol, body_pct, velocity, "
            "trend_label, velocity_zscore, range_zscore "
            "FROM asset_daily WHERE date = ? ORDER BY asset",
            (date_str,),
        ).fetchall()
        db.close()
        result = {}
        for row in rows:
            result[row[0]] = {
                "open": row[1], "high": row[2], "low": row[3], "close": row[4],
                "range_pct": row[5], "realized_vol": row[6],
                "body_pct": row[7], "velocity": row[8],
                "trend_label": row[9],
                "velocity_zscore": row[10], "range_zscore": row[11],
            }
        return result
    except Exception:
        return {}


def format_report(
    date_str,
    data_5m,
    data_15m,
    decision_alerts=None,
    data_eth=None,
    data_kalshi=None,
    data_bybit=None,
    canary_readiness=None,
):
    """Format analysis data into markdown report."""
    decision_alerts = decision_alerts or []
    era = "Live" if date_str >= LIVE_START_DATE else "Paper"
    lines = [
        f"# BOTSY Daily Report — {date_str} ({era})",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    # Daily macro context from asset_daily.db
    regime_ctx = _get_daily_regime(date_str)
    if regime_ctx:
        lines.extend([
            "## Market Context (Daily Regime)",
            "",
            "| Asset | Close | Range% | RealVol | Body% | Velocity | Trend | Vel-Z | Rng-Z |",
            "|-------|-------|--------|---------|-------|----------|-------|-------|-------|",
        ])
        for asset in sorted(regime_ctx):
            r = regime_ctx[asset]
            close_str = f"${r['close']:,.0f}" if r['close'] and r['close'] > 100 else f"${r['close']:.2f}" if r['close'] else "N/A"
            vel_z = f"{r['velocity_zscore']:+.1f}" if r['velocity_zscore'] is not None else "—"
            rng_z = f"{r['range_zscore']:+.1f}" if r['range_zscore'] is not None else "—"
            lines.append(
                f"| {asset} | {close_str} | "
                f"{r['range_pct']*100:.2f}% | {r['realized_vol']*100:.2f}% | "
                f"{r['body_pct']*100:+.2f}% | {r['velocity']:+.1f} | "
                f"{r['trend_label']} | {vel_z} | {rng_z} |"
            )
        lines.append("")

    pipelines = [
        ("5-Minute Pipeline", data_5m),
        ("15-Minute Pipeline", data_15m),
        ("ETH 5-Minute Pipeline", data_eth),
        ("Kalshi BTC Pipeline", data_kalshi),
        ("Bybit BTC Perps Pipeline", data_bybit),
    ]
    for label, data in pipelines:
        if data is None:
            continue

        s = data["summary"]
        lines.extend([
            f"## {label}",
            "",
            "### Summary",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Predictions | {s['total_predictions']} |",
            f"| Bets (conv≥3) | {s['bets']} |",
            f"| Skips | {s['skips']} |",
            f"| Resolved bets | {s['resolved_bets']} |",
            f"| Win rate | {s['wr']}% ({s['wins']}W / {s['losses']}L) |",
            f"| P&L | ${s['pnl']:+.2f} |",
            f"| Wagered | ${s['wagered']:.2f} |",
            "",
        ])

        # EHR (Excess Hit Rate) — spec_maker_mode.md AC-EHR-1
        ehr = data.get("ehr")
        if ehr:
            lines.append("### Excess Hit Rate (EHR)")
            lines.extend([
                "| Metric | Value |",
                "|--------|-------|",
            ])
            if ehr.get("signal"):
                lines.append(f"| Signal EHR (today) | {ehr['signal']['ehr']:+.4f} ({ehr['signal']['n']} bets) |")
            if ehr.get("execution"):
                lines.append(f"| Execution EHR (today) | {ehr['execution']['ehr']:+.4f} ({ehr['execution']['n']} fills) |")
            if ehr.get("rolling_signal") is not None:
                lines.append(f"| Signal EHR (7-day) | {ehr['rolling_signal']:+.4f} ({ehr['rolling_n']} bets) |")
            if ehr.get("rolling_execution") is not None:
                lines.append(f"| Execution EHR (7-day) | {ehr['rolling_execution']:+.4f} |")
            if ehr.get("signal") and ehr.get("execution"):
                gap = ehr["signal"]["ehr"] - ehr["execution"]["ehr"]
                lines.append(f"| Gap (signal − exec) | {gap:+.4f} ({gap*100:.1f}¢/dollar) |")
            lines.append("")

        # Regime breakdown
        if data["regimes"]:
            lines.extend([
                "### Regime Breakdown",
                "| Regime | Total | Bets | Skips |",
                "|--------|-------|------|-------|",
            ])
            for regime, r in sorted(data["regimes"].items()):
                lines.append(f"| {regime} | {r['total']} | {r['bets']} | {r['skips']} |")
            lines.append("")

        # Filter breakdown
        if data.get("filters"):
            lines.extend([
                "### Filter Breakdown",
                "| Filter | Skipped | Counterfactual WR |",
                "|--------|---------|-------------------|",
            ])
            for reason, f in sorted(data["filters"].items(), key=lambda x: -x[1]["count"]):
                if f["resolved"] > 0:
                    cf_wr = f"{f['would_win']}/{f['resolved']} ({f['would_win']/f['resolved']*100:.0f}%)"
                else:
                    cf_wr = "—"
                lines.append(f"| {reason} | {f['count']} | {cf_wr} |")
            lines.append("")

        # Regime gate (BTC daily-regime, see src/regime_gate.py)
        rg = data.get("regime_gate")
        if rg:
            ls = rg.get("last_state") or {}
            reg = ls.get("regime") or {}
            asof = reg.get("asof_date", "?")
            r_z = reg.get("range_zscore")
            r_z_str = f"{r_z:+.2f}" if isinstance(r_z, (int, float)) else "—"
            v_z = reg.get("velocity_zscore")
            v_z_str = f"{v_z:+.2f}" if isinstance(v_z, (int, float)) else "—"
            thr = ls.get("r_z_gate", "?")
            cur = "FIRING" if ls.get("gated") else "open"
            lines.extend([
                "### Regime Gate (BTC range_zscore)",
                f"Last evaluation: **{cur}** "
                f"(asof={asof} r_z={r_z_str} v_z={v_z_str} threshold={thr})",
                "",
                "| Slice | Conv≥3 cycles | Resolved | Correct | WR |",
                "|---|--:|--:|--:|--:|",
            ])
            def _wr(c, n):
                return f"{c/n*100:.1f}%" if n else "—"
            lines.append(
                f"| Kept (gate open) | {rg['kept_count']} | {rg['kept_resolved']} | "
                f"{rg['kept_correct']} | {_wr(rg['kept_correct'], rg['kept_resolved'])} |"
            )
            lines.append(
                f"| Skipped (gate firing) | {rg['gated_count']} | {rg['gated_resolved']} | "
                f"{rg['gated_correct']} | {_wr(rg['gated_correct'], rg['gated_resolved'])} |"
            )
            lines.append("")

        # Direction analysis
        if data["directions"]:
            lines.extend([
                "### Direction Analysis",
                "| Direction | Bets | WR | P&L |",
                "|-----------|------|----|-----|",
            ])
            for direction, d in sorted(data["directions"].items()):
                lines.append(f"| {direction} | {d['total']} | {d['wr']}% | ${d['pnl']:+.2f} |")
            lines.append("")

        # Side × regime cohorts
        if data.get("side_regime_cohorts"):
            lines.extend([
                "### Side / Regime Cohorts",
                "| Side | Regime | Bets | WR | P&L |",
                "|------|--------|------|----|-----|",
            ])
            cohorts = sorted(
                data["side_regime_cohorts"].values(),
                key=lambda c: (-c["total"], c["direction"], c["regime"]),
            )
            for c in cohorts:
                lines.append(
                    f"| {c['direction']} | {c['regime']} | {c['total']} | "
                    f"{c['wr']}% | ${c['pnl']:+.2f} |"
                )
            lines.append("")

        # Price buckets
        if data["price_buckets"]:
            lines.extend([
                "### Price Bucket Performance",
                "| Price Range | Bets | WR | P&L |",
                "|-------------|------|----|-----|",
            ])
            for bucket, b in data["price_buckets"].items():
                if b["total"] > 0:
                    lines.append(f"| {bucket} | {b['total']} | {b['wr']}% | ${b['pnl']:+.2f} |")
            lines.append("")

        # Conviction tiers
        if data["conviction"]:
            lines.extend([
                "### Conviction Tiers",
                "| Tier | Total | WR | P&L | Wagered |",
                "|------|-------|----|-----|---------|",
            ])
            for tier, t in sorted(data["conviction"].items()):
                lines.append(f"| {tier} | {t['total']} | {t['wr']}% | ${t['pnl']:+.2f} | ${t['wagered']:.2f} |")
            lines.append("")

        # Liquidity profile (Phase 6a)
        if data.get("liquidity"):
            liq = data["liquidity"]
            lines.extend([
                "### Liquidity Profile (CLOB)",
                "",
                f"*Based on {liq['count']} predictions with order book data.*",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Avg spread | {liq['avg_spread']:.2f}% |",
                f"| Avg max bet @2% slippage | ${liq['avg_max_bet_2pct']:,.0f} |",
                f"| Avg max bet @5% slippage | ${liq['avg_max_bet_5pct']:,.0f} |",
                f"| Avg depth levels | {liq['avg_depth_levels']:.0f} |",
                f"| Avg slippage at $200 | {liq['avg_slip_200']:.2f}% |",
                f"| Bets exceeding 2% slippage ceiling | {liq['exceeded_2pct']} |",
                "",
                "**Spread distribution:**",
                f"| Range | Count | % |",
                f"|-------|-------|---|",
                f"| Tight (<1%) | {liq['spread_tight']} | {liq['spread_tight']/liq['count']*100:.0f}% |",
                f"| Medium (1-3%) | {liq['spread_medium']} | {liq['spread_medium']/liq['count']*100:.0f}% |",
                f"| Wide (>3%) | {liq['spread_wide']} | {liq['spread_wide']/liq['count']*100:.0f}% |",
                "",
            ])
            if liq["by_direction"]:
                lines.extend([
                    "**By token:**",
                    "| Token | Count | Avg Spread | Avg Max Bet @2% |",
                    "|-------|-------|------------|-----------------|",
                ])
                for token, stats in sorted(liq["by_direction"].items()):
                    lines.append(
                        f"| {token} | {stats['count']} | {stats['avg_spread']:.2f}% | ${stats['avg_max_bet']:,.0f} |"
                    )
                lines.append("")

        # Rolling 7-day trend
        if data["rolling"]:
            lines.extend([
                "### Rolling 7-Day Trend",
                "| Date | Era | Bets | WR | P&L |",
                "|------|-----|------|----|-----|",
            ])
            for day in data["rolling"]:
                day_era = "Live" if day["date"] >= LIVE_START_DATE else "Paper"
                if day["bets"] > 0:
                    lines.append(f"| {day['date']} | {day_era} | {day['bets']} | {day['wr']}% | ${day['pnl']:+.2f} |")
                else:
                    lines.append(f"| {day['date']} | {day_era} | — | — | — |")
            lines.append("")

        # Alerts
        if data["alerts"]:
            lines.extend([
                "### Alerts",
                "",
            ])
            for alert in data["alerts"]:
                lines.append(f"- {alert}")
            lines.append("")

        # Trade Execution
        orders = data.get("orders")
        if orders and orders["count"] > 0:
            breaker_status = (
                "🚨 TRIPPED — trading halted for remainder of day"
                if orders["breaker_tripped"]
                else "✅ OK"
            )
            record = f"{orders['wins']}W / {orders['losses']}L" if (orders["wins"] + orders["losses"]) > 0 else "—"

            # Fill rate line
            fill_rate_str = ""
            if orders.get("submitted_count", 0) > 0:
                fr = orders["fill_rate"]
                filled_c = orders["filled_count"]
                submitted_c = orders["submitted_count"]
                expired_c = orders["expired_count"]
                fr_icon = "✅" if fr >= 80 else ("⚠️" if fr >= 60 else "🚨")
                fill_rate_str = f"{fr_icon} {fr:.0f}% ({filled_c}/{submitted_c} submitted → filled, {expired_c} expired)"
                if orders.get("expired_would_win", 0) > 0:
                    fill_rate_str += f" — **{orders['expired_would_win']} expired orders would have WON**"

            lines.extend([
                "### Trade Execution",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Mode | {orders['mode']} |",
                f"| Orders placed | {orders['count']} |",
                f"| Wagered | ${orders['total_wagered']:.2f} |",
                f"| P&L (settled) | ${orders['total_pnl']:+.2f} |",
                f"| Record | {record} |",
                f"| Bet size | ${orders['bet_size']:.0f} |",
            ])
            if fill_rate_str:
                lines.append(f"| Fill rate | {fill_rate_str} |")
            lines.extend([
                "",
                f"**Circuit Breaker:** ${orders['daily_loss']:.0f} / ${orders['breaker_limit']:.0f} "
                f"({orders['breaker_pct']:.0f}%) — {breaker_status}",
                "",
            ])

        # Bybit position lifecycle (Phase 8)
        bp = data.get("bybit_positions")
        if bp and (bp["opened"] + bp["closed"]) > 0:
            record = (
                f"{bp['wins']}W / {bp['losses']}L"
                if (bp["wins"] + bp["losses"]) > 0 else "—"
            )
            lines.extend([
                "### Position Lifecycle (Bybit)",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Opened today | {bp['opened']} |",
                f"| Closed today | {bp['closed']} |",
                f"| Settled P&L | ${bp['total_pnl']:+.2f} |",
                f"| Funding cost paid | ${bp['total_funding']:+.4f} |",
                f"| Record | {record} |",
                f"| Avg cycles held | {bp['avg_cycles_held']} |",
                "",
            ])
            if bp["reasons"]:
                lines.extend([
                    "**Close reasons:**",
                    "| Reason | N | Wins | P&L |",
                    "|--------|--:|-----:|----:|",
                ])
                for k, v in sorted(bp["reasons"].items(),
                                    key=lambda x: -x[1]["n"]):
                    lines.append(
                        f"| {k} | {v['n']} | {v['wins']} | ${v['pnl']:+.2f} |"
                    )
                lines.append("")
            if bp["by_side"]:
                lines.extend([
                    "**By side:**",
                    "| Side | N | Wins | P&L |",
                    "|------|--:|-----:|----:|",
                ])
                for k, v in sorted(bp["by_side"].items()):
                    lines.append(
                        f"| {k} | {v['n']} | {v['wins']} | ${v['pnl']:+.2f} |"
                    )
                lines.append("")

            # Direction breakdown
            if orders and orders.get("by_direction"):
                lines.extend([
                    "| Direction | Orders | P&L |",
                    "|-----------|--------|-----|",
                ])
                for d, v in sorted(orders["by_direction"].items()):
                    lines.append(f"| {d} | {v['count']} | ${v['pnl']:+.2f} |")
                lines.append("")

    # Engine metrics (websocket health — from ws_metrics.json)
    engine_metrics = _get_engine_metrics()
    if engine_metrics:
        lines.extend([
            "## Engine Metrics",
            "",
            "| Feed | Status | Reconnects (24h) | Last Event |",
            "|------|--------|-----------------|------------|",
            f"| Bybit Spot | {engine_metrics['bybit_spot_status']} | {engine_metrics['bybit_spot_reconnects']} | {engine_metrics['bybit_spot_last'] or 'N/A'} |",
            f"| Bybit Linear | {engine_metrics['bybit_linear_status']} | {engine_metrics['bybit_linear_reconnects']} | {engine_metrics['bybit_linear_last'] or 'N/A'} |",
            f"| Polymarket | {engine_metrics['polymarket_status']} | {engine_metrics['polymarket_reconnects']} | {engine_metrics['polymarket_last'] or 'N/A'} |",
            "",
        ])
        lat = engine_metrics.get("dispatch_latency", {})
        event_lag = engine_metrics.get("event_lag", {})
        ta = engine_metrics.get("ta_build", {})
        fanout = engine_metrics.get("pipeline_fanout", {})
        lab = engine_metrics.get("strategy_lab", {})
        total_wall = engine_metrics.get("total_dispatch_wall", {})
        slowest = engine_metrics.get("slowest_pipeline_runtime", {})
        ob = engine_metrics.get("orderbook_age", {})
        cache = engine_metrics.get("orderbook_cache", {})
        fb = engine_metrics.get("fallback_fires", 0)
        lines.extend([
            f"- **Production dispatch latency:** {lat.get('p50', 0)}ms p50 / {lat.get('p95', 0)}ms p95 ({lat.get('samples', 0)} samples)",
            f"- **Bybit event lag:** {event_lag.get('p50', 0)}ms p50 / {event_lag.get('p95', 0)}ms p95",
            f"- **TA build:** {ta.get('p50', 0)}ms p50 / {ta.get('p95', 0)}ms p95",
            f"- **Pipeline fanout:** {fanout.get('p50', 0)}ms p50 / {fanout.get('p95', 0)}ms p95",
            f"- **Strategy Lab runtime:** {lab.get('p50', 0)}ms p50 / {lab.get('p95', 0)}ms p95",
            f"- **Total dispatch wall time:** {total_wall.get('p50', 0)}ms p50 / {total_wall.get('p95', 0)}ms p95",
            f"- **Slowest pipeline runtime:** {slowest.get('pipeline') or 'N/A'} {slowest.get('p95', 0)}ms p95",
            f"- **True orderbook age:** {ob.get('p50', 0)}ms p50 / {ob.get('p95', 0)}ms p95",
            f"- **Orderbook cache coverage:** {cache.get('tokens', 0)} tokens, {cache.get('token_set_changes_24h', 0)} token-set changes",
            f"- **Fallback fires (24h):** {fb}",
            f"- **Cycles:** {engine_metrics.get('cycles', 0)}",
            "",
        ])
        lines.extend(_orderbook_diagnostic_lines(engine_metrics))
        lines.append("")

    if canary_readiness:
        lines.extend(_format_canary_readiness_lines(canary_readiness))
        lines.append("")

    # Decision alerts (cross-pipeline, appended at end)
    if decision_alerts:
        lines.extend([
            "## Decision Alerts",
            "",
            "Tracked on [BOTSY Kanban](https://github.com/users/mariomerinom/projects/1). "
            "These fire when data crosses predefined thresholds.",
            "",
        ])
        for alert in decision_alerts:
            lines.append(f"- {alert}")
        lines.append("")

    # Shadow indicators (experimental)
    for label, data in pipelines:
        if data is None:
            continue
        shadow = data.get("shadow")
        # Shadow Maker (Phase 1) — spec_maker_mode.md AC-SM-4/5
        sm = data.get("shadow_maker")
        if sm:
            lines.extend([
                f"## Shadow Maker ({label})",
                "",
                "*Phase 1 — hypothetical maker orders logged, no real trades.*",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Shadow orders logged | {sm['n_logged']} |",
            ])
            if sm.get("fill_rate") is not None:
                lines.append(f"| Shadow fill rate | {sm['fill_rate']*100:.1f}% ({sm['n_filled']}/{sm['n_resolved']}) |")
            if sm.get("adverse_pct") is not None:
                lines.append(f"| Adverse selection % | {sm['adverse_pct']*100:.1f}% |")
            if sm.get("shadow_ehr") is not None:
                lines.append(f"| Shadow maker EHR | {sm['shadow_ehr']:+.4f} |")
            lines.extend(["", ""])

        # Multi-poll research grid — per-(offset × regime) WR snapshot.
        # Plan: docs/plans/multi_poll_predict_plan.md.
        mp = data.get("multi_poll")
        if mp:
            lines.extend([
                f"## Multi-Poll Research Grid ({label})",
                "",
                "*Research-only directional WR by (offset × regime), N≥20. "
                "These rows are not executable promotion evidence.*",
                "",
                f"Total polls today: {mp['total_polls']:,}",
                "",
            ])
            if mp.get("best_t180"):
                b = mp["best_t180"]
                lines.append(
                    f"**Best cell at T+180s:** {b['regime']} — "
                    f"{b['wr_pct']}% WR on {b['dir_resolved']} directional resolved"
                )
                lines.append("")

            lines.extend([
                "| Offset | Regime | Dir resolved | WR | Realistic n | Realistic P&L | EV/bet |",
                "|-------:|--------|-------------:|---:|------------:|--------------:|-------:|",
            ])
            for c in mp["cells"]:
                wr_str = f"{c['wr_pct']}%" if c["wr_pct"] is not None else "—"
                rn = c.get("realistic_n", 0)
                rpnl = c.get("realistic_pnl")
                rev = c.get("realistic_ev_per_bet")
                rpnl_str = f"${rpnl:+,.2f}" if rpnl is not None else "—"
                rev_str = f"${rev:+.2f}" if rev is not None else "—"
                lines.append(
                    f"| T+{c['offset_seconds']}s | {c['regime']} | "
                    f"{c['dir_resolved']} | {wr_str} | {rn} | {rpnl_str} | {rev_str} |"
                )
            lines.extend([
                "",
                "*Research-grid realistic P&L: $25 bet, entry at orderbook best_ask "
                "(or 1−best_bid for NO side) captured at poll time, less "
                "2% taker fee. Replaces the prior fictional $0.50 "
                "entry assumption, but still does not apply conviction or "
                "one-order-per-cycle execution gates.*",
                "", "",
            ])

        replay = data.get("timing_replay")
        if replay:
            lines.extend([
                f"## BTC 5m Timing Replay ({label})",
                "",
                "*Executable replay only: conviction, freshness, valid price, "
                "resolution, and one-order-per-cycle gates applied.*",
                "",
                "| Policy | Candidates | Fired | WR | P&L | EHR |",
                "|--------|-----------:|------:|---:|----:|----:|",
            ])
            for p in replay["policies"]:
                wr = f"{p['wr']}%" if p["wr"] is not None else "—"
                ehr = f"{p['ehr']:+.4f}" if p["ehr"] is not None else "—"
                lines.append(
                    f"| {p['policy']} | {p['candidates']} | {p['fired']} | "
                    f"{wr} | ${p['pnl']:+,.2f} | {ehr} |"
                )
            if replay.get("skip_reasons"):
                reasons = ", ".join(
                    f"{k}: {v}" for k, v in sorted(replay["skip_reasons"].items())
                )
                lines.append("")
                lines.append(f"Skipped replay rows: {reasons}")
            lines.extend(["", ""])

        delayed = data.get("delayed_execution")
        if delayed:
            lines.extend([
                f"## BTC 5m Delayed FAK Execution ({label})",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Candidates | {delayed['total_candidates']} |",
                f"| Orderbook age p95 | {delayed['orderbook_age_p95'] if delayed['orderbook_age_p95'] is not None else '—'} ms |",
            ])
            states = ", ".join(
                f"{k}: {v}" for k, v in sorted(delayed["states"].items())
            )
            lines.append(f"| States | {states} |")
            if delayed.get("skip_reasons"):
                skips = ", ".join(
                    f"{k}: {v}" for k, v in sorted(delayed["skip_reasons"].items())
                )
                lines.append(f"| Skip reasons | {skips} |")
            lines.extend(["", ""])

        if not shadow:
            continue

        lines.extend([
            f"## Shadow Indicators ({label})",
            "",
            "*Experimental — logged only, no trading decisions affected.*",
            "",
        ])

        if "rsi" in shadow:
            r = shadow["rsi"]
            lines.extend([
                f"**RSI(14):** {r['count']} predictions tracked",
                f"- Avg RSI on wins: {r['avg_win']} | Avg RSI on losses: {r['avg_loss']}",
                f"- Overbought (>70): {r['overbought_count']} | Oversold (<30): {r['oversold_count']}",
                "",
            ])

        if "obv" in shadow:
            o = shadow["obv"]
            pos_total = o["positive_slope_wins"] + o["positive_slope_losses"]
            neg_total = o["negative_slope_wins"] + o["negative_slope_losses"]
            pos_wr = round(o["positive_slope_wins"] / pos_total * 100, 1) if pos_total > 0 else 0
            neg_wr = round(o["negative_slope_wins"] / neg_total * 100, 1) if neg_total > 0 else 0
            lines.extend([
                f"**OBV Slope (0.50-0.70 bucket):** {o['count']} predictions tracked",
                f"- Positive slope: {pos_total} bets, {pos_wr}% WR",
                f"- Negative slope: {neg_total} bets, {neg_wr}% WR",
                "",
            ])

        if "vwap" in shadow:
            v = shadow["vwap"]
            lines.extend([
                f"**VWAP Mean-Reversion (paper):** {v['predictions']} signals, "
                f"{v['resolved']} resolved, {v['wr']}% WR ({v['wins']}W)",
                "",
            ])

    # Shadow conviction scorer
    for label, data in pipelines:
        if data is None:
            continue
        sc = data.get("shadow_conviction")
        if not sc:
            continue

        lines.extend([
            f"## Shadow Conviction Scorer ({label}, n={sc['total']})",
            "",
            "*Continuous strength signal — logged only, no trading decisions affected.*",
            "",
            "| Tier | Shadow WR | Prod WR | Shadow n | Prod n |",
            "|------|-----------|---------|----------|--------|",
        ])

        all_tiers = sorted(set(list(sc["tier_data"].keys()) + list(sc["prod_data"].keys())))
        for tier in all_tiers:
            sd = sc["tier_data"].get(tier, {"wins": 0, "total": 0})
            pd = sc["prod_data"].get(tier, {"wins": 0, "total": 0})
            s_wr = f"{sd['wins']/sd['total']*100:.0f}%" if sd["total"] > 0 else "—"
            p_wr = f"{pd['wins']/pd['total']*100:.0f}%" if pd["total"] > 0 else "—"
            lines.append(f"| {tier} | {s_wr} | {p_wr} | {sd['total']} | {pd['total']} |")

        lines.append("")

        # Divergence
        div = sc["divergence"]
        sh = div["shadow_higher"]
        sl = div["shadow_lower"]
        sh_wr = f"{sh['wins']/sh['total']*100:.0f}%" if sh["total"] > 0 else "—"
        sl_wr = f"{sl['wins']/sl['total']*100:.0f}%" if sl["total"] > 0 else "—"
        lines.append(f"**Divergence:** shadow > prod: {sh['total']} bets → {sh_wr} WR | "
                     f"shadow < prod: {sl['total']} bets → {sl_wr} WR")
        lines.append(f"**Strength-WR correlation:** r={sc['correlation']}")
        lines.append(f"**Avg strength:** wins={sc['avg_strength_win']} | losses={sc['avg_strength_loss']}")
        lines.append("")

    # Phase 2 fill diagnostics (from VPS log DIAG lines)
    try:
        phase2_section = _generate_fill_diagnostic_section()
        if phase2_section:
            lines.append(phase2_section)
    except Exception as e:
        lines.append(f"\n## Fill Diagnostic (Phase 2)\n\nSkipped: {e}\n")

    # Strategy Lab
    lab = _analyze_strategy_lab()
    if lab:
        lines.extend([
            "## Strategy Lab",
            "",
            "*Discovery-only candle scoring. No real trades; P&L is synthetic and cannot justify promotion without forward shadow/paper validation.*",
            "",
        ])

        # Leaderboard
        if lab["leaderboard"]:
            lines.extend([
                "### Leaderboard (10+ resolved bets)",
                "",
                "| Rank | Strategy | Bets | Wins | WR% | Synthetic P&L |",
                "|------|----------|------|------|-----|-----|",
            ])
            for i, s in enumerate(lab["leaderboard"], 1):
                lines.append(
                    f"| {i} | {s['strategy']} | {s['total']} | {s['wins']} | "
                    f"{s['wr']}% | ${s['synthetic_pnl']:+.2f} |"
                )
            lines.append("")
        else:
            lines.extend([
                "### Leaderboard",
                "",
                "*No strategies have 10+ resolved bets yet.*",
                "",
            ])

        # Gate tracker
        if lab["gate_tracker"]:
            lines.extend([
                "### Gate Tracker (200-bet graduation)",
                "",
            ])
            for g in sorted(lab["gate_tracker"], key=lambda x: -x["total"]):
                days_str = f"~{g['days_to_gate']:.0f} days to gate" if g["days_to_gate"] else "gate reached" if g["remaining"] == 0 else "estimating..."
                lines.append(
                    f"- **{g['strategy']}:** {g['total']}/200 bets, "
                    f"{g['wr']}% WR, {days_str}"
                )
            lines.append("")

        # Kill candidates
        if lab["kill_candidates"]:
            lines.extend([
                "### Kill Candidates (<48% WR on 50+ bets)",
                "",
            ])
            for s in lab["kill_candidates"]:
                lines.append(
                    f"- **{s['strategy']}:** {s['wr']}% WR on {s['total']} bets, "
                    f"${s['synthetic_pnl']:+.2f} synthetic P&L"
                )
            lines.append("")

        # Graduation candidates
        if lab["graduation_candidates"]:
            lines.extend([
                "### Graduation Candidates (>52% WR on 200+ bets)",
                "",
            ])
            for s in lab["graduation_candidates"]:
                lines.append(
                    f"- **{s['strategy']}:** {s['wr']}% WR on {s['total']} bets, "
                    f"${s['synthetic_pnl']:+.2f} synthetic P&L"
                )
            lines.append("")

    lines.append("---")
    lines.append("*Generated by `src/daily_report.py`*")
    return "\n".join(lines)


def _format_canary_readiness_lines(readiness: dict) -> list[str]:
    live_blockers = readiness.get("live_blockers") or []
    delayed_blockers = readiness.get("delayed_blockers") or []
    blockers = live_blockers + delayed_blockers
    verdict = "READY" if not blockers else "BLOCKED"
    lines = [
        "## BTC 5m Production Readiness",
        "",
        f"**Verdict:** {verdict}",
        "",
    ]
    if not blockers:
        lines.append("- No live-canary or delayed-policy blockers.")
        return lines
    if live_blockers:
        lines.append("### Live Canary Blockers")
        for blocker in live_blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    if delayed_blockers:
        lines.append("### Delayed FAK Blockers")
        for blocker in delayed_blockers:
            lines.append(f"- {blocker}")
    return lines


def _get_btc5m_canary_readiness(db_path=DB_5M) -> dict | None:
    try:
        import sqlite3
        from canary_readiness import (
            btc5m_delayed_policy_blockers,
            btc5m_live_canary_blockers,
        )
        db = sqlite3.connect(str(db_path))
        try:
            db.row_factory = sqlite3.Row
            return {
                "live_blockers": btc5m_live_canary_blockers(db),
                "delayed_blockers": btc5m_delayed_policy_blockers(db),
            }
        finally:
            db.close()
    except Exception as exc:
        return {
            "live_blockers": [f"canary_readiness_unavailable ({exc})"],
            "delayed_blockers": [],
        }


def analyze_shadow_indicators(predictions, resolved):
    """Analyze shadow indicator values from reasoning JSON.

    Returns dict with RSI, OBV, and VWAP summary stats, or None if no shadow data.
    """
    rsi_wins, rsi_losses = [], []
    obv_wins, obv_losses = [], []
    vwap_preds, vwap_resolved, vwap_wins = 0, 0, 0

    for p in resolved:
        try:
            reasoning = json.loads(p["reasoning"]) if p["reasoning"] else {}
        except (json.JSONDecodeError, TypeError):
            continue

        rsi = reasoning.get("shadow_rsi_14")
        if rsi is not None:
            won = (p["estimate"] >= 0.5 and p["outcome"] == 1) or \
                  (p["estimate"] < 0.5 and p["outcome"] == 0)
            if won:
                rsi_wins.append(rsi)
            else:
                rsi_losses.append(rsi)

        obv = reasoning.get("shadow_obv_slope")
        if obv is not None:
            won = (p["estimate"] >= 0.5 and p["outcome"] == 1) or \
                  (p["estimate"] < 0.5 and p["outcome"] == 0)
            if won:
                obv_wins.append(obv)
            else:
                obv_losses.append(obv)

    # VWAP meanrev agent predictions
    for p in predictions:
        if p["agent"] == "vwap_meanrev":
            vwap_preds += 1

    for p in resolved:
        if p["agent"] == "vwap_meanrev":
            vwap_resolved += 1
            won = (p["estimate"] >= 0.5 and p["outcome"] == 1) or \
                  (p["estimate"] < 0.5 and p["outcome"] == 0)
            if won:
                vwap_wins += 1

    if not rsi_wins and not rsi_losses and not vwap_preds:
        return None

    result = {}

    if rsi_wins or rsi_losses:
        all_rsi = rsi_wins + rsi_losses
        avg_rsi = sum(all_rsi) / len(all_rsi) if all_rsi else 0
        avg_rsi_win = sum(rsi_wins) / len(rsi_wins) if rsi_wins else 0
        avg_rsi_loss = sum(rsi_losses) / len(rsi_losses) if rsi_losses else 0
        result["rsi"] = {
            "count": len(all_rsi),
            "avg": round(avg_rsi, 1),
            "avg_win": round(avg_rsi_win, 1),
            "avg_loss": round(avg_rsi_loss, 1),
            "overbought_count": sum(1 for r in all_rsi if r > 70),
            "oversold_count": sum(1 for r in all_rsi if r < 30),
        }

    if obv_wins or obv_losses:
        all_obv = obv_wins + obv_losses
        result["obv"] = {
            "count": len(all_obv),
            "positive_slope_wins": sum(1 for o in obv_wins if o > 0),
            "positive_slope_losses": sum(1 for o in obv_losses if o > 0),
            "negative_slope_wins": sum(1 for o in obv_wins if o < 0),
            "negative_slope_losses": sum(1 for o in obv_losses if o < 0),
        }

    if vwap_preds > 0:
        vwap_wr = round(vwap_wins / vwap_resolved * 100, 1) if vwap_resolved > 0 else 0
        result["vwap"] = {
            "predictions": vwap_preds,
            "resolved": vwap_resolved,
            "wins": vwap_wins,
            "wr": vwap_wr,
        }

    return result if result else None


def analyze_shadow_conviction(resolved):
    """Analyze shadow conviction scorer data from reasoning JSON.

    Compares shadow tiers to production tiers on resolved predictions.
    Returns dict with tier WRs and divergence analysis, or None if no data.
    """
    tier_data = {}     # shadow_tier → {wins, total}
    prod_data = {}     # prod_tier → {wins, total}
    divergence = {"shadow_higher": {"wins": 0, "total": 0},
                  "shadow_lower": {"wins": 0, "total": 0},
                  "same": {"wins": 0, "total": 0}}
    strengths_win = []
    strengths_loss = []

    for p in resolved:
        try:
            reasoning = json.loads(p["reasoning"]) if p["reasoning"] else {}
        except (json.JSONDecodeError, TypeError):
            continue

        shadow = reasoning.get("shadow_generic_scorer")
        if not shadow:
            continue

        shadow_tier = shadow.get("conviction_tier", 0)
        prod_tier = shadow.get("production_conviction", 0)
        strength = shadow.get("strength", 0)

        won = (p["estimate"] >= 0.5 and p["outcome"] == 1) or \
              (p["estimate"] < 0.5 and p["outcome"] == 0)

        # Per-tier WR
        for tier, data_dict in [(shadow_tier, tier_data), (prod_tier, prod_data)]:
            if tier not in data_dict:
                data_dict[tier] = {"wins": 0, "total": 0}
            data_dict[tier]["total"] += 1
            if won:
                data_dict[tier]["wins"] += 1

        # Divergence analysis
        if shadow_tier > prod_tier:
            bucket = divergence["shadow_higher"]
        elif shadow_tier < prod_tier:
            bucket = divergence["shadow_lower"]
        else:
            bucket = divergence["same"]
        bucket["total"] += 1
        if won:
            bucket["wins"] += 1

        # Strength-WR correlation data
        if won:
            strengths_win.append(strength)
        else:
            strengths_loss.append(strength)

    total = sum(d["total"] for d in tier_data.values())
    if total < 5:
        return None

    # Compute correlation between strength and win (point-biserial approx)
    all_strengths = strengths_win + strengths_loss
    if len(all_strengths) >= 5 and strengths_win and strengths_loss:
        avg_win = sum(strengths_win) / len(strengths_win)
        avg_loss = sum(strengths_loss) / len(strengths_loss)
        avg_all = sum(all_strengths) / len(all_strengths)
        var = sum((s - avg_all) ** 2 for s in all_strengths) / len(all_strengths)
        if var > 0:
            n = len(all_strengths)
            n1 = len(strengths_win)
            n0 = len(strengths_loss)
            correlation = (avg_win - avg_loss) * ((n1 * n0) / (n * n)) ** 0.5 / (var ** 0.5)
        else:
            correlation = 0.0
    else:
        correlation = 0.0

    return {
        "total": total,
        "tier_data": tier_data,
        "prod_data": prod_data,
        "divergence": divergence,
        "correlation": round(correlation, 3),
        "avg_strength_win": round(sum(strengths_win) / len(strengths_win), 3) if strengths_win else 0,
        "avg_strength_loss": round(sum(strengths_loss) / len(strengths_loss), 3) if strengths_loss else 0,
    }


def analyze_ehr(db, date_str):
    """Compute Excess Hit Rate (EHR) for AC-EHR-1/AC-EHR-2.

    Signal EHR: predictions JOIN markets, using market price_yes.
    Execution EHR: orders with settled_at, using actual price_filled.
    Rolling 7-day with alert trigger.

    Reference: spec_maker_mode.md, ehr_baseline_2026-04-16.md
    """
    result = {"signal": None, "execution": None, "rolling_signal": None,
              "rolling_execution": None, "rolling_n": 0, "alert": False}

    try:
        # Daily signal EHR
        row = db.execute("""
            SELECT COUNT(*) as n,
              AVG(CASE WHEN p.estimate > 0.5 THEN (1.0*m.outcome - m.price_yes)
                   ELSE ((1.0 - m.outcome) - (1.0 - m.price_yes)) END) as ehr
            FROM predictions p JOIN markets m ON p.market_id = m.id
            WHERE p.conviction_score >= 3 AND m.resolved = 1
              AND date(p.predicted_at) = ?
        """, (date_str,)).fetchone()
        if row and row["n"] and row["n"] > 0:
            result["signal"] = {"ehr": round(row["ehr"], 4), "n": row["n"]}

        # Daily execution EHR
        row = db.execute("""
            SELECT COUNT(*) as n,
              AVG((CASE WHEN o.pnl > 0 THEN 1.0 ELSE 0.0 END) - o.price_filled) as ehr
            FROM orders o JOIN predictions p ON o.prediction_id = p.id
            WHERE o.settled_at IS NOT NULL AND o.price_filled IS NOT NULL
              AND p.conviction_score >= 3 AND date(o.settled_at) = ?
        """, (date_str,)).fetchone()
        if row and row["n"] and row["n"] > 0:
            result["execution"] = {"ehr": round(row["ehr"], 4), "n": row["n"]}

        # Rolling 7-day signal EHR (AC-EHR-2)
        row = db.execute("""
            SELECT COUNT(*) as n,
              AVG(CASE WHEN p.estimate > 0.5 THEN (1.0*m.outcome - m.price_yes)
                   ELSE ((1.0 - m.outcome) - (1.0 - m.price_yes)) END) as ehr
            FROM predictions p JOIN markets m ON p.market_id = m.id
            WHERE p.conviction_score >= 3 AND m.resolved = 1
              AND date(p.predicted_at) >= date(?, '-7 days')
              AND date(p.predicted_at) <= ?
        """, (date_str, date_str)).fetchone()
        if row and row["n"] and row["n"] > 0:
            result["rolling_signal"] = round(row["ehr"], 4)
            result["rolling_n"] = row["n"]
            # AC-EHR-2: Alert if 7d EHR < 0 on 50+ bets
            if row["n"] >= 50 and row["ehr"] < 0:
                result["alert"] = True

        # Rolling 7-day execution EHR
        row = db.execute("""
            SELECT COUNT(*) as n,
              AVG((CASE WHEN o.pnl > 0 THEN 1.0 ELSE 0.0 END) - o.price_filled) as ehr
            FROM orders o JOIN predictions p ON o.prediction_id = p.id
            WHERE o.settled_at IS NOT NULL AND o.price_filled IS NOT NULL
              AND p.conviction_score >= 3
              AND date(o.settled_at) >= date(?, '-7 days')
              AND date(o.settled_at) <= ?
        """, (date_str, date_str)).fetchone()
        if row and row["n"] and row["n"] > 0:
            result["rolling_execution"] = round(row["ehr"], 4)

    except Exception:
        pass

    return result


def _realistic_pnl_for_cell(db, date_str, offset_seconds, regime,
                             bet_size=25.0, fee_rate=0.02):
    """Compute realistic-entry P&L for one (offset × regime) cell.

    Replaces the fictional $0.50 entry assumption with the live YES-token
    best_ask captured at poll time. This is the layer-2 fidelity step
    discussed 2026-04-30: lab-WR alone overestimates edge because the
    market has often already moved against the signal by the time the
    quote firms up.

    For each directional poll with orderbook context:
      estimate > 0.5  →  BUY YES at mkt_best_ask
                          (or fall back to mkt_mid if best_ask is NULL)
      estimate < 0.5  →  BUY NO at (1 - mkt_best_bid)
                          (NO best_ask = 1 - YES best_bid)
      Win:  shares × $1 - bet_size, less fees
      Lose: -bet_size

    Returns None if no polls in this cell have orderbook context.
    """
    rows = db.execute(
        """
        SELECT mpp.estimate, mpp.mkt_mid, mpp.mkt_best_bid, mpp.mkt_best_ask,
               m.outcome
        FROM multi_poll_predictions mpp
        JOIN markets m ON mpp.market_id = m.id
        WHERE date(mpp.predicted_at) = ?
          AND mpp.offset_seconds = ?
          AND mpp.regime = ?
          AND mpp.estimate IS NOT NULL AND mpp.estimate != 0.5
          AND m.resolved = 1
        """,
        (date_str, offset_seconds, regime),
    ).fetchall()

    n = 0
    pnl = 0.0
    for est, mid, bid, ask, outcome in rows:
        # Determine entry price for the side we'd take
        if est > 0.5:
            entry = ask if ask is not None else mid
        else:
            entry = (1.0 - bid) if bid is not None else (
                (1.0 - mid) if mid is not None else None
            )
        if entry is None or entry <= 0 or entry >= 1:
            continue
        n += 1
        won = (
            (est > 0.5 and outcome == 1)
            or (est < 0.5 and outcome == 0)
        )
        if won:
            shares = bet_size / entry
            gross_profit = shares * 1.0 - bet_size
            net = gross_profit - bet_size * fee_rate
            pnl += net
        else:
            pnl -= bet_size

    return {
        "n_with_orderbook": n,
        "realistic_pnl": round(pnl, 2),
        "ev_per_bet": round(pnl / n, 2) if n else None,
    }


def analyze_multi_poll(db, date_str):
    """Multi-poll Phase A daily snapshot — per-(offset × regime) WR.

    Reads multi_poll_predictions JOINed to markets. Reports directional
    resolved + WR for each (offset_seconds × regime) cell with N >= 20
    on the given date. Also surfaces the BEST cell across regimes for
    the canonical T+180 offset, which Phase B will likely select.

    Each cell now also includes realistic-entry P&L: hypothetical $25
    bets at the actual orderbook best_ask captured at poll time, less
    a 2% taker fee. realistic_pnl is None when no polls in the cell
    have orderbook context (e.g. pre-2026-04-30 data).

    Returns None if the table doesn't exist or has no rows for the date
    (e.g. recovered DB with no fresh data).

    See docs/plans/multi_poll_predict_plan.md for the experiment design.
    """
    try:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='multi_poll_predictions'"
        ).fetchone()
        if not tables:
            return None

        rows = db.execute(
            """
            SELECT mpp.offset_seconds AS off,
                   mpp.regime AS regime,
                   SUM(CASE WHEN mpp.estimate != 0.5 AND m.resolved = 1
                            THEN 1 ELSE 0 END) AS dir_resolved,
                   SUM(CASE WHEN mpp.estimate != 0.5 AND m.resolved = 1 AND
                            ((mpp.estimate > 0.5 AND m.outcome = 1) OR
                             (mpp.estimate < 0.5 AND m.outcome = 0))
                            THEN 1 ELSE 0 END) AS dir_wins
            FROM multi_poll_predictions mpp
            LEFT JOIN markets m ON mpp.market_id = m.id
            WHERE date(mpp.predicted_at) = ?
            GROUP BY mpp.offset_seconds, mpp.regime
            HAVING dir_resolved >= 20
            ORDER BY mpp.regime, mpp.offset_seconds
            """,
            (date_str,),
        ).fetchall()

        if not rows:
            return None

        cells = []
        for r in rows:
            off, regime, dir_resolved, dir_wins = r
            wr = (
                round(100.0 * dir_wins / dir_resolved, 1)
                if dir_resolved else None
            )
            realistic = _realistic_pnl_for_cell(db, date_str, off, regime)
            cells.append({
                "offset_seconds": off,
                "regime": regime,
                "dir_resolved": dir_resolved,
                "dir_wins": dir_wins,
                "wr_pct": wr,
                "realistic_n": realistic["n_with_orderbook"],
                "realistic_pnl": realistic["realistic_pnl"]
                                 if realistic["n_with_orderbook"] else None,
                "realistic_ev_per_bet": realistic["ev_per_bet"],
            })

        # Best cell at canonical T+180 offset (Phase B's likely target).
        # Among cells with N>=50 at offset=180, pick highest WR.
        t180 = [c for c in cells if c["offset_seconds"] == 180
                and c["dir_resolved"] >= 50]
        best_t180 = (
            max(t180, key=lambda c: c["wr_pct"]) if t180 else None
        )

        # Total polls today (for context — across all offsets/regimes).
        total_row = db.execute(
            "SELECT COUNT(*) FROM multi_poll_predictions "
            "WHERE date(predicted_at) = ?",
            (date_str,),
        ).fetchone()
        total_polls = total_row[0] if total_row else 0

        return {
            "cells": cells,
            "best_t180": best_t180,
            "total_polls": total_polls,
        }
    except Exception as e:
        print(f"  [multi_poll] analyze failed: {e}")
        return None


def analyze_timing_replay(db, date_str):
    """Summarize executable BTC 5m timing replay rows."""
    try:
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='btc5m_timing_replay'"
        ).fetchone()
        if not table:
            return None
        rows = db.execute(
            """
            SELECT policy,
                   COUNT(*) AS candidates,
                   SUM(CASE WHEN would_fire = 1 THEN 1 ELSE 0 END) AS fired,
                   SUM(CASE WHEN would_fire = 1 AND won = 1 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN would_fire = 1 THEN pnl ELSE 0 END) AS pnl,
                   AVG(CASE WHEN would_fire = 1 THEN ehr ELSE NULL END) AS ehr
            FROM btc5m_timing_replay
            WHERE trade_date = ?
            GROUP BY policy
            ORDER BY policy
            """,
            (date_str,),
        ).fetchall()
        if not rows:
            return None
        policies = []
        for r in rows:
            policy, candidates, fired, wins, pnl, ehr = r
            fired = fired or 0
            policies.append({
                "policy": policy,
                "candidates": candidates or 0,
                "fired": fired,
                "wins": wins or 0,
                "wr": round((wins or 0) / fired * 100, 1) if fired else None,
                "pnl": round(pnl or 0, 2),
                "ehr": round(ehr, 4) if ehr is not None else None,
            })
        skip_rows = db.execute(
            """
            SELECT skip_reason, COUNT(*)
            FROM btc5m_timing_replay
            WHERE trade_date = ? AND would_fire = 0 AND skip_reason IS NOT NULL
            GROUP BY skip_reason
            """,
            (date_str,),
        ).fetchall()
        return {
            "policies": policies,
            "skip_reasons": {r[0]: r[1] for r in skip_rows},
        }
    except Exception:
        return None


def analyze_delayed_execution(db, date_str):
    """Summarize delayed BTC 5m FAK candidates for daily reports."""
    try:
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='btc5m_timing_candidates'"
        ).fetchone()
        if not table:
            return None
        rows = db.execute(
            """
            SELECT state, COUNT(*)
            FROM btc5m_timing_candidates
            WHERE date(created_at) = ?
            GROUP BY state
            """,
            (date_str,),
        ).fetchall()
        if not rows:
            return None
        skip_rows = db.execute(
            """
            SELECT skip_reason, COUNT(*)
            FROM btc5m_timing_candidates
            WHERE date(created_at) = ? AND skip_reason IS NOT NULL
            GROUP BY skip_reason
            """,
            (date_str,),
        ).fetchall()
        ages = [
            r[0] for r in db.execute(
                "SELECT orderbook_age_ms FROM btc5m_timing_candidates "
                "WHERE date(created_at) = ? AND orderbook_age_ms IS NOT NULL "
                "ORDER BY orderbook_age_ms",
                (date_str,),
            ).fetchall()
        ]
        p95 = None
        if ages:
            p95 = ages[int(len(ages) * 0.95)] if len(ages) >= 20 else ages[-1]
        states = {r[0]: r[1] for r in rows}
        return {
            "total_candidates": sum(states.values()),
            "states": states,
            "skip_reasons": {r[0]: r[1] for r in skip_rows},
            "orderbook_age_p95": p95,
        }
    except Exception:
        return None


def analyze_shadow_maker(db, date_str):
    """Shadow maker Phase 1 metrics for daily report (AC-SM-4, AC-SM-5).

    Reads from shadow_maker table, computes fill rate, adverse %,
    and shadow EHR for resolved markets.

    Also resolves any pending shadow rows whose underlying markets
    have since resolved. This is the batch-at-report-time resolution
    path — the engine hot path only LOGS shadow rows, never resolves.
    """
    try:
        # Check table exists
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shadow_maker'"
        ).fetchone()
        if not tables:
            return None

        # Resolve any pending shadow orders whose markets are now resolved.
        # One pipeline per DB — we don't know the name here, but the SQL
        # filter `pipeline=?` would require it. Resolve all pending rows
        # regardless of pipeline (they're all in this DB, for this pipeline).
        try:
            from shadow_maker import resolve_shadow_fills_polymarket
            # Look up the pipeline name from any row — they're all the same DB
            pipeline_row = db.execute(
                "SELECT DISTINCT pipeline FROM shadow_maker LIMIT 1"
            ).fetchone()
            if pipeline_row:
                resolve_shadow_fills_polymarket(db, pipeline_row[0])
        except Exception as _e:
            print(f"  [shadow_maker] resolve failed: {_e}")

        row = db.execute("""
            SELECT COUNT(*) as n_logged,
              SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as n_filled,
              SUM(CASE WHEN filled IS NOT NULL THEN 1 ELSE 0 END) as n_resolved
            FROM shadow_maker WHERE date(timestamp) = ?
        """, (date_str,)).fetchone()

        n_logged = row["n_logged"] or 0
        if n_logged == 0:
            return None

        n_filled = row["n_filled"] or 0
        n_resolved = row["n_resolved"] or 0

        # Adverse selection rate
        adv_row = db.execute("""
            SELECT SUM(CASE WHEN adverse = 1 THEN 1 ELSE 0 END) as n_adverse
            FROM shadow_maker WHERE filled = 1 AND date(timestamp) = ?
        """, (date_str,)).fetchone()
        n_adverse = adv_row["n_adverse"] or 0

        # Shadow maker EHR on resolved+filled
        ehr_row = db.execute("""
            SELECT AVG(
              CASE WHEN s.direction = 'UP' THEN (1.0 * m.outcome - s.shadow_price)
                   ELSE ((1.0 - m.outcome) - s.shadow_price) END
            ) as shadow_ehr,
            COUNT(*) as n_ehr
            FROM shadow_maker s
            JOIN markets m ON s.market_id = m.id
            WHERE s.filled = 1 AND m.resolved = 1 AND date(s.timestamp) = ?
        """, (date_str,)).fetchone()
        shadow_ehr = round(ehr_row["shadow_ehr"], 4) if ehr_row and ehr_row["n_ehr"] > 0 and ehr_row["shadow_ehr"] is not None else None

        return {
            "n_logged": n_logged,
            "n_filled": n_filled,
            "n_resolved": n_resolved,
            "fill_rate": round(n_filled / n_resolved, 3) if n_resolved else None,
            "adverse_pct": round(n_adverse / n_filled, 3) if n_filled else None,
            "shadow_ehr": shadow_ehr,
        }
    except Exception:
        return None


def analyze_pipeline(db_path, date_str):
    """Run full analysis for one pipeline (5m, 15m, ETH, or Kalshi)."""
    global CONVICTION_BETS
    if not Path(db_path).exists():
        return None

    # Use appropriate sizing for each pipeline
    db_str = str(db_path).lower()
    is_eth = "eth" in db_str
    is_kalshi = "kalshi" in db_str
    is_bybit = "bybit" in db_str
    old_bets = CONVICTION_BETS
    if is_kalshi:
        CONVICTION_BETS = LIVE_KALSHI_CONVICTION_BETS
    elif is_bybit:
        CONVICTION_BETS = LIVE_BTC_CONVICTION_BETS  # $25 flat for signal simulation
    elif is_eth:
        CONVICTION_BETS = ETH_CONVICTION_BETS

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    predictions = get_daily_predictions(db, date_str)
    resolved = get_daily_resolved(db, date_str)

    if not predictions:
        db.close()
        CONVICTION_BETS = old_bets
        return None

    try:
        summary = analyze_summary(predictions, resolved)
        regimes = analyze_regime_distribution(predictions)
        directions = analyze_direction(resolved)
        side_regime_cohorts = analyze_side_regime_cohorts(resolved)
        price_buckets = analyze_price_buckets(resolved)
        conviction = analyze_conviction_tiers(resolved)
        liquidity = analyze_liquidity(predictions)
        filters = analyze_filter_breakdown(predictions, resolved)
        regime_gate = analyze_regime_gate(predictions, resolved)
        rolling = rolling_trend(db, date_str, window=7)
        orders = analyze_orders(db_path, date_str)
        bybit_positions = analyze_bybit_positions(db_path, date_str) if is_bybit else None
        shadow = analyze_shadow_indicators(predictions, resolved)
        shadow_conviction = analyze_shadow_conviction(resolved)
        ehr = analyze_ehr(db, date_str)
        shadow_maker_data = analyze_shadow_maker(db, date_str)
        multi_poll_data = analyze_multi_poll(db, date_str)
        if multi_poll_data:
            try:
                from timing_replay import build_timing_replay
                build_timing_replay(db, date_str)
            except Exception as e:
                print(f"  [timing_replay] build failed: {e}")
        timing_replay_data = analyze_timing_replay(db, date_str)
        delayed_execution_data = analyze_delayed_execution(db, date_str)
    finally:
        db.close()
        CONVICTION_BETS = old_bets

    # Query integrity issues for this date
    integrity_issues = []
    try:
        db2 = sqlite3.connect(str(db_path))
        db2.row_factory = sqlite3.Row
        rows = db2.execute("""
            SELECT timestamp, check_name, status, detail
            FROM integrity_log
            WHERE date(timestamp) = ? AND status != 'OK'
            ORDER BY timestamp DESC
        """, (date_str,)).fetchall()
        integrity_issues = [dict(r) for r in rows]
        db2.close()
    except Exception:
        pass  # Table doesn't exist yet or DB issue

    # Re-generate alerts with integrity data
    alerts = generate_alerts(
        summary,
        rolling,
        orders=orders,
        integrity_issues=integrity_issues,
        ehr=ehr,
        side_regime_cohorts=side_regime_cohorts,
        side_regime_guardrail=not is_kalshi,
    )

    return {
        "summary": summary,
        "regimes": regimes,
        "directions": directions,
        "side_regime_cohorts": side_regime_cohorts,
        "price_buckets": price_buckets,
        "conviction": conviction,
        "liquidity": liquidity,
        "rolling": rolling,
        "orders": orders,
        "alerts": alerts,
        "filters": filters,
        "regime_gate": regime_gate,
        "shadow": shadow,
        "shadow_conviction": shadow_conviction,
        "integrity_issues": integrity_issues,
        "bybit_positions": bybit_positions,
        "ehr": ehr,
        "shadow_maker": shadow_maker_data,
        "multi_poll": multi_poll_data,
        "timing_replay": timing_replay_data,
        "delayed_execution": delayed_execution_data,
    }


def update_index(daily_dir, date_str):
    """Update the daily index file with a link to the new report."""
    index_path = daily_dir / "index.md"

    # Read existing links
    existing_links = []
    if index_path.exists():
        content = index_path.read_text()
        for line in content.split("\n"):
            if line.startswith("- ["):
                existing_links.append(line)

    # Add new link if not already present
    new_link = f"- [{date_str}]({date_str}.md)"
    if new_link not in existing_links:
        existing_links.insert(0, new_link)  # most recent first

    # Write index
    lines = [
        "# Daily Reports",
        "",
        "Daily analysis of prediction performance.",
        "",
    ]
    lines.extend(existing_links)
    lines.append("")
    index_path.write_text("\n".join(lines))


def generate_ci_summary(date_str, data_5m, data_15m, decision_alerts=None, data_eth=None, data_kalshi=None, data_bybit=None):
    """Generate concise markdown for GitHub Actions Job Summary."""
    decision_alerts = decision_alerts or []
    era = "Live" if date_str >= LIVE_START_DATE else "Paper"
    lines = [f"# BOTSY Daily Report \u2014 {date_str} ({era})", ""]

    for label, data in [("5m", data_5m), ("15m", data_15m), ("ETH", data_eth), ("Kalshi", data_kalshi), ("Bybit", data_bybit)]:
        if data is None:
            lines.append(f"**{label}:** No data")
            lines.append("")
            continue
        s = data["summary"]
        if s["resolved_bets"] == 0:
            lines.append(f"**{label}:** {s['total_predictions']} predictions, no resolved bets")
            lines.append("")
            continue

        lines.extend([
            f"## {label} Pipeline",
            f"**{s['resolved_bets']} bets | {s['wr']}% WR | ${s['pnl']:+.2f} P&L** (wagered ${s['wagered']:.0f})",
            "",
        ])

        # Direction table
        if data["directions"]:
            lines.extend(["| Direction | Bets | WR | P&L |", "|---|---|---|---|"])
            for d, v in sorted(data["directions"].items()):
                lines.append(f"| {d} | {v['total']} | {v['wr']}% | ${v['pnl']:+.2f} |")
            lines.append("")

        # Orders summary
        orders = data.get("orders")
        if orders and orders["count"] > 0:
            breaker_tag = "🚨 TRIPPED" if orders["breaker_tripped"] else f"{orders['breaker_pct']:.0f}%"
            lines.append(
                f"**Orders:** {orders['count']} placed, "
                f"${orders['total_wagered']:.0f} wagered, "
                f"${orders['total_pnl']:+.0f} P&L, "
                f"breaker {breaker_tag}"
            )
            lines.append("")

        # Alerts
        if data["alerts"]:
            for alert in data["alerts"]:
                lines.append(f"> {alert}")
            lines.append("")

    # Strategy Lab summary
    lab = _analyze_strategy_lab()
    if lab and lab["leaderboard"]:
        top = lab["leaderboard"][0]
        lines.extend([
            "## Strategy Lab",
            f"**Top discovery strategy:** {top['strategy']} ({top['wr']}% WR on {top['total']} candle-scored rows)",
            "**Caveat:** Lab output is discovery-only; promotion requires forward shadow/paper validation.",
        ])
        if lab["kill_candidates"]:
            kills = ", ".join(s["strategy"] for s in lab["kill_candidates"])
            lines.append(f"**Kill candidates:** {kills}")
        if lab["graduation_candidates"]:
            grads = ", ".join(s["strategy"] for s in lab["graduation_candidates"])
            lines.append(f"**Graduation candidates:** {grads}")
        lines.append("")

    # Decision alerts
    if decision_alerts:
        lines.extend(["## Decision Alerts", ""])
        for alert in decision_alerts:
            lines.append(f"> {alert}")
        lines.append("")

    lines.append(
        f"[Full report](https://github.com/mariomerinom/polymarket-bot/blob/main/docs/daily/{date_str}.md)"
    )
    return "\n".join(lines)


def generate_report(date_str=None, db_5m_path=None, db_15m_path=None, output_dir=None,
                    summary_path=None, db_eth_path=None, db_kalshi_path=None,
                    db_bybit_path=None):
    """
    Main entry point. Generates daily report for the given date.
    Defaults to yesterday (UTC).
    """
    if date_str is None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    db_5m = db_5m_path or DB_5M
    db_15m = db_15m_path or DB_15M
    db_eth = db_eth_path or DB_ETH
    db_kalshi = db_kalshi_path or DB_KALSHI
    db_bybit = db_bybit_path or DB_BYBIT
    daily_dir = Path(output_dir) if output_dir else DAILY_DIR

    print(f"Daily Report for {date_str}")
    print("=" * 40)

    # Analyze all 5 pipelines
    data_5m = analyze_pipeline(db_5m, date_str)
    data_15m = analyze_pipeline(db_15m, date_str)
    data_eth = analyze_pipeline(db_eth, date_str)
    data_kalshi = analyze_pipeline(db_kalshi, date_str)
    data_bybit = analyze_pipeline(db_bybit, date_str)

    if data_5m is None and data_15m is None and data_eth is None and data_kalshi is None and data_bybit is None:
        print(f"  No predictions found for {date_str}")
        return None

    for label, data in [("5m", data_5m), ("15m", data_15m), ("ETH", data_eth), ("Kalshi", data_kalshi), ("Bybit", data_bybit)]:
        if data:
            s = data["summary"]
            print(f"  {label}: {s['total_predictions']} predictions, {s['resolved_bets']} resolved bets, "
                  f"{s['wr']}% WR, ${s['pnl']:+.2f} P&L")

    # ── Consolidated cross-pipeline analysis (all 12 pipelines) ──
    # Runs analyze_pipeline for every pipeline in config/pipelines.json.
    # Prepends a summary block to the legacy daily and writes a separate
    # consolidated-YYYY-MM-DD.md drill-down file.
    consolidated_overview_md = ""
    try:
        import consolidated_report
        all_results = consolidated_report.analyze_all_pipelines(date_str)
        consolidated_overview_md = consolidated_report.render_overview_block(
            all_results, date_str)
        detail_path = consolidated_report.write_consolidated_detail(
            all_results, date_str, daily_dir)
        print(f"  Consolidated detail: {detail_path}")
    except Exception as e:
        print(f"  [WARN] Consolidated report failed: {e}")

    # Check decision triggers
    decision_alerts = check_decisions(db_5m, db_15m)

    # Check optimization tracker
    try:
        from optimization_tracker import check_all as check_optimizations
        optimization_alerts = check_optimizations()
    except Exception:
        optimization_alerts = []
    decision_alerts.extend(optimization_alerts)

    # Generate markdown
    canary_readiness = _get_btc5m_canary_readiness(db_5m)
    report = format_report(date_str, data_5m, data_15m,
                           decision_alerts=decision_alerts, data_eth=data_eth,
                           data_kalshi=data_kalshi, data_bybit=data_bybit,
                           canary_readiness=canary_readiness)

    # Prepend consolidated overview (after the H1 title) if we have it
    if consolidated_overview_md:
        lines = report.split("\n", 1)
        if len(lines) == 2 and lines[0].startswith("# "):
            # Insert after title + one blank line
            report = lines[0] + "\n\n" + consolidated_overview_md + "\n" + lines[1]
        else:
            report = consolidated_overview_md + "\n\n" + report

    # Write report file
    daily_dir.mkdir(parents=True, exist_ok=True)
    report_path = daily_dir / f"{date_str}.md"
    report_path.write_text(report)
    print(f"  Report: {report_path}")

    # Update index
    update_index(daily_dir, date_str)
    print(f"  Index updated: {daily_dir / 'index.md'}")

    # Generate CI summary (for GitHub Actions Job Summary)
    ci_summary = generate_ci_summary(date_str, data_5m, data_15m,
                                     decision_alerts=decision_alerts, data_eth=data_eth,
                                     data_kalshi=data_kalshi, data_bybit=data_bybit)
    if summary_path:
        Path(summary_path).write_text(ci_summary)
        print(f"  CI summary: {summary_path}")

    # Print alerts
    for label, data in [("5m", data_5m), ("15m", data_15m), ("ETH", data_eth), ("Kalshi", data_kalshi), ("Bybit", data_bybit)]:
        if data and data["alerts"]:
            print(f"\n  {label} Alerts:")
            for alert in data["alerts"]:
                print(f"    {alert}")

    # Print decision alerts
    if decision_alerts:
        print(f"\n  Decision Alerts:")
        for alert in decision_alerts:
            print(f"    {alert}")

    return report_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate daily analysis report")
    parser.add_argument("--date", type=str, default=None,
                        help="Date to analyze (YYYY-MM-DD). Default: yesterday")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory. Default: docs/daily/")
    parser.add_argument("--summary", type=str, default=None,
                        help="Write CI summary markdown to this path (for $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args()
    generate_report(date_str=args.date, output_dir=args.output, summary_path=args.summary)
