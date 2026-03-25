"""
predict.py — Regime-filtered momentum predictions.

V4: No LLM agents. Pure computation from BTC candle data.
- Fetch 20 candles from Kraken/Coinbase
- Compute regime (volatility + autocorrelation)
- If mean-reverting → skip
- If streak >= 3 + exhaustion → RIDE the streak (momentum)
- Cost: $0/day

History: V3 contrarian (fade) lost at 37% WR on live Polymarket.
Inverting to momentum (ride) validated at 63% WR. Do NOT revert to fade.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def compute_regime_from_candles(candles):
    """
    Compute regime indicators from candle list.
    Returns dict with autocorrelation, volatility, and label.
    """
    closes = [c["close"] for c in candles]

    # Volatility: stdev of 5-min returns
    returns = [(closes[i] - closes[i-1]) / closes[i-1]
               for i in range(1, len(closes))]

    if len(returns) < 3:
        return {"autocorrelation": 0.0, "volatility": 0.0, "label": "UNKNOWN"}

    import statistics
    volatility = statistics.stdev(returns) * 100  # as percentage

    # Autocorrelation: lag-1
    n = len(returns)
    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n
    autocorr = 0.0
    if var > 0:
        cov = sum(
            (returns[i] - mean_r) * (returns[i-1] - mean_r)
            for i in range(1, n)
        ) / (n - 1)
        autocorr = cov / var

    # Labels
    if volatility < 0.05:
        vol_label = "LOW_VOL"
    elif volatility < 0.12:
        vol_label = "MEDIUM_VOL"
    else:
        vol_label = "HIGH_VOL"

    if autocorr > 0.15:
        trend_label = "TRENDING"
    elif autocorr < -0.15:
        trend_label = "MEAN_REVERTING"
    else:
        trend_label = "NEUTRAL"

    return {
        "autocorrelation": round(autocorr, 4),
        "volatility": round(volatility, 4),
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": autocorr < -0.15,
    }


def momentum_signal(candles):
    """
    Momentum signal: ride BTC streaks when exhaustion confirms continuation.
    1. streak >= 3 same direction
    2. At least one exhaustion signal (compression, volume spike, or shrinking range)
    3. RIDE the streak (bet WITH it, not against it)

    History: V3 "contrarian" faded streaks and lost at 37% WR on live Polymarket.
    Inverting to momentum (ride) validated at 63% WR. Do NOT revert to fade.

    Returns dict with estimate, confidence, should_trade, and signal details.
    """
    if len(candles) < 5:
        return {"estimate": 0.5, "should_trade": False, "reason": "insufficient_data"}

    # Count consecutive streak (from most recent candle backward)
    last_dir = "UP" if candles[-1]["close"] >= candles[-1]["open"] else "DOWN"
    streak = 1
    for i in range(len(candles) - 2, -1, -1):
        d = "UP" if candles[i]["close"] >= candles[i]["open"] else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed_streak = streak if last_dir == "UP" else -streak

    if abs(signed_streak) < 3:
        return {
            "estimate": 0.5, "should_trade": False,
            "reason": f"streak_too_short ({signed_streak})",
            "streak": signed_streak,
        }

    # Exhaustion signals
    # 1. Compression: last 3 candle ranges shrinking
    compression = False
    if len(candles) >= 3:
        ranges = [c["high"] - c["low"] for c in candles[-3:]]
        compression = ranges[0] > ranges[1] > ranges[2] and ranges[2] > 0

    # 2. Volume spike: last candle volume > 1.8x average
    volumes = [c["volume"] for c in candles]
    avg_vol = sum(volumes) / len(volumes) if volumes else 1
    vol_ratio = candles[-1]["volume"] / avg_vol if avg_vol > 0 else 1.0
    volume_spike = vol_ratio > 1.8

    # 3. Shrinking range: last candle range < 70% of average
    avg_range = sum(c["high"] - c["low"] for c in candles) / len(candles)
    last_range = candles[-1]["high"] - candles[-1]["low"]
    range_ratio = last_range / avg_range if avg_range > 0 else 1.0
    shrinking = range_ratio < 0.7

    has_exhaustion = compression or volume_spike or shrinking

    if not has_exhaustion:
        return {
            "estimate": 0.5, "should_trade": False,
            "reason": f"no_exhaustion (streak={signed_streak})",
            "streak": signed_streak,
        }

    # Ride the streak (momentum — inverted from V3 contrarian which lost at 37% WR)
    if signed_streak >= 3:
        estimate = 0.62  # streak UP → predict UP (ride it)
        direction = "UP"
    else:
        estimate = 0.38  # streak DOWN → predict DOWN (ride it)
        direction = "DOWN"

    confidence = "medium"
    if abs(signed_streak) >= 5:
        confidence = "high"
    if volume_spike and compression:
        confidence = "high"

    return {
        "estimate": estimate,
        "should_trade": True,
        "direction": direction,
        "confidence": confidence,
        "streak": signed_streak,
        "exhaustion": {
            "compression": compression,
            "volume_spike": volume_spike,
            "vol_ratio": round(vol_ratio, 2),
            "shrinking_range": shrinking,
            "range_ratio": round(range_ratio, 2),
        },
        "reason": f"ride_streak_{direction}",
    }


# Backward compatibility alias — old tests/imports may reference this name
contrarian_signal = momentum_signal


def ensure_regime_column(db):
    """Add regime column to predictions table if it doesn't exist."""
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN regime TEXT")
        db.commit()
    except sqlite3.OperationalError:
        pass  # already exists


