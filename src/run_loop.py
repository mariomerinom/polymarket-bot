"""
run_loop.py — Continuous autoresearch loop for BTC 5-minute markets.

Runs indefinitely:
  1. Fetch the next upcoming 5-min market
  2. Predict with all agents
  3. Wait for it to resolve
  4. Auto-resolve & score
  5. Every EVOLVE_EVERY resolved markets, evolve the worst agent
  6. Repeat

Usage:
    python run_loop.py                # Run the continuous loop
    python run_loop.py --evolve-every 10  # Evolve after every 10 resolved markets
"""

import time
import sqlite3
import signal
import sys
from datetime import datetime, timezone

from fetch_markets import init_db, fetch_active_markets, store_markets, DB_PATH
from predict import run_predictions
from score import calculate_brier_scores, print_scorecard, auto_resolve
from evolve import evolve

EVOLVE_EVERY = 10  # Evolve worst agent every N resolved markets


def get_next_market(db):
    """Get the single next unresolved, un-predicted market closest to resolving."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT id, question, end_date, price_yes
        FROM markets
        WHERE resolved = 0 AND end_date > ?
        ORDER BY end_date ASC
        LIMIT 1
    """, (now,))
    row = cursor.fetchone()
    if row:
        return {"id": row[0], "question": row[1], "end_date": row[2], "price_yes": row[3]}
    return None


def already_predicted(db, market_id):
    """Check if we already have predictions for this market."""
    cursor = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE market_id = ?", (market_id,)
    )
    return cursor.fetchone()[0] > 0


def count_resolved(db):
    """Count total resolved markets."""
    cursor = db.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1")
    return cursor.fetchone()[0]


def wait_for_resolution(end_date_str):
    """Sleep until the market's end time + a small buffer for API to update."""
    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    wait_secs = (end_dt - now).total_seconds()

    if wait_secs > 0:
        print(f"  Waiting {wait_secs:.0f}s for market to close...")
        time.sleep(wait_secs)

    # Extra buffer for Polymarket to mark it resolved
    print(f"  Market closed. Waiting 60s for resolution data...")
    time.sleep(60)


def run_loop(evolve_every=EVOLVE_EVERY):
    """Main continuous loop."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()
    cycle = 1
    last_resolved_count = count_resolved(db)

    print("=" * 60)
    print("BTC 5-MIN AUTORESEARCH LOOP")
    print(f"Evolving worst agent every {evolve_every} resolved markets")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    while True:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        print(f"\n--- Loop iteration at {now_str} (cycle {cycle}) ---")

        # Step 1: Fetch latest markets
        print("[1] Fetching markets...")
        try:
            markets = fetch_active_markets()
            store_markets(db, markets)
            print(f"    {len(markets)} active markets in DB")
        except Exception as e:
            print(f"    Fetch error: {e}")

        # Step 2: Find the next market to predict on
        next_mkt = get_next_market(db)
        if not next_mkt:
            print("[2] No upcoming markets found. Retrying in 2 minutes...")
            time.sleep(120)
            continue

        print(f"[2] Next market: {next_mkt['question'][:60]}")
        print(f"    Resolves: {next_mkt['end_date']}")
        print(f"    Market price (UP): {next_mkt['price_yes']:.1%}")

        # Step 3: Predict if we haven't already
        if already_predicted(db, next_mkt["id"]):
            print("[3] Already predicted on this market, waiting for resolution...")
        else:
            print("[3] Running predictions...")
            db.close()
            try:
                run_predictions(cycle=cycle, market_limit=1)
            except Exception as e:
                print(f"    Prediction error: {e}")
            db = sqlite3.connect(DB_PATH)

        # Step 4: Wait for the market to resolve
        wait_for_resolution(next_mkt["end_date"])

        # Step 5: Auto-resolve and score
        print("[4] Checking resolution...")
        retries = 0
        resolved_this_round = 0
        while retries < 5:
            resolved_this_round = auto_resolve(db)
            if resolved_this_round > 0:
                break
            retries += 1
            print(f"    Not resolved yet, retry {retries}/5 in 30s...")
            time.sleep(30)

        if resolved_this_round > 0:
            print(f"    Resolved {resolved_this_round} market(s)!")
            results = calculate_brier_scores(db)
            print_scorecard(results)
        else:
            print("    Could not resolve market after retries. Moving on.")

        # Step 6: Evolve if we've hit the threshold
        total_resolved = count_resolved(db)
        new_resolved = total_resolved - last_resolved_count
        if new_resolved >= evolve_every:
            print(f"\n[5] {new_resolved} new resolved markets — triggering evolution!")
            db.close()
            try:
                evolve(cycle=cycle)
            except Exception as e:
                print(f"    Evolution error: {e}")
            db = sqlite3.connect(DB_PATH)
            last_resolved_count = total_resolved

        cycle += 1


def signal_handler(sig, frame):
    print("\n\nStopping loop. Goodbye!")
    sys.exit(0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Continuous BTC 5-min autoresearch loop")
    parser.add_argument("--evolve-every", type=int, default=EVOLVE_EVERY,
                        help=f"Evolve worst agent every N resolved markets (default: {EVOLVE_EVERY})")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    run_loop(evolve_every=args.evolve_every)
