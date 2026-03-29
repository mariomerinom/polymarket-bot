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

# Dead hours (UTC) — consistently below 50% WR on 5+ bets each.
# 3 UTC = 9pm CST (41.7% WR, 12 bets), 21 UTC = 3pm CST (37.5% WR, 8 bets)
DEAD_HOURS_UTC = {3, 21}

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def compute_regime_from_candles(candles, autocorr_threshold=-0.15,
                                regime_method="autocorr", hurst_threshold=0.4):
    """
    Compute regime indicators from candle list.
    Returns dict with autocorrelation, volatility, and label.

    autocorr_threshold: below this → mean-reverting (default -0.15 for 5m, -0.20 for 15m)
    regime_method: "autocorr" (default/5m) or "hurst" (15m, validated +3% WR)
    hurst_threshold: below this → mean-reverting when using hurst method (default 0.4)
    """
    closes = [c["close"] for c in candles]

    # Volatility: stdev of returns
    returns = [(closes[i] - closes[i-1]) / closes[i-1]
               for i in range(1, len(closes))]

    if len(returns) < 3:
        return {"autocorrelation": 0.0, "volatility": 0.0, "label": "UNKNOWN",
                "is_mean_reverting": False, "hurst": 0.5}

    import statistics
    import math
    volatility = statistics.stdev(returns) * 100  # as percentage

    # Autocorrelation: lag-1 (always compute for logging)
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

    # Hurst exponent via R/S method (always compute for logging)
    hurst = 0.5
    if n >= 3 and var > 0:
        Y = []
        cumsum = 0
        for r in returns:
            cumsum += (r - mean_r)
            Y.append(cumsum)
        R = max(Y) - min(Y)
        S = (sum((r - mean_r) ** 2 for r in returns) / n) ** 0.5
        if R > 0 and S > 0:
            hurst = math.log(R / S) / math.log(n)

    # Labels
    if volatility < 0.05:
        vol_label = "LOW_VOL"
    elif volatility < 0.12:
        vol_label = "MEDIUM_VOL"
    else:
        vol_label = "HIGH_VOL"

    # Determine mean-reversion based on chosen method
    if regime_method == "hurst":
        is_mean_reverting = hurst < hurst_threshold
        if hurst > 0.6:
            trend_label = "TRENDING"
        elif hurst < hurst_threshold:
            trend_label = "MEAN_REVERTING"
        else:
            trend_label = "NEUTRAL"
    else:
        is_mean_reverting = autocorr < autocorr_threshold
        if autocorr > 0.15:
            trend_label = "TRENDING"
        elif autocorr < autocorr_threshold:
            trend_label = "MEAN_REVERTING"
        else:
            trend_label = "NEUTRAL"

    return {
        "autocorrelation": round(autocorr, 4),
        "volatility": round(volatility, 4),
        "hurst": round(hurst, 4),
        "label": f"{vol_label} / {trend_label}",
        "is_mean_reverting": is_mean_reverting,
    }


