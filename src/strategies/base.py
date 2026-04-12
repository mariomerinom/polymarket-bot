"""
Strategy Lab base types.

Strategies are plain functions with signature:
    def signal(ctx: StrategyContext) -> StrategySignal | None

Returns None when there's no signal this cycle.

The `indicator_snapshot()` helper flattens the nested TA engine dict
into a flat dict suitable for metadata storage and post-hoc analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StrategyContext:
    """Market state passed to every strategy function.

    Built from data already in memory (candle buffer, TA engine output).
    No data is copied — candles and indicators are references.
    """
    symbol: str              # "BTCUSDT"
    timeframe: str           # "5"
    pipeline: str            # "btc_5m" — which production pipeline triggered this
    candles: list            # from candle_buffer (already in memory)
    indicators: dict | None  # from TAEngine (already computed)
    regime: dict | None      # from compute_regime_from_candles
    current_price: float
    timestamp: datetime
    # Optional enrichment (not always available):
    orderbook: dict | None = None
    funding_rate: float | None = None
    consensus: dict | None = None


@dataclass
class StrategySignal:
    """Output from a strategy function."""
    direction: str           # "UP" or "DOWN"
    estimate: float          # 0.0 - 1.0
    conviction: int          # 0-5
    reason: str
    metadata: dict = field(default_factory=dict)


def indicator_snapshot(ctx) -> dict:
    """Flatten the nested TA engine indicators dict into a flat dict.

    Used by always-fire strategies to log ALL indicator values in metadata
    for post-hoc parameter optimization.

    TA engine returns nested structures (bbands: {lower, mid, upper, bandwidth, pctb},
    stoch: {k, d}). This flattens them into bb_lower, bb_mid, bb_upper, bb_bandwidth,
    bb_pctb, stoch_k, stoch_d for easy bucketing/filtering.
    """
    snap = {}
    ind = ctx.indicators

    if not ind:
        ind = {}  # still compute candle-derived and regime features below

    # Flat scalars — copy directly
    for key in ("rsi_14", "rsi_7", "vwap", "obv", "obv_slope",
                "rvol", "z_score", "ema_9", "ema_21"):
        val = ind.get(key)
        if val is not None:
            snap[key] = round(float(val), 6)

    # Bollinger Bands — flatten nested dict
    bb = ind.get("bbands")
    if bb and isinstance(bb, dict):
        for sub_key in ("lower", "mid", "upper", "bandwidth", "pctb"):
            val = bb.get(sub_key)
            if val is not None:
                snap[f"bb_{sub_key}"] = round(float(val), 6)

    # Stochastic — flatten nested dict
    stoch = ind.get("stoch")
    if stoch and isinstance(stoch, dict):
        for sub_key in ("k", "d"):
            val = stoch.get(sub_key)
            if val is not None:
                snap[f"stoch_{sub_key}"] = round(float(val), 6)

    # Regime info
    if ctx.regime:
        snap["regime_label"] = ctx.regime.get("label", "")
        for rkey in ("autocorrelation", "volatility"):
            val = ctx.regime.get(rkey)
            if val is not None:
                snap[f"regime_{rkey}"] = round(float(val), 6)
        snap["is_mean_reverting"] = ctx.regime.get("is_mean_reverting", False)

    # Candle-derived features
    if ctx.candles and len(ctx.candles) >= 2:
        c = ctx.candles[-1]
        snap["candle_body_pct"] = round(abs(c["close"] - c["open"]) / c["open"] * 100, 4) if c["open"] else 0
        snap["candle_range"] = round(abs(c["high"] - c["low"]), 2)
        snap["candle_direction"] = c.get("direction", "UP" if c["close"] >= c["open"] else "DOWN")

        # Streak length
        streak = 0
        last_dir = ctx.candles[-1].get("direction", "")
        for candle in reversed(ctx.candles):
            if candle.get("direction", "") == last_dir:
                streak += 1
            else:
                break
        snap["streak_length"] = streak
        snap["streak_direction"] = last_dir

    # EMA crossover state
    if snap.get("ema_9") and snap.get("ema_21"):
        snap["ema_cross"] = "BULLISH" if snap["ema_9"] > snap["ema_21"] else "BEARISH"

    return snap
