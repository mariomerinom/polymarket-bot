"""
VWAP Mean-Reversion strategy (always-fire mode).

Computes VWAP z-score and predicts reversion. ALWAYS returns a signal
with full indicator snapshot in metadata for parameter optimization.

The post-hoc analysis will determine which z-score ranges and regime
combinations actually have edge — we don't gate with hard thresholds.
"""

import statistics

from strategies.base import StrategySignal, indicator_snapshot


def signal(ctx):
    """Generate mean-reversion signal from VWAP deviation.

    Always fires when data is available. Stores all parameters in
    metadata so we can optimize thresholds post-hoc.
    """
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

    # Direction: price above VWAP → bet DOWN (reversion), below → UP
    direction = "DOWN" if zscore > 0 else "UP"

    # Conviction scales with z-score magnitude (still useful for filtering)
    if abs_z >= 2.5:
        conviction = 4
    elif abs_z >= 2.0:
        conviction = 3
    elif abs_z >= 1.0:
        conviction = 2
    else:
        conviction = 1

    # Estimate: higher deviation → more confident in reversion
    estimate = 0.50 + min(abs_z * 0.03, 0.15)
    if direction == "DOWN":
        estimate = 1.0 - estimate

    # Full indicator snapshot for parameter optimization
    meta = indicator_snapshot(ctx)
    meta.update({
        "vwap": round(vwap, 2),
        "zscore": round(zscore, 4),
        "abs_zscore": round(abs_z, 4),
        "deviation": round(deviation, 2),
        "std": round(std, 2),
        "regime": ctx.regime.get("label", "") if ctx.regime else "",
        "is_mean_reverting": ctx.regime.get("is_mean_reverting", False) if ctx.regime else False,
    })

    return StrategySignal(
        direction=direction,
        estimate=round(estimate, 4),
        conviction=conviction,
        reason=f"vwap_meanrev z={zscore:+.2f} vwap={vwap:.0f} price={current_close:.0f}",
        metadata=meta,
    )
