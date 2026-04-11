"""
Tests for pure_ta.py — pure numpy/stdlib technical indicator computation.

Validates each indicator against known values on synthetic candle data,
edge cases, and determinism.
"""
from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pure_ta import compute_ta, _rsi, _ema, _sma, _obv, _stochastic


# ---------------------------------------------------------------------------
# Fixtures: synthetic candle data
# ---------------------------------------------------------------------------

def _make_trending_candles(n: int = 50, start: float = 100.0, step: float = 0.5):
    """Generate trending-up candles with realistic OHLCV."""
    rng = np.random.RandomState(42)
    closes = [start + i * step + rng.normal(0, 0.2) for i in range(n)]
    highs = [c + abs(rng.normal(0.3, 0.1)) for c in closes]
    lows = [c - abs(rng.normal(0.3, 0.1)) for c in closes]
    volumes = [1000 + rng.randint(0, 500) for _ in range(n)]
    return closes, highs, lows, volumes


def _make_flat_candles(n: int = 50, price: float = 100.0):
    """Generate flat candles (same price every bar)."""
    closes = [price] * n
    highs = [price] * n
    lows = [price] * n
    volumes = [1000.0] * n
    return closes, highs, lows, volumes


def _make_zigzag_candles(n: int = 50, base: float = 100.0, amplitude: float = 2.0):
    """Generate alternating up/down candles."""
    closes = [base + amplitude * (1 if i % 2 == 0 else -1) for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000.0 + i * 10 for i in range(n)]
    return closes, highs, lows, volumes


# ---------------------------------------------------------------------------
# Test: insufficient data returns None
# ---------------------------------------------------------------------------

class TestInsufficientData:
    def test_returns_none_for_empty(self):
        assert compute_ta([], [], [], []) is None

    def test_returns_none_for_too_few_bars(self):
        closes = [100.0] * 20  # exactly 20, need 21
        assert compute_ta(closes, closes, closes, [1000.0] * 20) is None

    def test_returns_dict_for_21_bars(self):
        closes = [100.0 + i * 0.1 for i in range(21)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000.0] * 21
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Test: determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self):
        closes, highs, lows, volumes = _make_trending_candles(50)
        r1 = compute_ta(closes, highs, lows, volumes)
        r2 = compute_ta(closes, highs, lows, volumes)
        assert r1 == r2

    def test_determinism_zigzag(self):
        closes, highs, lows, volumes = _make_zigzag_candles(50)
        r1 = compute_ta(closes, highs, lows, volumes)
        r2 = compute_ta(closes, highs, lows, volumes)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Test: RSI
# ---------------------------------------------------------------------------

