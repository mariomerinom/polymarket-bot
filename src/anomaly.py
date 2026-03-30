"""
anomaly.py — Real-time anomaly detection for prediction pipelines.

Ported from arbitrageur's AnomalyDetector pattern.
Runs after each scoring cycle (called from daily_report or standalone).

Rules:
  1. WR drop >15% (baseline 50 trades vs recent 20) → WARN
  2. Profit factor <1.0 (rolling 20-trade window) → CRITICAL
  3. Signal frequency deviation >2σ from mean interval → WARN
  4. Consecutive loss streak >= 4 → WARN, >= 6 → CRITICAL
  5. Edge decay: recent edge < 50% of historical edge → WARN

Does NOT modify trading behavior — read-only analysis.
Anomaly alerts surface in daily report and dashboard.
"""

import sqlite3
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


@dataclass
class Anomaly:
    rule: str
    severity: str  # INFO, WARN, CRITICAL
    message: str
    value: float
    threshold: float


def detect_anomalies(db_path=None):
    """
    Run all anomaly detection rules against resolved predictions.

    Returns list of Anomaly objects (empty if everything is healthy).
    """
    if db_path is None:
        db_path = DB_PATH

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    anomalies = []
    anomalies.extend(_check_wr_drop(db))
    anomalies.extend(_check_profit_factor(db))
    anomalies.extend(_check_signal_frequency(db))
    anomalies.extend(_check_consecutive_losses(db))
    anomalies.extend(_check_edge_decay(db))

    db.close()
    return anomalies


def _check_wr_drop(db, baseline_n=50, recent_n=20, threshold_pct=15):
    """Rule 1: WR drop >15% between baseline and recent window."""
    rows = db.execute("""
        SELECT p.estimate, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
            AND p.conviction_score >= 3
        ORDER BY p.predicted_at DESC
        LIMIT ?
    """, (baseline_n,)).fetchall()

    if len(rows) < baseline_n:
        return []

    def wr(subset):
        wins = sum(1 for r in subset if (
            (r["estimate"] >= 0.5 and r["outcome"] == 1) or
            (r["estimate"] < 0.5 and r["outcome"] == 0)
        ))
        return wins / len(subset) * 100 if subset else 0

    recent_wr = wr(rows[:recent_n])
    baseline_wr = wr(rows)
    drop = baseline_wr - recent_wr

    if drop > threshold_pct:
        return [Anomaly(
            rule="wr_drop",
            severity="WARN",
            message=f"WR dropped {drop:.1f}pp: baseline {baseline_wr:.1f}% → recent {recent_wr:.1f}%",
            value=drop,
            threshold=threshold_pct,
        )]
    return []


def _check_profit_factor(db, window=20):
    """Rule 2: Profit factor <1.0 on rolling window → CRITICAL."""
    rows = db.execute("""
        SELECT p.estimate, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
            AND p.conviction_score >= 3
        ORDER BY p.predicted_at DESC
        LIMIT ?
    """, (window,)).fetchall()

    if len(rows) < window:
        return []

    gross_profit = 0.0
    gross_loss = 0.0
    for r in rows:
        est = r["estimate"]
        won = (est >= 0.5 and r["outcome"] == 1) or (est < 0.5 and r["outcome"] == 0)
        if won:
            price = est if est >= 0.5 else (1 - est)
            pnl = 25 * (1.0 / price - 1) * 0.985
            gross_profit += pnl
        else:
            gross_loss += 25

    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    if pf < 1.0:
        return [Anomaly(
            rule="profit_factor_collapse",
            severity="CRITICAL",
            message=f"Profit factor {pf:.2f} < 1.0 on last {window} trades (losing money)",
            value=pf,
            threshold=1.0,
        )]
    return []


