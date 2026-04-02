"""
ci_run_bybit.py — One-shot Bybit cycle for GitHub Actions.

PARALLEL PIPELINE — does NOT touch ci_run.py (BTC), ci_run_eth.py (ETH),
or ci_run_kalshi.py (Kalshi).

Bybit BTCUSDT Perpetual Futures Pipeline:
  1. Sync position status (catch stop-loss triggers)
  2. Auto-resolve expired synthetic markets
  3. Fetch candles → regime → momentum signal → create synthetic market
  4. Execute trades (open/close positions)
  5. Shadow conviction scorer
  6. Score
  7. Generate dashboard
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from bybit_markets import (
    init_db_bybit, create_synthetic_market, DB_PATH_BYBIT,
    get_open_position,
)
from bybit_data import fetch_bybit_candles, fetch_bybit_funding_rate
from bybit_score import auto_resolve_bybit
from bybit_trade import (
    execute_bybit_trades, is_bybit_kill_switched, get_bybit_trading_summary,
    BYBIT_TRADING_ENABLED,
)
from predict import compute_regime_from_candles, momentum_signal
from score import calculate_brier_scores, print_scorecard
from config import BYBIT_MIN_CONVICTION

# Dead hours gate — EMPTY until calibrated from Bybit trading data.
DEAD_HOURS_UTC = set()


def get_next_cycle(db):
    """Derive cycle number from the highest cycle recorded."""
    cursor = db.execute("SELECT COALESCE(MAX(cycle), 0) + 1 FROM predictions")
    return cursor.fetchone()[0]


def store_prediction_bybit(db, market_id, signal, regime, cycle,
                           predicted_at=None, mark_price=None,
                           funding_rate=None):
    """Store a Bybit prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # Conviction: use signal's should_trade + shadow scorer
    if signal["should_trade"]:
        conviction = 3  # Default tradeable conviction
        streak = abs(signal.get("streak", 0))
        if streak >= 5:
            conviction = 4
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "asset": "BTC",
        "venue": "bybit",
        "instrument": "BTCUSDT_perp",
        "signal_type": "momentum",
        "conviction_tier": conviction,
        "mark_price": mark_price,
    }
    if funding_rate:
        reasoning_data["funding_rate"] = funding_rate
    reasoning = json.dumps(reasoning_data)

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning,
         predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "momentum_bybit", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()

    return {
        "id": db.execute("SELECT last_insert_rowid()").fetchone()[0],
        "market_id": market_id,
        "agent": "momentum_bybit",
        "estimate": estimate,
        "edge": edge,
        "confidence": confidence,
        "conviction_score": conviction,
        "regime": regime["label"],
    }


def main():
    DB_PATH_BYBIT.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_bybit()

    mode_label = "LIVE" if BYBIT_TRADING_ENABLED else "PAPER"
    print(f"=== Bybit BTCUSDT Perps ({mode_label}) ===\n")

    # [1/7] Sync position status (stop-loss check)
    print("[1/7] Syncing position status...")
    pos = get_open_position(db)
    if pos:
        print(f"  Open position: {pos['side']} {pos['size']} BTC "
              f"@ ${pos['entry_price']:,.2f} (held {pos['cycles_held']} cycles)")
    else:
        print("  No open position")

    # [2/7] Auto-resolve expired synthetic markets
    print("[2/7] Auto-resolving synthetic markets...")
    resolved = auto_resolve_bybit(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    # [3/7] Fetch candles → regime → signal → synthetic market
    cycle = get_next_cycle(db)
    print(f"[3/7] Predictions — Bybit momentum (cycle {cycle})...")

    bybit_data = fetch_bybit_candles(interval="5", limit=20)

    if not bybit_data:
        print("  WARNING: No BTC data available — skipping cycle")
        db.close()
        _generate_dashboard()
        return

    candles = bybit_data["candles"]
    current_price = bybit_data["current_price"]
    print(f"  BTC: ${current_price:,.2f} | "
          f"1h: {bybit_data['1h_change_pct']:+.3f}% | "
          f"Trend: {bybit_data['trend']}")

    # Create synthetic market for this cycle
    market_id = create_synthetic_market(db, current_price)

    # Compute regime
    regime = compute_regime_from_candles(candles)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    # Fetch funding rate for logging
    funding_rate = fetch_bybit_funding_rate()

    # Gates
    prediction = None
    current_hour_utc = datetime.now(timezone.utc).hour

    if DEAD_HOURS_UTC and current_hour_utc in DEAD_HOURS_UTC:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
        }
        store_prediction_bybit(db, market_id, skip_signal, regime, cycle,
                               mark_price=current_price)
        print(f"  -> SKIP (dead hour: UTC {current_hour_utc})")

    elif regime["is_mean_reverting"]:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": "regime_gate_mean_reverting",
        }
        store_prediction_bybit(db, market_id, skip_signal, regime, cycle,
                               mark_price=current_price)
        print(f"  -> SKIP (mean-reverting regime)")

    else:
        # Compute momentum signal
        signal = momentum_signal(candles, min_streak=3, config_key="bybit_5m")
        if signal["should_trade"]:
            print(f"  Signal: RIDE {signal['direction']} "
                  f"(streak={signal['streak']}, conf={signal['confidence']})")
        else:
            print(f"  Signal: NONE ({signal['reason']})")

        prediction = store_prediction_bybit(
            db, market_id, signal, regime, cycle,
            mark_price=current_price, funding_rate=funding_rate,
        )

        direction = signal.get("direction", "?")
        est = signal["estimate"]
        conv = prediction["conviction_score"]
        print(f"  -> {direction} @ {est:.0%} (conv={conv})")

    # [4/7] Execute trades
    print(f"[4/7] Trade execution...")

    if is_bybit_kill_switched():
        print("  KILL SWITCH ACTIVE — skipping trades")
    else:
        orders = execute_bybit_trades(db, cycle, candles, prediction)
        if orders:
            for o in orders:
                action = o.get("action", "?")
                if action == "open":
                    print(f"  Opened {o.get('direction', '?')} position")
                elif action == "close":
                    print(f"  Closed position: {o.get('reason', '?')} "
                          f"(PnL=${o.get('pnl', 0):.2f})")
        else:
            print("  No trade action this cycle")

    # [5/7] Shadow conviction scorer
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if candles:
            shadow_log_cycle(db, cycle, candles, "bybit_5m")
    except Exception as e:
        print(f"  [shadow] skipped: {e}")

    # [6/7] Score
    print("[6/7] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # Trading summary
    summary = get_bybit_trading_summary(db)
    print(f"\n  Today: {summary['positions_opened']} opened, "
          f"{summary['positions_closed']} closed, "
          f"PnL=${summary['total_pnl']:.2f} ({summary['mode']})")

    db.close()

    # [7/7] Generate dashboard
    print("[7/7] Generating Bybit dashboard...")
    _generate_dashboard()

    print("\nBybit CI run complete.")


def _generate_dashboard():
    from dashboard import build_html
    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    output = docs_dir / "bybit-perps.html"
    output.write_text(build_html(
        db_path=DB_PATH_BYBIT,
        subtitle="Bybit BTCUSDT Perps"
    ))
    print(f"  Dashboard written to {output}")


if __name__ == "__main__":
    main()