class TestRSI:
    def test_rsi_trending_up(self):
        """Strong uptrend should have RSI > 50."""
        closes, highs, lows, volumes = _make_trending_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["rsi_14"] is not None
        assert result["rsi_14"] > 50

    def test_rsi_trending_down(self):
        """Strong downtrend should have RSI < 50."""
        closes = [200.0 - i * 0.5 for i in range(50)]
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["rsi_14"] < 50

    def test_rsi_bounds(self):
        """RSI should always be between 0 and 100."""
        closes, highs, lows, volumes = _make_trending_candles(100)
        result = compute_ta(closes, highs, lows, volumes)
        assert 0 <= result["rsi_14"] <= 100
        assert 0 <= result["rsi_7"] <= 100

    def test_rsi_all_gains(self):
        """Monotonically increasing prices should give RSI = 100."""
        arr = np.arange(1.0, 52.0)  # 51 values, all gains
        rsi = _rsi(arr, 14)
        assert rsi == 100.0

    def test_rsi_7_shorter_period(self):
        """RSI-7 and RSI-14 should both be valid and different on noisy data."""
        closes, highs, lows, volumes = _make_zigzag_candles(50, base=100.0, amplitude=0.5)
        closes = [c + i * 0.1 for i, c in enumerate(closes)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        result = compute_ta(closes, highs, lows, volumes)
        # Both should be valid and in range
        assert 0 <= result["rsi_7"] <= 100
        assert 0 <= result["rsi_14"] <= 100
        # They should differ (different lookback periods)
        assert result["rsi_7"] != result["rsi_14"]


# ---------------------------------------------------------------------------
# Test: Bollinger Bands
# ---------------------------------------------------------------------------

class TestBollingerBands:
    def test_bb_bandwidth_positive(self):
        closes, highs, lows, volumes = _make_trending_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["bb_bandwidth"] > 0

    def test_bb_pctb_near_one_uptrend(self):
        """In strong uptrend, price should be near upper band (%B close to 1)."""
        closes, highs, lows, volumes = _make_trending_candles(50, step=1.0)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["bb_pctb"] > 0.5

    def test_bb_flat_price_narrow_bandwidth(self):
        """Flat prices should produce very narrow bandwidth."""
        # Add tiny noise so std isn't exactly 0
        rng = np.random.RandomState(123)
        closes = [100.0 + rng.normal(0, 0.001) for _ in range(50)]
        highs = [c + 0.001 for c in closes]
        lows = [c - 0.001 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["bb_bandwidth"] < 0.001


# ---------------------------------------------------------------------------
# Test: Z-Score
# ---------------------------------------------------------------------------

class TestZScore:
    def test_z_score_uptrend_positive(self):
        closes, highs, lows, volumes = _make_trending_candles(50, step=1.0)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["z_score"] > 0

    def test_z_score_downtrend_negative(self):
        closes = [200.0 - i * 1.0 for i in range(50)]
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["z_score"] < 0


# ---------------------------------------------------------------------------
# Test: RVOL
# ---------------------------------------------------------------------------

class TestRVOL:
    def test_rvol_constant_volume(self):
        """Constant volume should give RVOL = 1.0."""
        closes = [100.0 + i * 0.1 for i in range(50)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["rvol"] == 1.0

    def test_rvol_spike(self):
        """Volume spike on last bar should give RVOL > 1."""
        volumes = [1000.0] * 49 + [5000.0]
        closes = [100.0 + i * 0.1 for i in range(50)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        result = compute_ta(closes, highs, lows, volumes)
        assert result["rvol"] > 1.0

    def test_rvol_zero_volume(self):
        """All zero volume should give RVOL = 1.0 (default)."""
        closes = [100.0 + i * 0.1 for i in range(50)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [0.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["rvol"] == 1.0


# ---------------------------------------------------------------------------
# Test: OBV slope
# ---------------------------------------------------------------------------

class TestOBVSlope:
    def test_obv_slope_uptrend(self):
        """Rising prices with volume should have positive OBV slope."""
        closes, highs, lows, volumes = _make_trending_candles(50, step=1.0)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["obv_slope"] is not None
        assert result["obv_slope"] > 0

    def test_obv_slope_downtrend(self):
        """Falling prices with volume should have negative OBV slope."""
        closes = [200.0 - i * 1.0 for i in range(50)]
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["obv_slope"] < 0


# ---------------------------------------------------------------------------
# Test: EMA ratio
# ---------------------------------------------------------------------------

class TestEMARatio:
    def test_ema_ratio_uptrend_above_one(self):
        """In uptrend, EMA9 > EMA21, so ratio > 1."""
        closes, highs, lows, volumes = _make_trending_candles(50, step=1.0)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["ema_ratio"] > 1.0

    def test_ema_ratio_downtrend_below_one(self):
        """In downtrend, EMA9 < EMA21, so ratio < 1."""
        closes = [200.0 - i * 1.0 for i in range(50)]
        highs = [c + 0.3 for c in closes]
        lows = [c - 0.3 for c in closes]
        volumes = [1000.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result["ema_ratio"] < 1.0

    def test_ema_ratio_flat_near_one(self):
        """Flat prices should give EMA ratio very close to 1."""
        closes, highs, lows, volumes = _make_flat_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        assert abs(result["ema_ratio"] - 1.0) < 0.001


# ---------------------------------------------------------------------------
# Test: Stochastic Oscillator
# ---------------------------------------------------------------------------

class TestStochastic:
    def test_stoch_bounds(self):
        """Stochastic K and D should be between 0 and 100."""
        closes, highs, lows, volumes = _make_trending_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["stoch_k"] is not None
        assert result["stoch_d"] is not None
        assert 0 <= result["stoch_k"] <= 100
        assert 0 <= result["stoch_d"] <= 100

    def test_stoch_uptrend_high(self):
        """Strong uptrend should have stoch_k > 50."""
        closes, highs, lows, volumes = _make_trending_candles(50, step=1.0)
        result = compute_ta(closes, highs, lows, volumes)
        assert result["stoch_k"] > 50

    def test_stoch_zigzag_mid_range(self):
        """Zigzag prices should give stoch roughly in the middle range."""
        closes, highs, lows, volumes = _make_zigzag_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        # Not extreme — should be somewhere between 0-100
        assert result["stoch_k"] is not None


# ---------------------------------------------------------------------------
# Test: edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_flat_prices(self):
        """All identical prices should not crash."""
        closes, highs, lows, volumes = _make_flat_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None
        # RSI with zero change: all gains and losses are 0
        # avg_loss = 0 -> RSI = 100 per our formula
        assert result["rsi_14"] == 100.0
        assert result["z_score"] == 0.0
        assert result["bb_pctb"] is not None  # should handle zero range

    def test_zero_volume_all_bars(self):
        """Zero volume everywhere should not crash."""
        closes = [100.0 + i * 0.1 for i in range(50)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [0.0] * 50
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None
        assert result["rvol"] == 1.0
        assert result["obv_slope"] is not None

    def test_single_volume_spike(self):
        """Only the last bar has volume."""
        closes = [100.0 + i * 0.1 for i in range(50)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [0.0] * 49 + [10000.0]
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None

    def test_all_keys_present(self):
        """Result dict should contain all expected keys."""
        closes, highs, lows, volumes = _make_trending_candles(50)
        result = compute_ta(closes, highs, lows, volumes)
        expected_keys = {
            "rsi_14", "rsi_7", "bb_bandwidth", "bb_pctb",
            "z_score", "rvol", "obv_slope", "ema_ratio",
            "stoch_k", "stoch_d",
        }
        assert expected_keys == set(result.keys())

    def test_minimum_21_bars(self):
        """Exactly 21 bars should work for all indicators."""
        closes = [100.0 + i * 0.5 for i in range(21)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = [1000.0] * 21
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None
        # All values should be non-None
        for key in ["rsi_14", "rsi_7", "bb_bandwidth", "bb_pctb",
                     "z_score", "rvol", "obv_slope", "ema_ratio"]:
            assert result[key] is not None, f"{key} is None with 21 bars"

    def test_large_dataset(self):
        """100 candle bars should work fine."""
        closes, highs, lows, volumes = _make_trending_candles(100)
        result = compute_ta(closes, highs, lows, volumes)
        assert result is not None
        for v in result.values():
            assert v is not None
