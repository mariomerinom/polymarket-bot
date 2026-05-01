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

from strategies.base import StrategyContext, StrategySignal, indicator_snapshot


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


def _make_indicators():
    """TA engine style indicators with nested structures."""
    return {
        "rsi_14": 55.0,
        "rsi_7": 58.0,
        "bbands": {
            "lower": 79500.0,
            "mid": 80000.0,
            "upper": 80500.0,
            "bandwidth": 2.5,
            "pctb": 0.7,
        },
        "vwap": 80050.0,
        "obv": 5000.0,
        "obv_slope": 0.3,
        "stoch": {"k": 65.0, "d": 60.0},
        "rvol": 1.2,
        "z_score": 0.3,
        "ema_9": 80100.0,
        "ema_21": 79900.0,
        "candle_count": 20,
        "symbol": "BTCUSDT",
        "timeframe": "5",
    }


def _make_context(**overrides):
    """Build a StrategyContext with sensible defaults."""
    defaults = {
        "symbol": "BTCUSDT",
        "timeframe": "5",
        "pipeline": "btc_5m",
        "candles": _make_candles(),
        "indicators": _make_indicators(),
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


# ── Test: Indicator Snapshot ────────────────────────────────────────────

class TestIndicatorSnapshot:
    def test_snapshot_flattens_bbands(self):
        ctx = _make_context()
        snap = indicator_snapshot(ctx)
        assert snap["bb_bandwidth"] == 2.5
        assert snap["bb_pctb"] == 0.7
        assert snap["bb_lower"] == 79500.0

    def test_snapshot_flattens_stoch(self):
        ctx = _make_context()
        snap = indicator_snapshot(ctx)
        assert snap["stoch_k"] == 65.0
        assert snap["stoch_d"] == 60.0

    def test_snapshot_includes_scalars(self):
        ctx = _make_context()
        snap = indicator_snapshot(ctx)
        assert snap["rsi_14"] == 55.0
        assert snap["rsi_7"] == 58.0
        assert snap["z_score"] == 0.3
        assert snap["rvol"] == 1.2

    def test_snapshot_includes_regime(self):
        ctx = _make_context()
        snap = indicator_snapshot(ctx)
        assert snap["regime_label"] == "MEDIUM_VOL / TRENDING"
        assert snap["is_mean_reverting"] is False

    def test_snapshot_includes_ema_cross(self):
        ctx = _make_context()
        snap = indicator_snapshot(ctx)
        # ema_9 (80100) > ema_21 (79900) → BULLISH
        assert snap["ema_cross"] == "BULLISH"

    def test_snapshot_includes_streak(self):
        ctx = _make_context(candles=_make_candles(direction="UP"))
        snap = indicator_snapshot(ctx)
        assert snap["streak_length"] == 20  # all UP candles
        assert snap["streak_direction"] == "UP"

    def test_snapshot_handles_no_indicators(self):
        ctx = _make_context(indicators=None)
        snap = indicator_snapshot(ctx)
        # Should still have candle-derived features
        assert "streak_length" in snap
        assert "rsi_14" not in snap

    def test_snapshot_handles_no_regime(self):
        ctx = _make_context(regime=None)
        snap = indicator_snapshot(ctx)
        assert "regime_label" not in snap


# ── Test: Always-Fire Strategies ────────────────────────────────────────

class TestAlwaysFireStrategies:
    def test_vwap_meanrev_always_fires(self):
        """VWAP should fire on every cycle, not just mean-reverting regimes."""
        from strategies.vwap_meanrev import signal
        # Trending regime — old version would return None
        ctx = _make_context(regime={"label": "HIGH_VOL / TRENDING",
                                     "autocorrelation": 0.4,
                                     "volatility": 0.15,
                                     "is_mean_reverting": False})
        result = signal(ctx)
        assert result is not None
        assert result.direction in ("UP", "DOWN")
        assert "zscore" in result.metadata
        assert "rsi_14" in result.metadata  # indicator snapshot present

    def test_vwap_meanrev_logs_all_indicators(self):
        from strategies.vwap_meanrev import signal
        ctx = _make_context()
        result = signal(ctx)
        assert result is not None
        meta = result.metadata
        # Strategy-specific params
        assert "vwap" in meta
        assert "zscore" in meta
        assert "abs_zscore" in meta
        # General indicator snapshot
        assert "bb_bandwidth" in meta
        assert "stoch_k" in meta

    def test_vol_breakout_always_fires(self):
        """Vol breakout should fire even without compression."""
        from strategies.vol_breakout import signal
        ctx = _make_context()
        result = signal(ctx)
        assert result is not None
        assert result.direction in ("UP", "DOWN")
        assert "expansion_ratio" in result.metadata
        assert "bb_bandwidth" in result.metadata

    def test_vol_breakout_reads_nested_bbands(self):
        """Vol breakout must read bb_bandwidth from nested bbands dict."""
        from strategies.vol_breakout import signal
        ctx = _make_context()
        result = signal(ctx)
        # Should have the actual value, not None
        assert result.metadata["bb_bandwidth"] == 2.5

    def test_candle_snapshot_always_fires(self):
        from strategies.candle_snapshot import signal
        ctx = _make_context()
        result = signal(ctx)
        assert result is not None
        assert result.conviction == 1  # data collection, not trading
        meta = result.metadata
        # Should have OHLCV
        assert "open" in meta
        assert "close" in meta
        assert "volume" in meta
        # Should have all indicators
        assert "rsi_14" in meta
        assert "bb_bandwidth" in meta

    def test_momentum_lab_always_fires(self):
        from strategies.momentum_lab import signal
        ctx = _make_context()
        result = signal(ctx)
        assert result is not None
        assert "streak_length" in result.metadata
        assert "production_would_bet" in result.metadata

    def test_momentum_lab_streak_detection(self):
        from strategies.momentum_lab import signal
        # All UP candles → long streak
        ctx = _make_context(candles=_make_candles(20, direction="UP"))
        result = signal(ctx)
        assert result.direction == "UP"
        assert result.metadata["streak_length"] == 20
        assert result.conviction == 4  # long streak

    def test_strategies_store_metadata_as_json(self):
        """All strategy metadata must be JSON-serializable for DB storage."""
        from strategies.candle_snapshot import signal as snap_signal
        from strategies.momentum_lab import signal as mom_signal
        from strategies.vwap_meanrev import signal as vwap_signal
        from strategies.vol_breakout import signal as vol_signal

        ctx = _make_context()
        for fn in [snap_signal, mom_signal, vwap_signal, vol_signal]:
            result = fn(ctx)
            assert result is not None
            # Must not throw
            serialized = json.dumps(result.metadata)
            # Must round-trip
            deserialized = json.loads(serialized)
            assert isinstance(deserialized, dict)


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
        assert row[1] == "test_strat"  # strategy
        assert row[2] == "btc_5m"      # pipeline
        assert row[3] == "BTCUSDT"     # symbol
        assert row[4] == "UP"          # direction
        db.close()

    def test_write_prediction_stores_reliability_metadata_columns(self):
        """Lab rows carry deploy/timing fields so reports can partition results."""
        from strategy_lab import _init_db, _write_prediction
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={"k": "v"})
        _write_prediction(
            db, "test_strat", "btc_5m", "BTCUSDT", sig,
            "MEDIUM_VOL / TRENDING", 80000.0,
            datetime(2026, 4, 11, 12, 1, tzinfo=timezone.utc),
            cycle_close_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            offset_seconds=60,
            source_interval="5",
            deploy_epoch="test-epoch",
            engine_commit="abc1234",
        )
        row = db.execute("""
            SELECT schema_version, engine_commit, deploy_epoch, cycle_close_at,
                   offset_seconds, source_interval, synthetic_pnl
            FROM lab_predictions
        """).fetchone()
        assert row[0] == 2
        assert row[1] == "abc1234"
        assert row[2] == "test-epoch"
        assert row[3] == "2026-04-11T12:00:00+00:00"
        assert row[4] == 60
        assert row[5] == "5"
        assert row[6] is None
        db.close()

    def test_write_prediction_backfills_reliability_metadata_into_json(self):
        """Metadata JSON includes the same reliability keys for param sweeps."""
        from strategy_lab import _init_db, _write_prediction
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={})
        _write_prediction(
            db, "test_strat", "btc_5m", "BTCUSDT", sig, "", 80000.0,
            datetime(2026, 4, 11, 12, 1, tzinfo=timezone.utc),
            cycle_close_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
            offset_seconds=60,
            source_interval="5",
            deploy_epoch="test-epoch",
            engine_commit="abc1234",
        )
        meta = json.loads(db.execute(
            "SELECT metadata FROM lab_predictions"
        ).fetchone()[0])
        assert meta["schema_version"] == 2
        assert meta["engine_commit"] == "abc1234"
        assert meta["deploy_epoch"] == "test-epoch"
        assert meta["cycle_close_at"] == "2026-04-11T12:00:00+00:00"
        assert meta["offset_seconds"] == 60
        assert meta["symbol"] == "BTCUSDT"
        assert meta["pipeline"] == "btc_5m"
        assert meta["source_interval"] == "5"
        db.close()

    def test_write_prediction_stores_large_metadata(self):
        """Always-fire strategies store large metadata — verify it persists."""
        from strategy_lab import _init_db, _write_prediction
        db = sqlite3.connect(":memory:")
        _init_db(db)
        # Simulate a full indicator snapshot
        big_meta = {
            "rsi_14": 55.0, "rsi_7": 58.0, "bb_bandwidth": 2.5,
            "bb_pctb": 0.7, "stoch_k": 65.0, "stoch_d": 60.0,
            "z_score": 0.3, "rvol": 1.2, "streak_length": 3,
            "regime_label": "MEDIUM_VOL / TRENDING",
        }
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata=big_meta)
        _write_prediction(db, "snapshot", "btc_5m", "BTCUSDT",
                          sig, "", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        row = db.execute("SELECT metadata FROM lab_predictions").fetchone()
        recovered = json.loads(row[0])
        assert recovered["rsi_14"] == 55.0
        assert recovered["streak_length"] == 3
        db.close()


class TestStrategyDispatch:
    def test_matching_strategy_fires(self):
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
        _dispatch_strategies(db, strategies, ctx)
        count = db.execute("SELECT COUNT(*) FROM lab_predictions").fetchone()[0]
        assert count == 1
        db.close()

    def test_multiple_strategies_multiple_writes(self):
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
        from strategy_lab import _init_db, _write_prediction, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        sig = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                             reason="test", metadata={})
        _write_prediction(db, "test", "btc_5m", "BTCUSDT", sig,
                          "MEDIUM_VOL / TRENDING", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        next_candle = {"open": 80000, "close": 80100, "high": 80150, "low": 79950}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 1
        row = db.execute("SELECT outcome, pnl, synthetic_pnl FROM lab_predictions WHERE id=1").fetchone()
        assert row[0] == 1
        assert row[1] == 25.0
        assert row[2] == 25.0
        db.close()

    def test_resolve_incorrect_up(self):
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
        assert row[0] == 0
        db.close()

    def test_resolve_down_correct(self):
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
        assert row[0] == 1
        db.close()

    def test_no_pending_returns_zero(self):
        from strategy_lab import _init_db, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        next_candle = {"open": 80000, "close": 80100, "high": 80150, "low": 79950}
        resolved = _auto_resolve(db, next_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc))
        assert resolved == 0
        db.close()

    def test_resolve_scoped_by_symbol(self):
        """Only resolve predictions matching the current symbol."""
        from strategy_lab import _init_db, _write_prediction, _auto_resolve
        db = sqlite3.connect(":memory:")
        _init_db(db)
        # BTC prediction
        sig_btc = StrategySignal(direction="UP", estimate=0.58, conviction=3,
                                  reason="test", metadata={})
        _write_prediction(db, "test", "btc_5m", "BTCUSDT", sig_btc,
                          "", 80000.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))
        # ETH prediction
        sig_eth = StrategySignal(direction="DOWN", estimate=0.42, conviction=3,
                                  reason="test", metadata={})
        _write_prediction(db, "test", "eth_5m", "ETHUSDT", sig_eth,
                          "", 2200.0,
                          datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc))

        # Resolve with BTC candle — only BTC should resolve
        btc_candle = {"open": 80000, "close": 80100, "high": 80150, "low": 79950}
        resolved = _auto_resolve(db, btc_candle,
                                 datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc),
                                 symbol="BTCUSDT")
        assert resolved == 1
        # ETH should still be pending
        eth_pending = db.execute(
            "SELECT outcome FROM lab_predictions WHERE symbol='ETHUSDT'").fetchone()
        assert eth_pending[0] is None
        db.close()


class TestConfigLoading:
    def test_load_strategies_from_json(self, tmp_path):
        from strategy_lab import _load_strategies
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
        from strategy_lab import strategy_lab_run
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
