from config import DEFAULT_CANDLE_LIMIT
"""
ci_run_15m.py — One-shot cycle for 15-minute BTC markets.

Uses 5m candles as atomic signal source (higher resolution streak
detection), with 5m predictions as confirmation signal. Isolated DB
and dashboard — if this crashes, the 5-min pipeline is unaffected.
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

    from pipeline_control import load_pipeline_config
    cfg = load_pipeline_config("btc_15m")
    if cfg["mode"] == "paused":
        print(f"BTC 15m pipeline PAUSED: {cfg['notes']}")
        db.close()
        return

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

    # 3. Predict using momentum rule with 5m candles (atomic unit)
    cycle = get_next_cycle(db)
    print(f"[15M 3/5] Predictions — momentum rule 5m→15m (cycle {cycle})...")
    btc_data = fetch_btc_candles(limit=DEFAULT_CANDLE_LIMIT)  # 5m candles — atomic unit
    if btc_data:
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}% | Trend: {btc_data['trend']}")
    else:
        print("  Warning: BTC price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            # Uses 5m candles with standard thresholds (min_streak=3, autocorr=-0.15)
            # loose_mode=True: disable dead hours, enable 5m sibling confirmation
            run_predictions(cycle=cycle, market_limit=1, btc_data=btc_data,
                            db_path=str(DB_PATH_15M),
                            loose_mode=True)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH_15M)

        # DOWN+NEUTRAL has no edge on 15m (48% WR on 27 bets, Apr 2026).
        # Demote post-prediction. Symmetric with 5m.
        # HIGH_VOL/NEUTRAL+DOWN allowed through (64% WR on 50 bets on 5m).
        demoted = db.execute("""
            UPDATE predictions SET conviction_score = 2
            WHERE cycle = ? AND conviction_score >= 3
            AND regime LIKE '%NEUTRAL%'
            AND regime NOT LIKE 'HIGH_VOL%'
            AND json_extract(reasoning, '$.signal.direction') = 'DOWN'
        """, (cycle,)).rowcount
        db.commit()
        if demoted:
            print(f"  [15m] Demoted {demoted} DOWN+MEDIUM_VOL/NEUTRAL prediction(s) to conv=2")
    else:
        print("  No unpredicted markets")

    # Shadow indicators — log RSI/OBV/VWAP for BTC 15m predictions
    try:
        from shadow_indicators import shadow_log_indicators
        btc_15m_shadow = fetch_btc_candles(limit=SHADOW_CANDLE_LIMIT)  # 5m candles
        if btc_15m_shadow and btc_15m_shadow.get("candles"):
            shadow = shadow_log_indicators(db, cycle, candles=btc_15m_shadow["candles"])
            if shadow:
                print(f"    [SHADOW] {shadow.get('summary', 'logged')}")
    except Exception as e:
        print(f"    [SHADOW] skipped: {e}")

    # Shadow conviction scorer — continuous strength signal
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if btc_data and btc_data.get("candles"):
            shadow_log_cycle(db, cycle, btc_data["candles"], "btc_15m")
    except Exception as e:
        print(f"    [shadow] skipped: {e}")

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
        subtitle="BTC 15-Minute Momentum"
    ))
    print(f"  Dashboard written to {output}")


if __name__ == "__main__":
    main()
