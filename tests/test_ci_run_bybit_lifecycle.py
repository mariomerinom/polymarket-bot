"""
test_ci_run_bybit_lifecycle.py — Bybit pipeline lifecycle behavioral tests.

Tests ci_run_bybit.main() — the most structurally different pipeline.
Verifies contracts for synthetic market creation, regime gating, consensus
boost, and position sync.

Phase A4 of TDD-first refactoring plan (docs/plans/tdd-plan.md).
"""

import json
import os
import sys
import sqlite3
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Fixtures ────────────────────────────────────────────────────────────────


def _fake_bybit_candle_data(direction="UP", n=12):
    """Minimal candle_data dict that ci_run_bybit.main() expects."""
    candles = [
        {
            "open": 84000 + i * 50,
            "high": 84100 + i * 50,
            "low": 83900 + i * 50,
            "close": 84050 + i * 50,
            "volume": 100,
            "direction": direction,
            "time": f"{i:02d}:00",
        }
        for i in range(n)
    ]
    return {
        "current_price": candles[-1]["close"],
        "1h_change_pct": 0.35,
        "trend": "up" if direction == "UP" else "down",
        "candles": candles,
        "consensus": {
            "score": 0,
            "sources": 2,
            "streak_bybit": {"direction": direction, "length": 3},
            "streak_spot": {"direction": direction, "length": 3},
        },
    }


def _fake_regime(is_mean_reverting=False, label="HIGH_VOL / TRENDING"):
    """Fake regime dict."""
    return {
        "label": label,
        "autocorrelation": 0.25 if not is_mean_reverting else -0.35,
        "volatility": 0.15,
        "is_mean_reverting": is_mean_reverting,
    }


def _fake_signal(should_trade=True, direction="UP", streak=3):
    """Fake momentum signal dict."""
    return {
        "should_trade": should_trade,
        "estimate": 0.62 if direction == "UP" else 0.38,
        "confidence": "medium",
        "direction": direction,
        "streak": streak,
        "reason": "ride_streak" if should_trade else "no_streak",
    }


