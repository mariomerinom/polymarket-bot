"""
Volatility Breakout strategy.

Detects Bollinger Band compression (low bandwidth) followed by
an expansion candle (range > 2× average). Fires at candle 1 of
a potential trend, BEFORE momentum (which needs candle 3).
"""

from strategies.base import StrategySignal


# Bollinger bandwidth threshold for "compressed" state
COMPRESSION_THRESHOLD = 2.5

# Expansion: current range must be this multiple of avg range
EXPANSION_MULTIPLIER = 2.0

# Minimum candles needed for avg range calculation
MIN_CANDLES = 20


def signal(ctx):
    """Generate breakout signal from compression → expansion."""
    if not ctx.indicators or not ctx.candles:
        return None

    if len(ctx.candles) < MIN_CANDLES:
        return None

    # Check for compression: low Bollinger bandwidth
    bb_bw = ctx.indicators.get("bb_bandwidth")
    if bb_bw is None:
        return None
    if bb_bw > COMPRESSION_THRESHOLD:
        return None  # Not compressed

    # Check for expansion: current candle range vs average
    candle = ctx.candles[-1]
    current_range = abs(candle["high"] - candle["low"])
    if current_range == 0:
        return None

    avg_range = sum(
        abs(c["high"] - c["low"]) for c in ctx.candles[-MIN_CANDLES:]
    ) / MIN_CANDLES

    if avg_range == 0:
        return None

    expansion_ratio = current_range / avg_range
    if expansion_ratio < EXPANSION_MULTIPLIER:
        return None  # No expansion

    # Direction from breakout candle
    direction = "UP" if candle["close"] > candle["open"] else "DOWN"

    # Conviction: higher expansion = higher conviction
    conviction = 4 if expansion_ratio >= 3.0 else 3

    estimate = 0.58 if direction == "UP" else 0.42

    return StrategySignal(
        direction=direction,
        estimate=estimate,
        conviction=conviction,
        reason=f"vol_breakout bw={bb_bw:.2f} exp={expansion_ratio:.1f}x",
        metadata={
            "bb_bandwidth": round(bb_bw, 4),
            "expansion_ratio": round(expansion_ratio, 2),
            "current_range": round(current_range, 2),
            "avg_range": round(avg_range, 2),
        },
    )
