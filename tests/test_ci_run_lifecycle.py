"""
test_ci_run_lifecycle.py — BTC 5m pipeline lifecycle behavioral tests.

Tests ci_run.main() — the live production pipeline — end-to-end with mocked
I/O boundaries. Verifies contracts, not structure.

Phase A2 of TDD-first refactoring plan (docs/plans/tdd-plan.md).
"""

import os
import sys
import sqlite3
from contextlib import ExitStack
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Fixtures ────────────────────────────────────────────────────────────────


def _fake_candle_data():
    """Minimal candle_data dict that ci_run.main() expects."""
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
    """Apply standard mocks for ci_run.main() using an ExitStack. Returns mock dict."""
    defaults = {
        "ci_run.fetch_active_markets": MagicMock(return_value=[_fake_market()]),
        "ci_run.store_markets": MagicMock(),
        "ci_run.auto_resolve": MagicMock(return_value=0),
        "ci_run.fetch_btc_candles": MagicMock(return_value=_fake_candle_data()),
        "ci_run.run_predictions": MagicMock(),
        "ci_run.execute_trades": MagicMock(return_value=[]),
        "ci_run.is_kill_switched": MagicMock(return_value=False),
        "ci_run.ensure_orders_table": MagicMock(),
        "ci_run.get_trading_summary": MagicMock(return_value={
            "mode": "PAPER", "bet_size": 25, "total_orders": 0,
            "total_wagered": 0, "total_pnl": 0,
        }),
        "ci_run.calculate_brier_scores": MagicMock(return_value=None),
        "ci_run._generate_dashboard": MagicMock(),
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
            _apply_patches(stack, {
                "ci_run.fetch_active_markets": MagicMock(return_value=[]),
            })
            main(candle_data=_fake_candle_data())

    def test_candle_fetch_failure_continues(self):
        """When candle_data is None and fetch_btc_candles returns None, pipeline still runs."""
        from ci_run import main

        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run.fetch_btc_candles": MagicMock(return_value=None),
            })
            main(candle_data=None)

    def test_kill_switch_prevents_trades(self):
        """Kill switch active → execute_trades() is NOT called."""
        from ci_run import main

        mock_execute = MagicMock(return_value=[])
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run.is_kill_switched": MagicMock(return_value=True),
                "ci_run.execute_trades": mock_execute,
            })
            main(candle_data=_fake_candle_data())

        mock_execute.assert_not_called()

    def test_candle_data_passthrough(self):
        """When candle_data kwarg is provided, fetch_btc_candles is NOT called."""
        from ci_run import main

        mock_fetch = MagicMock(return_value=_fake_candle_data())
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run.fetch_btc_candles": mock_fetch,
            })
            main(candle_data=_fake_candle_data())

        mock_fetch.assert_not_called()

    def test_dashboard_generated(self):
        """Dashboard generation is called after scoring."""
        from ci_run import main

        mock_dashboard = MagicMock()
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run._generate_dashboard": mock_dashboard,
            })
            main(candle_data=_fake_candle_data())

        mock_dashboard.assert_called_once()

    def test_market_fetch_exception_handled(self):
        """Exception in fetch_active_markets → caught gracefully, pipeline continues."""
        from ci_run import main

        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run.fetch_active_markets": MagicMock(
                    side_effect=Exception("API timeout")
                ),
            })
            main(candle_data=_fake_candle_data())

    def test_trade_execution_exception_handled(self):
        """Exception in execute_trades → caught gracefully, scoring still runs."""
        from ci_run import main

        mock_score = MagicMock(return_value=None)
        with ExitStack() as stack:
            _apply_patches(stack, {
                "ci_run.execute_trades": MagicMock(
                    side_effect=Exception("DB locked")
                ),
                "ci_run.calculate_brier_scores": mock_score,
            })
            main(candle_data=_fake_candle_data())

        mock_score.assert_called_once()
