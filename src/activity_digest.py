"""
activity_digest.py — Auto-generated activity digest for days without a manual session log.

Runs via GitHub Actions cron after the daily report. Produces a lightweight
session log at docs/sessions/YYYY-MM-DD.md covering:
  - Commits shipped (non-CI)
  - Pipeline health (from daily report data)
  - Decision tracker status
  - Active optimizations

This is a safety net — if a manual /eod-log already exists for the date,
this script exits without overwriting.

Output: docs/sessions/YYYY-MM-DD.md (only if not already present)
"""

import json
import re
import subprocess
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paths
ROOT = Path(__file__).parent.parent
SESSIONS_DIR = ROOT / "docs" / "sessions"
DAILY_DIR = ROOT / "docs" / "daily"
OPTIMIZATIONS_PATH = ROOT / "docs" / "optimizations.json"
DECISIONS_PATH = ROOT / "docs" / "core" / "decisions.md"
DB_5M = ROOT / "data" / "predictions.db"
DB_15M = ROOT / "data" / "predictions_15m.db"
DB_ETH = ROOT / "data" / "predictions_eth.db"
DB_KALSHI = ROOT / "data" / "predictions_kalshi.db"

# Reuse daily report sizing
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import LIVE_START_DATE


def get_date_str(date_str=None):
    """Return target date (default: yesterday UTC)."""
    if date_str:
        return date_str
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def session_exists(date_str):
    """Check if a session log already exists for this date (any suffix)."""
    for f in SESSIONS_DIR.glob(f"{date_str}*.md"):
        if f.name != "index.md":
            return True
    return False


