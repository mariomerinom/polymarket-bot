"""
shadow_conviction_scorer.py — Continuous strength signal for conviction scoring.

Computes a strength signal (0.0–1.0) from streak length and price magnitude,
maps it to conviction tiers, and logs alongside production conviction.

Shadow mode only: never modifies production conviction_score or estimates.
Called from ci_run_*.py and trade.py after production logic completes.
Failures are caught — this module must never crash production.
"""

import json
import math
from datetime import datetime, timezone


# ── Asset configs ────────────────────────────────────────────────────────
# BTC 5m values derived from 227+ paper bets. ETH values are placeholders
# until ETH momentum data accumulates. Kalshi mirrors btc_15m.

SHADOW_CONFIGS = {
    "btc_5m": {
        "min_streak": 3,
        "baseline_streak": 8,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],  # edge → tier 2/3/4/5
    },
    "btc_15m": {
        "min_streak": 2,
        "baseline_streak": 5,
        "magnitude_multiplier": 2.5,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
    "eth_5m": {
        # Recalibrated 2026-04-02: max_edge bumped from 0.08 to 0.10 so streak=3
        # clears the 0.05 edge gate in trade.py (was 0.049, now 0.061).
        "min_streak": 3,
        "baseline_streak": 6,
        "magnitude_multiplier": 2.0,
        "max_edge": 0.10,
        "high_confidence_threshold": 0.85,
        "conv_thresholds": [0.03, 0.04, 0.05, 0.07],
    },
    "kalshi": {
        "min_streak": 2,
        "baseline_streak": 5,
        "magnitude_multiplier": 2.5,
        "max_edge": 0.14,
        "high_confidence_threshold": 0.80,
        "conv_thresholds": [0.02, 0.05, 0.08, 0.12],
    },
}

VOL_FLOOR = 0.02  # Prevent division by near-zero volatility


def strength_signal(candles, signed_streak, config_key, regime=None):
    """
    Continuous signal strength from 0.0 (barely qualifies) to 1.0 (max conviction).

    Components:
      length_strength    = min(log(|streak|) / log(baseline_streak), 1.0)
      magnitude_strength = min(|net_return_pct| / (realized_vol × multiplier), 1.0)
      strength           = length_strength × magnitude_strength

    Returns dict with estimate, confidence, strength, and component breakdowns.
    """
    config = SHADOW_CONFIGS.get(config_key)
    if not config or not candles or signed_streak == 0:
        return None

    streak_len = abs(signed_streak)
    direction = "UP" if signed_streak > 0 else "DOWN"

    # Length component: log curve, capped at 1.0
    if streak_len <= 1:
        length_strength = 0.0
    else:
        length_strength = min(
            math.log(streak_len) / math.log(config["baseline_streak"]),
            1.0
        )

    # Magnitude component: net return relative to volatility
    net_return_pct = _net_return(candles, streak_len)
    realized_vol = _realized_vol(candles)
    vol = max(realized_vol, VOL_FLOOR)

    magnitude_strength = min(
        abs(net_return_pct) / (vol * config["magnitude_multiplier"]),
        1.0
    )

    strength = length_strength * magnitude_strength

    # Estimate: 0.50 ± (max_edge × strength)
    edge = config["max_edge"] * strength
    if direction == "UP":
        estimate = 0.50 + edge
    else:
        estimate = 0.50 - edge

    confidence = "high" if strength >= config["high_confidence_threshold"] else "medium"

    return {
        "estimate": round(estimate, 4),
        "confidence": confidence,
        "strength": round(strength, 4),
        "length_strength": round(length_strength, 4),
        "magnitude_strength": round(magnitude_strength, 4),
        "net_return_pct": round(net_return_pct, 4),
        "realized_vol": round(realized_vol, 4),
        "direction": direction,
        "streak_len": streak_len,
        "config_key": config_key,
    }


def conviction_from_estimate(estimate, config_key):
    """
    Map continuous estimate to conviction tier (0, 2, 3, 4, 5).

    tier = highest tier where abs(estimate - 0.50) >= conv_thresholds[tier_index]
    Thresholds map to tiers [2, 3, 4, 5].
    """
    config = SHADOW_CONFIGS.get(config_key)
    if not config:
        return 0

    edge = abs(estimate - 0.50)
    thresholds = config["conv_thresholds"]
    tiers = [2, 3, 4, 5]

    tier = 0
    for i, threshold in enumerate(thresholds):
        if edge >= threshold:
            tier = tiers[i]

    return tier


def shadow_log(db, market_id, candles, signed_streak, config_key, regime,
               production_conviction, production_estimate):
    """
    Compute shadow conviction and return the shadow dict for logging.

    This is the convenience entry point called from ci_run_*.py and trade.py.
    Returns the shadow dict on success, None on failure. Never raises.
    """
    try:
        signal = strength_signal(candles, signed_streak, config_key, regime)
        if not signal:
            return None

        tier = conviction_from_estimate(signal["estimate"], config_key)

        result = {
            "config_key": config_key,
            "strength": signal["strength"],
            "length_strength": signal["length_strength"],
            "magnitude_strength": signal["magnitude_strength"],
            "estimate": signal["estimate"],
            "confidence": signal["confidence"],
            "conviction_tier": tier,
            "production_conviction": production_conviction,
            "production_estimate": production_estimate,
            "net_return_pct": signal["net_return_pct"],
            "realized_vol": signal["realized_vol"],
        }

        # Embed in reasoning JSON of the most recent prediction for this market
        _embed_in_reasoning(db, market_id, result)

        return result
    except Exception:
        return None


