"""
test_clob_resolution.py — CLOB price resolution behavioral tests.

Tests the CLOB price resolution path inside execute_trades() (trade.py lines 713-774).
This is where the $2.18 pricing bug lived. Tests assert WHAT the system does (contracts),
not HOW it's organized — they survive refactoring.

Phase A1 of TDD-first refactoring plan (docs/plans/tdd-plan.md).
"""

import os
import sys
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trade import execute_trades, ensure_orders_table, compute_order
from predict import store_prediction


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_db():
    """Create in-memory DB with full schema for execute_trades()."""
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, market_id TEXT, agent TEXT,
        estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
        predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    ensure_orders_table(db)
    db.commit()
    return db


def _insert_market(db, market_id="mkt_clob_test", price_yes=0.50):
    """Insert a market with given Gamma price."""
    db.execute(
        "INSERT INTO markets (id, question, category, end_date, volume, "
        "price_yes, price_no, resolved, outcome) "
        "VALUES (?, 'Test BTC market', 'crypto', '2099-01-01T00:00:00Z', "
        "1000, ?, ?, 0, NULL)",
        (market_id, price_yes, round(1 - price_yes, 4)),
    )
    db.commit()


def _insert_qualifying_prediction(db, market_id="mkt_clob_test", cycle=1,
                                  estimate=0.62, conviction=4):
    """Insert a prediction that passes all gates (conv >= 3, edge > threshold)."""
    signal = {
        "should_trade": True,
        "estimate": estimate,
        "confidence": "medium",
        "direction": "UP" if estimate > 0.5 else "DOWN",
        "streak": 3,
        "reason": "ride_streak",
    }
    regime = {
        "label": "HIGH_VOL / TRENDING",
        "autocorrelation": 0.25,
        "volatility": 0.15,
        "is_mean_reverting": False,
    }
    store_prediction(db, market_id, signal, regime, cycle, mkt_price=0.50)
    # Override conviction if needed
    if conviction != 3:
        db.execute(
            "UPDATE predictions SET conviction_score = ? WHERE cycle = ? AND market_id = ?",
            (conviction, cycle, market_id),
        )
        db.commit()


# Suppress shadow imports that would fail in test env
_SHADOW_PATCHES = [
    patch("trade.shadow_log_indicators", create=True, side_effect=ImportError),
    patch("trade.shadow_log_cycle", create=True, side_effect=ImportError),
]


def _shadow_context():
    """Context manager to suppress shadow indicator imports in execute_trades()."""
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        # Shadow imports are inside try/except in execute_trades, so they fail silently.
        # No patching needed — they already handle ImportError gracefully.
        yield
    return ctx()


# ── Tests ───────────────────────────────────────────────────────────────────


