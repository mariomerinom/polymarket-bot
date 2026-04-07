"""
test_paper_settlement.py — Paper orders settle against resolved markets.

Contract:
  - Paper orders (status='paper') on RESOLVED markets get marked
    'paper_settled' and have pnl computed assuming optimistic fill at
    price_limit.
  - Paper orders on UNRESOLVED markets are left alone.
  - Live order settlement contract (status='filled' → 'settled') is
    unchanged.
  - Paper P&L MUST NOT count toward the live circuit breaker.

Why optimistic fill: paper P&L is the upper-bound "what the signal said."
Real fill cost is measured separately via fill_diagnostic on live FAK
attempts. Mixing the two is what cost us last night.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _db_with_orders():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, price_yes REAL, price_no REAL,
        resolved INTEGER, outcome INTEGER
    )""")
    from trade import ensure_orders_table
    ensure_orders_table(db)
    return db


def _insert_market(db, mid, resolved=1, outcome=1):
    db.execute(
        "INSERT INTO markets (id, price_yes, price_no, resolved, outcome) "
        "VALUES (?, 0.5, 0.5, ?, ?)",
        (mid, resolved, outcome),
    )


def _insert_paper_order(db, mid, direction="UP", price_limit=0.55, size=25.0):
    db.execute("""
        INSERT INTO orders (market_id, prediction_id, direction, size,
            price_limit, status, mode, placed_at, cycle)
        VALUES (?, 1, ?, ?, ?, 'paper', 'paper', '2026-04-07T10:00:00', 1)
    """, (mid, direction, size, price_limit))
    db.commit()


class TestPaperSettlement:

    def test_paper_winner_settles_with_pnl(self):
        """Paper UP bet on resolved YES market → paper_settled, positive pnl."""
        from trade import compute_order_pnl, POLYMARKET_FEE_FACTOR
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=1, outcome=1)  # YES wins
        _insert_paper_order(db, "m1", direction="UP", price_limit=0.50)
        updated = compute_order_pnl(db)
        assert updated == 1
        row = db.execute(
            "SELECT status, pnl, price_filled FROM orders WHERE market_id='m1'"
        ).fetchone()
        assert row["status"] == "paper_settled"
        # Optimistic fill at price_limit
        assert row["price_filled"] == 0.50
        expected = round(25.0 * (1.0 / 0.50 - 1) * POLYMARKET_FEE_FACTOR, 2)
        assert row["pnl"] == expected

    def test_paper_loser_settles_with_negative_pnl(self):
        """Paper UP bet on resolved NO market → paper_settled, -size pnl."""
        from trade import compute_order_pnl
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=1, outcome=0)  # NO wins
        _insert_paper_order(db, "m1", direction="UP", price_limit=0.55)
        compute_order_pnl(db)
        row = db.execute(
            "SELECT status, pnl FROM orders WHERE market_id='m1'"
        ).fetchone()
        assert row["status"] == "paper_settled"
        assert row["pnl"] == -25.0

    def test_paper_down_winner(self):
        """Paper DOWN bet on resolved NO market → paper_settled, positive pnl."""
        from trade import compute_order_pnl, POLYMARKET_FEE_FACTOR
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=1, outcome=0)
        _insert_paper_order(db, "m1", direction="DOWN", price_limit=0.45)
        compute_order_pnl(db)
        row = db.execute(
            "SELECT status, pnl FROM orders WHERE market_id='m1'"
        ).fetchone()
        assert row["status"] == "paper_settled"
        expected = round(25.0 * (1.0 / 0.45 - 1) * POLYMARKET_FEE_FACTOR, 2)
        assert row["pnl"] == expected

    def test_paper_unresolved_market_skipped(self):
        """Paper order on unresolved market stays in 'paper' status."""
        from trade import compute_order_pnl
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=0)
        _insert_paper_order(db, "m1")
        compute_order_pnl(db)
        row = db.execute(
            "SELECT status, pnl FROM orders WHERE market_id='m1'"
        ).fetchone()
        assert row["status"] == "paper"
        assert row["pnl"] is None

    def test_paper_idempotent(self):
        """Running compute_order_pnl twice doesn't double-update paper rows."""
        from trade import compute_order_pnl
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=1, outcome=1)
        _insert_paper_order(db, "m1", direction="UP", price_limit=0.50)
        first = compute_order_pnl(db)
        second = compute_order_pnl(db)
        assert first == 1
        assert second == 0

    def test_live_settlement_unchanged(self):
        """Live filled order on resolved market still goes 'filled' → 'settled'."""
        from trade import compute_order_pnl
        db = _db_with_orders()
        _insert_market(db, "m1", resolved=1, outcome=1)
        db.execute("""
            INSERT INTO orders (market_id, prediction_id, direction, size,
                price_limit, price_filled, status, mode, placed_at, cycle)
            VALUES ('m1', 1, 'UP', 25.0, 0.55, 0.52, 'filled', 'live',
                '2026-04-07T10:00:00', 1)
        """)
        db.commit()
        compute_order_pnl(db)
        row = db.execute("SELECT status, pnl FROM orders WHERE market_id='m1'").fetchone()
        assert row["status"] == "settled"  # NOT paper_settled
        assert row["pnl"] > 0


class TestCircuitBreakerScope:
    """Paper losses must not trip the live circuit breaker."""

    def test_paper_loss_excluded_from_daily_loss(self):
        """system_state._compute_daily_loss only counts live (filled/settled)."""
        from system_state import _compute_daily_loss
        from datetime import datetime, timezone
        db = _db_with_orders()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Big paper loss today
        db.execute("""
            INSERT INTO orders (market_id, prediction_id, direction, size,
                price_limit, price_filled, status, mode, placed_at, cycle, pnl)
            VALUES ('m_paper', 1, 'UP', 25, 0.55, 0.55, 'paper_settled',
                'paper', ?, 1, -500.0)
        """, (f"{today}T10:00:00",))
        db.commit()
        loss, _ = _compute_daily_loss(db)
        assert loss == 0.0, f"Paper losses leaked into circuit breaker: ${loss}"