def _check_signal_frequency(db):
    """Rule 3: Signal frequency deviation >2σ from mean → WARN."""
    rows = db.execute("""
        SELECT predicted_at FROM predictions
        WHERE conviction_score >= 3
        ORDER BY predicted_at DESC
        LIMIT 100
    """).fetchall()

    if len(rows) < 20:
        return []

    # Compute intervals in minutes between consecutive predictions
    times = []
    for r in rows:
        try:
            t = datetime.fromisoformat(r["predicted_at"].replace("Z", "+00:00"))
            times.append(t)
        except (ValueError, TypeError):
            continue

    if len(times) < 20:
        return []

    intervals = []
    for i in range(len(times) - 1):
        delta = (times[i] - times[i + 1]).total_seconds() / 60  # minutes
        if delta > 0:
            intervals.append(delta)

    if len(intervals) < 10:
        return []

    mean_int = statistics.mean(intervals)
    stdev_int = statistics.stdev(intervals)
    if stdev_int == 0:
        return []

    # Check last 5 intervals vs baseline
    recent = intervals[:5]
    recent_mean = statistics.mean(recent)
    z_score = abs(recent_mean - mean_int) / stdev_int

    if z_score > 2.0:
        return [Anomaly(
            rule="signal_frequency_deviation",
            severity="WARN",
            message=f"Signal frequency shifted: recent avg {recent_mean:.0f}min vs baseline {mean_int:.0f}min ({z_score:.1f}σ)",
            value=z_score,
            threshold=2.0,
        )]
    return []


def _check_consecutive_losses(db, warn_threshold=4, critical_threshold=6):
    """Rule 4: Consecutive loss streak → WARN at 4, CRITICAL at 6."""
    rows = db.execute("""
        SELECT p.estimate, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
            AND p.conviction_score >= 3
        ORDER BY p.predicted_at DESC
        LIMIT 20
    """).fetchall()

    streak = 0
    for r in rows:
        won = (r["estimate"] >= 0.5 and r["outcome"] == 1) or \
              (r["estimate"] < 0.5 and r["outcome"] == 0)
        if not won:
            streak += 1
        else:
            break

    if streak >= critical_threshold:
        return [Anomaly(
            rule="consecutive_losses",
            severity="CRITICAL",
            message=f"{streak} consecutive losses — consider kill switch",
            value=streak,
            threshold=critical_threshold,
        )]
    elif streak >= warn_threshold:
        return [Anomaly(
            rule="consecutive_losses",
            severity="WARN",
            message=f"{streak} consecutive losses — monitoring",
            value=streak,
            threshold=warn_threshold,
        )]
    return []


def _check_edge_decay(db, baseline_n=100, recent_n=20, threshold=0.5):
    """Rule 5: Recent edge < 50% of historical edge → WARN."""
    rows = db.execute("""
        SELECT p.estimate, m.outcome, m.price_yes
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
            AND p.conviction_score >= 3
        ORDER BY p.predicted_at DESC
        LIMIT ?
    """, (baseline_n,)).fetchall()

    if len(rows) < baseline_n:
        return []

    def avg_edge(subset):
        edges = [abs(r["estimate"] - 0.5) for r in subset]
        return statistics.mean(edges) if edges else 0

    baseline_edge = avg_edge(rows)
    recent_edge = avg_edge(rows[:recent_n])

    if baseline_edge > 0 and recent_edge < baseline_edge * threshold:
        return [Anomaly(
            rule="edge_decay",
            severity="WARN",
            message=f"Edge decaying: recent {recent_edge:.3f} < {threshold*100:.0f}% of baseline {baseline_edge:.3f}",
            value=recent_edge,
            threshold=baseline_edge * threshold,
        )]
    return []


def format_anomalies(anomalies):
    """Format anomalies for daily report / dashboard."""
    if not anomalies:
        return "No anomalies detected."

    lines = []
    for a in anomalies:
        icon = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🚨"}.get(a.severity, "?")
        lines.append(f"  {icon} [{a.severity}] {a.rule}: {a.message}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    db_path = DB_PATH
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    print(f"Anomaly Detection — {db_path.name}")
    print("=" * 50)
    anomalies = detect_anomalies(db_path)

    if not anomalies:
        print("\n  All clear. No anomalies detected.")
    else:
        print(f"\n  {len(anomalies)} anomaly(ies) found:\n")
        print(format_anomalies(anomalies))
