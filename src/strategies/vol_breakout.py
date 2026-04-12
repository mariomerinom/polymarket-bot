"""
Volatility Breakout strategy (always-fire mode).

Detects Bollinger Band compression followed by expansion candles.
ALWAYS returns a signal with full indicator snapshot for parameter
optimization. Post-hoc analysis determines optimal bandwidth and
expansion thresholds.
"""

from strategies.base import StrategySignal, indicator_snapshot


# Minimum candles needed for avg range calculation
MIN_CANDLES = 20


def signal(ctx):
    """Generate breakout signal — always fires when data available.

    Stores BB bandwidth, expansion ratio, and all indicators in
    metadata for post-hoc parameter sweep.
    """
    if not ctx.candles or len(ctx.candles) < MIN_CANDLES:
        return None

    # Get BB bandwidth from TA engine (nested under bbands dict)
    bb_bw = None
    if ctx.indicators:
        bb = ctx.indicators.get("bbands")
        if bb and isinstance(bb, dict):
            bb_bw = bb.get("bandwidth")

    # Current candle range vs average
    candle = ctx.candles[-1]
    current_range = abs(candle["high"] - candle["low"])

    avg_range = sum(
        abs(c["high"] - c["low"]) for c in ctx.candles[-MIN_CANDLES:]
    ) / MIN_CANDLES

    expansion_ratio = current_range / avg_range if avg_range > 0 else 0

    # Direction from candle
    direction = "UP" if candle["close"] > candle["open"] else "DOWN"

    # Conviction scales with compression + expansion strength
    is_compressed = bb_bw is not None and bb_bw < 3.0
    is_expanding = expansion_ratio >= 2.0

    if is_compressed and is_expanding:
        conviction = 4 if expansion_ratio >= 3.0 else 3
    elif is_compressed or is_expanding:
        conviction = 2
    else:
        conviction = 1

    estimate = 0.55 if direction == "UP" else 0.45

    # Full indicator snapshot for parameter optimization
    meta = indicator_snapshot(ctx)
    meta.update({
        "bb_bandwidth": round(bb_bw, 4) if bb_bw is not None else None,
        "expansion_ratio": round(expansion_ratio, 2),
        "current_range": round(current_range, 2),
        "avg_range": round(avg_range, 2),
        "is_compressed": is_compressed,
        "is_expanding": is_expanding,
    })

    return StrategySignal(
        direction=direction,
        estimate=estimate,
        conviction=conviction,
        reason=f"vol_breakout bw={f'{bb_bw:.2f}' if bb_bw is not None else '?'} exp={expansion_ratio:.1f}x",
        metadata=meta,
    )
