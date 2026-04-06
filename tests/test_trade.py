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


    def test_consecutive_loss_breaker(self):
        """After N consecutive losses, should_trade returns False."""
        from datetime import datetime, timezone, timedelta
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        # Use recent timestamps (within 8h cooldown window)
        now = datetime.now(timezone.utc)
        for i in range(5):
            ts = (now - timedelta(minutes=10 + i)).isoformat()
            db.execute("""
                INSERT INTO orders (market_id, direction, size, status, mode,
                    placed_at, settled_at, pnl)
                VALUES (?, 'UP', 25, 'settled', 'paper', ?, ?, -25)
            """, (f"mkt_loss_{i}", ts, ts))
        db.commit()
        pred = {"conviction_score": 4, "estimate": 0.65}
        ok, reason = should_trade(pred, db)
        assert not ok
        assert "consecutive_loss_breaker" in reason
        db.close()

    def test_consecutive_loss_resets_on_win(self):
        """A win resets the consecutive loss streak."""
        from datetime import datetime, timezone, timedelta
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        # 3 losses then 1 win then 2 losses = streak of 2 (not 5)
        # Use recent timestamps within 8h cooldown window
        now = datetime.now(timezone.utc)
        pnls = [-25, -25, -25, 30, -25, -25]
        for i, pnl in enumerate(pnls):
            ts = (now - timedelta(minutes=60 - i * 10)).isoformat()
            db.execute("""
                INSERT INTO orders (market_id, direction, size, status, mode,
                    placed_at, settled_at, pnl)
                VALUES (?, 'UP', 25, 'settled', 'paper', ?, ?, ?)
            """, (f"mkt_{i}", ts, ts, pnl))
        db.commit()
        pred = {"conviction_score": 4, "estimate": 0.65}
        ok, reason = should_trade(pred, db)
        assert ok  # Only 2 consecutive losses, not 5
        db.close()

    def test_consecutive_loss_auto_resets_after_cooldown(self):
        """Regression: consecutive loss breaker must auto-reset after 8h to
        prevent permanent deadlock (incident 2026-04-06: 5 losses on Apr 5
        locked out all trading for 30+ hours since breaker can't get a win
        to reset itself if it blocks all trades).
        """
        from datetime import datetime, timezone, timedelta
        from trade import should_trade, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        # 5 losses, all > 8 hours ago → breaker should auto-reset
        old = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
        for i in range(5):
            db.execute("""
                INSERT INTO orders (market_id, direction, size, status, mode,
                    placed_at, settled_at, pnl)
                VALUES (?, 'UP', 25, 'settled', 'paper', ?, ?, -25)
            """, (f"mkt_old_{i}", old, old))
        db.commit()
        pred = {"conviction_score": 4, "estimate": 0.65}
        ok, reason = should_trade(pred, db)
        assert ok, f"breaker should auto-reset after 8h cooldown, got: {reason}"
        db.close()

    # max_drawdown_breaker removed — cold start bug tripped at 78.5% on $17 peak.
    # Daily loss limit + consecutive loss breaker are sufficient protection.


