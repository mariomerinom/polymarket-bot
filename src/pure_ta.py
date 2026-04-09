"""
pure_ta.py — Pure numpy/stdlib technical indicator computation.

Mirrors the output of ta_engine.py without requiring pandas-ta or pandas.
Used for local development and testing where pandas-ta is unavailable.

All formulas match pandas-ta defaults (Wilder's RSI, EMA multiplier, etc.).
"""
from __future__ import annotations

import numpy as np

MIN_CANDLES = 21  # max(EMA 21, SMA 20, RSI 14 warmup)


def compute_ta(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float],
) -> dict | None:
    """Compute TA indicators from OHLCV arrays using only numpy/stdlib.

    Returns None if insufficient data (< 21 bars for warmup).
    """
    if len(closes) < MIN_CANDLES:
        return None

    c = np.asarray(closes, dtype=np.float64)
    h = np.asarray(highs, dtype=np.float64)
    lo = np.asarray(lows, dtype=np.float64)
    v = np.asarray(volumes, dtype=np.float64)

    # --- RSI (Wilder's smoothed) ---
    rsi_14 = _rsi(c, 14)
    rsi_7 = _rsi(c, 7)

    # --- Bollinger Bands (SMA 20, 2 std) ---
    sma_20 = _sma(c, 20)
    std_20 = _rolling_std(c, 20)

    if sma_20 is not None and std_20 is not None and std_20 > 0:
        bb_upper = sma_20 + 2.0 * std_20
        bb_lower = sma_20 - 2.0 * std_20
        bb_mid = sma_20
        bb_bandwidth = (bb_upper - bb_lower) / bb_mid if bb_mid != 0 else 0.0
        bb_pctb = (c[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) != 0 else 0.5
    else:
        bb_bandwidth = 0.0
        bb_pctb = 0.5

    # --- Z-Score ---
    if sma_20 is not None and std_20 is not None and std_20 > 0:
        z_score = round((c[-1] - sma_20) / std_20, 4)
    else:
        z_score = 0.0

    # --- RVOL (relative volume) ---
    vol_mean_20 = _sma(v, 20)
    if v[-1] is not None and vol_mean_20 is not None and vol_mean_20 > 0:
        rvol = round(float(v[-1]) / vol_mean_20, 4)
    else:
        rvol = 1.0

    # --- OBV + slope ---
    obv = _obv(c, v)
    obv_slope = _obv_slope(obv)

    # --- EMA ratio ---
    ema_9 = _ema(c, 9)
    ema_21 = _ema(c, 21)
    if ema_9 is not None and ema_21 is not None and ema_21 != 0:
        ema_ratio = round(ema_9 / ema_21, 6)
    else:
        ema_ratio = 1.0

    # --- Stochastic Oscillator (5, 3, 3) ---
    stoch_k, stoch_d = _stochastic(h, lo, c, k_period=5, d_period=3, smooth_k=3)

    return {
        "rsi_14": _round_or_none(rsi_14, 6),
        "rsi_7": _round_or_none(rsi_7, 6),
        "bb_bandwidth": _round_or_none(bb_bandwidth, 6),
        "bb_pctb": _round_or_none(bb_pctb, 6),
        "z_score": z_score,
        "rvol": rvol,
        "obv_slope": _round_or_none(obv_slope, 6),
        "ema_ratio": ema_ratio,
        "stoch_k": _round_or_none(stoch_k, 6),
        "stoch_d": _round_or_none(stoch_d, 6),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _round_or_none(val, decimals: int = 6):
    """Round a value, returning None if input is None or NaN."""
    if val is None:
        return None
    if np.isnan(val) or np.isinf(val):
        return None
    return round(float(val), decimals)


def _sma(arr: np.ndarray, period: int) -> float | None:
    """Simple moving average of last `period` values."""
    if len(arr) < period:
        return None
    return float(np.mean(arr[-period:]))


def _rolling_std(arr: np.ndarray, period: int) -> float | None:
    """Population-corrected rolling std of last `period` values (ddof=1 like pandas)."""
    if len(arr) < period:
        return None
    return float(np.std(arr[-period:], ddof=1))


def _ema(arr: np.ndarray, period: int) -> float | None:
    """Exponential moving average matching pandas-ta default (adjust=False).

    Uses the recursive formula: EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
    Seed: first value of the array.
    """
    if len(arr) < period:
        return None
    alpha = 2.0 / (period + 1)
    ema = float(arr[0])
    for i in range(1, len(arr)):
        ema = alpha * float(arr[i]) + (1.0 - alpha) * ema
    return ema


def _rsi(arr: np.ndarray, period: int) -> float | None:
    """Wilder's smoothed RSI matching pandas-ta rsi().

    Uses Wilder's smoothing (equivalent to EMA with alpha = 1/period).
    """
    if len(arr) < period + 1:
        return None

    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Seed: SMA of first `period` changes
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Wilder's smoothing for remaining
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """On-Balance Volume."""
    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def _obv_slope(obv: np.ndarray) -> float | None:
    """Linear regression slope of last 5 OBV values."""
    valid = obv[~np.isnan(obv)]
    if len(valid) < 5:
        return None
    last5 = valid[-5:]
    try:
        return float(np.polyfit(range(5), last5, 1)[0])
    except (np.linalg.LinAlgError, ValueError):
        return 0.0


def _stochastic(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    k_period: int = 5,
    d_period: int = 3,
    smooth_k: int = 3,
) -> tuple[float | None, float | None]:
    """Stochastic Oscillator (%K, %D) matching pandas-ta stoch(k=5, d=3, smooth_k=3).

    Fast %K = (close - lowest_low_k) / (highest_high_k - lowest_low_k) * 100
    %K (slow) = SMA(fast %K, smooth_k)
    %D = SMA(%K, d_period)
    """
    n = len(closes)
    needed = k_period + smooth_k + d_period - 2
    if n < needed:
        return None, None

    # Compute raw (fast) %K for each bar
    fast_k = np.full(n, np.nan)
    for i in range(k_period - 1, n):
        hh = np.max(highs[i - k_period + 1 : i + 1])
        ll = np.min(lows[i - k_period + 1 : i + 1])
        if hh - ll == 0:
            fast_k[i] = 50.0  # midpoint when range is zero
        else:
            fast_k[i] = (closes[i] - ll) / (hh - ll) * 100.0

    # Slow %K = SMA(fast_k, smooth_k)
    slow_k = _rolling_sma_array(fast_k, smooth_k)

    # %D = SMA(slow_k, d_period)
    stoch_d = _rolling_sma_array(slow_k, d_period)

    last_k = _last_valid(slow_k)
    last_d = _last_valid(stoch_d)

    return last_k, last_d


def _rolling_sma_array(arr: np.ndarray, period: int) -> np.ndarray:
    """Compute rolling SMA over a numpy array, skipping NaNs at the start."""
    n = len(arr)
    result = np.full(n, np.nan)
    for i in range(n):
        # Find the window of valid values ending at i
        start = max(0, i - period + 1)
        window = arr[start : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) == period:
            result[i] = np.mean(valid)
    return result


def _last_valid(arr: np.ndarray) -> float | None:
    """Return the last non-NaN value from a numpy array."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return None
    return float(valid[-1])
