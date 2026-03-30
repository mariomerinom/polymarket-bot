"""
predict_eth.py — Regime-filtered CONTRARIAN predictions for ETH.

PARALLEL PIPELINE — does NOT touch predict.py (BTC momentum).

ETH uses the OPPOSITE signal direction from BTC:
- BTC: streak UP + exhaustion → predict UP (ride/momentum). Validated 63% WR.
- ETH: streak UP + exhaustion → predict DOWN (fade/contrarian). Validated 54.4% WR on 1,601 markets.

Phase 2 pattern mining (scripts/pattern_mining.py) proved ETH is contrarian:
- contrarian_s3_RF: 54.4% WR on 1,601 bets
- momentum_s3_RF: 45.6% WR on 1,601 bets (inverse)
- Best regimes: LOW_VOL/NEUTRAL (72.5%), MEDIUM_VOL/TRENDING (60.2%)

PAPER TRADING ONLY — all predictions at conviction 2 (no money risked)
until 200+ resolved predictions validate the signal on live Polymarket.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Import regime computation from BTC predict (generic, asset-agnostic)
from predict import compute_regime_from_candles

# ETH-specific dead hours — EMPTY until calibrated from ETH paper trading data.
# BTC uses {3, 21} UTC but those are BTC-specific. ETH may differ.
DEAD_HOURS_UTC = set()

DB_PATH_ETH = Path(__file__).parent.parent / "data" / "predictions_eth.db"


def contrarian_signal_eth(candles, min_streak=3):
    """
    Contrarian signal for ETH: FADE streaks when exhaustion confirms trend fatigue.
    1. streak >= min_streak same direction (default 3)
    2. At least one exhaustion signal (compression, volume spike, or shrinking range)
    3. FADE the streak (bet AGAINST it)

    Validated on 1,601 resolved Polymarket ETH markets at 54.4% WR.
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

    if abs(signed_streak) < min_streak:
        return {
            "estimate": 0.5, "should_trade": False,
            "reason": f"streak_too_short ({signed_streak})",
            "streak": signed_streak,
        }

    # Exhaustion signals (identical logic to BTC — these are asset-agnostic)
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

    # FADE the streak (contrarian — opposite of BTC's momentum)
    if signed_streak >= min_streak:
        # Streak is UP → predict DOWN (fade it)
        estimate = 0.38
        direction = "DOWN"
    else:
        # Streak is DOWN → predict UP (fade it)
        estimate = 0.62
        direction = "UP"

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
        "reason": f"fade_streak_{direction}",
    }


def ensure_schema(db):
    """Create tables if they don't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            regime TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)
    db.commit()


def store_prediction_eth(db, market_id, signal, regime, cycle, predicted_at=None,
                         mkt_price=None, consensus=None, liquidity=None):
    """Store an ETH prediction in the database.

    PAPER TRADING: All predictions stored at conviction 2 (no money).
    After 200+ resolved predictions, calibrate conviction tiers from ETH data.
    """
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # PAPER TRADING — conviction 2 for all bets (no real money)
    # After 200+ resolved predictions, we'll calibrate ETH-specific tiers.
    if signal["should_trade"] and confidence in ("medium", "high"):
        conviction = 2  # Paper trade only — no money risked
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "paper_trading": True,
        "asset": "ETH",
        "signal_type": "contrarian",
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
        "conviction_tier": conviction,
        "mkt_price": mkt_price,
    }
    if consensus:
        reasoning_data["consensus"] = consensus
    if liquidity:
        reasoning_data["liquidity"] = liquidity
    reasoning = json.dumps(reasoning_data)

    # Store as "contrarian_eth" agent (distinct from BTC's "momentum_rule")
    db.execute("""
        INSERT INTO predictions
        (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, "contrarian_eth", estimate, edge, confidence,
        reasoning, predicted_at, cycle, conviction, regime["label"],
    ))
    db.commit()


