"""
test_pipeline_e2e.py — End-to-end pipeline lifecycle tests.

Exercises the COMPLETE bet lifecycle: predict → trade → settle → score
on a fresh in-memory database. Uses real functions, no mocks.

Prevents recurrence of:
- Cold-start breaker bug (max_drawdown_breaker at 78.5% on $17 equity)
- Circuit breaker misconfiguration
- PnL computation errors on settled orders
- Duplicate orders across cycles
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trade import (
    should_trade, compute_order, execute_trades,
    compute_order_pnl, ensure_orders_table,
    POLYMARKET_FEE_FACTOR,
)
from predict import store_prediction
from config import (
    MIN_CONVICTION, EDGE_THRESHOLD, DAILY_LOSS_LIMIT,
    CONSECUTIVE_LOSS_MAX, BET_SIZE,
)


# ── CLOB mock for e2e tests ───────────────────────────────────────────────
# Production requires real CLOB prices (no Gamma fallback). E2e tests don't
# have a live CLOB, so we mock token resolution + WS cache to return the
# Gamma price from the DB (good enough for lifecycle testing).

@pytest.fixture(autouse=True)
def _mock_clob_for_e2e():
    """Provide fake CLOB token resolution so execute_trades() doesn't skip."""
    fake_tokens = {"yes": "tok_yes_e2e", "no": "tok_no_e2e"}
    with patch("predict._get_clob_tokens_safe", return_value=fake_tokens), \
         patch("trade._get_live_token_mid", return_value=0.50):
        yield


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_pipeline_db():
    """Create an in-memory DB with full pipeline schema."""
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


def _insert_market(db, market_id, price_yes=0.50, resolved=0, outcome=None):
    """Insert a market row with sensible defaults."""
    db.execute(
        "INSERT INTO markets (id, question, category, end_date, volume, price_yes, price_no, resolved, outcome) "
        "VALUES (?, ?, 'crypto', '2099-01-01T00:00:00Z', 1000, ?, ?, ?, ?)",
        (market_id, f"Test market {market_id}", price_yes, round(1 - price_yes, 4), resolved, outcome),
    )
    db.commit()


def _store_qualifying_prediction(db, market_id, cycle, estimate=0.62,
                                 direction="UP", conv=None):
    """Insert a prediction that passes all gates using real store_prediction()."""
    signal = {
        "should_trade": True,
        "estimate": estimate,
        "confidence": "medium",
        "direction": direction,
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
    # Override conviction if caller specified
    if conv is not None:
        db.execute(
            "UPDATE predictions SET conviction_score = ? WHERE market_id = ? AND cycle = ?",
            (conv, market_id, cycle),
        )
        db.commit()


def _simulate_fill(db, order_db_id, fill_price):
    """Bridge paper→filled: update order status and price_filled."""
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE orders SET status = 'filled', price_filled = ?, filled_at = ? WHERE id = ?",
        (fill_price, now, order_db_id),
    )
    db.commit()


def _resolve_market(db, market_id, outcome):
    """Resolve a market with the given outcome (1=UP, 0=DOWN)."""
    db.execute(
        "UPDATE markets SET resolved = 1, outcome = ? WHERE id = ?",
        (outcome, market_id),
    )
    db.commit()


def _insert_settled_loss(db, market_id, cycle, placed_at=None, pnl=-25.0):
    """Insert a pre-settled losing order for breaker tests."""
    placed_at = placed_at or datetime.now(timezone.utc).isoformat()
    settled_at = placed_at  # same time for simplicity
    db.execute("""
        INSERT INTO orders (market_id, prediction_id, direction, size, price_limit,
            price_filled, status, mode, placed_at, settled_at, pnl, cycle)
        VALUES (?, 1, 'UP', 25.0, 0.55, 0.52, 'settled', 'paper', ?, ?, ?, ?)
    """, (market_id, placed_at, settled_at, pnl, cycle))
    db.commit()


def _insert_settled_win(db, market_id, cycle, placed_at=None, pnl=20.0):
    """Insert a pre-settled winning order for breaker tests."""
    placed_at = placed_at or datetime.now(timezone.utc).isoformat()
    settled_at = placed_at
    db.execute("""
        INSERT INTO orders (market_id, prediction_id, direction, size, price_limit,
            price_filled, status, mode, placed_at, settled_at, pnl, cycle)
        VALUES (?, 1, 'UP', 25.0, 0.55, 0.52, 'settled', 'paper', ?, ?, ?, ?)
    """, (market_id, placed_at, settled_at, pnl, cycle))
    db.commit()


