"""
run_cycle.py — Orchestrator that runs one full prediction cycle.

Usage:
    python run_cycle.py                  # Fetch + predict (default cycle 1)
    python run_cycle.py --cycle 2        # Run cycle 2
    python run_cycle.py --score-only     # Just print scores
"""

import argparse
from fetch_markets import init_db, fetch_active_markets, store_markets, DB_PATH
from predict import run_predictions
from score import calculate_brier_scores, print_scorecard, auto_resolve
import sqlite3


def main():
    parser = argparse.ArgumentParser(description="Polymarket Prediction Cycle Runner")
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets per cycle")
    parser.add_argument("--score-only", action="store_true", help="Only print scores")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()

    if args.score_only:
        resolved = auto_resolve(db)
        if resolved:
            print(f"Auto-resolved {resolved} market(s)")
        results = calculate_brier_scores(db)
        print_scorecard(results)
        db.close()
        return

    # Fetch markets
    print(f"{'=' * 50}")
    print(f"CYCLE {args.cycle}")
    print(f"{'=' * 50}")

    print("\n[1/3] Fetching markets...")
    markets = fetch_active_markets()
    store_markets(db, markets)
    print(f"  Found {len(markets)} qualifying markets")
    db.close()

    # Run predictions
    print("\n[2/3] Running predictions...")
    run_predictions(cycle=args.cycle, market_limit=args.markets)

    # Auto-resolve and score
    print("\n[3/3] Checking for resolved markets & scoring...")
    db = sqlite3.connect(DB_PATH)
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Auto-resolved {resolved} market(s)")
    results = calculate_brier_scores(db)
    print_scorecard(results)
    db.close()

    print(f"\nCycle {args.cycle} complete.")


if __name__ == "__main__":
    main()
