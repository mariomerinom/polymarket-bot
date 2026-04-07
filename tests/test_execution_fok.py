"""
test_execution_fok.py — Tests for Phase 1 FOK execution layer.

TDD: Written BEFORE implementation. Tests the behavioral contracts from
docs/specs/spec_execution.md Phase 1 (AC-1 through AC-7).

Covers: edge computation against execution price, FOK-or-skip gating,
schema migration, FOK metadata logging, rejection rate alerting.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db():
    """In-memory DB with predictions + orders tables."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, estimate REAL,
        conviction_score INTEGER, agent TEXT, predicted_at TEXT,
        edge REAL, reasoning TEXT, cycle INTEGER, regime TEXT
    )""")
    db.commit()
    return db


# ── AC-1: Edge computation against execution price ───────────────────────


class TestEdgeComputation:
    """AC-1.1/1.2: Edge computed against best_ask (BUY) or best_bid (SELL)."""

    def test_buy_edge_against_best_ask(self):
        """UP: edge = p - yes_best_ask (AC-1.2)."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, reason = compute_order(pred, market)
        assert order is not None
        # edge = 0.65 - 0.57 = 0.08
        assert abs(order["edge"] - 0.08) < 0.001
        assert order["direction"] == "UP"

    def test_sell_edge_against_no_best_ask(self):
        """DOWN: edge = (1-p) - no_best_ask (AC-1.2)."""
        from trade import compute_order
        pred = {"estimate": 0.35, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, reason = compute_order(pred, market)
        assert order is not None
        # DOWN buys NO. edge = (1-0.35) - 0.47 = 0.65 - 0.47 = 0.18
        assert abs(order["edge"] - 0.18) < 0.001
        assert order["direction"] == "DOWN"


# ── AC-2: Take or Skip ───────────────────────────────────────────────────


class TestTakeOrSkip:
    """AC-2.1/2.2: FOK when edge >= min_edge, skip otherwise."""

    def test_strong_edge_places_fok(self):
        """Edge above min_edge => order placed (AC-2.1)."""
        from trade import compute_order
        pred = {"estimate": 0.70, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, reason = compute_order(pred, market)
        assert order is not None
        # edge = 0.70 - 0.57 = 0.13; min_edge = 0.04 + 0.02 = 0.06; take
        assert order["action"] == "fak_take"

    def test_weak_edge_skips(self):
        """Edge below min_edge => skip, no order (AC-2.2)."""
        from trade import compute_order
        pred = {"estimate": 0.55, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.50, "price_no": 0.50,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.54, "_yes_best_bid": 0.46, "_yes_spread": 0.08,
            "_no_best_ask": 0.54, "_no_best_bid": 0.46, "_no_spread": 0.08,
        }
        order, reason = compute_order(pred, market)
        # edge = 0.55 - 0.54 = 0.01; min_edge = 0.08 + 0.02 = 0.10; skip
        assert order is None
        assert "low_edge" in reason

    def test_fok_price_is_best_ask_for_buy(self):
        """FOK submits at best_ask for UP (AC-2.1, AC-3.1)."""
        from trade import compute_order
        pred = {"estimate": 0.70, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, _ = compute_order(pred, market)
        # best_ask + cushion(min(0.01, 0.04/2, alpha)) = 0.57 + 0.01
        assert order["price_limit"] == 0.58

    def test_fok_price_is_no_best_ask_for_sell(self):
        """FOK submits at no_best_ask for DOWN."""
        from trade import compute_order
        pred = {"estimate": 0.30, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, _ = compute_order(pred, market)
        assert order is not None
        # no_best_ask + cushion = 0.47 + 0.01
        assert order["price_limit"] == 0.48

    def test_no_bid_ask_falls_back_to_legacy(self):
        """Without _yes_best_ask, falls back to legacy GTC logic (paper pipelines)."""
        from trade import compute_order
        pred = {"estimate": 0.65, "conviction_score": 4, "agent": "momentum_eth"}
        market = {
            "price_yes": 0.50, "price_no": 0.50,
            "_clob_verified": {"yes": True, "no": True},
            # No _yes_best_ask, _yes_best_bid, _yes_spread
        }
        order, reason = compute_order(pred, market)
        # Should still work using legacy path
        assert order is not None
        assert order["direction"] == "UP"


# ── AC-4: Position Sizing ─��──────────────────────────────────────────────


class TestFOKSizing:
    """AC-4.1/4.2: Flat $25, no taker reduction."""

    def test_fok_size_flat_25(self):
        """FOK orders use flat $25 (AC-4.1)."""
        from trade import compute_order
        pred = {"estimate": 0.70, "conviction_score": 5, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, _ = compute_order(pred, market)
        assert order["size"] == 25.0


# ── AC-6: Logging / Metadata ─────────────────────────────────────��───────


class TestFOKMetadata:
    """AC-6.1: Orders include edge, spread, bid, ask, action."""

    def test_order_includes_fok_fields(self):
        """FOK order dict has all required metadata."""
        from trade import compute_order
        pred = {"estimate": 0.70, "conviction_score": 4, "agent": "momentum_rule"}
        market = {
            "price_yes": 0.55, "price_no": 0.45,
            "_clob_verified": {"yes": True, "no": True},
            "_yes_best_ask": 0.57, "_yes_best_bid": 0.53, "_yes_spread": 0.04,
            "_no_best_ask": 0.47, "_no_best_bid": 0.43, "_no_spread": 0.04,
        }
        order, _ = compute_order(pred, market)
        assert "edge" in order
        assert "spread" in order
        assert "best_ask" in order
        assert "best_bid" in order
        assert "action" in order
        assert order["action"] == "fak_take"
        assert order["spread"] == 0.04
        assert order["best_ask"] == 0.57
        assert order["best_bid"] == 0.53


# ── Schema Migration ─────────────────────────────────────────────────────


class TestSchemaMigration:
    """Orders table has FOK columns."""

    def test_new_columns_exist(self):
        """ensure_orders_table adds FOK columns."""
        from trade import ensure_orders_table
        db = sqlite3.connect(":memory:")
        ensure_orders_table(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(orders)").fetchall()}
        for col in ["order_type", "edge", "best_bid", "best_ask", "spread", "action"]:
            assert col in cols, f"Missing column: {col}"
        db.close()

    def test_migration_idempotent(self):
        """Running ensure_orders_table twice doesn't crash."""
        from trade import ensure_orders_table
        db = sqlite3.connect(":memory:")
        ensure_orders_table(db)
        ensure_orders_table(db)  # Second call should be safe
        db.close()


# ── FOK order storage ────────────────────────────────────────────────────


class TestFOKOrderStorage:
    """FOK metadata flows through place_order to DB."""

    def test_paper_mode_stores_fok_metadata(self):
        """Paper order stores edge, spread, bid, ask, action in DB."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        order_params = {
            "direction": "UP", "side": "buy", "token": "yes",
            "size": 25, "price_limit": 0.57, "slippage": 0.0,
            "market_price": 0.55,
            "edge": 0.08, "spread": 0.04, "best_bid": 0.53,
            "best_ask": 0.57, "action": "fok_take", "order_type": "fok",
        }
        result = place_order(db, "mkt_123", 1, order_params, cycle=5)
        assert result["status"] == "paper"

        row = db.execute(
            "SELECT edge, best_bid, best_ask, spread, action, order_type FROM orders WHERE id=1"
        ).fetchone()
        assert row is not None
        assert row["edge"] == 0.08
        assert row["best_bid"] == 0.53
        assert row["best_ask"] == 0.57
        assert row["spread"] == 0.04
        assert row["action"] == "fok_take"
        assert row["order_type"] == "fok"
        db.close()


# ── FOK Rejection Rate Alert (AC-3.3) ────────────────────────────────────


class TestFOKRejectionAlert:
    """AC-3.3: Alert when FOK rejection rate > 30% over 50 orders."""

    def test_alert_when_above_30pct(self):
        """20 rejected out of 50 = 40% => alert."""
        from trade import check_fok_rejection_rate, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        for i in range(20):
            db.execute(
                "INSERT INTO orders (market_id, direction, size, status, mode, "
                "placed_at, cycle, order_type, action) "
                "VALUES (?, 'UP', 25, 'fok_rejected', 'live', '2026-04-06', 1, 'fok', 'fok_rejected')",
                (f"mkt_{i}",))
        for i in range(30):
            db.execute(
                "INSERT INTO orders (market_id, direction, size, status, mode, "
                "placed_at, cycle, order_type, action) "
                "VALUES (?, 'UP', 25, 'filled', 'live', '2026-04-06', 1, 'fok', 'fok_filled')",
                (f"mkt_f_{i}",))
        db.commit()
        rate, alert = check_fok_rejection_rate(db)
        assert abs(rate - 0.4) < 0.01
        assert alert is True
        db.close()

    def test_no_alert_when_below_30pct(self):
        """10 rejected out of 50 = 20% => no alert."""
        from trade import check_fok_rejection_rate, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        for i in range(10):
            db.execute(
                "INSERT INTO orders (market_id, direction, size, status, mode, "
                "placed_at, cycle, order_type, action) "
                "VALUES (?, 'UP', 25, 'fok_rejected', 'live', '2026-04-06', 1, 'fok', 'fok_rejected')",
                (f"mkt_{i}",))
        for i in range(40):
            db.execute(
                "INSERT INTO orders (market_id, direction, size, status, mode, "
                "placed_at, cycle, order_type, action) "
                "VALUES (?, 'UP', 25, 'filled', 'live', '2026-04-06', 1, 'fok', 'fok_filled')",
                (f"mkt_f_{i}",))
        db.commit()
        rate, alert = check_fok_rejection_rate(db)
        assert abs(rate - 0.2) < 0.01
        assert alert is False
        db.close()

    def test_insufficient_orders_no_alert(self):
        """Fewer than 50 FOK orders => no alert (not enough data)."""
        from trade import check_fok_rejection_rate, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)
        for i in range(10):
            db.execute(
                "INSERT INTO orders (market_id, direction, size, status, mode, "
                "placed_at, cycle, order_type, action) "
                "VALUES (?, 'UP', 25, 'fok_rejected', 'live', '2026-04-06', 1, 'fok', 'fok_rejected')",
                (f"mkt_{i}",))
        db.commit()
        rate, alert = check_fok_rejection_rate(db)
        assert alert is False
        db.close()


# ── resolve_clob_prices bid/ask passthrough ──────────────────────────────


class TestResolvePassesBidAsk:
    """resolve_clob_prices populates per-token bid/ask/spread."""

    def test_ws_cache_passes_bid_ask(self, tmp_path):
        """WS cache with bid/ask => market_row has _yes_best_ask etc."""
        import trade
        from orderbook_cache import OrderbookCache, TokenEntry

        now = datetime.now(timezone.utc).isoformat()
        cache_data = {"version": 2, "tokens": {
            "tok_yes": {"mid": 0.55, "best_bid": 0.54, "best_ask": 0.56,
                        "spread": 0.02, "updated_at": now},
            "tok_no": {"mid": 0.45, "best_bid": 0.44, "best_ask": 0.46,
                       "spread": 0.02, "updated_at": now},
        }}
        cache_file = tmp_path / "live_orderbook.json"
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(trade, "LIVE_ORDERBOOK_PATH", cache_file):
            pred = {"price_yes": 0.50, "market_id": "mkt_1"}
            tokens = {"yes": "tok_yes", "no": "tok_no"}
            market_row, _ = trade.resolve_clob_prices(pred, tokens)

        assert market_row.get("_yes_best_ask") == 0.56
        assert market_row.get("_yes_best_bid") == 0.54
        assert market_row.get("_yes_spread") == 0.02
        assert market_row.get("_no_best_ask") == 0.46
        assert market_row.get("_no_best_bid") == 0.44
        assert market_row.get("_no_spread") == 0.02

    def test_no_tokens_no_bid_ask(self):
        """Without tokens, no bid/ask fields."""
        import trade
        pred = {"price_yes": 0.50, "market_id": "mkt_1"}
        market_row, _ = trade.resolve_clob_prices(pred, None)
        assert "_yes_best_ask" not in market_row

    def test_rest_fallback_passes_bid_ask(self):
        """REST fallback populates bid/ask from analyze_depth."""
        import trade

        fake_depth = {
            "mid": 0.55, "best_bid": 0.54, "best_ask": 0.56, "spread": 0.02,
            "spread_pct": 3.6, "max_bet_2pct": 500, "max_bet_5pct": 1000,
            "depth_levels": 10,
        }

        with patch.object(trade, "LIVE_ORDERBOOK_PATH", Path("/nonexistent")), \
             patch("clob_depth.get_order_book", return_value={"bids": [], "asks": []}), \
             patch("clob_depth.analyze_depth", return_value=fake_depth):
            pred = {"price_yes": 0.50, "market_id": "mkt_1"}
            tokens = {"yes": "tok_yes", "no": "tok_no"}
            market_row, _ = trade.resolve_clob_prices(pred, tokens)

        assert market_row.get("_yes_best_ask") == 0.56
        assert market_row.get("_yes_best_bid") == 0.54


# ── AC-3: FOK order submission ─────────────────────────────────────────


class TestFOKSubmission:
    """AC-3.1/3.2: Live FOK orders use MarketOrderArgs + post_order(FOK)."""

    def test_fok_filled_sets_status_filled(self):
        """FOK fill → status='filled', action='fok_filled', filled_at set."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "BUY", "size": 25,
            "price_limit": 0.56, "order_type": "fok", "action": "fok_take",
            "edge": 0.06, "spread": 0.02, "best_bid": 0.54, "best_ask": 0.56,
        }

        fake_response = {"orderID": "fok_123", "status": "MATCHED", "success": True}
        with patch("trade.TRADING_ENABLED", True), \
             patch("trade._submit_fak_order", return_value=fake_response):
            result = place_order(db, "mkt_1", 1, order_params, cycle=1,
                                 clob_token_id="tok_yes")

        assert result["status"] == "filled"
        assert result["action"] == "fak_filled"
        assert result["filled_at"] is not None
        assert result["order_id"] == "fok_123"

        db.close()

    def test_fok_rejected_sets_status_rejected(self):
        """FOK reject → status='fok_rejected', action='fok_rejected'."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "BUY", "size": 25,
            "price_limit": 0.56, "order_type": "fok", "action": "fok_take",
            "edge": 0.06, "spread": 0.02, "best_bid": 0.54, "best_ask": 0.56,
        }

        fake_response = {"orderID": None, "status": "UNMATCHED", "success": False}
        with patch("trade.TRADING_ENABLED", True), \
             patch("trade._submit_fak_order", return_value=fake_response):
            result = place_order(db, "mkt_1", 1, order_params, cycle=1,
                                 clob_token_id="tok_yes")

        assert result["status"] == "fak_rejected"
        assert result["action"] == "fak_rejected"

        db.close()

    def test_fok_error_sets_status_failed(self):
        """FOK SDK exception → status='failed'."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "BUY", "size": 25,
            "price_limit": 0.56, "order_type": "fok", "action": "fok_take",
            "edge": 0.06, "spread": 0.02, "best_bid": 0.54, "best_ask": 0.56,
        }

        with patch("trade.TRADING_ENABLED", True), \
             patch("trade._submit_fak_order", side_effect=RuntimeError("API down")):
            result = place_order(db, "mkt_1", 1, order_params, cycle=1,
                                 clob_token_id="tok_yes")

        assert result["status"] == "failed"
        assert "API down" in result["reason"]

        db.close()

    def test_legacy_gtc_still_works(self):
        """Non-FOK orders still use _submit_clob_order (GTC path)."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "BUY", "size": 25,
            "price_limit": 0.56,
            # No order_type = "fok" → legacy GTC
        }

        fake_response = {"orderID": "gtc_456", "status": "live"}
        with patch("trade.TRADING_ENABLED", True), \
             patch("trade._submit_clob_order", return_value=fake_response) as mock_gtc, \
             patch("trade._submit_fak_order") as mock_fak:
            result = place_order(db, "mkt_1", 1, order_params, cycle=1,
                                 clob_token_id="tok_yes")

        assert result["status"] == "submitted"
        mock_gtc.assert_called_once()
        mock_fak.assert_not_called()

        db.close()

    def test_fok_uses_amount_not_shares(self):
        """FOK path passes dollar amount directly, not shares."""
        from trade import place_order, ensure_orders_table
        db = _make_db()
        ensure_orders_table(db)

        order_params = {
            "direction": "UP", "side": "BUY", "size": 25,
            "price_limit": 0.56, "order_type": "fok", "action": "fok_take",
            "edge": 0.06, "spread": 0.02, "best_bid": 0.54, "best_ask": 0.56,
        }

        fake_response = {"orderID": "fok_789", "status": "MATCHED", "success": True}
        with patch("trade.TRADING_ENABLED", True), \
             patch("trade._submit_fak_order", return_value=fake_response) as mock_fak:
            place_order(db, "mkt_1", 1, order_params, cycle=1,
                        clob_token_id="tok_yes")

        mock_fak.assert_called_once_with(
            token_id="tok_yes",
            side="BUY",
            amount=25,
            price=0.56,
        )

        db.close()
