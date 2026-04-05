"""
bybit_markets.py — DB initialization, synthetic markets, and position tracking
for the Bybit USDT perpetual futures pipeline.

PARALLEL PIPELINE — does NOT touch any BTC/ETH/Kalshi pipeline files.

Unlike Polymarket/Kalshi which have discrete markets, Bybit perps are continuous.
We create "synthetic 5-minute markets" so the scoring, dashboard, and Brier score
infrastructure works unchanged.
"""

import os
import sqlite3
from datetime import datetime, timezone
from config import DB_BUSY_TIMEOUT_MS
from pathlib import Path

DB_PATH_BYBIT = Path(__file__).parent.parent / "data" / "predictions_bybit.db"


def init_db_bybit():
    """Initialize the Bybit database with all required tables."""
    DB_PATH_BYBIT.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH_BYBIT)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
    db.execute("PRAGMA foreign_keys=ON")

    # Markets table — identical schema to other pipelines
    db.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT,
            end_date TEXT,
            volume REAL,
            price_yes REAL,
            price_no REAL,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT NULL
        )
    """)

    # Predictions table — identical schema to other pipelines
    db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            regime TEXT,
            FOREIGN KEY (market_id) REFERENCES markets(id)
        )
    """)

    # Orders table — identical schema to trade.ensure_orders_table()
    db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            prediction_id INTEGER,
            direction TEXT,
            size REAL,
            price_limit REAL,
            price_filled REAL,
            slippage_pct REAL,
            status TEXT DEFAULT 'pending',
            order_id TEXT,
            mode TEXT,
            reason TEXT,
            placed_at TEXT,
            filled_at TEXT,
            settled_at TEXT,
            pnl REAL,
            cycle INTEGER,
            FOREIGN KEY (market_id) REFERENCES markets(id),
            FOREIGN KEY (prediction_id) REFERENCES predictions(id)
        )
    """)

    # Positions table — NEW for continuous perp position lifecycle
    db.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            side TEXT,
            size REAL,
            entry_price REAL,
            stop_loss REAL,
            status TEXT DEFAULT 'open',
            opened_at TEXT,
            closed_at TEXT,
            close_price REAL,
            pnl REAL,
            cycles_held INTEGER DEFAULT 0,
            close_reason TEXT,
            bybit_order_id TEXT
        )
    """)

    db.commit()
    return db


def create_synthetic_market(db, current_price, cycle_time=None):
    """
    Create a synthetic 5-minute market for this cycle.

    Market ID format: BTCUSDT-2026-04-02T14:15:00Z (rounded to 5min boundary).
    Returns market_id. Deduplicates by checking if market_id already exists.
    """
    if cycle_time is None:
        cycle_time = datetime.now(timezone.utc)

    # Round to nearest 5-minute boundary
    minute = (cycle_time.minute // 5) * 5
    rounded = cycle_time.replace(minute=minute, second=0, microsecond=0)
    market_id = f"BTCUSDT-{rounded.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    # End date is 5 minutes after the rounded start
    from datetime import timedelta
    end_time = rounded + timedelta(minutes=5)

    question = f"Will BTC be above ${current_price:,.0f} at {end_time.strftime('%H:%M')} UTC?"

    # Check for existing market (dedup)
    existing = db.execute(
        "SELECT id FROM markets WHERE id = ?", (market_id,)
    ).fetchone()

    if existing:
        return market_id

    db.execute("""
        INSERT INTO markets (id, question, category, end_date, volume, price_yes, price_no, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        market_id, question, "cryptocurrency",
        end_time.isoformat(), 0, 0.5, 0.5,
        cycle_time.isoformat(),
    ))
    db.commit()
    return market_id


def get_open_position(db):
    """Returns the single open position or None."""
    row = db.execute(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def get_open_positions(db):
    """Returns ALL open positions (supports concurrent positions)."""
    rows = db.execute(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at"
    ).fetchall()
    return [dict(r) for r in rows]


def get_position_by_id(db, position_id):
    """Returns a single position by ID."""
    row = db.execute(
        "SELECT * FROM positions WHERE id = ?", (position_id,)
    ).fetchone()
    return dict(row) if row else None


def open_position(db, market_id, side, size, entry_price, stop_loss,
                  bybit_order_id=None):
    """Insert a new position row. Returns position ID."""
    cursor = db.execute("""
        INSERT INTO positions (market_id, side, size, entry_price, stop_loss,
                               status, opened_at, cycles_held, bybit_order_id)
        VALUES (?, ?, ?, ?, ?, 'open', ?, 0, ?)
    """, (
        market_id, side, size, entry_price, stop_loss,
        datetime.now(timezone.utc).isoformat(), bybit_order_id,
    ))
    db.commit()
    return cursor.lastrowid


def close_position(db, position_id, close_price, pnl, reason,
                   bybit_order_id=None):
    """Mark a position as closed with PnL and reason."""
    db.execute("""
        UPDATE positions SET
            status = 'closed',
            closed_at = ?,
            close_price = ?,
            pnl = ?,
            close_reason = ?,
            bybit_order_id = COALESCE(?, bybit_order_id)
        WHERE id = ?
    """, (
        datetime.now(timezone.utc).isoformat(),
        close_price, pnl, reason, bybit_order_id, position_id,
    ))
    db.commit()


def increment_cycles_held(db, position_id):
    """Increment the cycles_held counter for an open position."""
    db.execute(
        "UPDATE positions SET cycles_held = cycles_held + 1 WHERE id = ?",
        (position_id,)
    )
    db.commit()


if __name__ == "__main__":
    print("Bybit Markets — DB init test")
    db = init_db_bybit()
    market_id = create_synthetic_market(db, 84000.0)
    print(f"  Created market: {market_id}")
    pos_id = open_position(db, market_id, "Buy", 0.005, 84000.0, 83850.0)
    print(f"  Opened position: {pos_id}")
    pos = get_open_position(db)
    print(f"  Open position: side={pos['side']}, size={pos['size']}, entry={pos['entry_price']}")
    close_position(db, pos_id, 84200.0, 1.0, "test_close")
    pos = get_open_position(db)
    print(f"  After close: {pos}")
    db.close()
    print(f"  DB at {DB_PATH_BYBIT}")
