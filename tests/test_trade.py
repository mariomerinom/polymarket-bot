"""Tests for trade.py — order execution module."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db():
    """Create an in-memory DB with markets + predictions + orders tables."""
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    return db


class TestShouldTrade:
    """Gate logic: which predictions become orders."""

    def test_conviction_too_low(self):
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        pred = {"conviction_score": 2, "estimate": 0.65}
        ok, reason = should_trade(pred, db)
        assert not ok
        assert "conviction_too_low" in reason
        db.close()

    def test_edge_too_small(self):
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        pred = {"conviction_score": 4, "estimate": 0.52}
        ok, reason = should_trade(pred, db)
        assert not ok
        assert "edge_too_small" in reason
        db.close()

    def test_qualifying_prediction_passes(self):
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        pred = {"conviction_score": 4, "estimate": 0.65}
        ok, reason = should_trade(pred, db)
        assert ok
        assert reason == "ok"
        db.close()


class TestComputeOrder:
    """Order parameter computation."""

    def test_up_prediction_buys_yes(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "UP"
        assert order["token"] == "yes"
        assert order["size"] == 25  # flat bet size

    def test_down_prediction_buys_no(self):
        from trade import compute_order
        pred = {"estimate": 0.38, "conviction_score": 3}
        market = {"price_yes": 0.55, "price_no": 0.45}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "DOWN"
        assert order["token"] == "no"

    def test_thin_book_caps_size(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50}
        liquidity = {"max_bet_2pct": 15.0}  # Only $15 available
        order, reason = compute_order(pred, market, liquidity)
        assert order is not None
        assert order["size"] <= 15  # Capped by book

    def test_very_thin_book_rejects(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50}
        liquidity = {"max_bet_2pct": 3.0}  # Only $3 — not worth it
        order, reason = compute_order(pred, market, liquidity)
        assert order is None
        assert "book_too_thin" in reason


class TestPlaceOrder:
    """Order placement in paper mode."""

    def test_paper_mode_logs_order(self):
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "buy", "token": "yes",
            "size": 25, "price_limit": 0.52,
        }
        result = place_order(db, "mkt_123", 1, order_params, cycle=5)
        assert result["status"] == "paper"
        assert result["mode"] == "paper"

        # Verify stored in DB
        row = db.execute("SELECT * FROM orders").fetchone()
        assert row is not None
        db.close()

    def test_paper_mode_no_sdk_required(self):
        """Paper mode must work without py-clob-client installed."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "DOWN", "side": "buy", "token": "no",
            "size": 25, "price_limit": 0.48,
        }
        # This should NOT raise ImportError
        result = place_order(db, "mkt_456", 2, order_params, cycle=1)
        assert result["status"] == "paper"
        db.close()


class TestKillSwitch:
    """Kill switch halts all trading."""

    def test_env_kill_switch(self, monkeypatch):
        from trade import is_kill_switched
        monkeypatch.setenv("KILL_SWITCH", "true")
        assert is_kill_switched()

    def test_no_kill_switch(self, monkeypatch):
        from trade import is_kill_switched
        monkeypatch.setenv("KILL_SWITCH", "false")
        # Also ensure no kill file
        assert not is_kill_switched()


class TestExecuteTrades:
    """Full execution flow."""

    def test_executes_qualifying_predictions(self):
        from trade import execute_trades, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        # Insert a market and a qualifying prediction
        db.execute("""INSERT INTO markets (id, question, end_date, price_yes, price_no, resolved)
            VALUES ('mkt_1', 'BTC Up?', '2099-01-01T00:00:00Z', 0.50, 0.50, 0)""")
        db.execute("""INSERT INTO predictions
            (id, market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (1, 'mkt_1', 'momentum_rule', 0.65, 0.15, 'high', '{}', '2026-01-01T00:00:00', 10, 4)""")
        db.commit()

        orders = execute_trades(db, cycle=10)
        assert len(orders) == 1
        assert orders[0]["status"] == "paper"
        assert orders[0]["direction"] == "UP"
        assert orders[0]["size"] == 25
        db.close()

    def test_skips_low_conviction(self):
        from trade import execute_trades, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        db.execute("""INSERT INTO markets (id, question, end_date, price_yes, price_no, resolved)
            VALUES ('mkt_2', 'BTC Up?', '2099-01-01T00:00:00Z', 0.50, 0.50, 0)""")
        db.execute("""INSERT INTO predictions
            (id, market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (1, 'mkt_2', 'momentum_rule', 0.65, 0.15, 'low', '{}', '2026-01-01T00:00:00', 10, 2)""")
        db.commit()

        orders = execute_trades(db, cycle=10)
        assert len(orders) == 0
        db.close()

    def test_no_duplicate_orders(self):
        """Same prediction in same cycle should not place two orders."""
        from trade import execute_trades, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        db.execute("""INSERT INTO markets (id, question, end_date, price_yes, price_no, resolved)
            VALUES ('mkt_3', 'BTC Up?', '2099-01-01T00:00:00Z', 0.50, 0.50, 0)""")
        db.execute("""INSERT INTO predictions
            (id, market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (1, 'mkt_3', 'momentum_rule', 0.65, 0.15, 'high', '{}', '2026-01-01T00:00:00', 10, 4)""")
        db.commit()

        orders_1 = execute_trades(db, cycle=10)
        orders_2 = execute_trades(db, cycle=10)  # Second call, same cycle
        assert len(orders_1) == 1
        assert len(orders_2) == 0  # No duplicate
        db.close()