def run_predictions_eth(cycle=1, market_limit=1, eth_data=None, db_path=None,
                        min_streak=3, autocorr_threshold=-0.15):
    """
    Main ETH prediction loop.
    Fetch candles → compute regime → apply CONTRARIAN rule → store.
    No API calls. $0 cost.
    """
    from eth_data import fetch_eth_candles

    db = sqlite3.connect(db_path or DB_PATH_ETH)
    ensure_schema(db)

    # Fetch ETH candles
    if eth_data is None:
        eth_data = fetch_eth_candles(limit=20)

    if eth_data:
        candles = eth_data["candles"]
        consensus = eth_data.get("consensus")
        print(f"  ETH: ${eth_data['current_price']:,.2f} | 1h: {eth_data['1h_change_pct']:+.3f}%")
    else:
        print("  WARNING: No ETH data available — skipping predictions")
        db.close()
        return

    # Compute regime (same generic function as BTC)
    regime = compute_regime_from_candles(candles, autocorr_threshold=autocorr_threshold)
    print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f})")

    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Compute CONTRARIAN signal (opposite of BTC's momentum)
    signal = contrarian_signal_eth(candles, min_streak=min_streak)
    if signal["should_trade"]:
        print(f"  Signal: FADE {signal['direction']} (streak={signal['streak']}, conf={signal['confidence']})")
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
        print("  No unresolved ETH markets found.")
        db.close()
        return

    print(f"  Markets: {len(markets)}")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        mkt_price = market['price_yes']
        print(f"  Mkt price: {mkt_price:.0%}")

        # Dead hours gate (empty for now — will be calibrated from ETH data)
        current_hour_utc = datetime.now(timezone.utc).hour
        if DEAD_HOURS_UTC and current_hour_utc in DEAD_HOURS_UTC:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
            }
            store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (dead hour: UTC {current_hour_utc})")
            continue

        # Price gate: skip extreme prices
        if mkt_price > 0.85 or mkt_price < 0.15:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"price_gate_extreme ({mkt_price:.0%})",
            }
            store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (price gate: {mkt_price:.0%})")
            continue

        # Regime gate
        if regime["is_mean_reverting"]:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": "regime_skip_mean_reverting",
            }
            store_prediction_eth(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (mean-reverting regime)")
            continue

        # Apply contrarian signal
        if signal["should_trade"]:
            # CLOB depth query (read-only, never blocks)
            liquidity = None
            try:
                from clob_depth import get_liquidity_summary, format_liquidity_log
                clob_tokens = _get_clob_tokens(market["id"])
                if clob_tokens:
                    direction_for_clob = "UP" if signal["estimate"] > 0.5 else "DOWN"
                    liquidity = get_liquidity_summary(
                        clob_tokens["yes"], clob_tokens["no"], direction_for_clob
                    )
                    print(f"    {format_liquidity_log(liquidity)}")
            except Exception as e:
                print(f"    [CLOB] skipped: {e}")

            store_prediction_eth(db, market["id"], signal, regime, cycle,
                                 mkt_price=mkt_price, consensus=consensus,
                                 liquidity=liquidity)
            direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
            print(f"    → FADE {direction} @ {signal['estimate']:.0%} ({signal['confidence']}, PAPER conv=2)")
        else:
            no_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": signal.get("reason", "no_signal"),
            }
            store_prediction_eth(db, market["id"], no_signal, regime, cycle)
            print(f"    → SKIP ({signal.get('reason', 'no_signal')})")

    db.close()
    print(f"\nDone. ETH predictions stored in {db_path or DB_PATH_ETH}")


def _get_clob_tokens(market_id):
    """Look up CLOB token IDs for a Polymarket market."""
    try:
        import requests
        resp = requests.get(
            f"https://gamma-api.polymarket.com/markets/{market_id}",
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        raw_clob = data.get("clobTokenIds", "[]")
        if isinstance(raw_clob, str):
            import json as _json
            clob_ids = _json.loads(raw_clob)
        else:
            clob_ids = raw_clob
        if len(clob_ids) >= 2:
            return {"yes": clob_ids[0], "no": clob_ids[1]}
    except Exception:
        pass
    return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions_eth(cycle=args.cycle, market_limit=args.markets)
