"""Tests for ta_engine.py — local indicator computation from candle buffer."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("numpy")

from candle_buffer import CandleBuffer
from ta_engine import TAEngine


def _seed_buffer(buf, symbol="BTCUSDT", tf="5", count=30, base_price=67000.0):
    """Helper: seed buffer with synthetic candles."""
    import random
    random.seed(42)  # reproducible
    price = base_price
    for i in range(count):
        change = random.uniform(-200, 200)
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + random.uniform(0, 100)
        low_p = min(open_p, close_p) - random.uniform(0, 100)
        vol = random.uniform(5, 50)
        buf.on_kline_event(symbol, tf, {
            "start": str(1775410500000 + i * 300000),
            "end": str(1775410500000 + (i + 1) * 300000 - 1),
            "open": str(round(open_p, 2)),
            "high": str(round(high_p, 2)),
            "low": str(round(low_p, 2)),
            "close": str(round(close_p, 2)),
            "volume": str(round(vol, 2)),
            "confirm": True,
        })
        price = close_p


class TestTAEngineInsufficient:
    """Test behavior with insufficient data."""

    def test_returns_none_below_min(self):
        buf = CandleBuffer(maxlen=100)
        _seed_buffer(buf, count=10)
        engine = TAEngine(buf)
        result = engine.compute("BTCUSDT", "5")
        assert result is None

    def test_returns_none_for_missing_symbol(self):
        buf = CandleBuffer(maxlen=100)
        engine = TAEngine(buf)
        result = engine.compute("SOLUSDT", "5")
        assert result is None


class TestTAEngineCompute:
    """Test indicator computation with sufficient data."""

    @pytest.fixture
    def engine_with_data(self):
        buf = CandleBuffer(maxlen=100)
        _seed_buffer(buf, count=50)
        return TAEngine(buf)

    def test_returns_dict(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert isinstance(result, dict)

    def test_has_all_indicators(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        expected_keys = [
            "rsi_14", "rsi_7", "bbands", "vwap", "obv", "obv_slope",
            "stoch", "rvol", "z_score", "ema_9", "ema_21",
            "candle_count", "symbol", "timeframe",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_rsi_in_range(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert 0 <= result["rsi_14"] <= 100
        assert 0 <= result["rsi_7"] <= 100

    def test_bbands_structure(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        bb = result["bbands"]
        assert bb is not None
        assert "lower" in bb
        assert "mid" in bb
        assert "upper" in bb
        # All values should be present with 50 candles (well above 20 SMA period)
        if bb["lower"] is not None and bb["upper"] is not None:
            assert bb["lower"] < bb["mid"] < bb["upper"]

    def test_stoch_structure(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        stoch = result["stoch"]
        assert stoch is not None
        assert "k" in stoch
        assert "d" in stoch

    def test_rvol_positive(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert result["rvol"] > 0

    def test_z_score_reasonable(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        # Z-score should be within a reasonable range for 50 candles
        assert -5 < result["z_score"] < 5

    def test_ema_values(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert result["ema_9"] is not None
        assert result["ema_21"] is not None
        # Both should be near the price range
        assert 60000 < result["ema_9"] < 75000
        assert 60000 < result["ema_21"] < 75000

    def test_meta_fields(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert result["candle_count"] == 50
        assert result["symbol"] == "BTCUSDT"
        assert result["timeframe"] == "5"

    def test_obv_slope_computed(self, engine_with_data):
        result = engine_with_data.compute("BTCUSDT", "5")
        assert result["obv_slope"] is not None
        assert isinstance(result["obv_slope"], float)


class TestTAEngineMultipleAssets:
    """Test that TA engine works for different symbols/timeframes."""

    def test_eth_indicators(self):
        buf = CandleBuffer(maxlen=100)
        _seed_buffer(buf, symbol="ETHUSDT", count=30, base_price=2000.0)
        engine = TAEngine(buf)
        result = engine.compute("ETHUSDT", "5")
        assert result is not None
        assert result["symbol"] == "ETHUSDT"
        assert 1000 < result["ema_9"] < 3000

    def test_1m_timeframe(self):
        buf = CandleBuffer(maxlen=100)
        _seed_buffer(buf, tf="1", count=30)
        engine = TAEngine(buf)
        result = engine.compute("BTCUSDT", "1")
        assert result is not None
        assert result["timeframe"] == "1"
