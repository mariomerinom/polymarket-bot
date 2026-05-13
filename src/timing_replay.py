"""BTC 5m executable timing replay.

Raw multi-poll rows are research observations. This module turns them into
production-like replay rows only when conviction, orderbook freshness, and
one-candidate-per-cycle constraints are satisfied.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


BET_SIZE = 25.0
TAKER_FEE = 0.02
MAX_ORDERBOOK_AGE_MS = 2_000


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS btc5m_timing_replay (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    cycle INTEGER,
    market_id TEXT NOT NULL,
    policy TEXT NOT NULL,
    offset_seconds INTEGER,
    source_poll_id INTEGER,
    estimate REAL,
    conviction_score INTEGER,
    regime TEXT,
    direction TEXT,
    would_fire INTEGER DEFAULT 0,
    skip_reason TEXT,
    entry_price REAL,
    orderbook_age_ms INTEGER,
    outcome INTEGER,
    won INTEGER,
    pnl REAL,
    ehr REAL,
    created_at TEXT NOT NULL,
    UNIQUE(trade_date, cycle, market_id, policy)
);
"""


def init_table(db: sqlite3.Connection) -> None:
    db.execute(SCHEMA_SQL)
    db.commit()


def build_timing_replay(
    db: sqlite3.Connection,
    date_str: str,
    *,
    offsets: tuple[int, ...] = (180, 240),
    max_orderbook_age_ms: int = MAX_ORDERBOOK_AGE_MS,
) -> dict:
    """Build executable delay replay rows for a date."""
    init_table(db)
    written = _build_immediate_actual(db, date_str)
    for offset in offsets:
        rows = db.execute(
            """
            SELECT mpp.*, m.resolved, m.outcome
            FROM multi_poll_predictions mpp
            JOIN markets m ON m.id = mpp.market_id
            WHERE date(mpp.predicted_at) = ?
              AND mpp.asset = 'BTC'
              AND mpp.offset_seconds = ?
            ORDER BY mpp.cycle, mpp.market_id, mpp.id
            """,
            (date_str, offset),
        ).fetchall()
        seen = set()
        for row in rows:
            key = (row["cycle"], row["market_id"], offset)
            if key in seen:
                continue
            seen.add(key)
            replay = _evaluate_delay_row(row, date_str, max_orderbook_age_ms)
            db.execute(
                """
                INSERT OR REPLACE INTO btc5m_timing_replay
                (trade_date, cycle, market_id, policy, offset_seconds,
                 source_poll_id, estimate, conviction_score, regime, direction,
                 would_fire, skip_reason, entry_price, orderbook_age_ms,
                 outcome, won, pnl, ehr, created_at)
                VALUES (:trade_date, :cycle, :market_id, :policy,
                        :offset_seconds, :source_poll_id, :estimate,
                        :conviction_score, :regime, :direction, :would_fire,
                        :skip_reason, :entry_price, :orderbook_age_ms,
                        :outcome, :won, :pnl, :ehr, :created_at)
                """,
                replay,
            )
            written += 1
    db.commit()
    return {"written": written}


