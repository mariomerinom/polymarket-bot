"""
VWAP Mean-Reversion strategy.

Fires in MEAN_REVERTING regimes that momentum skips.
When price deviates >2σ from VWAP, bet on reversion.

Ported from shadow_indicators.py:compute_vwap_zscore().
"""

import statistics

from strategies.base import StrategySignal


# Minimum z-score magnitude to fire
ZSCORE_THRESHOLD = 2.0

# Conviction tiers based on deviation magnitude
ZSCORE_CONV4 = 2.5
ZSCORE_CONV3 = 2.0


def signal(ctx):
    """Generate mean-reversion signal from VWAP deviation."""
    # Only fire in mean-reverting regimes
    if not ctx.regime or not ctx.regime.get("is_mean_reverting", False):
        return None

    if not ctx.candles or len(ctx.candles) < 10:
        return None

    # Compute VWAP
    cum_tpv = 0.0
    cum_vol = 0.0
    for c in ctx.candles:
        typical = (c["high"] + c["low"] + c["close"]) / 3.0
        vol = c.get("volume", 0)
        cum_tpv += typical * vol
        cum_vol += vol

    if cum_vol == 0:
        return None

    vwap = cum_tpv / cum_vol
    current_close = ctx.candles[-1]["close"]
    deviation = current_close - vwap

    # Z-score
    closes = [c["close"] for c in ctx.candles]
    std = statistics.stdev(closes) if len(closes) >= 2 else 0
    if std == 0:
        return None
    zscore = deviation / std

    abs_z = abs(zscore)
    if abs_z < ZSCORE_THRESHOLD:
        return None

    # Direction: price above VWAP → bet DOWN (reversion), below → UP
    if zscore < -ZSCORE_THRESHOLD:
        direction = "UP"
        estimate = 0.55 + min(abs_z - ZSCORE_THRESHOLD, 0.10)
    elif zscore > ZSCORE_THRESHOLD:
        direction = "DOWN"
        estimate = 0.45 - min(abs_z - ZSCORE_THRESHOLD, 0.10)
    else:
        return None

    # Conviction from magnitude
    conviction = 4 if abs_z >= ZSCORE_CONV4 else 3

    return StrategySignal(
        direction=direction,
        estimate=round(estimate, 4),
        conviction=conviction,
        reason=f"vwap_meanrev z={zscore:+.2f} vwap={vwap:.0f} price={current_close:.0f}",
        metadata={
            "vwap": round(vwap, 2),
            "zscore": round(zscore, 4),
            "deviation": round(deviation, 2),
            "regime": ctx.regime.get("label", "") if ctx.regime else "",
        },
    )
