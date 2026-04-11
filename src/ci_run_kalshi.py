from config import DEFAULT_CANDLE_LIMIT
from config import SHADOW_CANDLE_LIMIT
"""
ci_run_kalshi.py — One-shot Kalshi cycle for GitHub Actions.

PARALLEL PIPELINE — does NOT touch ci_run.py (BTC) or ci_run_eth.py (ETH).

Kalshi BTC Signal Transfer Test (Phase 0):
  1. Fetch active Kalshi BTC 15m/1h markets
  2. Auto-resolve settled markets
  3. Predict using regime-filtered MOMENTUM rule (same as BTC production)
  4. Score
  5. Generate static dashboard HTML

Phase 1 — conviction scoring with regime gates (upgraded from Phase 0 on 2026-04-11).
Uses Kraken/Coinbase 15m candles (BTC is BTC regardless of venue).
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from kalshi_markets import (
    init_db_kalshi, fetch_active_kalshi_markets, store_markets_kalshi,
    fetch_kalshi_orderbook, DB_PATH_KALSHI,
)
from kalshi_data import fetch_kalshi_candles
from kalshi_score import auto_resolve_kalshi
from predict import compute_regime_from_candles, momentum_signal
from score import calculate_brier_scores, print_scorecard


from pipeline_utils import get_next_cycle, has_unpredicted_market

# Dead hours gate — EMPTY until calibrated from Kalshi paper trading data.
DEAD_HOURS_UTC = set()


def store_prediction_kalshi(db, market_id, signal, regime, cycle,
                            predicted_at=None, mkt_price=None, kalshi_ob=None):
    """
    Store a Kalshi prediction in the database.

    Phase 1: Conviction scoring with regime gates and streak-based tiers.
    Upgraded from Phase 0 (hardcoded conv=2) on 2026-04-11.
    """
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # Phase 1: conviction scoring (upgraded from Phase 0 hardcoded conv=2).
    # Matches BTC/Bybit filtering logic: streak-based, regime-gated.
    if signal["should_trade"]:
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "") if regime else ""
        # DOWN+NEUTRAL demotion (same as Bybit pipeline)
        if direction == "DOWN" and "NEUTRAL" in regime_label and "HIGH_VOL" not in regime_label:
            conviction = 2  # Logged, not traded
        elif abs(signal.get("streak", 0)) >= 5:
            conviction = 4
        else:
            conviction = 3
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "paper_trading": True,
        "asset": "BTC",
        "venue": "kalshi",
        "signal_type": "momentum",
        "conviction_tier": conviction,
        "mkt_price": mkt_price,
    }
    if kalshi_ob:
        reasoning_data["kalshi_orderbook"] = kalshi_ob
    reasoning = json.dumps(reasoning_data)

    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "momentum_kalshi", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()

    return {
        "id": db.execute("SELECT last_insert_rowid()").fetchone()[0],
        "market_id": market_id,
        "agent": "momentum_kalshi",
        "estimate": estimate,
        "edge": edge,
        "confidence": confidence,
        "conviction_score": conviction,
        "regime": regime["label"],
    }


def main(candle_data=None, indicators=None):
    DB_PATH_KALSHI.parent.mkdir(parents=True, exist_ok=True)
    db = init_db_kalshi()

    from pipeline_control import load_pipeline_config
    cfg = load_pipeline_config("kalshi")
    if cfg["mode"] == "paused":
        print(f"Kalshi pipeline PAUSED: {cfg['notes']}")
        db.close()
        return

    # 1. Fetch Kalshi markets
    print("[1/5] Fetching Kalshi BTC markets...")
    try:
        markets = fetch_active_kalshi_markets()
        store_markets_kalshi(db, markets)
        print(f"  {len(markets)} active Kalshi markets")
    except Exception as e:
        print(f"  Fetch error: {e}")
        markets = []

    # 2. Auto-resolve settled markets
    print("[2/5] Auto-resolving...")
    resolved = auto_resolve_kalshi(db)
    if resolved:
        print(f"  Resolved {resolved} market(s)")

    if not markets and not has_unpredicted_market(db):
        print("No active Kalshi markets. Exiting early.")
        db.close()
        return

    # 3. Predict using momentum rule (15m candles)
    cycle = get_next_cycle(db)
    print(f"[3/5] Predictions — Kalshi momentum (cycle {cycle})...")

    # Fetch first market's ticker for orderbook logging
    first_ticker = markets[0]["id"] if markets else None
    kalshi_data = candle_data  # Use engine-provided data if available
    if kalshi_data is None:
        kalshi_data = fetch_kalshi_candles(interval="15m", limit=DEFAULT_CANDLE_LIMIT, kalshi_ticker=first_ticker)

    if kalshi_data:
        print(f"  BTC: ${kalshi_data['current_price']:,.2f} | 1h: {kalshi_data.get('1h_change_pct',0):+.3f}% | Trend: {kalshi_data.get('trend','?')}")
    else:
        print("  Warning: BTC price data unavailable")

    if has_unpredicted_market(db):
        db.close()
        try:
            _run_predictions(cycle, kalshi_data)
        except Exception as e:
            print(f"  Prediction error: {e}")
        db = sqlite3.connect(DB_PATH_KALSHI)
    else:
        print("  No unpredicted Kalshi markets")

    # Shadow conviction scorer — continuous strength signal
    try:
        from shadow_conviction_scorer import shadow_log_cycle
        if kalshi_data and kalshi_data.get("candles"):
            shadow_log_cycle(db, cycle, kalshi_data["candles"], "kalshi")
    except Exception as e:
        print(f"    [shadow] skipped: {e}")

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
        results = run_integrity_checks(db, pipeline="kalshi", cycle=cycle,
                                        api_ok=kalshi_data is not None,
                                        data_fetched=bool(kalshi_data))
        for r in results:
            if r["status"] != "OK":
                print(f"  [{r['status']}] {r['check_name']}: {r['detail']}")
    except Exception as e:
        print(f"  [INTEGRITY] check failed: {e}")

    db.close()

    print("\nKalshi CI run complete.")


def _run_predictions(cycle, kalshi_data, market_limit=5, min_streak=2,
                     autocorr_threshold=-0.20):
    """
    Fetch candles -> compute regime -> apply momentum rule -> store predictions.
    """
    db = sqlite3.connect(DB_PATH_KALSHI)
    db.row_factory = sqlite3.Row

    if kalshi_data is None:
        kalshi_data = fetch_kalshi_candles(interval="15m", limit=DEFAULT_CANDLE_LIMIT)

    if not kalshi_data:
        print("  WARNING: No BTC data available — skipping predictions")
        db.close()
        return

    candles = kalshi_data["candles"]

    # Compute regime
    regime = compute_regime_from_candles(candles, autocorr_threshold=autocorr_threshold)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Compute momentum signal
    signal = momentum_signal(candles, min_streak=min_streak)
    if signal["should_trade"]:
        print(f"  Signal: RIDE {signal['direction']} (streak={signal['streak']}, conf={signal['confidence']})")
    else:
        print(f"  Signal: NONE ({signal['reason']})")

    # Get markets to predict
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes
        FROM markets WHERE resolved = 0 AND end_date > ?
        AND id NOT IN (SELECT DISTINCT market_id FROM predictions)
        ORDER BY end_date ASC LIMIT ?
    """, (now_iso, market_limit))
    markets = [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row))
               for row in cursor.fetchall()]

    if not markets:
        print("  No unresolved Kalshi markets found.")
        db.close()
        return

    print(f"  Markets: {len(markets)}")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        mkt_price = market["price_yes"]
        print(f"  Mkt price: {mkt_price:.0%}")

        # Dead hours gate
        current_hour_utc = datetime.now(timezone.utc).hour
        if DEAD_HOURS_UTC and current_hour_utc in DEAD_HOURS_UTC:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
            }
            store_prediction_kalshi(db, market["id"], skip_signal, regime, cycle)
            print(f"    -> SKIP (dead hour: UTC {current_hour_utc})")
            continue

        # Price gate: skip extreme prices
        if mkt_price > 0.85 or mkt_price < 0.15:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"price_gate_extreme ({mkt_price:.0%})",
            }
            store_prediction_kalshi(db, market["id"], skip_signal, regime, cycle)
            print(f"    -> SKIP (price gate: {mkt_price:.0%})")
            continue

        # Mean-reverting regime gate
        if regime["is_mean_reverting"]:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": "regime_gate_mean_reverting",
            }
            store_prediction_kalshi(db, market["id"], skip_signal, regime, cycle)
            print(f"    -> SKIP (mean-reverting regime)")
            continue

        # HIGH_VOL non-trending gate (port from Bybit/BTC 5m pipelines)
        if "HIGH_VOL" in regime["label"] and "TRENDING" not in regime["label"]:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": "regime_gate_high_vol_non_trending",
            }
            store_prediction_kalshi(db, market["id"], skip_signal, regime, cycle)
            print(f"    -> SKIP (HIGH_VOL non-trending)")
            continue

        # Fetch Kalshi orderbook for this market (analysis logging)
        kalshi_ob = fetch_kalshi_orderbook(market["id"])

        # Store prediction
        prediction = store_prediction_kalshi(
            db, market["id"], signal, regime, cycle,
            mkt_price=mkt_price, kalshi_ob=kalshi_ob,
        )
        direction = signal.get("direction", "?")
        est = signal["estimate"]
        conv = prediction["conviction_score"]
        print(f"    -> {direction} @ {est:.0%} (conv={conv})")

    db.close()


if __name__ == "__main__":
    main()
