"""
optimization_tracker.py — Track and validate every optimization.

Level 1: Register optimizations with baseline stats. The daily report
checks post-change performance and alerts when revert criteria are met
or when the optimization is validated.

Usage:
    # Register a new optimization after shipping code
    python optimization_tracker.py register \
        --name "direction_regime_filter" \
        --description "DOWN + NEUTRAL → conv=2 (no bet)" \
        --revert-if "post_wr < baseline_wr - 2" \
        --min-sample 50

    # Check all active optimizations against current data
    python optimization_tracker.py check

    # Mark an optimization as validated or reverted
    python optimization_tracker.py close --name "direction_regime_filter" --status validated
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

OPTIMIZATIONS_PATH = Path(__file__).parent.parent / "docs" / "optimizations.json"
DB_5M = Path(__file__).parent.parent / "data" / "predictions.db"
DB_15M = Path(__file__).parent.parent / "data" / "predictions_15m.db"

# Conviction tier → bet size (must match dashboard.py and daily_report.py)
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 200}


def load_optimizations():
    """Load the optimization registry."""
    if OPTIMIZATIONS_PATH.exists():
        return json.loads(OPTIMIZATIONS_PATH.read_text())
    return {"optimizations": []}


def save_optimizations(data):
    """Save the optimization registry."""
    OPTIMIZATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPTIMIZATIONS_PATH.write_text(json.dumps(data, indent=2) + "\n")


def compute_stats(db_path, since=None):
    """Compute aggregate stats from the DB, optionally filtered to predictions after a date."""
    if not Path(db_path).exists():
        return None

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    date_filter = ""
    params = ()
    if since:
        date_filter = "AND p.predicted_at >= ?"
        params = (since,)

    try:
        rows = db.execute(f"""
            SELECT p.estimate, p.conviction_score, p.regime,
                   m.outcome, m.price_yes
            FROM predictions p
            JOIN markets m ON p.market_id = m.id
            WHERE m.resolved = 1 AND p.conviction_score >= 3
            {date_filter}
        """, params).fetchall()
    except sqlite3.OperationalError:
        db.close()
        return None

    if not rows:
        db.close()
        return {"bets": 0, "wins": 0, "wr": 0, "pnl": 0, "wagered": 0}

    wins = 0
    total_pnl = 0.0
    total_wagered = 0.0

    for r in rows:
        estimate = r["estimate"]
        outcome = r["outcome"]
        conv = r["conviction_score"]
        price_yes = r["price_yes"]
        bet_size = CONVICTION_BETS.get(conv, 0)

        correct = (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)
        if correct:
            wins += 1

        total_wagered += bet_size
        if estimate >= 0.5 and 0 < price_yes < 1:
            total_pnl += bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
        elif estimate < 0.5:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                total_pnl += bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

    db.close()

    bets = len(rows)
    return {
        "bets": bets,
        "wins": wins,
        "wr": round(wins / bets * 100, 1) if bets > 0 else 0,
        "pnl": round(total_pnl, 2),
        "wagered": round(total_wagered, 2),
    }


def register(name, description, revert_condition, min_sample=50, pipeline="5m"):
    """Register a new optimization with baseline stats."""
    data = load_optimizations()

    # Check for duplicate
    for opt in data["optimizations"]:
        if opt["name"] == name and opt["status"] == "active":
            print(f"  ⚠️  Optimization '{name}' already active. Use 'close' first.")
            return None

    # Compute baseline stats (all data up to now)
    db_path = DB_5M if pipeline == "5m" else DB_15M
    baseline = compute_stats(db_path)
    if baseline is None:
        print(f"  ⚠️  No DB found at {db_path}")
        return None

    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "name": name,
        "description": description,
        "registered_at": now,
        "pipeline": pipeline,
        "status": "active",
        "min_sample": min_sample,
        "revert_condition": revert_condition,
        "baseline": baseline,
        "latest_check": None,
        "post_stats": None,
        "closed_at": None,
        "close_reason": None,
    }

    data["optimizations"].append(entry)
    save_optimizations(data)

    print(f"  ✅ Registered: {name}")
    print(f"     Baseline: {baseline['bets']} bets, {baseline['wr']}% WR, ${baseline['pnl']:+.2f} P&L")
    print(f"     Revert if: {revert_condition}")
    print(f"     Min sample: {min_sample} post-change bets")

    return entry


def check_all():
    """Check all active optimizations against current data. Returns alerts."""
    data = load_optimizations()
    alerts = []
    now = datetime.now(timezone.utc).isoformat()

    for opt in data["optimizations"]:
        if opt["status"] != "active":
            continue

        db_path = DB_5M if opt["pipeline"] == "5m" else DB_15M
        post = compute_stats(db_path, since=opt["registered_at"])

        if post is None:
            continue

        opt["latest_check"] = now
        opt["post_stats"] = post

        baseline_wr = opt["baseline"]["wr"]
        post_wr = post["wr"]
        post_bets = post["bets"]
        min_sample = opt.get("min_sample", 50)

        if post_bets < min_sample:
            # Not enough data yet — report progress
            alerts.append(
                f"📊 {opt['name']}: {post_bets}/{min_sample} bets collected "
                f"({post_wr}% WR vs {baseline_wr}% baseline)"
            )
        else:
            # Enough data — evaluate
            delta = post_wr - baseline_wr
            if delta >= 0:
                alerts.append(
                    f"✅ {opt['name']}: VALIDATED — {post_wr}% WR vs {baseline_wr}% baseline "
                    f"(+{delta:.1f}pp on {post_bets} bets, ${post['pnl']:+.2f} P&L)"
                )
            else:
                # Check revert condition
                revert_expr = opt["revert_condition"]
                # Safe eval with limited namespace
                should_revert = False
                try:
                    should_revert = eval(revert_expr, {"__builtins__": {}}, {
                        "post_wr": post_wr,
                        "baseline_wr": baseline_wr,
                        "post_bets": post_bets,
                        "post_pnl": post["pnl"],
                        "baseline_pnl": opt["baseline"]["pnl"],
                    })
                except Exception:
                    pass

                if should_revert:
                    alerts.append(
                        f"🚨 {opt['name']}: REVERT CANDIDATE — {post_wr}% WR vs {baseline_wr}% baseline "
                        f"({delta:+.1f}pp on {post_bets} bets, ${post['pnl']:+.2f} P&L)"
                    )
                else:
                    alerts.append(
                        f"⚠️ {opt['name']}: underperforming — {post_wr}% WR vs {baseline_wr}% baseline "
                        f"({delta:+.1f}pp on {post_bets} bets, ${post['pnl']:+.2f} P&L)"
                    )

    save_optimizations(data)
    return alerts


def close(name, status="validated", reason=None):
    """Close an optimization (validated, reverted, or deferred)."""
    data = load_optimizations()
    now = datetime.now(timezone.utc).isoformat()

    for opt in data["optimizations"]:
        if opt["name"] == name and opt["status"] == "active":
            opt["status"] = status
            opt["closed_at"] = now
            opt["close_reason"] = reason
            save_optimizations(data)
            print(f"  ✅ Closed '{name}' as {status}")
            if reason:
                print(f"     Reason: {reason}")
            return opt

    print(f"  ⚠️  No active optimization named '{name}'")
    return None


def summary():
    """Print summary of all optimizations."""
    data = load_optimizations()
    if not data["optimizations"]:
        print("  No optimizations registered.")
        return

    active = [o for o in data["optimizations"] if o["status"] == "active"]
    closed = [o for o in data["optimizations"] if o["status"] != "active"]

    if active:
        print(f"\n  Active ({len(active)}):")
        for o in active:
            post = o.get("post_stats") or {}
            post_bets = post.get("bets", 0)
            post_wr = post.get("wr", "—")
            baseline_wr = o["baseline"]["wr"]
            min_sample = o.get("min_sample", 50)
            print(f"    {o['name']}: {post_bets}/{min_sample} bets, "
                  f"{post_wr}% WR (baseline {baseline_wr}%)")

    if closed:
        print(f"\n  Closed ({len(closed)}):")
        for o in closed:
            print(f"    {o['name']}: {o['status']} on {o.get('closed_at', '?')[:10]}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Track and validate optimizations")
    sub = parser.add_subparsers(dest="command")

    reg = sub.add_parser("register", help="Register a new optimization")
    reg.add_argument("--name", required=True)
    reg.add_argument("--description", required=True)
    reg.add_argument("--revert-if", required=True, dest="revert_condition")
    reg.add_argument("--min-sample", type=int, default=50)
    reg.add_argument("--pipeline", default="5m", choices=["5m", "15m"])

    chk = sub.add_parser("check", help="Check all active optimizations")

    cls = sub.add_parser("close", help="Close an optimization")
    cls.add_argument("--name", required=True)
    cls.add_argument("--status", default="validated", choices=["validated", "reverted", "deferred"])
    cls.add_argument("--reason", default=None)

    sub.add_parser("summary", help="Show optimization summary")

    args = parser.parse_args()

    if args.command == "register":
        register(args.name, args.description, args.revert_condition,
                 args.min_sample, args.pipeline)
    elif args.command == "check":
        alerts = check_all()
        for a in alerts:
            print(f"  {a}")
        if not alerts:
            print("  No active optimizations to check.")
    elif args.command == "close":
        close(args.name, args.status, args.reason)
    elif args.command == "summary":
        summary()
    else:
        parser.print_help()