# ── TestFullPipelineLifecycle ────────────────────────────────────────────────


class TestFullPipelineLifecycle:
    """Happy-path tests for the complete predict→trade→settle→score chain."""

    def test_single_cycle_predict_trade_settle_score(self):
        """One complete cycle: predict → trade → fill → resolve → PnL."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50)

        # Predict
        _store_qualifying_prediction(db, "m1", cycle=1)
        pred = db.execute("SELECT conviction_score FROM predictions WHERE market_id='m1'").fetchone()
        assert pred[0] >= MIN_CONVICTION, f"Should qualify: conv={pred[0]}"

        # Trade
        orders = execute_trades(db, cycle=1)
        assert len(orders) == 1, f"Expected 1 order, got {len(orders)}"
        assert orders[0]["direction"] == "UP"
        assert orders[0]["size"] == BET_SIZE
        assert orders[0]["status"] == "paper"

        # Fill + Resolve (UP wins)
        order_id = db.execute("SELECT id FROM orders").fetchone()[0]
        _simulate_fill(db, order_id, fill_price=0.52)
        _resolve_market(db, "m1", outcome=1)

        # PnL
        updated = compute_order_pnl(db)
        assert updated == 1
        row = db.execute("SELECT pnl, status FROM orders WHERE id=?", (order_id,)).fetchone()
        expected_pnl = round(BET_SIZE * (1.0 / 0.52 - 1) * POLYMARKET_FEE_FACTOR, 2)
        assert row[0] == expected_pnl, f"PnL should be {expected_pnl}, got {row[0]}"
        assert row[1] == "settled"
        db.close()

    def test_five_cycle_accumulation(self):
        """5 cycles, 3 wins 2 losses, verify totals and no duplicates."""
        db = _make_pipeline_db()
        outcomes = [1, 0, 1, 0, 1]  # UP, DOWN, UP, DOWN, UP wins

        for i in range(5):
            mid = f"m{i+1}"
            _insert_market(db, mid, price_yes=0.50)
            _store_qualifying_prediction(db, mid, cycle=i+1)
            execute_trades(db, cycle=i+1)

            oid = db.execute("SELECT id FROM orders WHERE market_id=?", (mid,)).fetchone()[0]
            _simulate_fill(db, oid, fill_price=0.52)
            _resolve_market(db, mid, outcome=outcomes[i])
            compute_order_pnl(db)

        # All 5 settled
        total = db.execute("SELECT COUNT(*) FROM orders WHERE status='settled'").fetchone()[0]
        assert total == 5

        # 3 wins, 2 losses
        wins = db.execute("SELECT COUNT(*) FROM orders WHERE pnl > 0").fetchone()[0]
        losses = db.execute("SELECT COUNT(*) FROM orders WHERE pnl < 0").fetchone()[0]
        assert wins == 3, f"Expected 3 wins, got {wins}"
        assert losses == 2, f"Expected 2 losses, got {losses}"

        # No duplicates
        unique_markets = db.execute("SELECT COUNT(DISTINCT market_id) FROM orders").fetchone()[0]
        assert unique_markets == 5

        # Breaker not tripped (consecutive loss streak = 1 max, since W-L-W-L-W)
        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"Should still trade after 3W-2L, got: {reason}"
        db.close()

    def test_cold_start_no_errors(self):
        """Fresh DB, first cycle — all gates pass, no crash."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50)

        # should_trade on empty DB
        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"Cold start should pass all gates, got: {reason}"

        # Full cycle works
        _store_qualifying_prediction(db, "m1", cycle=1)
        orders = execute_trades(db, cycle=1)
        assert len(orders) == 1, "First-ever order should succeed"
        db.close()


# ── TestCircuitBreakers ──────────────────────────────────────────────────────


