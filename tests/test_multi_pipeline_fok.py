"""
test_multi_pipeline_fok.py — Behavioral tests for multi-pipeline FOK unification.

TDD: Written BEFORE implementation. Verifies that ALL Polymarket pipelines
(BTC 5m, BTC 15m, ETH 5m) get WS bid/ask data and use FOK execution.

Covers:
  - Token subscription across all pipeline DBs
  - BTC 15m trade execution (newly added)
  - FOK path activation for ETH and BTC 15m when WS data present
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_market_db(db_path, market_ids):
    """Create a DB with markets table and insert unresolved markets."""
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    for mid in market_ids:
        db.execute(
            "INSERT OR IGNORE INTO markets (id, question, end_date, fetched_at, resolved) "
            "VALUES (?, 'Test', ?, ?, 0)",
            (
                mid,
                (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    db.commit()
    db.close()


# ── TestTokenSubscription ──────────────────────────────────────────────


class TestTokenSubscription:
    """_get_active_token_ids() must query all pipeline DBs."""

    def test_token_ids_from_all_dbs(self, tmp_path):
        """Returns token IDs from predictions.db, predictions_15m.db, AND predictions_eth.db."""
        # Create 3 DBs with distinct markets
        _make_market_db(tmp_path / "predictions.db", ["btc5m_mkt"])
        _make_market_db(tmp_path / "predictions_15m.db", ["btc15m_mkt"])
        _make_market_db(tmp_path / "predictions_eth.db", ["eth5m_mkt"])

        # Each market resolves to unique token pair
        token_map = {
            "btc5m_mkt": {"yes": "tok_btc5m_yes", "no": "tok_btc5m_no"},
            "btc15m_mkt": {"yes": "tok_btc15m_yes", "no": "tok_btc15m_no"},
            "eth5m_mkt": {"yes": "tok_eth_yes", "no": "tok_eth_no"},
        }

        from botsy_engine import BotsyEngine
        engine = BotsyEngine.__new__(BotsyEngine)

        with patch("botsy_engine.DATA_DIR", tmp_path), \
             patch("clob_depth.get_clob_tokens", side_effect=lambda mid: token_map.get(mid)):
            ids = engine._get_active_token_ids()

        ids_set = set(ids)
        # All 6 tokens present (3 markets × 2 tokens each)
        assert "tok_btc5m_yes" in ids_set
        assert "tok_btc5m_no" in ids_set
        assert "tok_btc15m_yes" in ids_set
        assert "tok_eth_yes" in ids_set
        assert "tok_eth_no" in ids_set
        assert len(ids_set) == 6

    def test_missing_db_skipped_gracefully(self, tmp_path):
        """If predictions_eth.db doesn't exist, BTC tokens still returned."""
        _make_market_db(tmp_path / "predictions.db", ["btc_mkt"])
        # predictions_15m.db and predictions_eth.db do NOT exist

        token_map = {"btc_mkt": {"yes": "tok_yes", "no": "tok_no"}}

        from botsy_engine import BotsyEngine
        engine = BotsyEngine.__new__(BotsyEngine)

        with patch("botsy_engine.DATA_DIR", tmp_path), \
             patch("clob_depth.get_clob_tokens", side_effect=lambda mid: token_map.get(mid)):
            ids = engine._get_active_token_ids()

        assert "tok_yes" in ids
        assert "tok_no" in ids

    def test_deduplicates_shared_markets(self, tmp_path):
        """BTC 5m and 15m share market IDs — token IDs deduplicated."""
        shared_mkt = "shared_btc_mkt"
        _make_market_db(tmp_path / "predictions.db", [shared_mkt])
        _make_market_db(tmp_path / "predictions_15m.db", [shared_mkt])

        token_map = {shared_mkt: {"yes": "tok_shared_yes", "no": "tok_shared_no"}}

        from botsy_engine import BotsyEngine
        engine = BotsyEngine.__new__(BotsyEngine)

        with patch("botsy_engine.DATA_DIR", tmp_path), \
             patch("clob_depth.get_clob_tokens", side_effect=lambda mid: token_map.get(mid)):
            ids = engine._get_active_token_ids()

        # Should have exactly 2 unique tokens, not 4
        assert len(ids) == 2
        assert set(ids) == {"tok_shared_yes", "tok_shared_no"}

    def test_expired_unresolved_markets_are_not_subscribed(self, tmp_path):
        """Expired rows that failed settlement must not poison WS subscriptions."""
        stale = "stale_unresolved"
        current = "current_unresolved"
        _make_market_db(tmp_path / "predictions.db", [stale, current])

        db = sqlite3.connect(str(tmp_path / "predictions.db"))
        db.execute(
            "UPDATE markets SET end_date = ? WHERE id = ?",
            (
                (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                stale,
            ),
        )
        db.execute(
            "UPDATE markets SET end_date = ? WHERE id = ?",
            (
                (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                current,
            ),
        )
        db.commit()
        db.close()

        token_map = {
            stale: {"yes": "tok_stale_yes", "no": "tok_stale_no"},
            current: {"yes": "tok_current_yes", "no": "tok_current_no"},
        }

        from botsy_engine import BotsyEngine
        engine = BotsyEngine.__new__(BotsyEngine)

        with patch("botsy_engine.DATA_DIR", tmp_path), \
             patch("clob_depth.get_clob_tokens", side_effect=lambda mid: token_map.get(mid)):
            ids = set(engine._get_active_token_ids())

        assert ids == {"tok_current_yes", "tok_current_no"}


# ── TestBtc15mTradeExecution ───────────────────────────────────────────


class TestBtc15mTradeExecution:
    """ci_run_15m.py must call execute_trades() gated by pipeline_control.

    After unification, lifecycle lives in polymarket_pipeline.
    """

    _M = "polymarket_pipeline"

    def test_15m_pipeline_calls_execute_trades(self):
        """ci_run_15m.main() calls execute_trades when not paused."""
        import ci_run_15m

        fake_market = [{"id": "mkt_test", "question": "Test"}]
        with patch(f"{self._M}.load_pipeline_config", return_value={"mode": "paper", "bet_size": None, "notes": ""}), \
             patch(f"{self._M}.is_pipeline_live", return_value=False), \
             patch(f"{self._M}.store_markets"), \
             patch(f"{self._M}.auto_resolve", return_value=0), \
             patch(f"{self._M}.has_unpredicted_market", return_value=False), \
             patch(f"{self._M}.is_kill_switched", return_value=False), \
             patch(f"{self._M}.ensure_orders_table"), \
             patch(f"{self._M}.execute_trades", return_value=[]) as mock_et, \
             patch(f"{self._M}.get_trading_summary", return_value={"mode": "paper", "bet_size": 25, "total_orders": 0, "total_wagered": 0, "total_pnl": 0}), \
             patch(f"{self._M}.calculate_brier_scores", return_value=None), \
             patch("ci_run_15m.fetch_active_markets_15m", return_value=fake_market):
            ci_run_15m.main()

        mock_et.assert_called_once()

    def test_15m_respects_pipeline_control(self):
        """Paper mode → execute_trades called with pipeline_name='btc_15m'.
        Mode resolution happens inside trade.execute_trades via pipeline_control.
        """
        import ci_run_15m

        fake_market = [{"id": "mkt_test", "question": "Test"}]
        with patch(f"{self._M}.load_pipeline_config", return_value={"mode": "paper", "bet_size": None, "notes": ""}), \
             patch(f"{self._M}.is_pipeline_live", return_value=False), \
             patch(f"{self._M}.store_markets"), \
             patch(f"{self._M}.auto_resolve", return_value=0), \
             patch(f"{self._M}.has_unpredicted_market", return_value=False), \
             patch(f"{self._M}.is_kill_switched", return_value=False), \
             patch(f"{self._M}.ensure_orders_table"), \
             patch(f"{self._M}.execute_trades", return_value=[]) as mock_et, \
             patch(f"{self._M}.get_trading_summary", return_value={"mode": "paper", "bet_size": 25, "total_orders": 0, "total_wagered": 0, "total_pnl": 0}), \
             patch(f"{self._M}.calculate_brier_scores", return_value=None), \
             patch("ci_run_15m.fetch_active_markets_15m", return_value=fake_market):
            ci_run_15m.main()

        # Verify pipeline_name passed correctly
        mock_et.assert_called_once()
        _, kwargs = mock_et.call_args
        assert kwargs.get("pipeline_name") == "btc_15m"

    def test_15m_kill_switch_blocks_trades(self, capsys):
        """Kill switch active → execute_trades NOT called."""
        import ci_run_15m

        fake_market = [{"id": "mkt_test", "question": "Test"}]
        with patch(f"{self._M}.load_pipeline_config", return_value={"mode": "paper", "bet_size": None, "notes": ""}), \
             patch(f"{self._M}.is_pipeline_live", return_value=False), \
             patch(f"{self._M}.store_markets"), \
             patch(f"{self._M}.auto_resolve", return_value=0), \
             patch(f"{self._M}.has_unpredicted_market", return_value=False), \
             patch(f"{self._M}.is_kill_switched", return_value=True), \
             patch(f"{self._M}.ensure_orders_table"), \
             patch(f"{self._M}.execute_trades") as mock_et, \
             patch(f"{self._M}.calculate_brier_scores", return_value=None), \
             patch("ci_run_15m.fetch_active_markets_15m", return_value=fake_market):
            ci_run_15m.main()

        mock_et.assert_not_called()
        captured = capsys.readouterr()
        assert "KILLED" in captured.out


# ── TestFOKAcrossAllPipelines ──────────────────────────────────────────


class TestFOKAcrossAllPipelines:
    """When WS bid/ask is available, all pipelines produce FOK orders."""

    def test_eth_gets_fok_with_ws_data(self):
        """ETH pipeline with WS bid/ask produces order_type=fok, not gtc."""
        from trade import compute_order

        pred = {"estimate": 0.62, "conviction_score": 4, "agent": "momentum_eth"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_bid": 0.54, "_yes_best_ask": 0.56, "_yes_spread": 0.02,
            "_no_best_bid": 0.44, "_no_best_ask": 0.46, "_no_spread": 0.02,
        }

        order, reason = compute_order(pred, market)
        assert order is not None, f"Should produce order: {reason}"
        assert order["order_type"] == "fak"
        assert order["action"] == "fak_take"
        # best_ask + cushion(min(0.01, spread/2=0.01, alpha)) = 0.56 + 0.01
        assert order["price_limit"] == 0.57

    def test_15m_gets_fok_with_ws_data(self):
        """BTC 15m pipeline with WS bid/ask produces order_type=fok, not gtc."""
        from trade import compute_order

        pred = {"estimate": 0.62, "conviction_score": 4, "agent": "momentum_v4"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_bid": 0.54, "_yes_best_ask": 0.56, "_yes_spread": 0.02,
            "_no_best_bid": 0.44, "_no_best_ask": 0.46, "_no_spread": 0.02,
        }

        order, reason = compute_order(pred, market)
        assert order is not None, f"Should produce order: {reason}"
        assert order["order_type"] == "fak"
        assert order["action"] == "fak_take"
