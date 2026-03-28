"""
daily_report.py — Daily morning analysis report.

Generates a markdown report analyzing the previous day's predictions.
Covers both 5m and 15m pipelines. Designed to run via GitHub Actions cron
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
DAILY_DIR = Path(__file__).parent.parent / "docs" / "daily"

# Conviction tier → bet size (must match dashboard.py)
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 200}


def is_correct(estimate, outcome):
    """Did the prediction call the direction right?"""
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def get_daily_predictions(db, date_str):
    """Get all predictions made on a specific date (resolved or not)."""
    try:
        rows = db.execute("""
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
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
            SELECT p.agent, p.estimate, p.confidence, p.predicted_at, p.market_id,
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

    # P&L
    total_pnl = 0.0
    total_wagered = 0.0
    for r in resolved:
        conv = r.get("conviction_score") or 0
        bet_size = CONVICTION_BETS.get(conv, 0)
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

        bet_size = CONVICTION_BETS.get(conv, 0)
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
        bet_size = CONVICTION_BETS.get(conv, 0)

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
        bet_size = CONVICTION_BETS.get(conv, 0)
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


def generate_alerts(summary, rolling):
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

    return alerts


# ── Decision alert system ─────────────────────────────────────────────
# Each decision has an id matching docs/decisions.md, a check function,
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
        bet_size = CONVICTION_BETS.get(conv, 0)
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
    {
        "id": 1,
        "decision": "Demote conv=4 to flat $75 (5m)",
        "check": lambda s: s["conv4_bets"] >= 50 and s["conv4_wr"] < 60,
        "describe": lambda s: (
            f"conv=4 WR is {s['conv4_wr']}% over {s['conv4_bets']} bets "
            f"(threshold: <60% at 50+)"
        ),
    },
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
            f"(threshold: >65% at 20+)"
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
                        f"\U0001f514 Decision #{d['id']} READY: {d['decision']} — {d['describe'](stats)}"
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
                        f"\U0001f514 Decision #{d['id']} READY: {d['decision']} — {d['describe'](stats)}"
                    )
            except (KeyError, ZeroDivisionError):
                pass

    return alerts


def format_report(date_str, data_5m, data_15m, decision_alerts=None):
    """Format analysis data into markdown report."""
    decision_alerts = decision_alerts or []
    lines = [
        f"# Daily Report — {date_str}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for label, data in [("5-Minute Pipeline", data_5m), ("15-Minute Pipeline", data_15m)]:
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

        # Rolling 7-day trend
        if data["rolling"]:
            lines.extend([
                "### Rolling 7-Day Trend",
                "| Date | Bets | WR | P&L |",
                "|------|------|----|-----|",
            ])
            for day in data["rolling"]:
                if day["bets"] > 0:
                    lines.append(f"| {day['date']} | {day['bets']} | {day['wr']}% | ${day['pnl']:+.2f} |")
                else:
                    lines.append(f"| {day['date']} | — | — | — |")
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

    # Decision alerts (cross-pipeline, appended at end)
    if decision_alerts:
        lines.extend([
            "## Decision Alerts",
            "",
            "Tracked in [`docs/decisions.md`](../decisions.md). "
            "These fire when data crosses predefined thresholds.",
            "",
        ])
        for alert in decision_alerts:
            lines.append(f"- {alert}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by `src/daily_report.py`*")
    return "\n".join(lines)


def analyze_pipeline(db_path, date_str):
    """Run full analysis for one pipeline (5m or 15m)."""
    if not Path(db_path).exists():
        return None

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    predictions = get_daily_predictions(db, date_str)
    resolved = get_daily_resolved(db, date_str)

    if not predictions:
        db.close()
        return None

    summary = analyze_summary(predictions, resolved)
    regimes = analyze_regime_distribution(predictions)
    directions = analyze_direction(resolved)
    price_buckets = analyze_price_buckets(resolved)
    conviction = analyze_conviction_tiers(resolved)
    rolling = rolling_trend(db, date_str, window=7)
    alerts = generate_alerts(summary, rolling)

    db.close()

    return {
        "summary": summary,
        "regimes": regimes,
        "directions": directions,
        "price_buckets": price_buckets,
        "conviction": conviction,
        "rolling": rolling,
        "alerts": alerts,
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


def generate_ci_summary(date_str, data_5m, data_15m, decision_alerts=None):
    """Generate concise markdown for GitHub Actions Job Summary."""
    decision_alerts = decision_alerts or []
    lines = [f"# Daily Report \u2014 {date_str}", ""]

    for label, data in [("5m", data_5m), ("15m", data_15m)]:
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

        # Alerts
        if data["alerts"]:
            for alert in data["alerts"]:
                lines.append(f"> {alert}")
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


def generate_report(date_str=None, db_5m_path=None, db_15m_path=None, output_dir=None, summary_path=None):
    """
    Main entry point. Generates daily report for the given date.
    Defaults to yesterday (UTC).
    """
    if date_str is None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    db_5m = db_5m_path or DB_5M
    db_15m = db_15m_path or DB_15M
    daily_dir = Path(output_dir) if output_dir else DAILY_DIR

    print(f"Daily Report for {date_str}")
    print("=" * 40)

    # Analyze both pipelines
    data_5m = analyze_pipeline(db_5m, date_str)
    data_15m = analyze_pipeline(db_15m, date_str)

    if data_5m is None and data_15m is None:
        print(f"  No predictions found for {date_str}")
        return None

    if data_5m:
        s = data_5m["summary"]
        print(f"  5m: {s['total_predictions']} predictions, {s['resolved_bets']} resolved bets, "
              f"{s['wr']}% WR, ${s['pnl']:+.2f} P&L")
    if data_15m:
        s = data_15m["summary"]
        print(f"  15m: {s['total_predictions']} predictions, {s['resolved_bets']} resolved bets, "
              f"{s['wr']}% WR, ${s['pnl']:+.2f} P&L")

    # Check decision triggers
    decision_alerts = check_decisions(db_5m, db_15m)

    # Generate markdown
    report = format_report(date_str, data_5m, data_15m, decision_alerts=decision_alerts)

    # Write report file
    daily_dir.mkdir(parents=True, exist_ok=True)
    report_path = daily_dir / f"{date_str}.md"
    report_path.write_text(report)
    print(f"  Report: {report_path}")

    # Update index
    update_index(daily_dir, date_str)
    print(f"  Index updated: {daily_dir / 'index.md'}")

    # Generate CI summary (for GitHub Actions Job Summary)
    ci_summary = generate_ci_summary(date_str, data_5m, data_15m, decision_alerts=decision_alerts)
    if summary_path:
        Path(summary_path).write_text(ci_summary)
        print(f"  CI summary: {summary_path}")

    # Print alerts
    for label, data in [("5m", data_5m), ("15m", data_15m)]:
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