def store_prediction(db, market_id, signal, regime, cycle, predicted_at=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # PAPER TRADING — full conviction scoring, simulated P&L only
    if signal["should_trade"] and confidence in ("medium", "high"):
        conviction = 3
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    reasoning = json.dumps({
        "signal": signal,
        "regime": regime,
        "observation_mode": True,
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
    })

    # Store as "momentum_rule" agent
    try:
        db.execute("""
            INSERT INTO predictions
            (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_id, "momentum_rule", estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction, regime["label"],
        ))
    except sqlite3.OperationalError:
        # regime column might not exist yet
        db.execute("""
            INSERT INTO predictions
            (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_id, "momentum_rule", estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction,
        ))
    db.commit()


def run_predictions(cycle=1, market_limit=5, btc_data=None):
    """
    Main prediction loop.
    Fetch candles → compute regime → apply momentum rule → store.
    No API calls. $0 cost.
    """
    from btc_data import fetch_btc_candles, format_for_prompt

    db = sqlite3.connect(DB_PATH)
    ensure_regime_column(db)

    # Ensure conviction_score column exists
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN conviction_score INTEGER")
        db.commit()
    except sqlite3.OperationalError:
        pass

    # Fetch BTC candles
    if btc_data is None:
        btc_data = fetch_btc_candles(limit=20)

    if btc_data:
        candles = btc_data["candles"]
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}%")
    else:
        print("  WARNING: No BTC data available — skipping predictions")
        db.close()
        return

    # Compute regime
    regime = compute_regime_from_candles(candles)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    # Check regime gate
    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Compute momentum signal
    signal = momentum_signal(candles)
    if signal["should_trade"]:
        print(f"  Signal: RIDE {signal['direction']} (streak={signal['streak']}, conf={signal['confidence']})")
        print(f"    Exhaustion: compression={signal['exhaustion']['compression']}, "
              f"vol_spike={signal['exhaustion']['volume_spike']} ({signal['exhaustion']['vol_ratio']:.1f}x), "
              f"shrink={signal['exhaustion']['shrinking_range']} ({signal['exhaustion']['range_ratio']:.2f}x)")
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
        print("  No unresolved markets found.")
        db.close()
        return

    print(f"  Markets: {len(markets)}")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        mkt_price = market['price_yes']
        print(f"  Mkt price: {mkt_price:.0%}")

        # Apply regime gate: if mean-reverting, store as NO_BET (estimate=market price)
        if regime["is_mean_reverting"]:
            skip_signal = {
                "estimate": mkt_price,  # anchor to market
                "should_trade": False,
                "confidence": "skip",
                "reason": "regime_skip_mean_reverting",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (mean-reverting regime)")
            continue

        # Apply momentum signal
        if signal["should_trade"]:
            store_prediction(db, market["id"], signal, regime, cycle)
            direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
            print(f"    → {direction} @ {signal['estimate']:.0%} ({signal['confidence']})")
        else:
            # No signal — store as NO_BET
            no_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": signal.get("reason", "no_signal"),
            }
            store_prediction(db, market["id"], no_signal, regime, cycle)
            print(f"    → SKIP ({signal.get('reason', 'no_signal')})")

    db.close()
    print(f"\nDone. Predictions stored in {DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