def shadow_log_cycle(db, cycle, candles, config_key):
    """
    Compute shadow conviction for all predictions in a cycle.

    Reads predictions from DB, extracts streak from reasoning JSON,
    computes shadow scores, and embeds them. Same pattern as
    shadow_log_indicators() — called from ci_run_*.py after predictions.

    Returns summary string. Never raises.
    """
    try:
        rows = db.execute(
            "SELECT id, market_id, reasoning, conviction_score, estimate "
            "FROM predictions WHERE cycle = ?",
            (cycle,),
        ).fetchall()

        if not rows:
            return None

        updated = 0
        for row in rows:
            pred_id = row[0] if not isinstance(row, dict) else row["id"]
            market_id = row[1] if not isinstance(row, dict) else row["market_id"]
            reasoning_raw = row[2] if not isinstance(row, dict) else row["reasoning"]
            prod_conviction = row[3] if not isinstance(row, dict) else row["conviction_score"]
            prod_estimate = row[4] if not isinstance(row, dict) else row["estimate"]

            # Extract streak from reasoning JSON
            try:
                reasoning = json.loads(reasoning_raw) if reasoning_raw else {}
            except (json.JSONDecodeError, TypeError):
                reasoning = {}

            signal_data = reasoning.get("signal", {})
            signed_streak = signal_data.get("streak", 0)
            if signed_streak == 0:
                continue

            # Compute shadow signal
            signal = strength_signal(candles, signed_streak, config_key)
            if not signal:
                continue

            tier = conviction_from_estimate(signal["estimate"], config_key)

            shadow_data = {
                "config_key": config_key,
                "strength": signal["strength"],
                "length_strength": signal["length_strength"],
                "magnitude_strength": signal["magnitude_strength"],
                "estimate": signal["estimate"],
                "confidence": signal["confidence"],
                "conviction_tier": tier,
                "production_conviction": prod_conviction,
                "production_estimate": prod_estimate,
                "net_return_pct": signal["net_return_pct"],
                "realized_vol": signal["realized_vol"],
            }

            # Embed in reasoning JSON
            reasoning["shadow_generic_scorer"] = shadow_data
            db.execute(
                "UPDATE predictions SET reasoning = ? WHERE id = ?",
                (json.dumps(reasoning), pred_id)
            )
            updated += 1

            print(f"    [shadow] {market_id[:30]} strength={signal['strength']:.2f} "
                  f"tier={tier} (prod={prod_conviction})")

        if updated:
            db.commit()
        return f"{updated} prediction(s) scored"
    except Exception as e:
        print(f"    [shadow] error: {e}")
        return None


def _embed_in_reasoning(db, market_id, shadow_data):
    """Append shadow data to the reasoning JSON of the latest prediction for this market."""
    try:
        row = db.execute(
            "SELECT id, reasoning FROM predictions WHERE market_id = ? ORDER BY id DESC LIMIT 1",
            (market_id,)
        ).fetchone()
        if not row:
            return

        pred_id = row[0] if not isinstance(row, dict) else row["id"]
        reasoning_raw = row[1] if not isinstance(row, dict) else row["reasoning"]

        reasoning = json.loads(reasoning_raw) if reasoning_raw else {}
        reasoning["shadow_generic_scorer"] = shadow_data

        db.execute(
            "UPDATE predictions SET reasoning = ? WHERE id = ?",
            (json.dumps(reasoning), pred_id)
        )
        db.commit()
    except Exception:
        pass  # Shadow must never break production


def _net_return(candles, streak_len):
    """Net return % over the streak period."""
    if not candles or streak_len <= 0:
        return 0.0

    streak_start_idx = len(candles) - streak_len
    if streak_start_idx < 0:
        streak_start_idx = 0

    start_price = candles[streak_start_idx]["open"]
    end_price = candles[-1]["close"]

    if start_price == 0:
        return 0.0

    return (end_price - start_price) / start_price * 100


def _realized_vol(candles):
    """Realized volatility as std dev of candle returns (%)."""
    if len(candles) < 2:
        return VOL_FLOOR

    returns = []
    for i in range(1, len(candles)):
        prev_close = candles[i - 1]["close"]
        if prev_close == 0:
            continue
        ret = (candles[i]["close"] - prev_close) / prev_close * 100
        returns.append(ret)

    if len(returns) < 2:
        return VOL_FLOOR

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return max(variance ** 0.5, VOL_FLOOR)


if __name__ == "__main__":
    # Quick smoke test with synthetic candles
    print("Shadow Conviction Scorer — smoke test")
    base = 84000
    candles = []
    for i in range(12):
        o = base + i * 50
        candles.append({
            "open": o, "high": o + 80, "low": o - 20,
            "close": o + 50, "volume": 1000000
        })

    # 5-candle UP streak
    result = strength_signal(candles, 5, "btc_5m")
    if result:
        print(f"  strength={result['strength']:.3f} estimate={result['estimate']:.4f}")
        print(f"  length={result['length_strength']:.3f} magnitude={result['magnitude_strength']:.3f}")
        tier = conviction_from_estimate(result["estimate"], "btc_5m")
        print(f"  shadow tier={tier}")

    # 3-candle DOWN streak (minimum)
    result_min = strength_signal(candles, -3, "btc_5m")
    if result_min:
        print(f"\n  min streak: strength={result_min['strength']:.3f} tier={conviction_from_estimate(result_min['estimate'], 'btc_5m')}")
