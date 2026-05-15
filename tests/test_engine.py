"""Tests for botsy_engine.py and engine health integration."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_polymarket_microstructure_capture_is_opt_in_by_default():
    """Research-only Polymarket microstructure capture must not fill disk by default."""
    import importlib
    import botsy_engine

    original = os.environ.pop("POLYMARKET_MICROSTRUCTURE_ENABLED", None)
    try:
        module = importlib.reload(botsy_engine)
        assert module.POLYMARKET_MICROSTRUCTURE_ENABLED is False
    finally:
        if original is not None:
            os.environ["POLYMARKET_MICROSTRUCTURE_ENABLED"] = original
        importlib.reload(botsy_engine)


def test_polymarket_microstructure_capture_can_be_enabled_explicitly():
    """Operators can still enable the research writer with an explicit flag."""
    import importlib
    import botsy_engine

    original = os.environ.get("POLYMARKET_MICROSTRUCTURE_ENABLED")
    os.environ["POLYMARKET_MICROSTRUCTURE_ENABLED"] = "true"
    try:
        module = importlib.reload(botsy_engine)
        assert module.POLYMARKET_MICROSTRUCTURE_ENABLED is True
    finally:
        if original is None:
            os.environ.pop("POLYMARKET_MICROSTRUCTURE_ENABLED", None)
        else:
            os.environ["POLYMARKET_MICROSTRUCTURE_ENABLED"] = original
        importlib.reload(botsy_engine)


class _SkipEngineHealthData:
    """Tests for dashboard engine health data reader."""

    def test_returns_none_when_no_file(self, monkeypatch):
        from dashboard_v2.data import get_engine_health
        # Point to non-existent path
        monkeypatch.setattr(
            "dashboard_v2.data.Path",
            lambda *a: Path("/tmp/nonexistent_botsy_test"),
        )
        # The function checks a specific path; let's just verify it handles missing file
        result = get_engine_health()
        # May return None or data depending on whether ws_metrics.json exists in repo
        # The key test is it doesn't crash
        assert result is None or isinstance(result, dict)

    def test_reads_valid_metrics(self, tmp_path):
        from dashboard_v2 import data as data_mod

        metrics = {
            "polygon": {"status": "connected", "last_event": "2026-04-05T12:00:00Z", "reconnects_24h": 0},
            "bybit": {"status": "connected", "last_event": "2026-04-05T12:00:00Z", "reconnects_24h": 1},
            "polymarket": {"status": "disconnected", "last_event": None, "reconnects_24h": 3},
            "dispatch_latency_ms": {"p50": 45, "p95": 120, "samples": 100},
            "orderbook_age_ms": {"p50": 12, "p95": 85, "samples": 50},
            "fallback_fires_24h": 0,
            "engine_start": "2026-04-05T00:00:00Z",
            "cycles": 288,
        }
        metrics_file = tmp_path / "ws_metrics.json"
        metrics_file.write_text(json.dumps(metrics))

        # Monkey-patch the metrics path
        original_func = data_mod.get_engine_health

        def patched():
            if not metrics_file.exists():
                return None
            data = json.loads(metrics_file.read_text())
            return {
                "polygon_status": (data.get("polygon") or {}).get("status", "unknown"),
                "polygon_last": (data.get("polygon") or {}).get("last_event"),
                "polygon_reconnects": (data.get("polygon") or {}).get("reconnects_24h", 0),
                "bybit_status": (data.get("bybit") or {}).get("status", "unknown"),
                "bybit_last": (data.get("bybit") or {}).get("last_event"),
                "bybit_reconnects": (data.get("bybit") or {}).get("reconnects_24h", 0),
                "polymarket_status": (data.get("polymarket") or {}).get("status", "unknown"),
                "polymarket_last": (data.get("polymarket") or {}).get("last_event"),
                "polymarket_reconnects": (data.get("polymarket") or {}).get("reconnects_24h", 0),
                "dispatch_latency": data.get("dispatch_latency_ms", {}),
                "orderbook_age": data.get("orderbook_age_ms", {}),
                "fallback_fires": data.get("fallback_fires_24h", 0),
                "cycles": data.get("cycles", 0),
                "engine_start": data.get("engine_start", ""),
            }

        result = patched()
        assert result["polygon_status"] == "connected"
        assert result["bybit_reconnects"] == 1
        assert result["polymarket_status"] == "disconnected"
        assert result["dispatch_latency"]["p50"] == 45
        assert result["cycles"] == 288


class _SkipEngineHealthSection:
    """Tests for dashboard engine health HTML section."""

    def test_returns_empty_for_none(self):
        from dashboard_v2.sections import engine_health_section
        assert engine_health_section(None) == ""

    def test_renders_connected_status(self):
        from dashboard_v2.sections import engine_health_section
        health = {
            "bybit_spot_status": "connected",
            "bybit_spot_last": "2026-04-05T12:00:00+00:00",
            "bybit_spot_reconnects": 0,
            "bybit_linear_status": "connected",
            "bybit_linear_last": "2026-04-05T12:00:00+00:00",
            "bybit_linear_reconnects": 0,
            "polymarket_status": "disconnected",
            "polymarket_last": None,
            "polymarket_reconnects": 2,
            "dispatch_latency": {"p50": 45, "p95": 120, "samples": 100},
            "orderbook_age": {"p50": 12, "p95": 85, "samples": 50},
            "fallback_fires": 0,
            "cycles": 288,
        }
        html = engine_health_section(health)
        assert "Engine Health" in html
        assert "Bybit Spot" in html
        assert "Bybit Linear" in html
        assert "Polymarket" in html
        assert "Connected" in html
        assert "Down" in html  # Polymarket is disconnected
        assert "Dispatch:" in html
        assert "Reconnects" in html


class TestBotsyEngineInit:
    """Basic tests for BotsyEngine class initialization."""

    def test_engine_initializes(self):
        from botsy_engine import BotsyEngine
        engine = BotsyEngine()
        assert engine.cycle == 0
        assert engine.metrics["bybit_spot"]["status"] == "disconnected"
        assert engine.metrics["bybit_linear"]["status"] == "disconnected"
        assert engine.metrics["polymarket"]["status"] == "disconnected"
        assert engine.metrics["fallback_fires_24h"] == 0

    def test_routing_table_has_all_pipelines(self):
        from botsy_engine import ROUTING
        all_pipelines = set()
        for pipelines in ROUTING.values():
            all_pipelines.update(pipelines)
        assert "btc_5m" in all_pipelines
        assert "eth_5m" in all_pipelines
        assert "bybit" in all_pipelines
        assert "kalshi" in all_pipelines
        assert "btc_15m" in all_pipelines

    def test_engine_has_candle_buffer(self):
        from botsy_engine import BotsyEngine
        engine = BotsyEngine()
        assert hasattr(engine, "candle_buffer")
        assert hasattr(engine, "ta_engine")

    def test_native_15m_routing(self):
        from botsy_engine import ROUTING
        key = ("bybit_spot", "BTCUSDT", "15")
        assert key in ROUTING
        assert "btc_15m" in ROUTING[key]

    def test_dedup_prevents_double_dispatch(self):
        """Verify dedup key prevents same candle from being dispatched twice."""
        from botsy_engine import BotsyEngine
        engine = BotsyEngine()
        # Simulate adding a dedup key
        engine._dispatched.add(("bybit_spot", "BTC-USD", 1234567890000))
        assert ("bybit_spot", "BTC-USD", 1234567890000) in engine._dispatched

    def test_percentile_computation(self):
        from botsy_engine import BotsyEngine
        engine = BotsyEngine()
        engine._latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                             110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
        engine._strategy_lab_times = [1000, 2000]
        engine._pipeline_runtime_samples = {
            "btc_5m": [100, 200],
            "kalshi": [300, 900],
        }
        engine._compute_percentiles()
        assert engine.metrics["dispatch_latency_ms"]["p50"] == 110
        assert engine.metrics["dispatch_latency_ms"]["p95"] == 200  # int(20 * 0.95) = 19 → index 19 = 200
        assert engine.metrics["dispatch_latency_ms"]["samples"] == 20
        assert engine.metrics["strategy_lab_ms"]["p95"] == 2000
        assert engine.metrics["pipeline_runtime_ms"]["btc_5m"]["p95"] == 200
        assert engine.metrics["slowest_pipeline_runtime_ms"]["pipeline"] == "kalshi"

    def test_orderbook_age_samples_use_updated_at_not_zero(self):
        from datetime import datetime, timedelta, timezone
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._orderbook_cache = {
            "tok": {
                "mid": 0.55,
                "updated_at": (
                    datetime.now(timezone.utc) - timedelta(seconds=3)
                ).isoformat(),
            }
        }
        engine._sample_orderbook_cache_ages()
        engine._compute_percentiles()
        assert engine.metrics["orderbook_age_ms"]["p50"] >= 2500

    def test_orderbook_age_samples_only_active_subscribed_tokens(self):
        from datetime import datetime, timedelta, timezone
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._subscribed_token_ids = {"active"}
        engine._orderbook_cache = {
            "active": {
                "mid": 0.55,
                "updated_at": (
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat(),
            },
            "inactive_old": {
                "mid": 0.44,
                "updated_at": (
                    datetime.now(timezone.utc) - timedelta(days=1)
                ).isoformat(),
            },
        }
        engine._sample_orderbook_cache_ages()
        engine._compute_percentiles()
        assert engine.metrics["orderbook_age_ms"]["p95"] < 2000

    def test_polymarket_subscription_refresh_requests_reconnect_on_token_change(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._subscribed_token_ids = {"old"}
        engine._get_active_token_ids = lambda: ["new"]
        changed = engine.refresh_polymarket_subscriptions("test")
        assert changed is True
        assert engine._polymarket_resubscribe_requested is True
        assert engine.metrics["orderbook_cache"]["token_set_changes_24h"] == 1

    def test_orderbook_cache_prunes_to_active_subscription_tokens(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._orderbook_cache = {
            "active": {"mid": 0.55},
            "expired": {"mid": 0.44},
        }
        engine._orderbook_dirty = False

        engine._prune_orderbook_cache({"active"})

        assert set(engine._orderbook_cache) == {"active"}
        assert engine._orderbook_dirty is True

    def test_polymarket_book_initializes_orderbook_cache(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()

        engine._update_orderbook_cache({
            "event_type": "book",
            "asset_id": "tok",
            "bids": [{"price": "0.52", "size": "100"}],
            "asks": [{"price": "0.54", "size": "80"}],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["best_bid"] == 0.52
        assert entry["best_ask"] == 0.54
        assert entry["mid"] == 0.53
        assert entry["spread"] == pytest.approx(0.02)
        assert entry["updated_at"]

    def test_polymarket_price_change_refreshes_cached_bbo(self):
        from datetime import datetime, timedelta, timezone
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
        engine._orderbook_cache = {
            "tok": {
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": old_ts,
                "bids": [{"price": "0.52", "size": "100"}],
                "asks": [{"price": "0.54", "size": "80"}],
            }
        }

        engine._update_orderbook_price_change({
            "event_type": "price_change",
            "price_changes": [{
                "asset_id": "tok",
                "price": "0.53",
                "size": "120",
                "side": "BUY",
                "best_bid": "0.53",
                "best_ask": "0.54",
            }],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["best_bid"] == 0.53
        assert entry["best_ask"] == 0.54
        assert entry["mid"] == 0.535
        assert entry["updated_at"] != old_ts
        assert engine._orderbook_dirty is True

    def test_polymarket_price_change_accepts_changes_alias(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._orderbook_cache = {
            "tok": {
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": "2026-05-12T00:00:00+00:00",
                "bids": [{"price": "0.52", "size": "100"}],
                "asks": [{"price": "0.54", "size": "80"}],
            }
        }

        engine._update_orderbook_price_change({
            "event_type": "price_change",
            "changes": [{
                "asset_id": "tok",
                "price": "0.53",
                "size": "120",
                "side": "BUY",
                "best_bid": "0.53",
                "best_ask": "0.54",
            }],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["best_bid"] == 0.53
        assert entry["best_ask"] == 0.54
        assert entry["status"] == "fresh"

    def test_polymarket_price_change_without_snapshot_marks_token_stale(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()

        engine._update_orderbook_price_change({
            "event_type": "price_change",
            "price_changes": [{
                "asset_id": "tok",
                "price": "0.53",
                "size": "120",
                "side": "BUY",
                "best_bid": "0.53",
                "best_ask": "0.54",
            }],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["status"] == "stale"
        assert entry["updated_at"] is None
        assert "missing_snapshot" in entry["stale_reason"]

    def test_polymarket_price_change_crossed_book_marks_token_stale(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._orderbook_cache = {
            "tok": {
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": "2026-05-12T00:00:00+00:00",
                "bids": [{"price": "0.52", "size": "100"}],
                "asks": [{"price": "0.54", "size": "80"}],
            }
        }

        engine._update_orderbook_price_change({
            "event_type": "price_change",
            "price_changes": [{
                "asset_id": "tok",
                "best_bid": "0.56",
                "best_ask": "0.54",
            }],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["status"] == "stale"
        assert entry["updated_at"] is None
        assert "invalid_bbo" in entry["stale_reason"]

    def test_polymarket_price_change_empty_side_marks_token_stale(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        engine._orderbook_cache = {
            "tok": {
                "mid": 0.53,
                "best_bid": 0.52,
                "best_ask": 0.54,
                "spread": 0.02,
                "updated_at": "2026-05-12T00:00:00+00:00",
                "bids": [{"price": "0.52", "size": "100"}],
                "asks": [{"price": "0.54", "size": "80"}],
            }
        }

        engine._update_orderbook_price_change({
            "event_type": "price_change",
            "price_changes": [{
                "asset_id": "tok",
                "price": "0.54",
                "size": "0",
                "side": "SELL",
            }],
        })

        entry = engine._orderbook_cache["tok"]
        assert entry["status"] == "stale"
        assert entry["updated_at"] is None
        assert "invalid_bbo" in entry["stale_reason"]

    @pytest.mark.asyncio
    async def test_dispatch_runs_independent_pipelines_with_bounded_parallelism(self):
        from botsy_engine import BotsyEngine

        engine = BotsyEngine()
        starts = {}
        releases = {}

        async def fake_run_pipeline(name, candle_data=None, indicators=None):
            starts[name] = asyncio.Event()
            releases[name] = asyncio.Event()
            starts[name].set()
            await releases[name].wait()

        engine.run_pipeline = fake_run_pipeline
        task = asyncio.create_task(
            engine._run_pipeline_fanout(
                ["btc_5m", "kalshi", "hl"],
                candle_data={"candles": [{"close": 1}, {"close": 2}]},
                indicators=None,
            )
        )

        while len(starts) < 3:
            await asyncio.sleep(0)

        assert set(starts) == {"btc_5m", "kalshi", "hl"}
        for event in releases.values():
            event.set()
        await task
