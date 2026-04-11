from config import DEFAULT_CANDLE_LIMIT
from config import SHADOW_CANDLE_LIMIT
"""
ci_run_hl.py — One-shot Hyperliquid cycle.

PARALLEL PIPELINE — does NOT touch any other pipeline files.

Hyperliquid BTCUSDT Perpetual Futures Pipeline:
  1. Sync position status
  2. Auto-resolve expired synthetic markets
  3. Candles (from engine) → regime → momentum signal → create synthetic market
  4. Execute trades (open/close positions)
  5. Shadow conviction scorer
  6. Score
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from hl_markets import (
    init_db_hl, create_synthetic_market, DB_PATH_HL,
    get_open_position,
)
from hl_data import fetch_hl_mark_price, fetch_hl_funding_rate
from hl_score import auto_resolve_hl
from hl_trade import (
    execute_hl_trades, is_hl_kill_switched, get_hl_trading_summary,
    HL_TRADING_ENABLED,
)
from predict import compute_regime_from_candles, momentum_signal
from score import calculate_brier_scores, print_scorecard
from config import HL_MIN_CONVICTION, MAX_CONVICTION
from pipeline_utils import get_next_cycle

# Dead hours gate — EMPTY until calibrated from HL paper trading data.
DEAD_HOURS_UTC = set()


def store_prediction_hl(db, market_id, signal, regime, cycle,
                        predicted_at=None, mark_price=None,
                        funding_rate=None, consensus=None):
    """Store a Hyperliquid prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # Conviction: matches BTC/Bybit filtering logic
    if signal["should_trade"]:
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "")
        # DOWN+NEUTRAL demotion
        if direction == "DOWN" and "NEUTRAL" in regime_label and "HIGH_VOL" not in regime_label:
            conviction = 2
        elif abs(signal.get("streak", 0)) >= 5:
            conviction = 4
        else:
            conviction = 3
    else:
        conviction = 0

    # Perps-vs-spot consensus boost (if available from engine data)
    consensus_score = consensus.get("score", 0) if consensus else 0
    if consensus_score == 2 and conviction >= 3:
        conviction = min(conviction + 1, MAX_CONVICTION)

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "asset": "BTC",
        "venue": "hyperliquid",
        "instrument": "BTC_perp",
        "signal_type": "momentum",
        "conviction_tier": conviction,
        "mark_price": mark_price,
    }
    if funding_rate:
        reasoning_data["funding_rate"] = funding_rate
    if consensus:
        reasoning_data["consensus"] = consensus
    reasoning = json.dumps(reasoning_data)

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning,
         predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "momentum_hl", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()

    return {
        "id": db.execute("SELECT last_insert_rowid()").fetchone()[0],
        "market_id": market_id,
        "agent": "momentum_hl",
        "estimate": estimate,
        "edge": edge,
        "confidence": confidence,
        "conviction_score": conviction,
        "regime": regime["label"],
    }


