"""
Tests for Strategy Lab framework.

TDD-first: these tests define the contract before implementation.
"""

import json
import sqlite3
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from strategies.base import StrategyContext, StrategySignal


# ── Test Fixtures ────────────────────────────────────────────────────────

def _make_candles(n=20, base_price=80000.0, direction="UP"):
    """Generate synthetic candles for testing."""
    candles = []
    price = base_price
    for i in range(n):
        delta = 10 if direction == "UP" else -10
        o = price
        c = price + delta
        h = max(o, c) + 5
        lo = min(o, c) - 5
        candles.append({
            "time": f"{i:02d}:00",
            "timestamp_ms": 1700000000000 + i * 300000,
            "open": o, "high": h, "low": lo, "close": c,
            "volume": 100.0,
            "direction": "UP" if c >= o else "DOWN",
            "body_pct": abs(c - o) / o * 100,
            "wick_ratio": 0.3,
        })
        price = c
    return candles


def _make_context(**overrides):
    """Build a StrategyContext with sensible defaults."""
    defaults = {
        "symbol": "BTCUSDT",
        "timeframe": "5",
        "pipeline": "btc_5m",
        "candles": _make_candles(),
        "indicators": {"rsi_14": 55.0, "bb_bandwidth": 2.5, "z_score": 0.3},
        "regime": {"label": "MEDIUM_VOL / TRENDING", "autocorrelation": 0.25,
                   "volatility": 0.08, "is_mean_reverting": False},
        "current_price": 80200.0,
        "timestamp": datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return StrategyContext(**defaults)


def _dummy_signal(ctx):
    """Always-fire test strategy."""
    return StrategySignal(
        direction="UP", estimate=0.58, conviction=3,
        reason="test_signal", metadata={"test": True},
    )


def _skip_signal(ctx):
    """Never-fire test strategy."""
    return None


def _crash_signal(ctx):
    """Strategy that raises an exception."""
    raise RuntimeError("strategy crashed on purpose")


# ── Test: Base Types ─────────────────────────────────────────────────────

class TestBaseTypes:
    def test_context_creation(self):
        ctx = _make_context()
        assert ctx.symbol == "BTCUSDT"
        assert ctx.timeframe == "5"
        assert ctx.pipeline == "btc_5m"
        assert len(ctx.candles) == 20
        assert ctx.indicators is not None
        assert ctx.orderbook is None  # optional, default None

    def test_signal_creation(self):
        sig = StrategySignal(direction="DOWN", estimate=0.42, conviction=4,
                             reason="test", metadata={"key": "val"})
        assert sig.direction == "DOWN"
        assert sig.estimate == 0.42
        assert sig.conviction == 4
        assert sig.metadata["key"] == "val"

    def test_signal_default_metadata(self):
        sig = StrategySignal(direction="UP", estimate=0.55, conviction=3, reason="x")
        assert sig.metadata == {}


# ── Test: Strategy Lab Runner ────────────────────────────────────────────

class TestStrategyLabDB:
    def test_init_db_creates_tables(self):
        from strategy_lab import _init_db
        db = sqlite3.connect(":memory:")
        _init_db(db)
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "lab_predictions" in tables
        db.close()

    def test_write_prediction(self):
        from strategy_lab import _init_db, _write_prediction
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={"k": "v"})
        _write_prediction(db, "test_strat", "btc_5m", "BTCUSDT",
                          sig, "MEDIUM_VOL / TRENDING", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        row = db.execute("SELECT * FROM lab_predictions").fetchone()
        assert row is not None
        # Check columns: strategy, pipeline, symbol, direction, estimate
        assert row[1] == "test_strat"  # strategy
        assert row[2] == "btc_5m"      # pipeline
        assert row[3] == "BTCUSDT"     # symbol
        assert row[4] == "UP"          # direction
        db.close()


class TestStrategyDispatch:
    def test_matching_strategy_fires(self):
        """Strategy matching (symbol, timeframe) produces a DB write."""
        from strategy_lab import _init_db, _dispatch_strategies
        db = sqlite3.connect(":memory:")
        _init_db(db)
        strategies = {
            "test_strat": {
                "fn": _dummy_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            }
        }
        ctx = _make_context()
        _dispatch_strategies(db, strategies, ctx)
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 1
        db.close()

    def test_non_matching_asset_skipped(self):
        """Strategy for ETHUSDT doesn't fire on BTCUSDT context."""
        from strategy_lab import _init_db, _dispatch_strategies
        db = sqlite3.connect(":memory:")
        _init_db(db)
        strategies = {
            "eth_only": {
                "fn": _dummy_signal,
                "assets": ["ETHUSDT"],
                "timeframes": ["5"],
            }
        }
        ctx = _make_context(symbol="BTCUSDT")
        _dispatch_strategies(db, strategies, ctx)
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 0
        db.close()

    def test_none_signal_no_write(self):
        """Strategy returning None produces no DB write."""
        from strategy_lab import _init_db, _dispatch_strategies
        db = sqlite3.connect(":memory:")
        _init_db(db)
        strategies = {
            "skip": {
                "fn": _skip_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            }
        }
        ctx = _make_context()
        _dispatch_strategies(db, strategies, ctx)
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 0
        db.close()

    def test_crashing_strategy_does_not_propagate(self):
        """A strategy that raises must not crash the lab or production."""
        from strategy_lab import _init_db, _dispatch_strategies
        db = sqlite3.connect(":memory:")
        _init_db(db)
        strategies = {
            "crasher": {
                "fn": _crash_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            },
            "good": {
                "fn": _dummy_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            }
        }
        ctx = _make_context()
        # Should not raise
        _dispatch_strategies(db, strategies, ctx)
        # The good strategy should still have fired
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 1
        db.close()

    def test_multiple_strategies_multiple_writes(self):
        """Two matching strategies produce two DB rows."""
        from strategy_lab import _init_db, _dispatch_strategies
        db = sqlite3.connect(":memory:")
        _init_db(db)
        strategies = {
            "strat_a": {
                "fn": _dummy_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            },
            "strat_b": {
                "fn": _dummy_signal,
                "assets": ["BTCUSDT"],
                "timeframes": ["5"],
            }
        }
        ctx = _make_context()
        _dispatch_strategies(db, strategies, ctx)
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 2
        db.close()


class TestAutoResolution:
    def test_resolve_correct_up(self):
        """UP prediction + next candle closes UP → outcome=1."""
        from strategy_lab import _init_db, _write_prediction, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        # Write prediction at T=12:00
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={})
        _write_prediction(db, "test", "btc_5m", "BTCUSDT", sig,
                          "MEDIUM_VOL / TRENDING", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        # Resolve with next candle that went UP
        next_candle = {"open": 80000, "close": 80100, "high": 80150, "low": 79950}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 1
        row = db.execute("SELECT outcome, pnl FROM lab_predictions WHERE id=1").fetchone()
        assert row[0] == 1  # correct
        db.close()

    def test_resolve_incorrect_up(self):
        """UP prediction + next candle closes DOWN → outcome=0."""
        from strategy_lab import _init_db, _write_prediction, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={})
        _write_prediction(db, "test", "btc_5m", "BTCUSDT", sig,
                          "MEDIUM_VOL / TRENDING", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        next_candle = {"open": 80000, "close": 79900, "high": 80050, "low": 79850}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 1
        row = db.execute("SELECT outcome FROM lab_predictions WHERE id=1").fetchone()
        assert row[0] == 0  # incorrect
        db.close()

    def test_resolve_down_correct(self):
        """DOWN prediction + next candle closes DOWN → outcome=1."""
        from strategy_lab import _init_db, _write_prediction, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="DOWN", estimate=0.42, conviction=3,
                             reason="test", metadata={})
        _write_prediction(db, "test", "btc_5m", "BTCUSDT", sig,
                          "MEDIUM_VOL / TRENDING", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        next_candle = {"open": 80000, "close": 79900, "high": 80050, "low": 79850}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 1
        row = db.execute("SELECT outcome FROM lab_predictions WHERE id=1").fetchone()
        assert row[0] == 1  # correct
        db.close()

    def test_no_pending_returns_zero(self):
        """No pending predictions → resolve returns 0."""
        from strategy_lab import _init_db, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        next_candle = {"open": 80000, "close": 80100, "high": 80150, "low": 79950}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 0
        db.close()


class TestConfigLoading:
    def test_load_strategies_from_json(self, tmp_path):
        """Strategies are loaded from config/strategy_lab.json."""
        from strategy_lab import _load_strategies
        # Use strategies.base module which we know exists, with a mock function
        config = {
            "strategies": {
                "test_strat": {
                    "module": "strategies.base",
                    "function": "StrategySignal",
                    "enabled": True,
                    "assets": ["BTCUSDT"],
                    "timeframes": ["5"],
                    "min_sample": 200,
                }
            }
        }
        config_path = tmp_path / "strategy_lab.json"
        config_path.write_text(json.dumps(config))

        with patch("strategy_lab.STRATEGY_LAB_CONFIG", config_path):
            strategies = _load_strategies()
        assert "test_strat" in strategies
        assert strategies["test_strat"]["assets"] == ["BTCUSDT"]

    def test_disabled_strategy_excluded(self, tmp_path):
        """Disabled strategies are not loaded."""
        from strategy_lab import _load_strategies
        config = {
            "strategies": {
                "disabled_one": {
                    "module": "strategies.vwap_meanrev",
                    "function": "signal",
                    "enabled": False,
                    "assets": ["BTCUSDT"],
                    "timeframes": ["5"],
                }
            }
        }
        config_path = tmp_path / "strategy_lab.json"
        config_path.write_text(json.dumps(config))

        with patch("strategy_lab.STRATEGY_LAB_CONFIG", config_path):
            strategies = _load_strategies()
        assert "disabled_one" not in strategies


class TestEngineIntegration:
    def test_strategy_lab_run_does_not_raise(self):
        """strategy_lab_run never raises, even with bad data."""
        from strategy_lab import strategy_lab_run
        # Should handle gracefully with no candle data
        try:
            strategy_lab_run(
                pipelines=["btc_5m"],
                symbol="BTCUSDT",
                interval="5",
                candle_data=None,
                indicators=None,
            )
        except Exception:
            pytest.fail("strategy_lab_run raised an exception")
