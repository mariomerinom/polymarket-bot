"""
perp_markets.py — Generic DB initialization, synthetic markets, and position
tracking for any symbol/exchange perpetual futures pipeline.

Parameterized version of bybit_markets.py / hl_markets.py. Works for any
crypto pair (ETH, SOL, DOGE, ...) on any exchange (Bybit, Hyperliquid).

Schema is identical to bybit_markets.py — same tables, same columns.
Market ID format: {SYMBOL}-{EXCHANGE}-{timestamp}
DB path: data/predictions_{exchange}_{symbol_lower}.db
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import DB_BUSY_TIMEOUT_MS

DATA_DIR = Path(__file__).parent.parent / "data"


def get_db_path(symbol, exchange):
    """Return DB path for a symbol/exchange pair.

    e.g., data/predictions_bybit_eth.db, data/predictions_hl_sol.db
    """
    # Strip "USDT" suffix for cleaner filenames
    short = symbol.replace("USDT", "").lower()
    return DATA_DIR / f"predictions_{exchange}_{short}.db"


def init_db_perp(symbol, exchange):
    """Initialize DB for any symbol/exchange pair.

    Returns an open sqlite3 connection with Row factory.
    Schema is identical to bybit_markets.py / hl_markets.py.
    """
    db_path = get_db_path(symbol, exchange)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
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

    # Predictions table
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

    # Orders table
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

    # Positions table — perp position lifecycle
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
            exchange_order_id TEXT,
            funding_cost REAL DEFAULT 0
        )
    """)

    db.commit()
    return db


def create_synthetic_market(db, symbol, exchange, current_price, cycle_time=None):
    """Create a synthetic 5-minute market for any symbol/exchange.

    Market ID format: {SYMBOL}-{EXCHANGE}-{timestamp}
    e.g., ETHUSDT-bybit-2026-04-11T14:15:00Z
    """
    if cycle_time is None:
        cycle_time = datetime.now(timezone.utc)

    # Round to nearest 5-minute boundary
    minute = (cycle_time.minute // 5) * 5
    rounded = cycle_time.replace(minute=minute, second=0, microsecond=0)
    market_id = f"{symbol}-{exchange}-{rounded.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    end_time = rounded + timedelta(minutes=5)

    short = symbol.replace("USDT", "")
    question = (f"Will {short} be above ${current_price:,.2f} at "
                f"{end_time.strftime('%H:%M')} UTC? ({exchange})")

    # Dedup
    existing = db.execute(
        "SELECT id FROM markets WHERE id = ?", (market_id,)
    ).fetchone()

    if existing:
        return market_id

    db.execute("""
        INSERT INTO markets (id, question, category, end_date, volume,
                             price_yes, price_no, fetched_at)
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
        "SELECT * FROM positions WHERE status = 'open' "
        "ORDER BY opened_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def get_open_positions(db):
    """Returns ALL open positions."""
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
                  exchange_order_id=None):
    """Insert a new position row. Returns position ID."""
    cursor = db.execute("""
        INSERT INTO positions (market_id, side, size, entry_price, stop_loss,
                               status, opened_at, cycles_held, exchange_order_id)
        VALUES (?, ?, ?, ?, ?, 'open', ?, 0, ?)
    """, (
        market_id, side, size, entry_price, stop_loss,
        datetime.now(timezone.utc).isoformat(), exchange_order_id,
    ))
    db.commit()
    return cursor.lastrowid


def close_position(db, position_id, close_price, pnl, reason,
                   exchange_order_id=None, funding_cost=0.0):
    """Mark a position as closed with PnL, reason, and funding cost."""
    db.execute("""
        UPDATE positions SET
            status = 'closed',
            closed_at = ?,
            close_price = ?,
            pnl = ?,
            close_reason = ?,
            exchange_order_id = COALESCE(?, exchange_order_id),
            funding_cost = ?
        WHERE id = ?
    """, (
        datetime.now(timezone.utc).isoformat(),
        close_price, pnl, reason, exchange_order_id, funding_cost, position_id,
    ))
    db.commit()


def increment_cycles_held(db, position_id):
    """Increment the cycles_held counter for an open position."""
    db.execute(
        "UPDATE positions SET cycles_held = cycles_held + 1 WHERE id = ?",
        (position_id,)
    )
    db.commit()
