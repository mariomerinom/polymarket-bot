"""
polymarket_microstructure.py — research-only Polymarket orderbook snapshots.

This module records summarized live CLOB cache state for validation of
dislocation, order-flow, dead-hour, and execution-aware strategies. It never
feeds conviction scoring or trade execution.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "polymarket_microstructure.db"
RETENTION_DAYS = 30


def init_db(db: sqlite3.Connection):
    db.execute("""
        CREATE TABLE IF NOT EXISTS orderbook_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            market_id TEXT,
            token_id TEXT,
            side TEXT,
            pipeline TEXT,
            mid REAL,
            best_bid REAL,
            best_ask REAL,
            spread REAL,
            top_bid_depth REAL,
            top_ask_depth REAL,
            imbalance REAL,
            cache_age_ms INTEGER
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_time
        ON orderbook_snapshots(captured_at)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_orderbook_snapshots_token
        ON orderbook_snapshots(token_id, captured_at)
    """)
    db.commit()


def _to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _depth(levels):
    total = 0.0
    for level in levels or []:
        size = _to_float(level.get("size") if isinstance(level, dict) else None)
        if size is not None:
            total += size
    return round(total, 6)


def _cache_age_ms(updated_at, now):
    if not updated_at:
        return None
    try:
        dt = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((now - dt).total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


def summarize_token_entry(token_id, entry, token_context=None, now=None):
    """Return a DB-ready summary for one cached token orderbook entry."""
    now = now or datetime.now(timezone.utc)
    token_context = token_context or {}
    bid_depth = _depth(entry.get("bids", []))
    ask_depth = _depth(entry.get("asks", []))
    total_depth = bid_depth + ask_depth
    imbalance = None
    if total_depth > 0:
        imbalance = round((bid_depth - ask_depth) / total_depth, 4)

    return {
        "captured_at": now.isoformat(),
        "market_id": token_context.get("market_id"),
        "token_id": token_id,
        "side": token_context.get("side"),
        "pipeline": token_context.get("pipeline"),
        "mid": _to_float(entry.get("mid")),
        "best_bid": _to_float(entry.get("best_bid")),
        "best_ask": _to_float(entry.get("best_ask")),
        "spread": _to_float(entry.get("spread")),
        "top_bid_depth": bid_depth,
        "top_ask_depth": ask_depth,
        "imbalance": imbalance,
        "cache_age_ms": _cache_age_ms(entry.get("updated_at"), now),
    }


def record_orderbook_snapshots(cache_tokens, token_contexts=None, db_path=DB_PATH,
                               now=None):
    """Persist one summarized snapshot per token in the live cache."""
    now = now or datetime.now(timezone.utc)
    token_contexts = token_contexts or {}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    try:
        init_db(db)
        rows = []
        for token_id, entry in (cache_tokens or {}).items():
            if not isinstance(entry, dict):
                continue
            rows.append(summarize_token_entry(
                token_id,
                entry,
                token_contexts.get(token_id, {}),
                now=now,
            ))

        if rows:
            db.executemany("""
                INSERT INTO orderbook_snapshots
                    (captured_at, market_id, token_id, side, pipeline, mid,
                     best_bid, best_ask, spread, top_bid_depth, top_ask_depth,
                     imbalance, cache_age_ms)
                VALUES
                    (:captured_at, :market_id, :token_id, :side, :pipeline,
                     :mid, :best_bid, :best_ask, :spread, :top_bid_depth,
                     :top_ask_depth, :imbalance, :cache_age_ms)
            """, rows)
            db.commit()
        return len(rows)
    finally:
        db.close()


def prune_old_snapshots(db_path=DB_PATH, now=None, retention_days=RETENTION_DAYS):
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    db = sqlite3.connect(str(db_path))
    try:
        init_db(db)
        cur = db.execute(
            "DELETE FROM orderbook_snapshots WHERE captured_at < ?",
            (cutoff,),
        )
        db.commit()
        return cur.rowcount
    finally:
        db.close()


def _avg(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)


def microstructure_summary(db_path=DB_PATH, days=1, max_fresh_age_ms=10_000):
    if not Path(db_path).exists():
        return {
            "snapshots": 0,
            "tokens": 0,
            "markets": 0,
            "pipelines": [],
            "fresh_cache_rate_pct": None,
            "missing_market_id_rate_pct": None,
            "spread": {"avg": None, "max": None},
            "imbalance": {"avg_abs": None, "max_abs": None},
        }

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    try:
        init_db(db)
        rows = db.execute("""
            SELECT market_id, token_id, pipeline, spread, imbalance, cache_age_ms
            FROM orderbook_snapshots
            WHERE captured_at >= ?
        """, (cutoff,)).fetchall()
    finally:
        db.close()

    if not rows:
        return {
            "snapshots": 0,
            "tokens": 0,
            "markets": 0,
            "pipelines": [],
            "fresh_cache_rate_pct": None,
            "missing_market_id_rate_pct": None,
            "spread": {"avg": None, "max": None},
            "imbalance": {"avg_abs": None, "max_abs": None},
        }

    spreads = [r["spread"] for r in rows if r["spread"] is not None]
    abs_imbalances = [abs(r["imbalance"]) for r in rows if r["imbalance"] is not None]
    fresh = [
        r for r in rows
        if r["cache_age_ms"] is not None and r["cache_age_ms"] <= max_fresh_age_ms
    ]
    missing_market = [r for r in rows if not r["market_id"]]

    return {
        "snapshots": len(rows),
        "tokens": len({r["token_id"] for r in rows if r["token_id"]}),
        "markets": len({r["market_id"] for r in rows if r["market_id"]}),
        "pipelines": sorted({r["pipeline"] for r in rows if r["pipeline"]}),
        "fresh_cache_rate_pct": round(len(fresh) / len(rows) * 100, 1),
        "missing_market_id_rate_pct": round(len(missing_market) / len(rows) * 100, 1),
        "spread": {
            "avg": _avg(spreads),
            "max": round(max(spreads), 6) if spreads else None,
        },
        "imbalance": {
            "avg_abs": _avg(abs_imbalances),
            "max_abs": round(max(abs_imbalances), 6) if abs_imbalances else None,
        },
    }
