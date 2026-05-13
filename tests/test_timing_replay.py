"""Executable BTC 5m timing replay tests."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE markets (
            id TEXT PRIMARY KEY,
            price_yes REAL,
            price_no REAL,
            resolved INTEGER,
            outcome INTEGER
        );
        CREATE TABLE multi_poll_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INTEGER,
            cycle_close_at TEXT NOT NULL,
            offset_seconds INTEGER NOT NULL,
            predicted_at TEXT NOT NULL,
            market_id TEXT NOT NULL,
            asset TEXT,
            estimate REAL,
            regime TEXT,
            spot_at_poll REAL,
            in_flight_return_pct REAL,
            poll_succeeded INTEGER DEFAULT 1,
            conviction_score INTEGER,
            mkt_mid REAL,
            mkt_best_bid REAL,
            mkt_best_ask REAL,
            mkt_spread REAL,
            orderbook_age_ms INTEGER
        );
    """)
    return db


def _market(db, mid="m1", outcome=1):
    db.execute(
        "INSERT INTO markets VALUES (?, 0.55, 0.45, 1, ?)",
        (mid, outcome),
    )


def _poll(db, **overrides):
    values = {
        "cycle": 10,
        "cycle_close_at": "2026-05-13T12:00:00+00:00",
        "offset_seconds": 180,
        "predicted_at": "2026-05-13T12:03:00+00:00",
        "market_id": "m1",
        "asset": "BTC",
        "estimate": 0.65,
        "regime": "MEDIUM_VOL / NEUTRAL",
        "poll_succeeded": 1,
        "conviction_score": 4,
        "mkt_mid": 0.54,
        "mkt_best_bid": 0.53,
        "mkt_best_ask": 0.55,
        "mkt_spread": 0.02,
        "orderbook_age_ms": 500,
    }
    values.update(overrides)
    db.execute(
        """INSERT INTO multi_poll_predictions
           (cycle, cycle_close_at, offset_seconds, predicted_at, market_id,
            asset, estimate, regime, poll_succeeded, conviction_score,
            mkt_mid, mkt_best_bid, mkt_best_ask, mkt_spread, orderbook_age_ms)
           VALUES (:cycle, :cycle_close_at, :offset_seconds, :predicted_at,
                   :market_id, :asset, :estimate, :regime, :poll_succeeded,
                   :conviction_score, :mkt_mid, :mkt_best_bid, :mkt_best_ask,
                   :mkt_spread, :orderbook_age_ms)""",
        values,
    )


def test_missing_conviction_rows_are_research_only():
    from timing_replay import build_timing_replay

    db = _db()
    _market(db)
    _poll(db, conviction_score=None)
    build_timing_replay(db, "2026-05-13", offsets=(180,))

    row = db.execute("SELECT would_fire, skip_reason FROM btc5m_timing_replay").fetchone()
    assert row["would_fire"] == 0
    assert row["skip_reason"] == "missing_conviction"


def test_replay_fires_only_fresh_conviction_eligible_poll():
    from timing_replay import build_timing_replay

    db = _db()
    _market(db)
    _poll(db)
    build_timing_replay(db, "2026-05-13", offsets=(180,))

    row = db.execute(
        "SELECT policy, would_fire, entry_price, won, pnl, ehr "
        "FROM btc5m_timing_replay"
    ).fetchone()
    assert row["policy"] == "delay_180"
    assert row["would_fire"] == 1
    assert row["entry_price"] == 0.55
    assert row["won"] == 1
    assert row["pnl"] > 0
    assert row["ehr"] == 0.45


def test_replay_blocks_stale_orderbook():
    from timing_replay import build_timing_replay

    db = _db()
    _market(db)
    _poll(db, orderbook_age_ms=2500)
    build_timing_replay(db, "2026-05-13", offsets=(180,))

    row = db.execute("SELECT would_fire, skip_reason FROM btc5m_timing_replay").fetchone()
    assert row["would_fire"] == 0
    assert row["skip_reason"] == "stale_book"