def _make_bybit_db():
    """Create in-memory DB with Bybit schema (same as init_db_bybit but in-memory)."""
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, market_id TEXT, agent TEXT,
        estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
        predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT, prediction_id INTEGER, direction TEXT,
        size REAL, price_limit REAL, price_filled REAL,
        slippage_pct REAL, status TEXT DEFAULT 'pending',
        order_id TEXT, mode TEXT, reason TEXT,
        placed_at TEXT, filled_at TEXT, settled_at TEXT,
        pnl REAL, cycle INTEGER
    )""")
    db.commit()
    return db


def _apply_patches(stack, overrides=None):
    """Apply standard mocks for ci_run_bybit.main() using ExitStack."""
    defaults = {
        # pipeline_control is imported inside main(), patch at source
        "pipeline_control.load_pipeline_config": MagicMock(
            return_value={"mode": "paper", "notes": ""}
        ),
        "pipeline_control.is_pipeline_live": MagicMock(return_value=False),
        # init_db_bybit returns in-memory DB instead of file DB
        "ci_run_bybit.init_db_bybit": MagicMock(return_value=_make_bybit_db()),
        # These are top-level imports in ci_run_bybit
        "ci_run_bybit.fetch_bybit_candles": MagicMock(
            return_value=_fake_bybit_candle_data()
        ),
        "ci_run_bybit.fetch_bybit_funding_rate": MagicMock(return_value=0.0001),
        "ci_run_bybit.get_open_position": MagicMock(return_value=None),
        "ci_run_bybit.auto_resolve_bybit": MagicMock(return_value=0),
        "ci_run_bybit.create_synthetic_market": MagicMock(
            return_value="synth_mkt_001"
        ),
        "ci_run_bybit.compute_regime_from_candles": MagicMock(
            return_value=_fake_regime()
        ),
        "ci_run_bybit.momentum_signal": MagicMock(
            return_value=_fake_signal()
        ),
        "ci_run_bybit.execute_bybit_trades": MagicMock(return_value=[]),
        "ci_run_bybit.is_bybit_kill_switched": MagicMock(return_value=False),
        "ci_run_bybit.get_bybit_trading_summary": MagicMock(return_value={
            "positions_opened": 0, "positions_closed": 0,
            "total_pnl": 0, "mode": "PAPER",
        }),
        "ci_run_bybit.calculate_brier_scores": MagicMock(return_value=None),
    }
    if overrides:
        defaults.update(overrides)

    mocks = {}
    for target, mock_obj in defaults.items():
        mocks[target] = stack.enter_context(patch(target, mock_obj))
    return mocks


# ── Tests ───────────────────────────────────────────────────────────────────


class TestCiRunBybitLifecycle:
    """Bybit pipeline lifecycle — behavioral contracts."""

    def test_happy_path_with_synthetic_market(self):
        """Full cycle: sync → resolve → predict → trade → score → dashboard. No crash."""
        from ci_run_bybit import main

        mock_create = MagicMock(return_value="synth_mkt_001")
        mock_execute = MagicMock(return_value=[])
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run_bybit.create_synthetic_market": mock_create,
                "ci_run_bybit.execute_bybit_trades": mock_execute,
            })
            main(candle_data=_fake_bybit_candle_data())

        mock_create.assert_called_once()
        mock_execute.assert_called_once()

    def test_no_candle_data_fetches_from_api(self):
        """When candle_data is None, fetch_bybit_candles() is called."""
        from ci_run_bybit import main

        mock_fetch = MagicMock(return_value=_fake_bybit_candle_data())
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run_bybit.fetch_bybit_candles": mock_fetch,
            })
            main(candle_data=None)

        mock_fetch.assert_called_once()

    def test_mean_reverting_regime_skip(self):
        """Mean-reverting regime → no momentum signal called."""
        from ci_run_bybit import main

        mock_momentum = MagicMock(return_value=_fake_signal())
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run_bybit.compute_regime_from_candles": MagicMock(
                    return_value=_fake_regime(is_mean_reverting=True, label="MEAN_REVERTING")
                ),
                "ci_run_bybit.momentum_signal": mock_momentum,
            })
            main(candle_data=_fake_bybit_candle_data())

        mock_momentum.assert_not_called()

    def test_dead_hours_skip(self):
        """Dead hour → skip signal stored, no momentum signal computed."""
        import ci_run_bybit
        from ci_run_bybit import main

        mock_momentum = MagicMock(return_value=_fake_signal())
        current_hour = datetime.now(timezone.utc).hour
        original_dead = ci_run_bybit.DEAD_HOURS_UTC

        try:
            ci_run_bybit.DEAD_HOURS_UTC = {current_hour}
            with ExitStack() as stack:
                _apply_patches(stack, {
                    "ci_run_bybit.momentum_signal": mock_momentum,
                })
                main(candle_data=_fake_bybit_candle_data())

            mock_momentum.assert_not_called()
        finally:
            ci_run_bybit.DEAD_HOURS_UTC = original_dead

    def test_consensus_boost(self):
        """Consensus score == 2 with conviction >= 3 → conviction boosted."""
        from ci_run_bybit import store_prediction_bybit

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        signal = _fake_signal(should_trade=True, streak=3)
        regime = _fake_regime()
        consensus = {"score": 2, "sources": 2,
                     "streak_bybit": {"direction": "UP", "length": 3},
                     "streak_spot": {"direction": "UP", "length": 3}}

        pred = store_prediction_bybit(
            db, "synth_mkt_001", signal, regime, cycle=1,
            mark_price=84500, consensus=consensus,
        )

        # Base conviction is 3 (should_trade=True), consensus boost adds 1
        assert pred["conviction_score"] == 4, \
            f"Expected conviction 4 (3 base + 1 consensus boost), got {pred['conviction_score']}"

        db.close()

    def test_position_sync(self):
        """Position sync (get_open_position) is called at pipeline start."""
        from ci_run_bybit import main

        mock_pos = MagicMock(return_value={
            "side": "LONG", "size": 0.005, "entry_price": 84000.0, "cycles_held": 3,
        })
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run_bybit.get_open_position": mock_pos,
            })
            main(candle_data=_fake_bybit_candle_data())

        mock_pos.assert_called_once()
