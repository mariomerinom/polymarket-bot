"""Tests for manual_test_bet.py — $5 smoke-test script."""

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
        """Script must refuse to run when TRADING_ENABLED=false."""
        with patch("manual_test_bet.TRADING_ENABLED", False):
            from manual_test_bet import main
            with pytest.raises(SystemExit) as exc_info:
                with patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
                    main()
            assert exc_info.value.code == 1


class TestPredictionStorage:
    def test_stores_prediction_as_manual(self):
        """Prediction must have agent='manual_test_user', conviction=0."""
        db = _make_db()
        # Insert the market for FK
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )

        # Wrap DB so main()'s db.close() doesn't destroy our test connection
        wrapper = MagicMock(wraps=db)
        wrapper.close = MagicMock()  # no-op close

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=wrapper), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("manual_test_bet.store_markets"), \
             patch("manual_test_bet._get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("manual_test_bet.place_order", return_value={"status": "submitted", "order_id": "abc123"}), \
             patch("builtins.input", return_value="YES"), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
            from manual_test_bet import main
            main()

        row = db.execute(
            "SELECT agent, conviction_score, confidence, regime FROM predictions"
        ).fetchone()
        assert row is not None
        assert row[0] == "manual_test_user"
        assert row[1] == 0
        assert row[2] == "manual"
        assert row[3] == "manual_test"

        # Check reasoning JSON
        reasoning_raw = db.execute("SELECT reasoning FROM predictions").fetchone()[0]
        reasoning = json.loads(reasoning_raw)
        assert reasoning["type"] == "manual_test_bet"
        assert reasoning["initiated_by"] == "user"
        db.close()


class TestBetSize:
    def test_bet_size_is_5(self):
        """Order size must always be $5."""
        from manual_test_bet import TEST_BET_SIZE
        assert TEST_BET_SIZE == 5

    def test_order_params_use_5(self):
        """place_order receives size=5."""
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )

        captured_params = {}

        def mock_place_order(db, market_id, pred_id, order_params, cycle, clob_token_id=None):
            captured_params.update(order_params)
            return {"status": "submitted", "order_id": "abc"}

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=db), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("manual_test_bet.store_markets"), \
             patch("manual_test_bet._get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("manual_test_bet.place_order", side_effect=mock_place_order), \
             patch("builtins.input", return_value="YES"), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
            from manual_test_bet import main
            main()

        assert captured_params["size"] == 5
        db.close()


class TestDirection:
    def test_up_uses_yes_token(self):
        """UP direction → token='yes', side='buy'."""
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )

        captured = {}

        def mock_place(db, market_id, pred_id, order_params, cycle, clob_token_id=None):
            captured["params"] = order_params
            captured["clob_token_id"] = clob_token_id
            return {"status": "submitted", "order_id": "abc"}

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=db), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("manual_test_bet.store_markets"), \
             patch("manual_test_bet._get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("manual_test_bet.place_order", side_effect=mock_place), \
             patch("builtins.input", return_value="YES"), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
            from manual_test_bet import main
            main()

        assert captured["params"]["direction"] == "UP"
        assert captured["params"]["token"] == "yes"
        assert captured["params"]["side"] == "buy"
        assert captured["clob_token_id"] == "tok_yes_abc"
        db.close()

    def test_down_uses_no_token(self):
        """DOWN direction → token='no', side='buy'."""
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )

        captured = {}

        def mock_place(db, market_id, pred_id, order_params, cycle, clob_token_id=None):
            captured["params"] = order_params
            captured["clob_token_id"] = clob_token_id
            return {"status": "submitted", "order_id": "abc"}

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=db), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("manual_test_bet.store_markets"), \
             patch("manual_test_bet._get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("manual_test_bet.place_order", side_effect=mock_place), \
             patch("builtins.input", return_value="YES"), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "DOWN"]):
            from manual_test_bet import main
            main()

        assert captured["params"]["direction"] == "DOWN"
        assert captured["params"]["token"] == "no"
        assert captured["params"]["side"] == "buy"
        assert captured["clob_token_id"] == "tok_no_xyz"
        db.close()


class TestNoMarkets:
    def test_exits_when_no_markets(self):
        """Empty market list → clean exit with error."""
        db = _make_db()

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=db), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[]), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
            from manual_test_bet import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        db.close()


class TestAbort:
    def test_abort_on_non_yes(self):
        """Typing anything other than YES aborts."""
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, question, category, end_date, volume, "
            "price_yes, price_no, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2026-04-04T00:00:00')",
            (FAKE_MARKET["id"], FAKE_MARKET["question"], FAKE_MARKET["category"],
             FAKE_MARKET["end_date"], FAKE_MARKET["volume"],
             FAKE_MARKET["price_yes"], FAKE_MARKET["price_no"]),
        )

        with patch("manual_test_bet.TRADING_ENABLED", True), \
             patch("manual_test_bet.init_db", return_value=db), \
             patch("manual_test_bet.ensure_orders_table"), \
             patch("manual_test_bet.fetch_active_markets", return_value=[FAKE_MARKET]), \
             patch("manual_test_bet.store_markets"), \
             patch("manual_test_bet._get_clob_tokens_safe", return_value=FAKE_TOKENS), \
             patch("builtins.input", return_value="no"), \
             patch("sys.argv", ["manual_test_bet.py", "--direction", "UP"]):
            from manual_test_bet import main
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        db.close()