class TestComputeOrder:
    """Order parameter computation."""

    def test_up_prediction_buys_yes(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "UP"
        assert order["token"] == "yes"
        assert order["size"] == 25  # flat bet size

    def test_down_prediction_buys_no(self):
        from trade import compute_order
        pred = {"estimate": 0.38, "conviction_score": 3}
        market = {"price_yes": 0.55, "price_no": 0.45,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "DOWN"
        assert order["token"] == "no"

    def test_thin_book_caps_size(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50,
                  "_clob_verified": {"yes": True, "no": True}}
        liquidity = {"max_bet_2pct": 15.0}  # Only $15 available
        order, reason = compute_order(pred, market, liquidity)
        assert order is not None
        assert order["size"] <= 15  # Capped by book

    def test_very_thin_book_rejects(self):
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50,
                  "_clob_verified": {"yes": True, "no": True}}
        liquidity = {"max_bet_2pct": 3.0}  # Only $3 — not worth it
        order, reason = compute_order(pred, market, liquidity)
        assert order is None
        assert "book_too_thin" in reason

    def test_price_cap_limits_slippage_up(self):
        """When market is far below estimate, limit price is capped at market + spread + fill priority."""
        from trade import compute_order, MAX_SLIPPAGE_SPREAD, FILL_PRIORITY_SPREAD
        pred = {"estimate": 0.62, "conviction_score": 4}
        market = {"price_yes": 0.34,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        # Should be capped at 0.34 + 0.05 + 0.02 = 0.41, not 0.64
        max_allowed = 0.34 + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
        assert order["price_limit"] <= max_allowed + 0.001
        assert order["price_limit"] < 0.62  # Much less than raw estimate

    def test_price_cap_limits_slippage_down(self):
        """DOWN prediction: limit price capped at market_no + spread + fill priority."""
        from trade import compute_order, MAX_SLIPPAGE_SPREAD, FILL_PRIORITY_SPREAD
        pred = {"estimate": 0.38, "conviction_score": 3}  # DOWN
        market = {"price_yes": 0.55, "price_no": 0.45,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        max_allowed = 0.45 + MAX_SLIPPAGE_SPREAD + FILL_PRIORITY_SPREAD
        assert order["price_limit"] <= max_allowed + 0.001

    def test_price_cap_no_effect_when_estimate_close(self):
        """When estimate is close to market, fill priority spread still applies."""
        from trade import compute_order, FILL_PRIORITY_SPREAD
        pred = {"estimate": 0.52, "conviction_score": 4}
        market = {"price_yes": 0.50,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        # Price should be estimate + FILL_PRIORITY_SPREAD
        expected = 0.52 + FILL_PRIORITY_SPREAD
        assert abs(order["price_limit"] - expected) < 0.001

    def test_slippage_computed_and_returned(self):
        """compute_order returns slippage and market_price."""
        from trade import compute_order
        pred = {"estimate": 0.62, "conviction_score": 4}
        market = {"price_yes": 0.49,
                  "_clob_verified": {"yes": True, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert "slippage" in order
        assert "market_price" in order
        assert order["market_price"] == 0.49
        # Slippage should be price_limit - market_price
        assert order["slippage"] == round(order["price_limit"] - 0.49, 4)

    # ── CLOB verification gate tests ──

    def test_skips_up_without_clob_yes(self):
        """UP prediction must be skipped when YES token has no CLOB price."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50,
                  "_clob_verified": {"yes": False, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is None
        assert "no CLOB price for YES token" in reason

    def test_skips_down_without_clob_no(self):
        """DOWN prediction must be skipped when NO token has no CLOB price."""
        from trade import compute_order
        pred = {"estimate": 0.38, "conviction_score": 3}
        market = {"price_yes": 0.55, "price_no": 0.45,
                  "_clob_verified": {"yes": True, "no": False}}
        order, reason = compute_order(pred, market)
        assert order is None
        assert "no CLOB price for NO token" in reason

    def test_skips_when_no_clob_verified_flag(self):
        """Legacy market_row without _clob_verified must skip (safe default)."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50}  # no _clob_verified
        order, reason = compute_order(pred, market)
        assert order is None
        assert "no CLOB price" in reason

    def test_up_trades_with_clob_yes_only(self):
        """UP prediction only needs YES CLOB verified, not NO."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4}
        market = {"price_yes": 0.50, "price_no": 0.50,
                  "_clob_verified": {"yes": True, "no": False}}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "UP"

    def test_down_trades_with_clob_no_only(self):
        """DOWN prediction only needs NO CLOB verified, not YES."""
        from trade import compute_order
        pred = {"estimate": 0.38, "conviction_score": 3}
        market = {"price_yes": 0.55, "price_no": 0.45,
                  "_clob_verified": {"yes": False, "no": True}}
        order, reason = compute_order(pred, market)
        assert order is not None
        assert order["direction"] == "DOWN"


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


class TestGetBetSize:
    """ETH-specific sizing: tiered by conviction, capped by book depth."""

    def test_btc_flat_25(self):
        from trade import get_bet_size
        row = {"agent": "momentum_rule", "conviction_score": 4}
        assert get_bet_size(row) == 25

    def test_eth_conv3(self):
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 3}
        assert get_bet_size(row) == 25

    def test_eth_conv4(self):
        """ETH is flat $25 via pipelines.json (same as BTC)."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 4}
        assert get_bet_size(row) == 25

    def test_eth_conv5(self):
        """ETH is flat $25 via pipelines.json (same as BTC)."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 5}
        assert get_bet_size(row) == 25

    def test_eth_capped_by_liquidity(self):
        """ETH flat $25 from pipelines.json override — liquidity cap doesn't apply."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 5}
        liq = {"max_bet_2pct": 60}
        assert get_bet_size(row, liquidity=liq) == 25

    def test_eth_no_liquidity_returns_base(self):
        """ETH flat $25 from pipelines.json override."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 4}
        assert get_bet_size(row, liquidity=None) == 25

    def test_eth_liquidity_error_returns_base(self):
        """ETH flat $25 from pipelines.json override."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 4}
        liq = {"error": "no data"}
        assert get_bet_size(row, liquidity=liq) == 25

    def test_eth_conv0_returns_flat(self):
        """ETH flat $25 from pipelines.json override — conviction doesn't matter."""
        from trade import get_bet_size
        row = {"agent": "momentum_eth", "conviction_score": 0}
        assert get_bet_size(row) == 25


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


class TestStartupValidation:
    """Fail fast if live mode is misconfigured."""

    def test_live_without_key_raises(self, monkeypatch):
        monkeypatch.setenv("TRADING_ENABLED", "true")
        monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
        import importlib
        import trade
        with __import__("pytest").raises(RuntimeError, match="POLYMARKET_PRIVATE_KEY not set"):
            importlib.reload(trade)
        # Restore to paper mode for other tests
        monkeypatch.setenv("TRADING_ENABLED", "false")
        importlib.reload(trade)

    def test_paper_without_key_ok(self, monkeypatch):
        monkeypatch.setenv("TRADING_ENABLED", "false")
        monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
        import importlib
        import trade
        importlib.reload(trade)  # Should not raise
        assert not trade.TRADING_ENABLED


class TestResolvedMarketGuard:
    """Orders should not be placed on resolved markets."""

    def test_no_orders_on_resolved_market(self):
        from trade import execute_trades, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        # Insert a RESOLVED market and a qualifying prediction
        db.execute("""INSERT INTO markets (id, question, end_date, price_yes, price_no, resolved, outcome)
            VALUES ('mkt_resolved', 'BTC Up?', '2099-01-01T00:00:00Z', 0.50, 0.50, 1, 1)""")
        db.execute("""INSERT INTO predictions
            (id, market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (1, 'mkt_resolved', 'momentum_rule', 0.65, 0.15, 'high', '{}', '2026-01-01T00:00:00', 10, 4)""")
        db.commit()

        orders = execute_trades(db, cycle=10)
        assert len(orders) == 0, "Should not place orders on resolved markets"
        db.close()


class TestWALMode:
    """SQLite WAL mode and busy timeout."""

    def test_wal_enabled_after_ensure_orders(self):
        from trade import ensure_orders_table
        import sqlite3
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE markets (id TEXT)")  # minimal schema
        ensure_orders_table(db)
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        # In-memory DBs use "memory" journal mode, but WAL pragma was called
        # Just verify it doesn't crash
        assert mode in ("wal", "memory")
        db.close()


class TestExecuteTrades:
    """Full execution flow."""

    def test_executes_qualifying_predictions(self):
        from unittest.mock import patch
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

        # Mock CLOB token resolution so the CLOB-verified gate passes
        from orderbook_cache import TokenEntry
        from datetime import datetime as dt, timezone as tz
        now = dt.now(tz.utc).isoformat()
        fake_entry = TokenEntry(mid=0.50, best_bid=0.49, best_ask=0.51, spread=0.02, updated_at=now)
        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}
        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", return_value=0.50), \
             patch("trade._get_live_token_entry", return_value=fake_entry):
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
        from unittest.mock import patch
        from trade import execute_trades, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        db.execute("""INSERT INTO markets (id, question, end_date, price_yes, price_no, resolved)
            VALUES ('mkt_3', 'BTC Up?', '2099-01-01T00:00:00Z', 0.50, 0.50, 0)""")
        db.execute("""INSERT INTO predictions
            (id, market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (1, 'mkt_3', 'momentum_rule', 0.65, 0.15, 'high', '{}', '2026-01-01T00:00:00', 10, 4)""")
        db.commit()

        from orderbook_cache import TokenEntry
        from datetime import datetime as dt, timezone as tz
        now = dt.now(tz.utc).isoformat()
        fake_entry = TokenEntry(mid=0.50, best_bid=0.49, best_ask=0.51, spread=0.02, updated_at=now)
        fake_tokens = {"yes": "tok_yes", "no": "tok_no"}
        with patch("clob_depth.get_clob_tokens_safe", return_value=fake_tokens), \
             patch("trade._get_live_token_mid", return_value=0.50), \
             patch("trade._get_live_token_entry", return_value=fake_entry):
            orders_1 = execute_trades(db, cycle=10)
            orders_2 = execute_trades(db, cycle=10)  # Second call, same cycle
        assert len(orders_1) == 1
        assert len(orders_2) == 0  # No duplicate
        db.close()


class TestLiveOrderbook:
    """Tests for the live orderbook cache integration."""

    def test_fresh_cache_returns_mid(self, tmp_path, monkeypatch):
        import json
        from datetime import datetime, timezone
        import trade

        cache_file = tmp_path / "live_orderbook.json"
        cache = {
            "tokens": {
                "tok_yes_123": {
                    "mid": 0.62,
                    "spread": 0.04,
                    "best_bid": 0.60,
                    "best_ask": 0.64,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "bids": [{"price": "0.60", "size": "100"}],
                    "asks": [{"price": "0.64", "size": "100"}],
                },
            },
        }
        cache_file.write_text(json.dumps(cache))
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", cache_file)

        result = trade._get_live_token_mid("tok_yes_123")
        assert result == 0.62

    def test_stale_cache_returns_none(self, tmp_path, monkeypatch):
        import json
        import trade

        cache_file = tmp_path / "live_orderbook.json"
        cache = {
            "tokens": {
                "tok_stale": {
                    "mid": 0.55,
                    "updated_at": "2020-01-01T00:00:00+00:00",  # very old
                },
            },
        }
        cache_file.write_text(json.dumps(cache))
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", cache_file)

        result = trade._get_live_token_mid("tok_stale")
        assert result is None

    def test_missing_file_returns_none(self, tmp_path, monkeypatch):
        import trade
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", tmp_path / "nope.json")
        result = trade._get_live_token_mid("any_token")
        assert result is None

    def test_corrupt_json_returns_none(self, tmp_path, monkeypatch):
        import trade
        cache_file = tmp_path / "live_orderbook.json"
        cache_file.write_text("NOT JSON {{{")
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", cache_file)
        result = trade._get_live_token_mid("any_token")
        assert result is None

    def test_out_of_range_mid_returns_none(self, tmp_path, monkeypatch):
        import json
        from datetime import datetime, timezone
        import trade

        cache_file = tmp_path / "live_orderbook.json"
        cache = {
            "tokens": {
                "tok_bad": {
                    "mid": 1.5,  # out of range
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        }
        cache_file.write_text(json.dumps(cache))
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", cache_file)

        result = trade._get_live_token_mid("tok_bad")
        assert result is None

    def test_missing_token_returns_none(self, tmp_path, monkeypatch):
        import json
        from datetime import datetime, timezone
        import trade

        cache_file = tmp_path / "live_orderbook.json"
        cache = {
            "tokens": {
                "tok_other": {
                    "mid": 0.50,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        }
        cache_file.write_text(json.dumps(cache))
        monkeypatch.setattr(trade, "LIVE_ORDERBOOK_PATH", cache_file)

        result = trade._get_live_token_mid("tok_not_in_cache")
        assert result is None


class TestClobTokenImport:
    """Regression: trade.py must import the correct clob token function."""

    def test_clob_token_import_from_clob_depth(self):
        """Verify trade.py imports get_clob_tokens_safe from clob_depth (not predict).

        History: Originally trade.py imported _get_clob_tokens from predict, which was
        renamed to _get_clob_tokens_safe. The silent except swallowed ImportError.
        Phase B Step 4 moved it to clob_depth.get_clob_tokens_safe (its proper home).
        """
        source = Path(__file__).parent.parent / "src" / "trade.py"
        content = source.read_text()
        assert "get_clob_tokens_safe" in content, \
            "trade.py must import get_clob_tokens_safe"
        assert "from clob_depth import get_clob_tokens_safe" in content, \
            "trade.py must import get_clob_tokens_safe from clob_depth (not predict)"
