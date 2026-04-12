"""
Candle Snapshot strategy — the wide-net data collector.

ALWAYS fires. Records ALL 19+ TA indicators, regime data, candle features,
and streak info for every cycle. Uses simple momentum (last candle direction)
as the prediction.

Purpose: build the raw dataset for parameter optimization across ALL
strategies. Post-hoc analysis buckets WR by indicator ranges to find
which parameter combinations have edge.

This is NOT a trading strategy — it's a data collection instrument.
"""

from strategies.base import StrategySignal, indicator_snapshot


def signal(ctx):
    """Always-fire snapshot of all market state.

    Prediction = momentum (last candle direction). The prediction is
    secondary — what matters is the METADATA containing all indicators
    for post-hoc optimization.
    """
    if not ctx.candles or len(ctx.candles) < 2:
        return None

    # Simple momentum: predict continuation of last candle
    last_candle = ctx.candles[-1]
    direction = "UP" if last_candle["close"] >= last_candle["open"] else "DOWN"

    # Full indicator snapshot — this is the whole point
    meta = indicator_snapshot(ctx)

    # Add candle OHLCV for backtesting reconstruction
    meta["open"] = last_candle.get("open")
    meta["high"] = last_candle.get("high")
    meta["low"] = last_candle.get("low")
    meta["close"] = last_candle.get("close")
    meta["volume"] = last_candle.get("volume")

    # Price context
    meta["current_price"] = ctx.current_price
    meta["candle_count"] = len(ctx.candles)

    return StrategySignal(
        direction=direction,
        estimate=0.52 if direction == "UP" else 0.48,
        conviction=1,  # always low — this is data collection, not conviction
        reason=f"snapshot {ctx.symbol} {direction}",
        metadata=meta,
    )