def main(candle_data=None, indicators=None):
    DB_PATH_HL.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_hl()

    from pipeline_control import load_pipeline_config, is_pipeline_live
    cfg = load_pipeline_config("hl")
    if cfg["mode"] == "paused":
        print(f"HL pipeline PAUSED: {cfg['notes']}")
        db.close()
        return
    # Override hl_trade.py's HL_TRADING_ENABLED based on pipeline config
    import hl_trade
    hl_trade.HL_TRADING_ENABLED = is_pipeline_live("hl")

    mode_label = "LIVE" if HL_TRADING_ENABLED else "PAPER"
    print(f"=== Hyperliquid BTC Perps ({mode_label}) ===\n")

    # [1/6] Sync position status
    print("[1/6] Syncing position status...")
    pos = get_open_position(db)
    if pos:
        print(f"  Open position: {pos['side']} {pos['size']} BTC "
              f"@ ${pos['entry_price']:,.2f} (held {pos['cycles_held']} cycles)")
    else:
        print("  No open position")

    # [2/6] Auto-resolve expired synthetic markets
    print("[2/6] Auto-resolving synthetic markets...")
    resolved = auto_resolve_hl(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    # [3/6] Candles → regime → signal → synthetic market
    cycle = get_next_cycle(db)
    print(f"[3/6] Predictions — HL momentum (cycle {cycle})...")

    # Use engine-provided candle data (piggybacking on Bybit spot WS)
    hl_data = candle_data
    if hl_data is None:
        # Fallback: fetch directly from Bybit API
        from bybit_data import fetch_bybit_candles
        hl_data = fetch_bybit_candles(interval="5", limit=DEFAULT_CANDLE_LIMIT)

    if not hl_data:
        print("  WARNING: No BTC data available — skipping cycle")
        db.close()
        return

    candles = hl_data["candles"]
    current_price = hl_data["current_price"]
    consensus = hl_data.get("consensus")
    print(f"  BTC: ${current_price:,.2f} | "
          f"1h: {hl_data.get('1h_change_pct',0):+.3f}% | "
          f"Trend: {hl_data.get('trend','?')}")

    # Fetch HL mark price for accurate order placement
    hl_mark_price = fetch_hl_mark_price()
    if hl_mark_price:
        print(f"  HL mark: ${hl_mark_price:,.2f} "
              f"(delta: ${hl_mark_price - current_price:+.2f})")
    else:
        hl_mark_price = current_price  # Fallback to Bybit price

    # Create synthetic market
    market_id = create_synthetic_market(db, current_price)

    # Compute regime
    regime = compute_regime_from_candles(candles)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    # Fetch funding rate for logging
    funding_rate_data = fetch_hl_funding_rate()
    funding_rate = funding_rate_data["rate"] if isinstance(funding_rate_data, dict) else 0.0

    # Gates
    prediction = None
    current_hour_utc = datetime.now(timezone.utc).hour

    if DEAD_HOURS_UTC and current_hour_utc in DEAD_HOURS_UTC:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
        }
        store_prediction_hl(db, market_id, skip_signal, regime, cycle,
                            mark_price=hl_mark_price, consensus=consensus)
        print(f"  -> SKIP (dead hour: UTC {current_hour_utc})")

    elif "HIGH_VOL" in regime["label"] and "TRENDING" not in regime["label"]:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": "regime_gate_high_vol_non_trending",
        }
        store_prediction_hl(db, market_id, skip_signal, regime, cycle,
                            mark_price=hl_mark_price, consensus=consensus)
        print(f"  -> SKIP (HIGH_VOL non-trending)")

    elif regime["is_mean_reverting"]:
        skip_signal = {
            "estimate": 0.5, "should_trade": False, "confidence": "skip",
            "reason": "regime_gate_mean_reverting",
        }
        store_prediction_hl(db, market_id, skip_signal, regime, cycle,
                            mark_price=hl_mark_price, consensus=consensus)
        print(f"  -> SKIP (mean-reverting regime)")

    else:
        signal = momentum_signal(candles, min_streak=3, config_key="hl_5m")
        if signal["should_trade"]:
            print(f"  Signal: RIDE {signal['direction']} "
                  f"(streak={signal['streak']}, conf={signal['confidence']})")
        else:
            print(f"  Signal: NONE ({signal['reason']})")

        prediction = store_prediction_hl(
            db, market_id, signal, regime, cycle,
            mark_price=hl_mark_price, funding_rate=funding_rate_data,
            consensus=consensus,
        )

        direction = signal.get("direction", "?")
        est = signal["estimate"]
        conv = prediction["conviction_score"]
        print(f"  -> {direction} @ {est:.0%} (conv={conv})")

    # [4/6] Execute trades
    print(f"[4/6] Trade execution...")

    if is_hl_kill_switched():
        print("  KILL SWITCH ACTIVE — skipping trades")
    else:
        orders = execute_hl_trades(db, cycle, candles, prediction,
                                   funding_rate=funding_rate or 0.0)
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

    # [5/6] Shadow conviction scorer
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if candles:
            shadow_log_cycle(db, cycle, candles, "hl_5m")
    except Exception as e:
        print(f"  [shadow] skipped: {e}")

    # [6/6] Score
    print("[6/6] Scoring...")
    results = calculate_brier_scores(db)
    if results:
        print_scorecard(results)
    else:
        print("  No resolved markets to score yet")

    # Trading summary
    summary = get_hl_trading_summary(db)
    print(f"\n  Today: {summary['positions_opened']} opened, "
          f"{summary['positions_closed']} closed, "
          f"PnL=${summary['total_pnl']:.2f} ({summary['mode']})")

    # [INTEGRITY] Per-cycle checks
    try:
        from pipeline_integrity import run_integrity_checks
        results = run_integrity_checks(db, pipeline="hl", cycle=cycle,
                                        api_ok=hl_data is not None,
                                        data_fetched=bool(hl_data))
        for r in results:
            if r["status"] != "OK":
                print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
    except Exception as e:
        print(f"  [INTEGRITY] check failed: {e}")

    db.close()

    print("\nHL CI run complete.")


if __name__ == "__main__":
    main()
