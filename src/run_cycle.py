"""
run_cycle.py — Orchestrator that runs one full autoresearch cycle.

Usage:
    python run_cycle.py                  # Fetch + predict (default cycle 1)
    python run_cycle.py --cycle 2        # Run cycle 2
    python run_cycle.py --score-only     # Just print scores
    python run_cycle.py --evolve         # Run evolution step
    python run_cycle.py --full           # Fetch → predict → score → evolve
"""

import argparse
from fetch_markets import init_db, fetch_active_markets, store_markets, DB_PATH
from predict import run_predictions
from score import calculate_brier_scores, print_scorecard, auto_resolve
from evolve import evolve
import sqlite3


def main():
    parser = argparse.ArgumentParser(description="Polymarket Autoresearch Cycle Runner")
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets per cycle")
    parser.add_argument("--score-only", action="store_true", help="Only print scores")
    parser.add_argument("--evolve", action="store_true", help="Run evolution step")
    parser.add_argument("--full", action="store_true", help="Run full cycle: fetch → predict → score → evolve")
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

    if args.evolve:
        db.close()
        evolve(cycle=args.cycle)
        return

    # Fetch markets
    print(f"{'=' * 50}")
    print(f"CYCLE {args.cycle}")
    print(f"{'=' * 50}")

    print("\n[1/4] Fetching markets...")
    markets = fetch_active_markets()
    store_markets(db, markets)
    print(f"  Found {len(markets)} qualifying markets")
    db.close()

    # Run predictions
    print("\n[2/4] Running agent predictions...")
    run_predictions(cycle=args.cycle, market_limit=args.markets)

    # Auto-resolve and score
    print("\n[3/4] Checking for resolved markets & scoring...")
    db = sqlite3.connect(DB_PATH)
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Auto-resolved {resolved} market(s)")
    results = calculate_brier_scores(db)
    worst = print_scorecard(results)
    db.close()

    # Evolve (only if --full and we have scores)
    if args.full and worst:
        print("\n[4/4] Evolving worst agent...")
        evolve(cycle=args.cycle)
    else:
        print("\n[4/4] Skipping evolution (no resolved markets yet or --full not set)")

    print(f"\nCycle {args.cycle} complete.")


if __name__ == "__main__":
    main()
