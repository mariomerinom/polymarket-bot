"""
ci_run_15m.py — One-shot cycle for 15-minute BTC markets.

Fully isolated from 5-min pipeline:
- Separate DB: data/predictions_15m.db
- Separate dashboard: docs/15m.html
- Same signal logic (momentum_signal, regime filter)

If this crashes, the 5-min pipeline is unaffected.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_markets import init_db_15m, fetch_active_markets_15m, store_markets, DB_PATH_15M
from predict import run_predictions
from score import auto_resolve, calculate_brier_scores, print_scorecard
from btc_data import fetch_btc_candles


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
    DB_PATH_15M.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_15m()

    # 1. Fetch 15-min markets
    print("[15M 1/5] Fetching 15-min markets...")
    try:
        markets = fetch_active_markets_15m()
        store_markets(db, markets)
        print(f"  {len(markets)} active 15-min markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 2. Auto-resolve closed markets
    print("[15M 2/5] Auto-resolving...")
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print("No active 15-min markets. Exiting early.")
        db.close()
        _generate_dashboard()
        return

    # 3. Predict using momentum rule with 15-min candles
    cycle = get_next_cycle(db)
    print(f"[15M 3/5] Predictions — momentum rule 15m (cycle {cycle})...")
    btc_data = fetch_btc_candles(interval="15m", limit=20)
    if btc_data:
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}% | Trend: {btc_data['trend']}")
    else:
        print("  Warning: BTC price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            # 15m thresholds: streak ≥ 2 (30 min ≈ 5m streak ≥ 3), relaxed regime gate
            # loose_mode=True: disable 5m-derived gates (dead hours, cooldown,
            # DOWN+NEUTRAL filter) to gather data for 15m-specific optimization
            run_predictions(cycle=cycle, market_limit=1, btc_data=btc_data,
                            db_path=str(DB_PATH_15M),
                            min_streak=2, autocorr_threshold=-0.20,
                            loose_mode=True)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH_15M)
    else:
        print("  No unpredicted markets")

    # 4. Score
    print("[15M 4/5] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    db.close()

    # 5. Generate 15-min dashboard
    print("[15M 5/5] Generating 15-min dashboard...")
    _generate_dashboard()

    print("\n15-min CI run complete.")


def _generate_dashboard():
    from dashboard import build_html
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    output = docs_dir / "15m.html"
    output.write_text(build_html(
        db_path=str(DB_PATH_15M),
        subtitle="BTC 15-minute candle prediction"
    ))
    print(f"  Dashboard written to {output}")


if __name__ == "__main__":
    main()
