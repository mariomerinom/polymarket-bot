from config import DEFAULT_CANDLE_LIMIT
from config import SHADOW_CANDLE_LIMIT
"""
ci_run.py — One-shot cycle for GitHub Actions.

V4→V5: Pure computation + trade execution.
  1. Fetch active BTC 5-min markets
  2. Predict using regime-filtered momentum rule ($0 cost)
  3. Execute trades (paper or live, controlled by TRADING_ENABLED env var)
  4. Auto-resolve closed markets
  5. Score
  6. Generate static dashboard HTML
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_markets import init_db, fetch_active_markets, store_markets, DB_PATH
from predict import run_predictions
from score import auto_resolve, calculate_brier_scores, print_scorecard
from btc_data import fetch_btc_candles
import trade
from trade import execute_trades, is_kill_switched, get_trading_summary, ensure_orders_table
from pipeline_control import is_pipeline_live


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


def main(candle_data=None, indicators=None):
    # Override trade.py's TRADING_ENABLED based on pipeline config
    # (env var may be stale from module import-time caching)
    trade.TRADING_ENABLED = is_pipeline_live("btc_5m")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_db()

    # 1. Fetch markets
    print("[1/6] Fetching markets...")
    try:
        markets = fetch_active_markets()
        store_markets(db, markets)
        print(f"  {len(markets)} active markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 2. Auto-resolve closed markets
    print("[2/6] Auto-resolving...")
    resolved = auto_resolve(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print("No active markets. Exiting early.")
        db.close()
        _generate_dashboard()
        return

    # 3. Predict using momentum rule (no API calls)
    cycle = get_next_cycle(db)
    print(f"[3/6] Predictions — momentum rule (cycle {cycle})...")
    btc_data = candle_data  # Use engine-provided data if available
    if btc_data is None:
        btc_data = fetch_btc_candles(limit=DEFAULT_CANDLE_LIMIT)
    if btc_data:
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data.get('1h_change_pct',0):+.3f}% | Trend: {btc_data.get('trend','?')}")
    else:
        print("  Warning: BTC price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            run_predictions(cycle=cycle, market_limit=1, btc_data=btc_data,
                            indicators=indicators)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH)
    else:
        print("  No unpredicted markets")

    # 3b. Execute trades
    if is_kill_switched():
        print("[3b/6] Trading KILLED — kill switch active")
    else:
        print(f"[3b/6] Trade execution...")
        try:
            ensure_orders_table(db)
            orders = execute_trades(db, cycle)
            summary = get_trading_summary(db)
            print(f"  Mode: {summary['mode']} | Bet size: ${summary['bet_size']:.0f} | "
                  f"Today: {summary['total_orders']} orders, ${summary['total_wagered']:.0f} wagered, "
                  f"${summary['total_pnl']:+.0f} P&L")
        except Exception as e:
            print(f"  Trade execution error: {e}")

    # 4. Score
    print("[4/6] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # [INTEGRITY] Per-cycle checks
    try:
        from pipeline_integrity import run_integrity_checks
        results = run_integrity_checks(db, pipeline="btc_5m", cycle=cycle,
                                        api_ok=btc_data is not None)
        if results:
            print(f"  Integrity: {results}")
    except Exception as e:
        print(f"  Integrity check error: {e}")

    db.close()

    # 5. Generate dashboard
    print("[5/6] Generating dashboard...")
    _generate_dashboard()

    print("\nCI run complete.")


def _generate_dashboard():
    from generate_dashboard import generate
    generate()


if __name__ == "__main__":
    main()
