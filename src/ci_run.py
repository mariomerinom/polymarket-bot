"""
ci_run.py — One-shot cycle for GitHub Actions.

Runs the full pipeline once:
  1. Fetch active BTC 5-min markets
  2. Predict on the next unpredicted market
  3. Auto-resolve closed markets
  4. Score agents
  5. Generate static dashboard HTML
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_markets import init_db, fetch_active_markets, store_markets, DB_PATH
from predict import run_predictions
from score import auto_resolve, calculate_brier_scores, print_scorecard


def get_next_cycle(db):
    """Derive cycle number from the highest cycle recorded."""
    cursor = db.execute("SELECT COALESCE(MAX(cycle), 0) + 1 FROM predictions")
    return cursor.fetchone()[0]


def has_unpredicted_market(db):
    """Check if there's an upcoming market we haven't predicted on yet."""
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT m.id FROM markets m
        WHERE m.resolved = 0 AND m.end_date > ?
        AND m.id NOT IN (SELECT DISTINCT market_id FROM predictions)
        ORDER BY m.end_date ASC LIMIT 1
    """, (now_iso,))
    return cursor.fetchone() is not None


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()

    # 1. Fetch markets
    print("[1/5] Fetching markets...")
    try:
        markets = fetch_active_markets()
        store_markets(db, markets)
        print(f"  {len(markets)} active markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 2. Auto-resolve closed markets (do this BEFORE predicting so we don't waste on stale markets)
    print("[2/5] Auto-resolving...")
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print("No active markets. Exiting early.")
        # Still generate dashboard even with no new data
        db.close()
        _generate_dashboard()
        return

    # 3. Predict on next unpredicted market
    cycle = get_next_cycle(db)
    print(f"[3/5] Predictions (cycle {cycle})...")
    if has_unpredicted_market(db):
        db.close()
        try:
            run_predictions(cycle=cycle, market_limit=1)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH)
    else:
        print("  No unpredicted markets")

    # 4. Score
    print("[4/5] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    db.close()

    # 5. Generate dashboard
    print("[5/5] Generating dashboard...")
    _generate_dashboard()

    print("\nCI run complete.")


def _generate_dashboard():
    from generate_dashboard import generate
    generate()


if __name__ == "__main__":
    main()
