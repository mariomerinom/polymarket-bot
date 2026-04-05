"""Tests for candle_buffer.py — ring buffer for WS candle events."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from candle_buffer import CandleBuffer, _build_candle_dict


class TestBuildCandleDict:
    """Test the candle dict builder."""

    def test_up_candle(self):
        c = _build_candle_dict(
            open_ts_ms=1775410500000,
            open_price=67000.0, high=67500.0, low=66900.0,
            close=67300.0, volume=10.5,
        )
        assert c["direction"] == "UP"
        assert c["open"] == 67000.0
        assert c["close"] == 67300.0
        assert c["volume"] == 10.5
        assert c["time"]  # should be a HH:MM string
        assert c["timestamp_ms"] == 1775410500000
        assert c["body_pct"] > 0

    def test_down_candle(self):
        c = _build_candle_dict(
            open_ts_ms=1775410500000,
            open_price=67300.0, high=67500.0, low=66900.0,
            close=67000.0, volume=8.2,
        )
        assert c["direction"] == "DOWN"
        assert c["body_pct"] < 0

    def test_doji_candle(self):
        c = _build_candle_dict(
            open_ts_ms=1775410500000,
            open_price=67000.0, high=67100.0, low=66900.0,
            close=67000.0, volume=5.0,
        )
        assert c["direction"] == "UP"  # close >= open
        assert c["body_pct"] == 0.0
        assert c["wick_ratio"] == 1.0  # all wick, no body


class TestCandleBufferBasics:
    """Test buffer append, get, and depth."""

    def test_empty_buffer(self):
        buf = CandleBuffer(maxlen=10)
        assert buf.depth("BTCUSDT", "5") == 0
        assert buf.get_candles("BTCUSDT", "5") == []
        assert buf.get_closes("BTCUSDT", "5") == []

    def test_append_confirmed_candle(self):
        buf = CandleBuffer(maxlen=10)
        kline = {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67500", "low": "66900",
            "close": "67300", "volume": "10.5",
            "confirm": True,
        }
        result = buf.on_kline_event("BTCUSDT", "5", kline)
        assert result is not None
        assert result["close"] == 67300.0
        assert buf.depth("BTCUSDT", "5") == 1

    def test_pending_candle_not_appended(self):
        buf = CandleBuffer(maxlen=10)
        kline = {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67100", "low": "66900",
            "close": "67050", "volume": "3.0",
            "confirm": False,
        }
        result = buf.on_kline_event("BTCUSDT", "5", kline)
        assert result is None
        assert buf.depth("BTCUSDT", "5") == 0

    def test_pending_then_confirmed(self):
        buf = CandleBuffer(maxlen=10)
        # Pending update
        buf.on_kline_event("BTCUSDT", "5", {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67100", "low": "66900",
            "close": "67050", "volume": "3.0",
            "confirm": False,
        })
        assert buf.depth("BTCUSDT", "5") == 0

        # Confirmed
        result = buf.on_kline_event("BTCUSDT", "5", {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67500", "low": "66900",
            "close": "67300", "volume": "10.5",
            "confirm": True,
        })
        assert result is not None
        assert buf.depth("BTCUSDT", "5") == 1

    def test_maxlen_enforced(self):
        buf = CandleBuffer(maxlen=5)
        for i in range(10):
            buf.on_kline_event("BTCUSDT", "5", {
                "start": str(1775410500000 + i * 300000),
                "end": str(1775410500000 + (i + 1) * 300000 - 1),
                "open": str(67000 + i), "high": str(67500 + i),
                "low": str(66900 + i), "close": str(67300 + i),
                "volume": "10.0",
                "confirm": True,
            })
        assert buf.depth("BTCUSDT", "5") == 5
        # Oldest should be candle #5 (0-indexed), not #0
        candles = buf.get_candles("BTCUSDT", "5")
        assert candles[0]["close"] == 67305.0

    def test_multiple_symbols(self):
        buf = CandleBuffer(maxlen=10)
        buf.on_kline_event("BTCUSDT", "5", {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67500", "low": "66900",
            "close": "67300", "volume": "10.0", "confirm": True,
        })
        buf.on_kline_event("ETHUSDT", "5", {
            "start": "1775410500000", "end": "1775410799999",
            "open": "2000", "high": "2050", "low": "1990",
            "close": "2030", "volume": "100.0", "confirm": True,
        })
        assert buf.depth("BTCUSDT", "5") == 1
        assert buf.depth("ETHUSDT", "5") == 1

    def test_multiple_timeframes(self):
        buf = CandleBuffer(maxlen=10)
        buf.on_kline_event("BTCUSDT", "1", {
            "start": "1775410500000", "end": "1775410559999",
            "open": "67000", "high": "67100", "low": "66950",
            "close": "67050", "volume": "2.0", "confirm": True,
        })
        buf.on_kline_event("BTCUSDT", "5", {
            "start": "1775410500000", "end": "1775410799999",
            "open": "67000", "high": "67500", "low": "66900",
            "close": "67300", "volume": "10.0", "confirm": True,
        })
        assert buf.depth("BTCUSDT", "1") == 1
        assert buf.depth("BTCUSDT", "5") == 1

    def test_get_closes(self):
        buf = CandleBuffer(maxlen=10)
        for i in range(3):
            buf.on_kline_event("BTCUSDT", "5", {
                "start": str(1775410500000 + i * 300000),
                "end": str(1775410500000 + (i + 1) * 300000 - 1),
                "open": "67000", "high": "67500", "low": "66900",
                "close": str(67000 + i * 100), "volume": "10.0",
                "confirm": True,
            })
        closes = buf.get_closes("BTCUSDT", "5")
        assert closes == [67000.0, 67100.0, 67200.0]

    def test_get_candles_with_limit(self):
        buf = CandleBuffer(maxlen=10)
        for i in range(5):
            buf.on_kline_event("BTCUSDT", "5", {
                "start": str(1775410500000 + i * 300000),
                "end": str(1775410500000 + (i + 1) * 300000 - 1),
                "open": "67000", "high": "67500", "low": "66900",
                "close": str(67000 + i * 100), "volume": "10.0",
                "confirm": True,
            })
        candles = buf.get_candles("BTCUSDT", "5", limit=3)
        assert len(candles) == 3
        assert candles[0]["close"] == 67200.0  # last 3: 200, 300, 400


class TestSeedFromRest:
    """Test REST seeding (mocked)."""

    def test_seed_populates_buffer(self, monkeypatch):
        """Verify seed_from_rest calls Bybit REST and populates buffer."""
        import requests

        # Mock Bybit response
        fake_klines = [
            [str(1775410500000 + i * 300000),
             "67000", "67500", "66900", str(67000 + i * 100), "10.0", "670000"]
            for i in range(50)
        ]
        # Bybit returns newest first
        fake_klines.reverse()

        class FakeResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"retCode": 0, "result": {"list": fake_klines}}

        monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())

        buf = CandleBuffer(maxlen=100)
        count = buf.seed_from_rest("BTCUSDT", "5", category="spot")
        assert count == 50
        assert buf.depth("BTCUSDT", "5") == 50
        # Verify chronological order (oldest first)
        candles = buf.get_candles("BTCUSDT", "5")
        assert candles[0]["timestamp_ms"] < candles[-1]["timestamp_ms"]
