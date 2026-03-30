"""
ci_run_eth.py — One-shot ETH cycle for GitHub Actions.

PARALLEL PIPELINE — does NOT touch ci_run.py (BTC).

ETH Contrarian Paper Trading:
  1. Fetch active ETH 5-min markets
  2. Predict using regime-filtered CONTRARIAN rule ($0 cost)
  3. Auto-resolve closed markets
  4. Score
  5. Generate static dashboard HTML
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_markets import init_db_eth, fetch_active_markets_eth, store_markets, DB_PATH_ETH
from predict_eth import run_predictions_eth
from score import auto_resolve, calculate_brier_scores, print_scorecard
from eth_data import fetch_eth_candles


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
    DB_PATH_ETH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_eth()

    # 1. Fetch ETH markets
    print("[1/5] Fetching ETH markets...")
    try:
        markets = fetch_active_markets_eth()
        store_markets(db, markets)
        print(f"  {len(markets)} active ETH markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 2. Auto-resolve closed markets
    print("[2/5] Auto-resolving...")
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print("No active ETH markets. Exiting early.")
        db.close()
        _generate_dashboard()
        return

    # 3. Predict using CONTRARIAN rule (no API calls)
    cycle = get_next_cycle(db)
    print(f"[3/5] Predictions — ETH contrarian rule (cycle {cycle})...")
    eth_data = fetch_eth_candles(limit=20)
    if eth_data:
        print(f"  ETH: ${eth_data['current_price']:,.2f} | 1h: {eth_data['1h_change_pct']:+.3f}% | Trend: {eth_data['trend']}")
    else:
        print("  Warning: ETH price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            run_predictions_eth(cycle=cycle, market_limit=1, eth_data=eth_data,
                                db_path=DB_PATH_ETH)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH_ETH)
    else:
        print("  No unpredicted ETH markets")

    # 4. Score
    print("[4/5] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    db.close()

    # 5. Generate dashboard
    print("[5/5] Generating ETH dashboard...")
    _generate_dashboard()

    print("\nETH CI run complete.")


def _generate_dashboard():
    from dashboard import build_html
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    output = docs_dir / "eth.html"
    output.write_text(build_html(
        db_path=DB_PATH_ETH,
        subtitle="ETH 5-minute contrarian (paper trading)"
    ))
    print(f"  ETH dashboard written to {output}")


if __name__ == "__main__":
    main()
