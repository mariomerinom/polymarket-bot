"""Tests for smoke_bet.py — $5 pipeline smoke test."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


FAKE_MARKET = {
    "id": "test-market-001",
    "question": "Bitcoin Up or Down 12:00PM-12:05PM",
    "category": "crypto",
    "end_date": "2026-04-04T18:05:00Z",
    "volume": 500.0,
    "price_yes": 0.55,
    "price_no": 0.45,
    "clob_token_yes": "tok_yes_abc",
    "clob_token_no": "tok_no_xyz",
}

FAKE_TOKENS = {"yes": "tok_yes_abc", "no": "tok_no_xyz"}

FAKE_CLOB_ANALYSIS = {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56, "spread": 0.02}

FAKE_BTC_DATA = {
    "candles": [
        {"open": 67000, "close": 67100, "high": 67200, "low": 66900, "volume": 10,
         "direction": "UP", "time": "12:00", "body_pct": 0.15, "wick_ratio": 0.3},
        {"open": 67100, "close": 67200, "high": 67300, "low": 67000, "volume": 12,
         "direction": "UP", "time": "12:05", "body_pct": 0.15, "wick_ratio": 0.3},
        {"open": 67200, "close": 67300, "high": 67400, "low": 67100, "volume": 11,
         "direction": "UP", "time": "12:10", "body_pct": 0.15, "wick_ratio": 0.3},
        {"open": 67300, "close": 67400, "high": 67500, "low": 67200, "volume": 13,
         "direction": "UP", "time": "12:15", "body_pct": 0.15, "wick_ratio": 0.3},
        {"open": 67400, "close": 67500, "high": 67600, "low": 67300, "volume": 14,
         "direction": "UP", "time": "12:20", "body_pct": 0.15, "wick_ratio": 0.3},
    ],
    "current_price": 67500,
    "1h_change_pct": 0.1,
}


def _make_db():
    """Create in-memory DB with markets + predictions + orders tables."""
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
    db.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY, market_id TEXT, prediction_id INTEGER,
        direction TEXT, size REAL, price_limit REAL, price_filled REAL,
        slippage_pct REAL, status TEXT DEFAULT 'pending', order_id TEXT,
        mode TEXT, reason TEXT, placed_at TEXT, filled_at TEXT,
        settled_at TEXT, pnl REAL, cycle INTEGER
    )""")
    return db


class TestRequiresTrading:
    def test_exits_when_trading_disabled(self):
        """Script must refuse to run in live mode when TRADING_ENABLED=false."""
        with patch("smoke_bet.TRADING_ENABLED", False), \
             patch("smoke_bet.fetch_btc_candles", return_value=FAKE_BTC_DATA), \
             patch("smoke_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("smoke_bet.get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("smoke_bet.init_db", return_value=_make_db()), \
             patch("smoke_bet.ensure_orders_table"), \
             patch("smoke_bet.store_markets"), \
             patch("sys.argv", ["smoke_bet.py"]):
            from smoke_bet import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestBetSize:
    def test_bet_size_is_5(self):
        """Order size must always be $5."""
        from smoke_bet import BET_SIZE
        assert BET_SIZE == 5


class TestPredictionStorage:
    def test_stores_prediction_as_smoke(self):
        """Prediction must have agent='smoke_test', conviction=0."""
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )
        wrapper = MagicMock(wraps=db)
        wrapper.close = MagicMock()

        with patch("smoke_bet.TRADING_ENABLED", True), \
             patch("smoke_bet.fetch_btc_candles", return_value=FAKE_BTC_DATA), \
             patch("smoke_bet.init_db", return_value=wrapper), \
             patch("smoke_bet.ensure_orders_table"), \
             patch("smoke_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("smoke_bet.store_markets"), \
             patch("smoke_bet.get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("smoke_bet.get_order_book", return_value={"bids": [], "asks": []}), \
             patch("smoke_bet.analyze_depth", return_value=FAKE_CLOB_ANALYSIS), \
             patch("smoke_bet.place_order", return_value={"status": "submitted", "order_id": "abc"}), \
             patch("sys.argv", ["smoke_bet.py"]):
            from smoke_bet import main
            main()

        row = db.execute(
            "SELECT agent, conviction_score, regime FROM predictions"
        ).fetchone()
        assert row is not None
        assert row[0] == "smoke_test"
        assert row[1] == 0
        assert row[2] == "smoke_test"
        db.close()


class TestNoMarkets:
    def test_exits_when_no_markets(self):
        """Empty market list -> clean exit with error."""
        with patch("smoke_bet.fetch_btc_candles", return_value=FAKE_BTC_DATA), \
             patch("smoke_bet.fetch_active_markets", return_value=[]), \
             patch("sys.argv", ["smoke_bet.py"]):
            from smoke_bet import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestDryRun:
    def test_dry_run_does_not_place(self):
        """--dry-run prints plan but touches nothing."""
        with patch("smoke_bet.fetch_btc_candles", return_value=FAKE_BTC_DATA), \
             patch("smoke_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("smoke_bet.get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("smoke_bet.get_order_book", return_value={"bids": [], "asks": []}), \
             patch("smoke_bet.analyze_depth", return_value=FAKE_CLOB_ANALYSIS), \
             patch("smoke_bet.place_order") as mock_place, \
             patch("sys.argv", ["smoke_bet.py", "--dry-run"]):
            from smoke_bet import main
            main()
            mock_place.assert_not_called()
