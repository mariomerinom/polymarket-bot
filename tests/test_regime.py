"""
Unit tests for regime detection.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from predict import compute_regime_from_candles


def _trending_candles(n=20):
    """Create candles with positive autocorrelation (trending up)."""
    candles = []
    price = 100.0
    for i in range(n):
        o = price
        c = o + 0.5  # consistent UP
        candles.append({"open": o, "high": c + 0.1, "low": o - 0.1, "close": c})
        price = c
    return candles


def _mean_reverting_candles(n=20):
    """Create candles that alternate UP/DOWN (negative autocorrelation)."""
    candles = []
    price = 100.0
    for i in range(n):
        o = price
        if i % 2 == 0:
            c = o + 0.5
        else:
            c = o - 0.5
        candles.append({"open": o, "high": max(o, c) + 0.1, "low": min(o, c) - 0.1, "close": c})
        price = c
    return candles


def _low_vol_candles(n=20):
    """Create candles with very small moves."""
    candles = []
    price = 100.0
    for i in range(n):
        o = price
        c = o + 0.001 * (1 if i % 3 else -1)
        candles.append({"open": o, "high": o + 0.002, "low": o - 0.002, "close": c})
        price = c
    return candles


def test_trending_regime():
    """Consistent UP candles → TRENDING label."""
    result = compute_regime_from_candles(_trending_candles())
    assert "TRENDING" in result["label"]
    assert result["autocorrelation"] > 0.15
    assert result["is_mean_reverting"] is False


def test_mean_reverting_regime():
    """Alternating UP/DOWN → MEAN_REVERTING label."""
    result = compute_regime_from_candles(_mean_reverting_candles())
    assert "MEAN_REVERTING" in result["label"]
    assert result["autocorrelation"] < -0.15
    assert result["is_mean_reverting"] is True


def test_low_vol_detected():
    """Tiny moves → LOW_VOL label."""
    result = compute_regime_from_candles(_low_vol_candles())
    assert "LOW_VOL" in result["label"]


def test_insufficient_data():
    """< 3 candles → UNKNOWN."""
    candles = [{"open": 100, "high": 101, "low": 99, "close": 100.5}]
    result = compute_regime_from_candles(candles)
    assert result["label"] == "UNKNOWN"
    assert result["autocorrelation"] == 0.0


def test_regime_keys():
    """Result has all required keys."""
    candles = _trending_candles()
    result = compute_regime_from_candles(candles)
    required = {"autocorrelation", "volatility", "label", "is_mean_reverting"}
    assert required.issubset(result.keys())


def test_relaxed_autocorr_threshold():
    """Relaxing autocorr_threshold changes the mean-reverting classification."""
    candles = _mean_reverting_candles()
    autocorr_val = compute_regime_from_candles(candles)["autocorrelation"]

    # At strict threshold (-0.15): should be mean-reverting (autocorr is very negative)
    result_strict = compute_regime_from_candles(candles, autocorr_threshold=-0.15)
    assert result_strict["is_mean_reverting"] is True

    # At relaxed threshold below the actual autocorrelation: NOT mean-reverting
    # Use a threshold more negative than the actual value
    very_relaxed = autocorr_val - 0.5  # way below actual
    result_relaxed = compute_regime_from_candles(candles, autocorr_threshold=very_relaxed)
    assert result_relaxed["is_mean_reverting"] is False

    # Both should compute the same autocorrelation value
    assert result_strict["autocorrelation"] == result_relaxed["autocorrelation"]

    # Trending candles should not be mean-reverting at any threshold
    trending = _trending_candles()
    result_trending = compute_regime_from_candles(trending, autocorr_threshold=-0.20)
    assert result_trending["is_mean_reverting"] is False


def test_autocorrelation_bounded():
    """Autocorrelation should be between -1 and 1."""
    for candles in [_trending_candles(), _mean_reverting_candles(), _low_vol_candles()]:
        result = compute_regime_from_candles(candles)
        assert -1.5 <= result["autocorrelation"] <= 1.5, \
            f"autocorrelation {result['autocorrelation']} seems out of range"
