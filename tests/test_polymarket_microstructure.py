"""
Tests for Polymarket microstructure capture.

The capture is a research dataset, not a trading input. It must tolerate
missing/wide books, summarize top depth, and enforce retention.
"""

import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _entry(**overrides):
    base = {
        "mid": 0.51,
        "best_bid": 0.50,
        "best_ask": 0.52,
        "spread": 0.02,
        "updated_at": datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
        "bids": [{"price": "0.50", "size": "100"}, {"price": "0.49", "size": "50"}],
        "asks": [{"price": "0.52", "size": "60"}, {"price": "0.53", "size": "40"}],
    }
    base.update(overrides)
    return base


def test_summarize_token_entry_computes_depth_and_imbalance():
    from polymarket_microstructure import summarize_token_entry

    row = summarize_token_entry(
        "tok_yes",
        _entry(),
        {"market_id": "m1", "side": "YES", "pipeline": "btc_5m"},
        now=datetime(2026, 5, 1, 12, 0, 5, tzinfo=timezone.utc),
    )

    assert row["token_id"] == "tok_yes"
    assert row["market_id"] == "m1"
    assert row["side"] == "YES"
    assert row["top_bid_depth"] == 150.0
    assert row["top_ask_depth"] == 100.0
    assert row["imbalance"] == 0.2
    assert row["cache_age_ms"] == 5000


def test_summarize_token_entry_handles_missing_side_of_book():
    from polymarket_microstructure import summarize_token_entry

    row = summarize_token_entry(
        "tok_yes",
        _entry(best_bid=None, best_ask=0.52, mid=None, spread=None, bids=[]),
        {},
        now=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert row["market_id"] is None
    assert row["top_bid_depth"] == 0.0
    assert row["top_ask_depth"] == 100.0
    assert row["imbalance"] == -1.0
    assert row["spread"] is None


def test_record_orderbook_snapshots_writes_rows(tmp_path):
    from polymarket_microstructure import record_orderbook_snapshots

    db_path = tmp_path / "micro.db"
    count = record_orderbook_snapshots(
        {"tok_yes": _entry()},
        {"tok_yes": {"market_id": "m1", "side": "YES", "pipeline": "btc_5m"}},
        db_path=db_path,
        now=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert count == 1
    db = sqlite3.connect(db_path)
    row = db.execute("""
        SELECT market_id, token_id, side, mid, spread, top_bid_depth,
               top_ask_depth, imbalance
        FROM orderbook_snapshots
    """).fetchone()
    db.close()
    assert row == ("m1", "tok_yes", "YES", 0.51, 0.02, 150.0, 100.0, 0.2)


def test_prune_retention_deletes_old_snapshots(tmp_path):
    from polymarket_microstructure import init_db, prune_old_snapshots

    db_path = tmp_path / "micro.db"
    db = sqlite3.connect(db_path)
    init_db(db)
    old_ts = (datetime(2026, 5, 1, tzinfo=timezone.utc) - timedelta(days=31)).isoformat()
    fresh_ts = datetime(2026, 5, 1, tzinfo=timezone.utc).isoformat()
    db.execute("""
        INSERT INTO orderbook_snapshots (captured_at, token_id)
        VALUES (?, ?), (?, ?)
    """, (old_ts, "old", fresh_ts, "fresh"))
    db.commit()
    db.close()

    deleted = prune_old_snapshots(
        db_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
        retention_days=30,
    )

    db = sqlite3.connect(db_path)
    tokens = [r[0] for r in db.execute(
        "SELECT token_id FROM orderbook_snapshots ORDER BY token_id"
    ).fetchall()]
    db.close()
    assert deleted == 1
    assert tokens == ["fresh"]


def test_microstructure_summary_reports_freshness_and_missing_tokens(tmp_path):
    from polymarket_microstructure import init_db, microstructure_summary

    db_path = tmp_path / "micro.db"
    db = sqlite3.connect(db_path)
    init_db(db)
    now = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    db.execute("""
        INSERT INTO orderbook_snapshots
            (captured_at, market_id, token_id, side, mid, best_bid, best_ask,
             spread, top_bid_depth, top_ask_depth, imbalance, cache_age_ms, pipeline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (now.isoformat(), "m1", "tok_yes", "YES", 0.51, 0.50, 0.52,
          0.02, 100.0, 50.0, 0.3333, 1000, "btc_5m"))
    db.execute("""
        INSERT INTO orderbook_snapshots
            (captured_at, market_id, token_id, side, mid, spread, pipeline)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now.isoformat(), None, "tok_unknown", None, None, None, None))
    db.commit()
    db.close()

    summary = microstructure_summary(db_path, days=1)

    assert summary["snapshots"] == 2
    assert summary["tokens"] == 2
    assert summary["missing_market_id_rate_pct"] == 50.0
    assert summary["fresh_cache_rate_pct"] == 50.0
    assert summary["spread"]["avg"] == 0.02
