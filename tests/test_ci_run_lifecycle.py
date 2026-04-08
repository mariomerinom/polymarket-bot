"""
test_ci_run_lifecycle.py — BTC 5m pipeline lifecycle behavioral tests.

Tests ci_run.main() → polymarket_pipeline.run_polymarket_pipeline()
end-to-end with mocked I/O boundaries. Verifies contracts, not structure.

Phase A2 of TDD-first refactoring plan (docs/plans/tdd-plan.md).
Updated for pipeline unification (incident #66 fix, 2026-04-06).
"""

import os
import sys
import sqlite3
from contextlib import ExitStack
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Module prefix: lifecycle now lives in polymarket_pipeline
_M = "polymarket_pipeline"


# ── Fixtures ────────────────────────────────────────────────────────────────


def _fake_candle_data():
    """Minimal candle_data dict that the pipeline expects."""
    return {
        "current_price": 84500.0,
        "1h_change_pct": 0.25,
        "trend": "up",
        "candles": [
            {"open": 84000, "high": 84600, "low": 83900, "close": 84500,
             "volume": 100, "direction": "UP", "time": "12:00"},
        ] * 12,
    }


def _fake_market():
    """Single active BTC market dict as returned by fetch_active_markets()."""
    return {
        "id": "mkt_btc_test_001",
        "question": "Will BTC go up?",
        "category": "crypto",
        "end_date": "2099-01-01T00:00:00Z",
        "volume": 5000,
        "price_yes": 0.50,
        "price_no": 0.50,
    }


def _apply_patches(stack, overrides=None):
    """Apply standard mocks for the unified pipeline. Returns mock dict."""
    defaults = {
        f"{_M}.load_pipeline_config": MagicMock(return_value={"mode": "paper", "bet_size": None, "notes": ""}),
        f"{_M}.is_pipeline_live": MagicMock(return_value=False),
        f"{_M}.store_markets": MagicMock(),
        f"{_M}.auto_resolve": MagicMock(return_value=0),
        f"{_M}.has_unpredicted_market": MagicMock(return_value=False),
        f"{_M}.execute_trades": MagicMock(return_value=[]),
        f"{_M}.is_kill_switched": MagicMock(return_value=False),
        f"{_M}.ensure_orders_table": MagicMock(),
        f"{_M}.get_trading_summary": MagicMock(return_value={
            "mode": "PAPER", "bet_size": 25, "total_orders": 0,
            "total_wagered": 0, "total_pnl": 0,
        }),
        f"{_M}.calculate_brier_scores": MagicMock(return_value=None),
    }
    if overrides:
        defaults.update(overrides)

    mocks = {}
    for target, mock_obj in defaults.items():
        mocks[target] = stack.enter_context(patch(target, mock_obj))
    return mocks


# ── Tests ───────────────────────────────────────────────────────────────────


class TestCiRunLifecycle:
    """BTC 5m pipeline lifecycle — behavioral contracts."""

    def test_happy_path_completes_without_error(self):
        """Full cycle: fetch → resolve → predict → trade → score → dashboard. No crash."""
        from ci_run import main

        with ExitStack() as stack:
            _apply_patches(stack)
            main(candle_data=_fake_candle_data())

    def test_no_active_markets_exits_clean(self):
        """Empty market list + no unpredicted markets → clean exit."""
        from ci_run import main

        with ExitStack() as stack:
            mocks = _apply_patches(stack)
            # Override: market_fetch_fn returns empty
            # Since ci_run passes fetch_active_markets as a param, we patch at source
            with patch("ci_run.fetch_active_markets", return_value=[]):
                main(candle_data=_fake_candle_data())

    def test_candle_fetch_failure_continues(self):
        """When candle_data is None and candle_fetch returns None, pipeline still runs."""
        from ci_run import main

        with ExitStack() as stack:
            _apply_patches(stack)
            with patch("ci_run.fetch_btc_candles", return_value=None):
                main(candle_data=None)

    def test_kill_switch_prevents_trades(self):
        """Kill switch active → execute_trades() is NOT called."""
        from ci_run import main

        with ExitStack() as stack:
            mock_execute = MagicMock(return_value=[])
            _apply_patches(stack, {
                f"{_M}.is_kill_switched": MagicMock(return_value=True),
                f"{_M}.execute_trades": mock_execute,
            })
            main(candle_data=_fake_candle_data())

        mock_execute.assert_not_called()

    def test_candle_data_passthrough(self):
        """When candle_data kwarg is provided, candle_fetch_fn is NOT called.

        Tests the unified pipeline directly: when candle_data is provided,
        the candle_fetch_fn parameter should never be invoked.
        """
        from polymarket_pipeline import run_polymarket_pipeline
        from pathlib import Path
        import tempfile

        mock_fetch = MagicMock(return_value=_fake_candle_data())
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (1,)
        mock_db.execute.return_value.fetchall.return_value = []

        with ExitStack() as stack, tempfile.TemporaryDirectory() as td:
            _apply_patches(stack)
            run_polymarket_pipeline(
                pipeline_name="btc_5m",
                db_init_fn=MagicMock(return_value=mock_db),
                db_path=Path(td) / "test.db",
                market_fetch_fn=MagicMock(return_value=[_fake_market()]),
                candle_fetch_fn=mock_fetch,
                predict_fn=MagicMock(),
                candle_data=_fake_candle_data(),
            )

        # Main candle fetch (limit=DEFAULT_CANDLE_LIMIT) should NOT be called.
        # Shadow fetch (limit=SHADOW_CANDLE_LIMIT=30) may still be called — that's fine.
        from config import DEFAULT_CANDLE_LIMIT
        main_calls = [c for c in mock_fetch.call_args_list
                      if c == call(limit=DEFAULT_CANDLE_LIMIT)]
        assert len(main_calls) == 0, \
            f"candle_fetch_fn called with limit={DEFAULT_CANDLE_LIMIT} despite candle_data being provided"

    def test_market_fetch_exception_handled(self):
        """Exception in market_fetch_fn → caught gracefully, pipeline continues."""
        from ci_run import main

        with ExitStack() as stack:
            _apply_patches(stack)
            with patch("ci_run.fetch_active_markets",
                        side_effect=Exception("API timeout")):
                main(candle_data=_fake_candle_data())

    def test_trade_execution_exception_handled(self):
        """Exception in execute_trades → caught gracefully, scoring still runs."""
        from ci_run import main

        mock_score = MagicMock(return_value=None)
        with ExitStack() as stack:
            _apply_patches(stack, {
                f"{_M}.execute_trades": MagicMock(
                    side_effect=Exception("DB locked")
                ),
                f"{_M}.calculate_brier_scores": mock_score,
            })
            main(candle_data=_fake_candle_data())

        mock_score.assert_called_once()
