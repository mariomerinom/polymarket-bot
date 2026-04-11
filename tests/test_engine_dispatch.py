"""
test_engine_dispatch.py — Engine dispatch logic behavioral tests.

Tests botsy_engine.py routing, dedup, and candle data building — pure logic,
no WebSocket needed.

Phase A3 of TDD-first refactoring plan (docs/plans/tdd-plan.md).
"""

import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from botsy_engine import BotsyEngine, ROUTING


# ── Helpers ────────────────────────────────────────────────────────────────


def _run(coro):
    """Run an async coroutine in a fresh event loop (Python 3.10+ safe)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_engine():
    """Create a BotsyEngine with mocked pipeline runner."""
    engine = BotsyEngine()
    engine.run_pipeline = AsyncMock()
    return engine


def _make_buffer_candles(n=12, direction_up=True):
    """Create minimal candle list for buffer testing."""
    return [
        {
            "open": 84000 + i * 10,
            "high": 84100 + i * 10,
            "low": 83900 + i * 10,
            "close": 84050 + i * 10,
            "volume": 100,
            "direction": "UP" if direction_up else "DOWN",
            "time": f"{i:02d}:00",
            "timestamp_ms": 1700000000000 + i * 300000,
            "body_pct": 0.05,
            "wick_ratio": 0.3,
        }
        for i in range(n)
    ]


# ── Tests ───────────────────────────────────────────────────────────────────


class TestEngineDispatch:
    """Engine dispatch logic — behavioral contracts."""

    def test_routing_btc_5m(self):
        """BTC 5m route dispatches to btc_5m, kalshi, and hl pipelines."""
        engine = _make_engine()

        asyncio.run(
            engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=1700000000000)
        )

        # Should have dispatched to btc_5m, kalshi, and hl
        assert engine.run_pipeline.call_count == 3
        pipeline_names = [c.args[0] for c in engine.run_pipeline.call_args_list]
        assert "btc_5m" in pipeline_names
        assert "kalshi" in pipeline_names
        assert "hl" in pipeline_names

    def test_routing_unknown_key(self):
        """Unknown routing key → no dispatch, no crash."""
        engine = _make_engine()

        asyncio.run(
            engine.dispatch("unknown_source", "XYZUSDT", "5", candle_ts=1700000000000)
        )

        engine.run_pipeline.assert_not_called()

    def test_dedup_prevents_double_dispatch(self):
        """Same (source, symbol, candle_ts) dispatches exactly once."""
        engine = _make_engine()

        ts = 1700000000000

        async def _run_both():
            await engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=ts)
            first_count = engine.run_pipeline.call_count
            await engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=ts)
            return first_count, engine.run_pipeline.call_count

        first_count, second_count = _run(_run_both())
        assert second_count == first_count, "Duplicate event should not trigger new dispatch"

    def test_dedup_allows_new_timestamp(self):
        """Different candle_ts for same symbol dispatches again."""
        engine = _make_engine()

        async def _run_both():
            await engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=1700000000000)
            first_count = engine.run_pipeline.call_count
            await engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=1700000300000)
            return first_count, engine.run_pipeline.call_count

        first_count, second_count = _run(_run_both())
        assert second_count > first_count, "New timestamp should trigger new dispatch"

    def test_dedup_pruning_keeps_entries(self):
        """After 100+ entries, dedup set is pruned but recent keys retained."""
        engine = _make_engine()

        # Add 101 dedup entries
        for i in range(101):
            engine._dispatched.add(("bybit_spot", "BTCUSDT", 1700000000000 + i))

        assert len(engine._dispatched) == 101

        # Trigger dispatch which will prune (set > 100)
        _run(
            engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=9999999999999)
        )

        # After pruning, set should be <= 51 (50 kept + 1 new)
        assert len(engine._dispatched) <= 51

    def test_candle_data_building(self):
        """Buffer candles → candle_data dict with correct fields."""
        engine = _make_engine()

        # Seed the buffer using on_kline_event (the real API)
        for i in range(12):
            kline = {
                "start": str(1700000000000 + i * 300000),
                "end": str(1700000300000 + i * 300000),
                "open": str(84000 + i * 10),
                "high": str(84100 + i * 10),
                "low": str(83900 + i * 10),
                "close": str(84050 + i * 10),
                "volume": str(100),
                "confirm": True,
            }
            engine.candle_buffer.on_kline_event("BTCUSDT", "5", kline)

        # Dispatch — run_pipeline should receive candle_data
        _run(
            engine.dispatch("bybit_spot", "BTCUSDT", "5", candle_ts=1700099999999)
        )

        # Check candle_data passed to run_pipeline
        assert engine.run_pipeline.call_count >= 1
        call_kwargs = engine.run_pipeline.call_args_list[0].kwargs
        candle_data = call_kwargs.get("candle_data")

        assert candle_data is not None, "candle_data should be passed to pipeline"
        assert "current_price" in candle_data
        assert "1h_change_pct" in candle_data
        assert "trend" in candle_data
        assert "candles" in candle_data
        assert isinstance(candle_data["current_price"], (int, float))
        assert isinstance(candle_data["1h_change_pct"], (int, float))
        assert candle_data["trend"] in ("up", "down", "neutral")