class TestClobResolution:
    """CLOB price resolution path — behavioral contracts."""

    def test_ws_hit_uses_live_price(self):
        """When WS cache has fresh price for both tokens, order uses WS price, not Gamma."""
        from orderbook_cache import TokenEntry
        from datetime import datetime, timezone
        db = _make_db()
        _insert_market(db, price_yes=0.50)  # Gamma says 0.50
        _insert_qualifying_prediction(db, estimate=0.62, conviction=4)

        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}
        ws_prices = {"tok_yes": 0.55, "tok_no": 0.45}
        now = datetime.now(timezone.utc).isoformat()
        ws_entries = {
            "tok_yes": TokenEntry(mid=0.55, best_bid=0.54, best_ask=0.56, spread=0.02, updated_at=now),
            "tok_no": TokenEntry(mid=0.45, best_bid=0.44, best_ask=0.46, spread=0.02, updated_at=now),
        }

        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", side_effect=lambda tid: ws_prices.get(tid)), \
             patch("trade._get_live_token_entry", side_effect=lambda tid: ws_entries.get(tid)):
            orders = execute_trades(db, cycle=1)

        # Order should exist and use WS price, not Gamma
        assert len(orders) == 1
        order = orders[0]
        assert order["direction"] == "UP"
        assert order["status"] == "paper"
        # FAK: price_limit = best_ask + cushion = 0.56 + 0.01 = 0.57
        assert order["price_limit"] == 0.57
        assert order["price_limit"] is not None

        db.close()

    def test_ws_miss_falls_back_to_rest(self):
        """When WS cache is None for a token, REST orderbook is fetched and used."""
        db = _make_db()
        _insert_market(db, price_yes=0.50)
        _insert_qualifying_prediction(db, estimate=0.62, conviction=4)

        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}
        rest_depth = {"mid": 0.53, "spread": 0.02, "depth_2pct": 500}

        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", return_value=None), \
             patch("clob_depth.get_order_book", return_value={"bids": [], "asks": []}) as mock_ob, \
             patch("clob_depth.analyze_depth", return_value=rest_depth):
            orders = execute_trades(db, cycle=1)

        # REST fallback was called for both tokens (2 in resolution + 1 in diagnostics)
        assert mock_ob.call_count >= 2

        # Order placed with REST price (not skipped)
        assert len(orders) == 1
        assert orders[0]["status"] == "paper"

        db.close()

    def test_both_miss_skips_trade(self):
        """When both WS and REST fail, order is skipped (not placed with Gamma price)."""
        db = _make_db()
        _insert_market(db, price_yes=0.50)
        _insert_qualifying_prediction(db, estimate=0.62, conviction=4)

        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}

        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", return_value=None), \
             patch("clob_depth.get_order_book", return_value=None), \
             patch("clob_depth.analyze_depth", return_value=None):
            orders = execute_trades(db, cycle=1)

        # No order placed — CLOB gate blocks it
        assert len(orders) == 0

        db.close()

    def test_stale_ws_cache_triggers_rest_fallback(self):
        """WS cache returning None (stale >10s) triggers REST fallback."""
        db = _make_db()
        _insert_market(db, price_yes=0.50)
        _insert_qualifying_prediction(db, estimate=0.62, conviction=4)

        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}
        rest_depth = {"mid": 0.54, "spread": 0.02, "depth_2pct": 500}

        # WS returns None (stale cache), REST provides fallback
        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", return_value=None), \
             patch("clob_depth.get_order_book", return_value={"bids": [], "asks": []}) as mock_ob, \
             patch("clob_depth.analyze_depth", return_value=rest_depth):
            orders = execute_trades(db, cycle=1)

        # REST was called as fallback
        assert mock_ob.call_count >= 1
        assert len(orders) == 1

        db.close()

    def test_clob_verified_flag_propagates(self):
        """_clob_verified dict is set correctly and compute_order() gates on it."""
        # Test compute_order directly — UP requires yes=True, DOWN requires no=True
        pred_up = {"estimate": 0.62, "conviction_score": 4, "agent": "momentum_v4"}
        pred_down = {"estimate": 0.38, "conviction_score": 4, "agent": "momentum_v4"}

        # Both verified → both should trade
        market_both = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
        }
        order_up, reason_up = compute_order(pred_up, market_both)
        order_down, reason_down = compute_order(pred_down, market_both)
        assert order_up is not None, f"UP should trade: {reason_up}"
        assert order_down is not None, f"DOWN should trade: {reason_down}"

        # YES not verified → UP blocked, DOWN still works
        market_no_yes = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": False, "no": True},
        }
        order_up, reason_up = compute_order(pred_up, market_no_yes)
        order_down, reason_down = compute_order(pred_down, market_no_yes)
        assert order_up is None, "UP should be blocked without YES verification"
        assert "no CLOB price" in reason_up
        assert order_down is not None, f"DOWN should work: {reason_down}"

        # NO not verified → DOWN blocked, UP still works
        market_no_no = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": False},
        }
        order_up, reason_up = compute_order(pred_up, market_no_no)
        order_down, reason_down = compute_order(pred_down, market_no_no)
        assert order_up is not None, f"UP should work: {reason_up}"
        assert order_down is None, "DOWN should be blocked without NO verification"
        assert "no CLOB price" in reason_down

        # No _clob_verified at all (legacy) → both blocked
        market_legacy = {"price_yes": 0.55, "price_no": 0.45}
        order_up, reason_up = compute_order(pred_up, market_legacy)
        order_down, reason_down = compute_order(pred_down, market_legacy)
        assert order_up is None, "UP should be blocked without _clob_verified"
        assert order_down is None, "DOWN should be blocked without _clob_verified"

    def test_token_resolution_failure_skips(self):
        """When _get_clob_tokens_safe() throws, trade is skipped."""
        db = _make_db()
        _insert_market(db, price_yes=0.50)
        _insert_qualifying_prediction(db, estimate=0.62, conviction=4)

        with patch("clob_depth.get_clob_tokens_safe", side_effect=Exception("API down")), \
             patch("trade._get_live_token_mid", return_value=None):
            orders = execute_trades(db, cycle=1)

        # Token resolution failed → no _clob_verified → compute_order returns None → skipped
        assert len(orders) == 0

        db.close()