def _build_immediate_actual(db: sqlite3.Connection, date_str: str) -> int:
    try:
        rows = db.execute(
            """
            SELECT o.id AS order_id, o.cycle, o.market_id, p.id AS prediction_id,
                   p.estimate, p.conviction_score, p.regime, o.direction,
                   COALESCE(o.price_filled, o.price_limit) AS entry_price,
                   m.outcome, o.pnl
            FROM orders o
            JOIN predictions p ON p.id = o.prediction_id
            JOIN markets m ON m.id = o.market_id
            WHERE date(o.placed_at) = ?
              AND m.resolved = 1
              AND p.agent LIKE '%momentum%'
              AND o.direction IN ('UP', 'DOWN')
            """,
            (date_str,),
        ).fetchall()
    except sqlite3.Error:
        return 0
    count = 0
    for row in rows:
        entry = row["entry_price"]
        if entry is None or entry <= 0 or entry >= 1:
            continue
        outcome = int(row["outcome"])
        direction = row["direction"]
        won = int((direction == "UP" and outcome == 1) or (direction == "DOWN" and outcome == 0))
        ehr = (outcome - entry) if direction == "UP" else ((1 - outcome) - entry)
        db.execute(
            """
            INSERT OR REPLACE INTO btc5m_timing_replay
            (trade_date, cycle, market_id, policy, offset_seconds,
             source_poll_id, estimate, conviction_score, regime, direction,
             would_fire, skip_reason, entry_price, orderbook_age_ms,
             outcome, won, pnl, ehr, created_at)
            VALUES (?, ?, ?, 'immediate_actual', NULL, NULL, ?, ?, ?, ?,
                    1, NULL, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                date_str,
                row["cycle"],
                row["market_id"],
                row["estimate"],
                row["conviction_score"],
                row["regime"],
                direction,
                entry,
                outcome,
                won,
                row["pnl"],
                round(ehr, 4),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        count += 1
    return count


def _evaluate_delay_row(row, date_str: str, max_orderbook_age_ms: int) -> dict:
    estimate = row["estimate"]
    direction = None
    if estimate is not None and estimate != 0.5:
        direction = "UP" if estimate > 0.5 else "DOWN"

    base = {
        "trade_date": date_str,
        "cycle": row["cycle"],
        "market_id": row["market_id"],
        "policy": f"delay_{row['offset_seconds']}",
        "offset_seconds": row["offset_seconds"],
        "source_poll_id": row["id"],
        "estimate": estimate,
        "conviction_score": row["conviction_score"],
        "regime": row["regime"],
        "direction": direction,
        "would_fire": 0,
        "skip_reason": None,
        "entry_price": None,
        "orderbook_age_ms": row["orderbook_age_ms"],
        "outcome": row["outcome"],
        "won": None,
        "pnl": None,
        "ehr": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    skip = _skip_reason(row, max_orderbook_age_ms)
    if skip:
        base["skip_reason"] = skip
        return base

    entry = _entry_price(row)
    outcome = int(row["outcome"])
    won = int((direction == "UP" and outcome == 1) or (direction == "DOWN" and outcome == 0))
    pnl = _pnl(entry, bool(won))
    ehr = (outcome - entry) if direction == "UP" else ((1 - outcome) - entry)
    base.update({
        "would_fire": 1,
        "entry_price": round(entry, 4),
        "won": won,
        "pnl": round(pnl, 2),
        "ehr": round(ehr, 4),
    })
    return base


def _skip_reason(row, max_orderbook_age_ms: int) -> str | None:
    if not row["poll_succeeded"]:
        return "poll_failed"
    if row["conviction_score"] is None:
        return "missing_conviction"
    if int(row["conviction_score"]) < 3:
        return "low_conviction"
    if row["estimate"] is None or row["estimate"] == 0.5:
        return "neutral_estimate"
    if not row["resolved"]:
        return "unresolved_market"
    if row["orderbook_age_ms"] is None:
        return "missing_book"
    if int(row["orderbook_age_ms"]) >= max_orderbook_age_ms:
        return "stale_book"
    if _entry_price(row) is None:
        return "invalid_entry"
    return None


def _entry_price(row) -> float | None:
    estimate = row["estimate"]
    if estimate is None or estimate == 0.5:
        return None
    if estimate > 0.5:
        entry = row["mkt_best_ask"] if row["mkt_best_ask"] is not None else row["mkt_mid"]
    else:
        entry = (
            1.0 - row["mkt_best_bid"]
            if row["mkt_best_bid"] is not None
            else (1.0 - row["mkt_mid"] if row["mkt_mid"] is not None else None)
        )
    if entry is None or entry <= 0 or entry >= 1:
        return None
    return float(entry)


def _pnl(entry: float, won: bool) -> float:
    if not won:
        return -BET_SIZE
    shares = BET_SIZE / entry
    return (shares * 1.0 - BET_SIZE) - BET_SIZE * TAKER_FEE