class TestCircuitBreakers:
    """Circuit breaker behavior across the full pipeline."""

    def test_daily_loss_limit_trips(self):
        """Daily losses >= $300 blocks trading."""
        db = _make_pipeline_db()
        # Insert 12 x $25 losses today = $300
        for i in range(12):
            _insert_settled_loss(db, f"loss{i}", cycle=i+1)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert not ok
        assert "daily_loss_limit" in reason
        db.close()

    def test_daily_loss_limit_resets_next_day(self):
        """Yesterday's losses don't count toward today's daily limit."""
        db = _make_pipeline_db()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        # Insert 4 losses (below consecutive breaker threshold of 5)
        # but totaling $100 — would trip daily limit if counted today
        for i in range(4):
            _insert_settled_loss(db, f"loss{i}", cycle=i+1, placed_at=yesterday)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"Yesterday's losses shouldn't count toward daily limit, got: {reason}"
        db.close()

    def test_consecutive_loss_at_threshold(self):
        """Exactly 5 consecutive losses triggers breaker."""
        db = _make_pipeline_db()
        for i in range(CONSECUTIVE_LOSS_MAX):
            _insert_settled_loss(db, f"loss{i}", cycle=i+1)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert not ok
        assert "consecutive_loss_breaker" in reason
        db.close()

    def test_consecutive_loss_below_threshold(self):
        """4 losses (below threshold) still allows trading."""
        db = _make_pipeline_db()
        for i in range(CONSECUTIVE_LOSS_MAX - 1):
            _insert_settled_loss(db, f"loss{i}", cycle=i+1)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"4 losses should pass, got: {reason}"
        db.close()

    def test_consecutive_loss_resets_on_win(self):
        """Win breaks the consecutive loss streak."""
        db = _make_pipeline_db()
        now = datetime.now(timezone.utc)
        # 3 losses, then 1 win, then 2 losses → streak = 2
        for i in range(3):
            ts = (now - timedelta(minutes=30-i)).isoformat()
            _insert_settled_loss(db, f"early_loss{i}", cycle=i+1, placed_at=ts)
        ts_win = (now - timedelta(minutes=26)).isoformat()
        _insert_settled_win(db, "win1", cycle=4, placed_at=ts_win)
        for i in range(2):
            ts = (now - timedelta(minutes=25-i)).isoformat()
            _insert_settled_loss(db, f"late_loss{i}", cycle=5+i, placed_at=ts)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"Streak is 2 (not 5), should pass, got: {reason}"
        db.close()

    def test_consecutive_losses_across_cycles(self):
        """5 cycles of losses → breaker trips on cycle 6."""
        db = _make_pipeline_db()

        for i in range(5):
            mid = f"m{i+1}"
            _insert_market(db, mid, price_yes=0.50)
            _store_qualifying_prediction(db, mid, cycle=i+1)
            execute_trades(db, cycle=i+1)

            oid = db.execute("SELECT id FROM orders WHERE market_id=?", (mid,)).fetchone()[0]
            _simulate_fill(db, oid, fill_price=0.52)
            _resolve_market(db, mid, outcome=0)  # all losses (UP bet, DOWN outcome)
            compute_order_pnl(db)

        # Cycle 6 should be blocked
        _insert_market(db, "m6", price_yes=0.50)
        _store_qualifying_prediction(db, "m6", cycle=6)
        orders = execute_trades(db, cycle=6)
        assert len(orders) == 0, "Breaker should block cycle 6 after 5 consecutive losses"
        db.close()

    def test_cold_start_single_loss_no_panic(self):
        """One loss on $25 equity must NOT trip any breaker.
        Regression: max_drawdown_breaker tripped at 78.5% on $17.36 peak.
        """
        db = _make_pipeline_db()
        _insert_settled_loss(db, "first_loss", cycle=1)

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"Single loss on small equity must not panic, got: {reason}"
        db.close()


# ── TestOrderConstruction ────────────────────────────────────────────────────


