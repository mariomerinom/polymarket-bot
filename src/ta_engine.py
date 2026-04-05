"""
ta_engine.py — Local technical indicator computation from candle buffer.

Uses pandas-ta to compute all indicators from in-memory OHLCV data.
No external API calls. Sub-millisecond latency.

Called by botsy_engine.py on every candle close. The resulting indicators
dict is passed through the pipeline to predict().
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta

from candle_buffer import CandleBuffer


class TAEngine:
    """Compute indicators from the candle buffer using pandas-ta."""

    # Minimum candles needed for all indicators to be valid
    MIN_CANDLES = 21  # max(EMA 21, SMA 20, RSI 14 warmup)

    def __init__(self, buffer: CandleBuffer):
        self.buffer = buffer

    def compute(self, symbol: str, timeframe: str) -> dict | None:
        """Compute all indicators for a (symbol, timeframe) pair.

        Returns dict of indicators, or None if insufficient data.
        """
        candles = self.buffer.get_candles(symbol, timeframe)
        if len(candles) < self.MIN_CANDLES:
            return None

        df = pd.DataFrame(candles)
        # Ensure numeric types
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # VWAP needs a DatetimeIndex; deduplicate to avoid reindex errors
        if "timestamp_ms" in df.columns:
            df = df.drop_duplicates(subset="timestamp_ms", keep="last")
            df.index = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
            df = df.sort_index()

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # --- Core Indicators ---

        rsi_14 = ta.rsi(close, length=14)
        rsi_7 = ta.rsi(close, length=7)
        bbands = ta.bbands(close, length=20, std=2)
        vwap = ta.vwap(high, low, close, volume)
        obv = ta.obv(close, volume)
        stoch = ta.stoch(high, low, close, k=5, d=3)

        # EMA ribbon
        ema_9 = ta.ema(close, length=9)
        ema_21 = ta.ema(close, length=21)

        # SMA + StdDev for Z-Score and Bollinger
        sma_20 = ta.sma(close, length=20)
        stdev_20 = ta.stdev(close, length=20)

        # Volume mean for RVOL
        vol_mean_20 = volume.rolling(20).mean()

        # OBV slope (linear regression over last 5 OBV values)
        obv_slope = None
        if obv is not None and len(obv.dropna()) >= 5:
            obv_last5 = obv.dropna().iloc[-5:].values
            try:
                obv_slope = float(np.polyfit(range(5), obv_last5, 1)[0])
            except (np.linalg.LinAlgError, ValueError):
                obv_slope = 0.0

        # --- Build result dict (latest values) ---

        result = {}

        # RSI
        result["rsi_14"] = _last(rsi_14)
        result["rsi_7"] = _last(rsi_7)

        # Bollinger Bands
        if bbands is not None and not bbands.empty:
            bb_row = bbands.iloc[-1]
            result["bbands"] = {
                "lower": _safe(bb_row.get("BBL_20_2.0")),
                "mid": _safe(bb_row.get("BBM_20_2.0")),
                "upper": _safe(bb_row.get("BBU_20_2.0")),
                "bandwidth": _safe(bb_row.get("BBB_20_2.0")),
                "pctb": _safe(bb_row.get("BBP_20_2.0")),
            }
        else:
            result["bbands"] = None

        # VWAP
        result["vwap"] = _last(vwap)

        # OBV + slope
        result["obv"] = _last(obv)
        result["obv_slope"] = obv_slope

        # Stochastic
        if stoch is not None and not stoch.empty:
            stoch_row = stoch.iloc[-1]
            result["stoch"] = {
                "k": _safe(stoch_row.get("STOCHk_5_3_3")),
                "d": _safe(stoch_row.get("STOCHd_5_3_3")),
            }
        else:
            result["stoch"] = None

        # RVOL — relative volume vs 20-period mean
        last_vol = _last(volume)
        mean_vol = _last(vol_mean_20)
        if last_vol is not None and mean_vol and mean_vol > 0:
            result["rvol"] = round(last_vol / mean_vol, 4)
        else:
            result["rvol"] = 1.0

        # Z-Score — distance from 20-SMA in standard deviations
        last_close = _last(close)
        last_sma = _last(sma_20)
        last_std = _last(stdev_20)
        if (last_close is not None and last_sma is not None
                and last_std is not None and last_std > 0):
            result["z_score"] = round((last_close - last_sma) / last_std, 4)
        else:
            result["z_score"] = 0.0

        # EMA ribbon
        result["ema_9"] = _last(ema_9)
        result["ema_21"] = _last(ema_21)

        # Meta
        result["candle_count"] = len(candles)
        result["symbol"] = symbol
        result["timeframe"] = timeframe

        return result


def _last(series) -> float | None:
    """Get the last non-NaN value from a pandas Series."""
    if series is None:
        return None
    try:
        val = series.dropna().iloc[-1]
        return round(float(val), 6) if pd.notna(val) else None
    except (IndexError, TypeError):
        return None


def _safe(val) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return round(float(val), 6)
    except (TypeError, ValueError):
        return None
