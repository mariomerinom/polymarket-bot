from config import DEFAULT_CANDLE_LIMIT, SHADOW_CANDLE_LIMIT
"""
ci_run_eth.py — One-shot ETH cycle for GitHub Actions.

PARALLEL PIPELINE — does NOT touch ci_run.py (BTC).

ETH Momentum Trading:
  1. Fetch active ETH 5-min markets
  2. Auto-resolve closed markets
  3. Predict using regime-filtered MOMENTUM rule
  3b. Execute trades (paper or live, controlled by TRADING_ENABLED env var)
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
from trade import execute_trades, is_kill_switched, get_trading_summary, ensure_orders_table


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

    from pipeline_control import load_pipeline_config, is_pipeline_live
    cfg = load_pipeline_config("eth_5m")
    if cfg["mode"] == "paused":
        print(f"ETH 5m pipeline PAUSED: {cfg['notes']}")
        db.close()
        return
    # Override trade.py's TRADING_ENABLED based on pipeline config
    import trade
    trade.TRADING_ENABLED = is_pipeline_live("eth_5m")

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

    # 3. Predict using MOMENTUM rule (no API calls)
    cycle = get_next_cycle(db)
    print(f"[3/5] Predictions — ETH momentum rule (cycle {cycle})...")
    eth_data = fetch_eth_candles(limit=DEFAULT_CANDLE_LIMIT)
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

    # Shadow indicators — log RSI/OBV/VWAP for ETH predictions
    try:
        from shadow_indicators import shadow_log_indicators
        eth_candles_shadow = fetch_eth_candles(limit=SHADOW_CANDLE_LIMIT)
        if eth_candles_shadow and eth_candles_shadow.get("candles"):
            shadow = shadow_log_indicators(db, cycle, candles=eth_candles_shadow["candles"])
            if shadow:
                print(f"    [SHADOW] {shadow.get('summary', 'logged')}")
    except Exception as e:
        print(f"    [SHADOW] skipped: {e}")

    # Shadow conviction scorer — continuous strength signal
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if eth_data and eth_data.get("candles"):
            shadow_log_cycle(db, cycle, eth_data["candles"], "eth_5m")
    except Exception as e:
        print(f"    [shadow] skipped: {e}")

    # 3b. Execute trades
    if is_kill_switched():
        print("[3b/5] Trading KILLED — kill switch active")
    else:
        print(f"[3b/5] Trade execution...")
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
    print("[4/5] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # [INTEGRITY] Per-cycle checks
    try:
        from pipeline_integrity import run_integrity_checks
        results = run_integrity_checks(db, pipeline="eth_5m", cycle=cycle,
                                        api_ok=eth_data is not None,
                                        data_fetched=bool(eth_data))
        for r in results:
            if r["status"] != "OK":
                print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
    except Exception as e:
        print(f"  [INTEGRITY] check failed: {e}")

    db.close()

    # 5. Generate dashboard
    print("[5/5] Generating ETH dashboard...")
    _generate_dashboard()

    print("\nETH CI run complete.")


def _generate_dashboard():
    """No-op — dashboards served dynamically by dashboard_server.py."""
    print("  Dashboard served dynamically — skipping static HTML generation")


if __name__ == "__main__":
    main()
