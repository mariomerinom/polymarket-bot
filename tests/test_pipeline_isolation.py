"""
test_pipeline_isolation.py — Behavioral tests for pipeline mode isolation.

Incident #66 (2026-04-06): trade.TRADING_ENABLED as a shared mutable global
caused BTC 5m to silently run in paper mode when another pipeline overwrote it.

These tests enforce:
  1. execute_trades() resolves mode from pipeline_name, not the global
  2. place_order() uses passed trading_enabled, not the global
  3. No ci_run file mutates trade.TRADING_ENABLED (AST guard)
  4. PID lock prevents dual engine processes
  5. Runtime assertion logs warning on global mismatch
  6. Unified pipeline passes pipeline_name through to execute_trades
"""

import ast
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

SRC_DIR = Path(__file__).parent.parent / "src"


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_test_db(tmp_path, pipeline_name="test"):
    """Create a minimal DB with markets + predictions + orders tables."""
    db_path = tmp_path / f"predictions_{pipeline_name}.db"
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT, cycle INTEGER, estimate REAL,
        conviction_score INTEGER, reasoning TEXT, agent TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT, prediction_id INTEGER, direction TEXT,
        size REAL, price_limit REAL, price_filled REAL, slippage_pct REAL,
        status TEXT, order_id TEXT, mode TEXT, reason TEXT,
        placed_at TEXT, filled_at TEXT, settled_at TEXT, pnl REAL,
        cycle INTEGER, order_type TEXT,
        edge REAL, best_bid REAL, best_ask REAL, spread REAL,
        action TEXT
    )""")
    db.commit()
    return db, db_path


# ── TestPipelineModeIsolation ─────────────────────────────────────────────


class TestPipelineModeIsolation:
    """execute_trades and place_order must use pipeline_name, not the global."""

    def test_execute_trades_uses_pipeline_name_not_global(self, tmp_path):
        """Flip TRADING_ENABLED to wrong value; execute_trades(pipeline_name=)
        still resolves the correct mode from pipeline_control."""
        import trade

        db, db_path = _make_test_db(tmp_path)
        # Insert a market + qualifying prediction
        now = datetime.now(timezone.utc)
        end = now.replace(hour=23, minute=59)
        db.execute(
            "INSERT INTO markets (id, question, end_date, fetched_at, resolved, price_yes, price_no) "
            "VALUES (?, 'Test?', ?, ?, 0, 0.55, 0.45)",
            ("mkt1", end.isoformat(), now.isoformat()),
        )
        db.execute(
            "INSERT INTO predictions (market_id, cycle, estimate, conviction_score, reasoning, agent) "
            "VALUES ('mkt1', 1, 0.65, 4, '{}', 'momentum_v4')",
        )
        db.commit()

        original = trade.TRADING_ENABLED
        try:
            # Set global to WRONG value (True), but pipeline is paper
            trade.TRADING_ENABLED = True

            with patch("pipeline_control.is_pipeline_live", return_value=False) as mock_live, \
                 patch("trade.compute_order", return_value=(None, "test skip")), \
                 patch("trade.run_shadow_logging"):
                trade.execute_trades(db, cycle=1, pipeline_name="eth_5m")

            mock_live.assert_called_with("eth_5m")
        finally:
            trade.TRADING_ENABLED = original
            db.close()

    def test_place_order_uses_passed_mode_not_global(self, tmp_path):
        """place_order(trading_enabled=False) logs paper even if global is True."""
        import trade

        db, _ = _make_test_db(tmp_path)
        original = trade.TRADING_ENABLED
        try:
            trade.TRADING_ENABLED = True  # Global says live

            order = trade.place_order(
                db, "mkt1", 1,
                {"direction": "BUY_YES", "size": 25, "price_limit": 0.55,
                 "slippage": 0.01, "side": "BUY", "token": "yes"},
                cycle=1, clob_token_id=None,
                trading_enabled=False,  # But we pass paper
            )

            assert order["mode"] == "paper"
            assert order["status"] == "paper"
        finally:
            trade.TRADING_ENABLED = original
            db.close()

    def test_eth_paper_does_not_corrupt_btc_live(self, tmp_path):
        """Running ETH (paper) then BTC (live) — BTC orders are mode=live."""
        import trade

        db, _ = _make_test_db(tmp_path)
        original = trade.TRADING_ENABLED

        try:
            # ETH paper order
            order_eth = trade.place_order(
                db, "eth_mkt", 1,
                {"direction": "BUY_YES", "size": 25, "price_limit": 0.55,
                 "slippage": 0.01, "side": "BUY", "token": "yes"},
                cycle=1, trading_enabled=False,
            )

            # BTC live order — should NOT be affected by ETH's paper mode
            with patch("trade._submit_clob_order", return_value={"orderID": "test123", "status": "LIVE"}):
                order_btc = trade.place_order(
                    db, "btc_mkt", 2,
                    {"direction": "BUY_YES", "size": 25, "price_limit": 0.55,
                     "slippage": 0.01, "side": "BUY", "token": "yes"},
                    cycle=1, clob_token_id="tok_btc_yes",
                    trading_enabled=True,
                )

            assert order_eth["mode"] == "paper"
            assert order_btc["mode"] == "live"
        finally:
            trade.TRADING_ENABLED = original
            db.close()


# ── TestStaticAnalysisGuards ──────────────────────────────────────────────


class TestStaticAnalysisGuards:
    """AST-level checks: no pipeline file may mutate trade.TRADING_ENABLED."""

    def test_no_direct_trading_enabled_mutation(self):
        """No ci_run or pipeline file should assign trade.TRADING_ENABLED.
        Incident: #66 dual-process paper mode (2026-04-06).
        """
        pipeline_files = list(SRC_DIR.glob("ci_run*.py")) + \
                         list(SRC_DIR.glob("polymarket_pipeline.py"))

        violations = []
        for f in pipeline_files:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and \
                           target.attr == "TRADING_ENABLED":
                            violations.append(f"{f.name}:{node.lineno}")

        assert not violations, \
            f"Files mutate trade.TRADING_ENABLED (incident #66): {violations}"

    def test_all_execute_trades_calls_pass_pipeline_name(self):
        """Every execute_trades() call in pipeline code must include pipeline_name=."""
        pipeline_files = list(SRC_DIR.glob("ci_run*.py")) + \
                         list(SRC_DIR.glob("polymarket_pipeline.py"))

        violations = []
        for f in pipeline_files:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = None
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr

                    if name == "execute_trades":
                        kw_names = [kw.arg for kw in node.keywords]
                        if "pipeline_name" not in kw_names:
                            violations.append(f"{f.name}:{node.lineno}")

        assert not violations, \
            f"execute_trades() calls missing pipeline_name=: {violations}"


# ── TestPIDLock ───────────────────────────────────────────────────────────


class TestPIDLock:
    """PID lock file prevents dual engine processes."""

    def test_pid_lock_prevents_dual_start(self, tmp_path):
        """If engine.pid exists with a live PID, acquire_pid_lock raises."""
        from botsy_engine import acquire_pid_lock, PIDLockError

        pid_file = tmp_path / "engine.pid"
        # Write our own PID (guaranteed alive)
        pid_file.write_text(str(os.getpid()))

        with pytest.raises(PIDLockError):
            acquire_pid_lock(pid_file)

    def test_stale_pid_lock_allows_start(self, tmp_path):
        """If engine.pid has a dead PID, acquire_pid_lock succeeds."""
        from botsy_engine import acquire_pid_lock

        pid_file = tmp_path / "engine.pid"
        # Write a definitely-dead PID
        pid_file.write_text("999999999")

        # Should not raise
        acquire_pid_lock(pid_file)
        # And PID file now has our PID
        assert pid_file.read_text() == str(os.getpid())


# ── TestRuntimeAssertion ──────────────────────────────────────────────────


class TestRuntimeAssertion:
    """Runtime defense-in-depth: warn when passed mode disagrees with global."""

    def test_place_order_logs_warning_on_global_mismatch(self, tmp_path, caplog):
        """Global=False, passed trading_enabled=True → warning logged, order placed as live."""
        import trade

        db, _ = _make_test_db(tmp_path)
        original = trade.TRADING_ENABLED

        try:
            trade.TRADING_ENABLED = False  # Global says paper

            with caplog.at_level(logging.WARNING), \
                 patch("trade._submit_clob_order", return_value={"orderID": "test123", "status": "LIVE"}):
                order = trade.place_order(
                    db, "mkt1", 1,
                    {"direction": "BUY_YES", "size": 25, "price_limit": 0.55,
                     "slippage": 0.01, "side": "BUY", "token": "yes"},
                    cycle=1, clob_token_id="tok_yes",
                    trading_enabled=True,  # Override says live
                )

            # Order should be live (passed value wins)
            assert order["mode"] == "live"
            # Warning should be logged
            assert any("TRADING_ENABLED" in r.message for r in caplog.records), \
                "Expected warning about global mismatch"
        finally:
            trade.TRADING_ENABLED = original
            db.close()


# ── TestUnifiedPipeline ───────────────────────────────────────────────────


class TestUnifiedPipeline:
    """Unified run_polymarket_pipeline() calls lifecycle steps correctly."""

    def test_unified_pipeline_calls_lifecycle_steps(self):
        """All lifecycle steps called in correct order."""
        from polymarket_pipeline import run_polymarket_pipeline

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (1,)  # cycle
        mock_db.execute.return_value.fetchall.return_value = []

        mock_init = MagicMock(return_value=mock_db)
        mock_fetch = MagicMock(return_value=[{"id": "mkt1", "question": "Test"}])
        mock_candle = MagicMock(return_value={"current_price": 85000, "candles": [], "1h_change_pct": 0, "trend": "up"})
        mock_predict = MagicMock()

        with patch("polymarket_pipeline.load_pipeline_config", return_value={"mode": "paper", "bet_size": None, "notes": ""}), \
             patch("polymarket_pipeline.is_pipeline_live", return_value=False), \
             patch("polymarket_pipeline.auto_resolve", return_value=0), \
             patch("polymarket_pipeline.store_markets"), \
             patch("polymarket_pipeline.has_unpredicted_market", return_value=False), \
             patch("polymarket_pipeline.is_kill_switched", return_value=False), \
             patch("polymarket_pipeline.ensure_orders_table"), \
             patch("polymarket_pipeline.execute_trades", return_value=[]) as mock_et, \
             patch("polymarket_pipeline.get_trading_summary", return_value={"mode": "PAPER", "bet_size": 25, "total_orders": 0, "total_wagered": 0, "total_pnl": 0}), \
             patch("polymarket_pipeline.calculate_brier_scores", return_value=None):

            run_polymarket_pipeline(
                pipeline_name="btc_5m",
                db_init_fn=mock_init,
                db_path=Path("/tmp/test.db"),
                market_fetch_fn=mock_fetch,
                candle_fetch_fn=mock_candle,
                predict_fn=mock_predict,
            )

        mock_init.assert_called_once()
        mock_fetch.assert_called_once()
        mock_et.assert_called_once()

    def test_unified_pipeline_passes_pipeline_name_to_execute_trades(self):
        """execute_trades receives pipeline_name= argument."""
        from polymarket_pipeline import run_polymarket_pipeline

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = (1,)
        mock_db.execute.return_value.fetchall.return_value = []

        with patch("polymarket_pipeline.load_pipeline_config", return_value={"mode": "paper", "bet_size": None, "notes": ""}), \
             patch("polymarket_pipeline.is_pipeline_live", return_value=False), \
             patch("polymarket_pipeline.auto_resolve", return_value=0), \
             patch("polymarket_pipeline.store_markets"), \
             patch("polymarket_pipeline.has_unpredicted_market", return_value=False), \
             patch("polymarket_pipeline.is_kill_switched", return_value=False), \
             patch("polymarket_pipeline.ensure_orders_table"), \
             patch("polymarket_pipeline.execute_trades", return_value=[]) as mock_et, \
             patch("polymarket_pipeline.get_trading_summary", return_value={"mode": "PAPER", "bet_size": 25, "total_orders": 0, "total_wagered": 0, "total_pnl": 0}), \
             patch("polymarket_pipeline.calculate_brier_scores", return_value=None):

            run_polymarket_pipeline(
                pipeline_name="eth_5m",
                db_init_fn=MagicMock(return_value=mock_db),
                db_path=Path("/tmp/test.db"),
                market_fetch_fn=MagicMock(return_value=[{"id": "m1"}]),
                candle_fetch_fn=MagicMock(return_value={"current_price": 2100, "candles": [], "1h_change_pct": 0, "trend": "up"}),
                predict_fn=MagicMock(),
            )

        # Verify pipeline_name was passed
        _, kwargs = mock_et.call_args
        assert kwargs.get("pipeline_name") == "eth_5m", \
            f"Expected pipeline_name='eth_5m', got {kwargs}"