def momentum_signal(candles, min_streak=3, min_exhaustion=1):
    """
    Momentum signal: ride BTC streaks when exhaustion confirms continuation.
    1. streak >= min_streak same direction (default 3 for 5m, 2 for 15m)
    2. At least min_exhaustion signals (compression, volume spike, or shrinking range)
    3. RIDE the streak (bet WITH it, not against it)

    min_exhaustion: 1 = any signal (default/5m), 2 = stricter (fewer but better trades)

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

    if abs(signed_streak) < min_streak:
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

    exhaustion_count = sum([compression, volume_spike, shrinking])
    has_exhaustion = exhaustion_count >= min_exhaustion

    if not has_exhaustion:
        return {
            "estimate": 0.5, "should_trade": False,
            "reason": f"no_exhaustion (streak={signed_streak}, signals={exhaustion_count}/{min_exhaustion})",
            "streak": signed_streak,
        }

    # Ride the streak (momentum — inverted from V3 contrarian which lost at 37% WR)
    if signed_streak >= min_streak:
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


def store_prediction(db, market_id, signal, regime, cycle, predicted_at=None,
                     mkt_price=None, loose_mode=False, sibling_context=None,
                     consensus=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    estimate = signal["estimate"]
    edge = abs(estimate - 0.5)
    confidence = signal.get("confidence", "low")

    # PAPER TRADING — tiered conviction scoring, simulated P&L only
    # Conviction tiers (dashboard maps to bet sizes):
    #   0 = skip ($0)    2 = low ($0)    3 = medium ($75)    4 = high ($200)    5 = max ($300)
    #
    # Tiered sizing based on 169-bet analysis (March 2026):
    #   RIDE UP + price 20-70%: 71% WR, +$2,314 P&L → conviction 4 ($200)
    #   All other bets in sweet spot: 61% WR → conviction 3 ($75)
    #   No signal or low confidence: conviction 0 ($0)
    #
    # Cross-exchange consensus (March 2026):
    #   2/2 exchanges agree on streak → conviction bump (+1)
    #   Disagreement → no bump (tracked for analysis)
    if signal["should_trade"] and confidence in ("medium", "high"):
        direction = signal.get("direction", "")
        regime_label = regime.get("label", "") if regime else ""

        # DOWN in NEUTRAL regimes has no edge (52% WR on 25 bets, Mar 2026)
        # Still tracked in DB (conv=2) but no money risked
        # Derived from 5m data — disabled in loose_mode (15m)
        if not loose_mode and direction == "DOWN" and "NEUTRAL" in regime_label:
            conviction = 2
        # RIDE UP in sweet spot → high conviction ($200 bet)
        elif direction == "UP" and mkt_price is not None and 0.20 <= mkt_price <= 0.70:
            conviction = 4
        else:
            conviction = 3

        # Cross-exchange consensus boost: both Kraken + Coinbase see the same streak
        # Bump conviction by 1 (max 5) when score=2 (strong agreement)
        consensus_score = consensus.get("score", 0) if consensus else 0
        if consensus_score == 2 and conviction >= 3:
            conviction = min(conviction + 1, 5)
    elif signal["should_trade"]:
        conviction = 2
    else:
        conviction = 0

    reasoning_data = {
        "signal": signal,
        "regime": regime,
        "observation_mode": True,
        "would_have_bet": signal.get("should_trade", False) and confidence in ("medium", "high"),
        "conviction_tier": conviction,
        "mkt_price": mkt_price,
    }
    if sibling_context:
        reasoning_data["sibling_5m"] = sibling_context
    if consensus:
        reasoning_data["consensus"] = consensus
    reasoning = json.dumps(reasoning_data)

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


def get_5m_context(lookback_minutes=60):
    """
    Query the 5m DB for recent signal activity.
    Returns a summary the 15m pipeline can use for cross-timeframe awareness.
    """
    if not DB_PATH.exists():
        return None

    try:
        db5 = sqlite3.connect(DB_PATH)
        # Recent 5m bets (conv >= 3) in the lookback window
        rows = db5.execute("""
            SELECT estimate, conviction_score
            FROM predictions
            WHERE conviction_score >= 3
              AND predicted_at >= datetime('now', ?)
            ORDER BY predicted_at DESC
        """, (f"-{lookback_minutes} minutes",)).fetchall()
        db5.close()
    except Exception:
        return None

    if not rows:
        return {"bets": 0, "direction": None, "streak": 0, "message": "no recent 5m bets"}

    # Count directions
    up = sum(1 for r in rows if r[0] >= 0.5)
    down = len(rows) - up

    # Consecutive streak from most recent
    streak_dir = "UP" if rows[0][0] >= 0.5 else "DOWN"
    streak = 1
    for r in rows[1:]:
        d = "UP" if r[0] >= 0.5 else "DOWN"
        if d == streak_dir:
            streak += 1
        else:
            break

    majority = "UP" if up > down else ("DOWN" if down > up else "SPLIT")

    return {
        "bets": len(rows),
        "up": up,
        "down": down,
        "majority": majority,
        "streak_direction": streak_dir,
        "streak_length": streak,
        "direction": streak_dir if streak >= 2 else majority,
        "message": f"5m: {len(rows)} bets in last {lookback_minutes}min, "
                   f"{up}UP/{down}DN, streak={streak_dir}×{streak}",
    }


def run_predictions(cycle=1, market_limit=5, btc_data=None, db_path=None,
                    min_streak=3, autocorr_threshold=-0.15, loose_mode=False,
                    regime_method="autocorr", hurst_threshold=0.4,
                    min_exhaustion=1):
    """
    Main prediction loop.
    Fetch candles → compute regime → apply momentum rule → store.
    No API calls. $0 cost.

    db_path: optional override (default: data/predictions.db for 5-min)
    min_streak: minimum consecutive candles for signal (3 for 5m, 2 for 15m)
    autocorr_threshold: below this → mean-reverting skip (-0.15 for 5m, -0.20 for 15m)
    loose_mode: if True, disable 5m-derived gates (dead hours, cooldown, DOWN+NEUTRAL).
                Used by 15m pipeline to gather data without 5m-specific filters.
    regime_method: "autocorr" (default/5m) or "hurst" (15m, validated +3% WR)
    hurst_threshold: below this → mean-reverting when using hurst method (default 0.4)
    """
    from btc_data import fetch_btc_candles, format_for_prompt

    db = sqlite3.connect(db_path or DB_PATH)
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
        consensus = btc_data.get("consensus")
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}%")
        # Log consensus
        if consensus and consensus.get("sources", 0) >= 2:
            k = consensus.get("streak_kraken", {})
            c = consensus.get("streak_coinbase", {})
            score = consensus.get("score", 0)
            label = {2: "STRONG", 1: "WEAK", -1: "DISAGREE"}.get(score, "?")
            print(f"  Consensus: {label} (score={score}) | Kraken: {k.get('direction','?')}x{k.get('length',0)} | Coinbase: {c.get('direction','?')}x{c.get('length',0)}")
        elif consensus:
            print(f"  Consensus: single source only ({consensus.get('sources', 0)}/2)")
        else:
            print(f"  Consensus: unavailable")
    else:
        print("  WARNING: No BTC data available — skipping predictions")
        db.close()
        return

    # Compute regime
    regime = compute_regime_from_candles(candles, autocorr_threshold=autocorr_threshold,
                                        regime_method=regime_method, hurst_threshold=hurst_threshold)
    if regime_method == "hurst":
        print(f"  Regime: {regime['label']} (hurst: {regime['hurst']:.4f}, autocorr: {regime['autocorrelation']:+.4f})")
    else:
        print(f"  Regime: {regime['label']} (autocorr: {regime['autocorrelation']:+.4f}, hurst: {regime.get('hurst', 'N/A')})")

    # Check regime gate
    if regime["is_mean_reverting"]:
        print(f"  SKIP: Mean-reverting regime detected — no trades")

    # Cross-timeframe context: 15m reads what 5m has been seeing
    sibling_context = None
    if loose_mode:
        sibling_context = get_5m_context(lookback_minutes=60)
        if sibling_context and sibling_context["bets"] > 0:
            print(f"  5m sibling: {sibling_context['message']}")
        else:
            print(f"  5m sibling: no recent activity")

    # Compute momentum signal
    signal = momentum_signal(candles, min_streak=min_streak, min_exhaustion=min_exhaustion)
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

        # Time-of-day gate: skip hours with consistently negative WR
        # Derived from 5m data — disabled in loose_mode (15m)
        current_hour_utc = datetime.now(timezone.utc).hour
        if not loose_mode and current_hour_utc in DEAD_HOURS_UTC:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"time_gate_dead_hour (UTC {current_hour_utc})",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (dead hour: UTC {current_hour_utc})")
            continue

        # Price gate: skip extreme prices (terrible risk/reward even when correct)
        # At price 0.95, need 95% WR to break even. Our signal hits ~66%. Math can't work.
        if mkt_price > 0.85 or mkt_price < 0.15:
            skip_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": f"price_gate_extreme ({mkt_price:.0%})",
            }
            store_prediction(db, market["id"], skip_signal, regime, cycle)
            print(f"    → SKIP (price gate: {mkt_price:.0%})")
            continue

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

        # Cooldown gate: if last bet (any market) was opposite direction, require stronger streak
        # Derived from 5m chop analysis — disabled in loose_mode (15m)
        if not loose_mode and signal["should_trade"] and signal.get("direction"):
            last_bet = db.execute('''
                SELECT estimate FROM predictions
                WHERE conviction_score >= 3
                ORDER BY predicted_at DESC LIMIT 1
            ''').fetchone()

            if last_bet:
                last_dir = "UP" if last_bet[0] > 0.5 else "DOWN"
                if last_dir != signal["direction"]:
                    streak_len = abs(signal.get("streak", 0))
                    if streak_len <= min_streak:
                        signal = {
                            "estimate": signal["estimate"],
                            "should_trade": False,
                            "confidence": "skip",
                            "reason": f"cooldown_flip ({last_dir}→{signal['direction']}, streak={streak_len})",
                        }
                        print(f"    → SKIP (cooldown: flip from {last_dir}, streak only {streak_len})")

        # Apply momentum signal
        if signal["should_trade"]:
            store_prediction(db, market["id"], signal, regime, cycle,
                             mkt_price=mkt_price, loose_mode=loose_mode,
                             sibling_context=sibling_context, consensus=consensus)
            direction = "DOWN" if signal["estimate"] < 0.5 else "UP"
            # Determine conviction label for logging
            consensus_score = consensus.get("score", 0) if consensus else 0
            if consensus_score == 2 and direction == "UP" and mkt_price and 0.20 <= mkt_price <= 0.70:
                conv_label = "MAX $300 (consensus+sweet)"
            elif consensus_score == 2:
                conv_label = "HIGH $200 (consensus)" if direction != "UP" or not mkt_price or not (0.20 <= mkt_price <= 0.70) else "HIGH $200"
            elif direction == "UP" and mkt_price and 0.20 <= mkt_price <= 0.70:
                conv_label = "HIGH $200"
            else:
                conv_label = "MED $75"
            # Cross-timeframe confirmation log
            if sibling_context and sibling_context.get("bets", 0) > 0:
                sib_dir = sibling_context.get("direction", "?")
                agrees = sib_dir == direction
                tag = "✓ 5m AGREES" if agrees else "✗ 5m DISAGREES"
                print(f"    → {direction} @ {signal['estimate']:.0%} ({signal['confidence']}, {conv_label}) [{tag}: {sibling_context['message']}]")
            else:
                print(f"    → {direction} @ {signal['estimate']:.0%} ({signal['confidence']}, {conv_label})")
        else:
            # No signal — store as NO_BET
            no_signal = {
                "estimate": mkt_price,
                "should_trade": False,
                "confidence": "skip",
                "reason": signal.get("reason", "no_signal"),
            }
            store_prediction(db, market["id"], no_signal, regime, cycle, sibling_context=sibling_context)
            print(f"    → SKIP ({signal.get('reason', 'no_signal')})")

    db.close()
    print(f"\nDone. Predictions stored in {db_path or DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