class TestOrderConstruction:
    """Order gating and dedup across the pipeline."""

    def test_shadow_prediction_no_order(self):
        """Conv=2 (shadow) → execute_trades produces 0 orders."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50)
        _store_qualifying_prediction(db, "m1", cycle=1, conv=2)

        orders = execute_trades(db, cycle=1)
        assert len(orders) == 0, "Shadow predictions (conv=2) should not produce orders"
        db.close()

    def test_no_duplicate_orders_same_cycle(self):
        """Same market + cycle → second call places 0 new orders."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50)
        _store_qualifying_prediction(db, "m1", cycle=1)

        orders1 = execute_trades(db, cycle=1)
        assert len(orders1) == 1

        # Second call for same cycle → dedup
        orders2 = execute_trades(db, cycle=1)
        assert len(orders2) == 0, "Duplicate orders should be blocked"

        total = db.execute("SELECT COUNT(*) FROM orders WHERE market_id='m1'").fetchone()[0]
        assert total == 1
        db.close()

    def test_different_cycle_allows_new_order(self):
        """Same market, different cycle → new order allowed."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50)

        _store_qualifying_prediction(db, "m1", cycle=1)
        execute_trades(db, cycle=1)

        _store_qualifying_prediction(db, "m1", cycle=2)
        orders2 = execute_trades(db, cycle=2)
        assert len(orders2) == 1, "Different cycle should allow new order"

        total = db.execute("SELECT COUNT(*) FROM orders WHERE market_id='m1'").fetchone()[0]
        assert total == 2
        db.close()


# ── TestPnLComputation ───────────────────────────────────────────────────────


class TestPnLComputation:
    """PnL computation correctness on settled orders."""

    def test_winning_up_bet(self):
        """UP direction, outcome=1 → positive PnL."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50, resolved=1, outcome=1)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'UP', 25.0, 0.55, 0.52, 'filled', 'paper',
            '2026-04-04T10:00:00', 1)""")
        db.commit()

        updated = compute_order_pnl(db)
        assert updated == 1
        pnl = db.execute("SELECT pnl FROM orders").fetchone()[0]
        expected = round(25.0 * (1.0 / 0.52 - 1) * POLYMARKET_FEE_FACTOR, 2)
        assert pnl == expected, f"Expected {expected}, got {pnl}"
        db.close()

    def test_losing_up_bet(self):
        """UP direction, outcome=0 → PnL = -size."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50, resolved=1, outcome=0)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'UP', 25.0, 0.55, 0.52, 'filled', 'paper',
            '2026-04-04T10:00:00', 1)""")
        db.commit()

        compute_order_pnl(db)
        pnl = db.execute("SELECT pnl FROM orders").fetchone()[0]
        assert pnl == -25.0, f"Losing UP bet should be -$25, got {pnl}"
        db.close()

    def test_winning_down_bet(self):
        """DOWN direction, outcome=0 → positive PnL."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50, resolved=1, outcome=0)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'DOWN', 25.0, 0.55, 0.48, 'filled', 'paper',
            '2026-04-04T10:00:00', 1)""")
        db.commit()

        compute_order_pnl(db)
        pnl = db.execute("SELECT pnl FROM orders").fetchone()[0]
        expected = round(25.0 * (1.0 / 0.48 - 1) * POLYMARKET_FEE_FACTOR, 2)
        assert pnl == expected, f"Expected {expected}, got {pnl}"
        assert pnl > 0
        db.close()

    def test_losing_down_bet(self):
        """DOWN direction, outcome=1 → PnL = -size."""
        db = _make_pipeline_db()
        _insert_market(db, "m1", price_yes=0.50, resolved=1, outcome=1)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'DOWN', 25.0, 0.55, 0.48, 'filled', 'paper',
            '2026-04-04T10:00:00', 1)""")
        db.commit()

        compute_order_pnl(db)
        pnl = db.execute("SELECT pnl FROM orders").fetchone()[0]
        assert pnl == -25.0, f"Losing DOWN bet should be -$25, got {pnl}"
        db.close()

    def test_only_filled_resolved_get_pnl(self):
        """Paper orders and unresolved markets are skipped."""
        db = _make_pipeline_db()
        # Paper order on resolved market
        _insert_market(db, "m1", price_yes=0.50, resolved=1, outcome=1)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'UP', 25.0, 0.55, 'paper', 'paper',
            '2026-04-04T10:00:00', 1)""")
        # Filled order on unresolved market
        _insert_market(db, "m2", price_yes=0.50)
        db.execute("""INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m2', 2, 'UP', 25.0, 0.55, 0.52, 'filled', 'paper',
            '2026-04-04T10:00:00', 1)""")
        db.commit()

        updated = compute_order_pnl(db)
        assert updated == 0, "Neither paper nor unresolved should get PnL"
        db.close()


# ── TestMultiCycleIntegration ────────────────────────────────────────────────


class TestMultiCycleIntegration:
    """Capstone tests: multi-cycle pipelines with real function calls."""

    def test_full_five_cycle_pipeline(self):
        """5 cycles (3W-2L), full chain. Assert totals and breaker state."""
        db = _make_pipeline_db()
        outcomes = [1, 0, 1, 1, 0]  # W, L, W, W, L
        fill_price = 0.52
        total_pnl = 0.0

        for i in range(5):
            mid = f"cycle{i+1}"
            _insert_market(db, mid, price_yes=0.50)
            _store_qualifying_prediction(db, mid, cycle=i+1)
            execute_trades(db, cycle=i+1)

            oid = db.execute(
                "SELECT id FROM orders WHERE market_id=? AND cycle=?", (mid, i+1)
            ).fetchone()[0]
            _simulate_fill(db, oid, fill_price=fill_price)
            _resolve_market(db, mid, outcome=outcomes[i])
            compute_order_pnl(db)

            pnl = db.execute("SELECT pnl FROM orders WHERE id=?", (oid,)).fetchone()[0]
            total_pnl += pnl

        # 5 orders, all settled
        settled = db.execute("SELECT COUNT(*) FROM orders WHERE status='settled'").fetchone()[0]
        assert settled == 5

        # 3 wins, 2 losses
        wins = db.execute("SELECT COUNT(*) FROM orders WHERE pnl > 0").fetchone()[0]
        assert wins == 3

        # Total PnL matches sum
        db_total = db.execute("SELECT SUM(pnl) FROM orders").fetchone()[0]
        assert abs(db_total - total_pnl) < 0.01

        # Breaker NOT tripped (last 2: W, L → streak = 1)
        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert ok, f"3W-2L should not trip breaker, got: {reason}"
        db.close()

    def test_breaker_trips_at_cycle_five(self):
        """5 cycles all losses → cycle 6 blocked by consecutive loss breaker."""
        db = _make_pipeline_db()

        for i in range(5):
            mid = f"loss{i+1}"
            _insert_market(db, mid, price_yes=0.50)
            _store_qualifying_prediction(db, mid, cycle=i+1)
            execute_trades(db, cycle=i+1)

            oid = db.execute(
                "SELECT id FROM orders WHERE market_id=? AND cycle=?", (mid, i+1)
            ).fetchone()[0]
            _simulate_fill(db, oid, fill_price=0.52)
            _resolve_market(db, mid, outcome=0)  # all losses
            compute_order_pnl(db)

        # Breaker should be tripped
        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert not ok
        assert "consecutive_loss_breaker" in reason

        # Cycle 6 produces 0 orders
        _insert_market(db, "m6", price_yes=0.50)
        _store_qualifying_prediction(db, "m6", cycle=6)
        orders = execute_trades(db, cycle=6)
        assert len(orders) == 0
        db.close()

    def test_daily_loss_accumulates_across_cycles(self):
        """Daily loss limit trips from accumulated losses, tested independently.
        Uses pre-inserted settled orders with wins interspersed to avoid
        consecutive loss breaker (which fires at 5 in a row)."""
        db = _make_pipeline_db()
        now = datetime.now(timezone.utc)

        # Insert 12 losses with wins every 4th to avoid consecutive breaker:
        # L L L W L L L W L L L W → consecutive streak = 3 (safe), daily loss = 12*$25 = $300
        for i in range(16):
            ts = (now - timedelta(minutes=16-i)).isoformat()
            mid = f"daily{i}"
            if (i + 1) % 4 == 0:
                _insert_settled_win(db, mid, cycle=i+1, placed_at=ts, pnl=5.0)
            else:
                _insert_settled_loss(db, mid, cycle=i+1, placed_at=ts, pnl=-25.0)
        # 12 losses x $25 = $300

        ok, reason = should_trade({"conviction_score": 4, "estimate": 0.65}, db)
        assert not ok, "12 x $25 losses = $300 should trip daily limit"
        assert "daily_loss_limit" in reason, f"Should be daily_loss_limit, got: {reason}"
        db.close()