def get_commits(date_str):
    """Get non-CI commits for the given date."""
    try:
        # Get commits from the target date (UTC)
        since = f"{date_str}T00:00:00Z"
        until_date = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
        until = until_date.strftime("%Y-%m-%dT00:00:00Z")

        result = subprocess.run(
            ["git", "log", f"--since={since}", f"--until={until}",
             "--oneline", "--all", "--no-merges"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Filter out CI auto-commits
            if line.startswith("Auto:") or "Auto:" in line or "cycle update" in line.lower():
                # Check after the hash
                parts = line.split(" ", 1)
                if len(parts) > 1 and ("Auto:" in parts[1] or "cycle update" in parts[1].lower()):
                    continue
            commits.append(line)
        return commits
    except Exception:
        return []


def get_pipeline_health(date_str):
    """Query pipeline DBs for the target date's stats."""
    pipelines = []
    for label, db_path in [("BTC 5m", DB_5M), ("BTC 15m", DB_15M),
                            ("ETH 5m", DB_ETH), ("Kalshi", DB_KALSHI)]:
        if not db_path.exists():
            continue
        try:
            db = sqlite3.connect(str(db_path))
            # Count predictions for the date
            total = db.execute(
                "SELECT COUNT(*) FROM predictions WHERE predicted_at LIKE ?",
                (f"{date_str}%",)
            ).fetchone()[0]

            # Count bets (conv >= 3) that resolved
            bets = db.execute("""
                SELECT COUNT(*) FROM predictions p
                JOIN markets m ON p.market_id = m.id
                WHERE p.predicted_at LIKE ?
                AND p.conviction_score >= 3
                AND m.resolved = 1
            """, (f"{date_str}%",)).fetchone()[0]

            # Win rate and P&L
            if bets > 0:
                rows = db.execute("""
                    SELECT p.estimate, m.outcome, p.conviction_score, p.predicted_at
                    FROM predictions p
                    JOIN markets m ON p.market_id = m.id
                    WHERE p.predicted_at LIKE ?
                    AND p.conviction_score >= 3
                    AND m.resolved = 1
                """, (f"{date_str}%",)).fetchall()

                wins = 0
                pnl = 0.0
                for est, outcome, conv, pred_at in rows:
                    predicted_up = est > 0.5
                    actual_up = outcome == "Yes"
                    correct = predicted_up == actual_up
                    if correct:
                        wins += 1
                    # Simplified P&L (actual P&L is in daily report)
                    # Just use $25 flat for live era
                    bet_size = 25 if pred_at[:10] >= LIVE_START_DATE else 75
                    mkt_price = est if predicted_up else (1 - est)
                    if correct:
                        pnl += bet_size * (1 / mkt_price - 1)
                    else:
                        pnl -= bet_size

                wr = round(wins / bets * 100, 1) if bets > 0 else 0
                pipelines.append({
                    "label": label, "predictions": total,
                    "bets": bets, "wr": wr, "pnl": pnl
                })
            else:
                pipelines.append({
                    "label": label, "predictions": total,
                    "bets": 0, "wr": 0, "pnl": 0
                })
            db.close()
        except Exception:
            continue
    return pipelines


def get_optimization_status():
    """Get active optimizations summary."""
    if not OPTIMIZATIONS_PATH.exists():
        return []
    try:
        data = json.loads(OPTIMIZATIONS_PATH.read_text())
        active = [o for o in data.get("optimizations", []) if o.get("status") == "active"]
        return active
    except Exception:
        return []


def get_decision_status():
    """Parse decisions.md for MONITORING and READY decisions."""
    if not DECISIONS_PATH.exists():
        return []
    try:
        content = DECISIONS_PATH.read_text()
        decisions = []
        # Find lines with status markers
        for line in content.split("\n"):
            if "MONITORING" in line or "READY" in line:
                # Extract decision number and description
                match = re.match(r'.*?#(\d+).*?\*\*(.*?)\*\*.*?(MONITORING|READY)', line)
                if match:
                    decisions.append({
                        "number": match.group(1),
                        "name": match.group(2).strip(),
                        "status": match.group(3)
                    })
        return decisions
    except Exception:
        return []


def format_digest(date_str, commits, pipelines, optimizations, decisions):
    """Format the activity digest markdown."""
    lines = [
        f"# Activity Digest \u2014 {date_str}",
        "",
        "> Auto-generated. No manual session log was created for this date.",
        "",
    ]

    # Commits
    lines.append("## Commits Shipped")
    lines.append("")
    if commits:
        for c in commits:
            lines.append(f"- `{c}`")
    else:
        lines.append("_No non-CI commits._")
    lines.append("")

    # Pipeline health
    lines.append("## Pipeline Health")
    lines.append("")
    if pipelines:
        lines.append("| Pipeline | Predictions | Bets | WR | P&L |")
        lines.append("|----------|-------------|------|----|-----|")
        for p in pipelines:
            pnl_str = f"${p['pnl']:+.2f}" if p['bets'] > 0 else "\u2014"
            wr_str = f"{p['wr']}%" if p['bets'] > 0 else "\u2014"
            lines.append(f"| {p['label']} | {p['predictions']} | {p['bets']} | {wr_str} | {pnl_str} |")
    else:
        lines.append("_No pipeline data available._")
    lines.append("")

    # Active optimizations
    lines.append("## Active Optimizations")
    lines.append("")
    if optimizations:
        for o in optimizations:
            post = o.get("post_change", {})
            post_bets = post.get("bets", 0)
            min_sample = o.get("min_sample", 50)
            post_wr = post.get("wr", 0)
            baseline_wr = o.get("baseline", {}).get("wr", 0)
            lines.append(
                f"- **{o['name']}**: {post_bets}/{min_sample} bets "
                f"({post_wr}% WR vs {baseline_wr}% baseline)"
            )
    else:
        lines.append("_No active optimizations._")
    lines.append("")

    # Decision tracker
    lines.append("## Decision Tracker")
    lines.append("")
    if decisions:
        ready = [d for d in decisions if d["status"] == "READY"]
        monitoring = [d for d in decisions if d["status"] == "MONITORING"]
        if ready:
            for d in ready:
                lines.append(f"- \U0001f534 **#{d['number']} {d['name']}** \u2014 READY (action needed)")
        if monitoring:
            for d in monitoring:
                lines.append(f"- \U0001f7e1 #{d['number']} {d['name']} \u2014 monitoring")
    else:
        lines.append("_No tracked decisions._")
    lines.append("")

    # References
    lines.append("## References")
    lines.append("")
    lines.append(f"- [Daily Report](../daily/{date_str}.md)")
    lines.append("- [Roadmap](../core/ROADMAP.md)")
    lines.append("- [Decisions](../core/decisions.md)")
    lines.append("")

    return "\n".join(lines)


def update_index(date_str, is_digest=True):
    """Add entry to sessions index (most recent first)."""
    index_path = SESSIONS_DIR / "index.md"
    if not index_path.exists():
        content = "# Session Logs\n\nWorking session summaries — what was built, shipped, learned, and kicked forward.\n\n"
    else:
        content = index_path.read_text()

    # Check if date already in index
    if date_str in content:
        return

    tag = "(auto-digest)" if is_digest else ""
    new_entry = f"- [{date_str}]({date_str}.md) \u2014 Activity digest {tag}"

    # Insert after the header lines (find first "- [" line and insert before it)
    lines = content.split("\n")
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith("- ["):
            insert_idx = i
            break

    if insert_idx is not None:
        lines.insert(insert_idx, new_entry)
    else:
        lines.append(new_entry)

    index_path.write_text("\n".join(lines))


def generate_digest(date_str=None):
    """Main entry point."""
    date_str = get_date_str(date_str)

    # Skip if manual session log already exists
    if session_exists(date_str):
        print(f"Session log already exists for {date_str} — skipping auto-digest.")
        return None

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    commits = get_commits(date_str)
    pipelines = get_pipeline_health(date_str)
    optimizations = get_optimization_status()
    decisions = get_decision_status()

    digest = format_digest(date_str, commits, pipelines, optimizations, decisions)

    output_path = SESSIONS_DIR / f"{date_str}.md"
    output_path.write_text(digest)
    print(f"Activity digest: {output_path}")

    update_index(date_str, is_digest=True)
    print(f"Index updated: {SESSIONS_DIR / 'index.md'}")

    # Print summary
    print(f"\n  {date_str}: {len(commits)} commits, {len(pipelines)} pipelines, "
          f"{len(optimizations)} active optimizations, {len(decisions)} tracked decisions")

    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate activity digest (safety net for missing session logs)")
    parser.add_argument("--date", type=str, default=None,
                        help="Date to analyze (YYYY-MM-DD). Default: yesterday")
    args = parser.parse_args()
    generate_digest(date_str=args.date)
