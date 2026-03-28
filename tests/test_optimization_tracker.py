"""
Tests for optimization_tracker.py — continuous validation system.
"""
import sys
import os
import json
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from optimization_tracker import (
    compute_stats,
    load_optimizations,
    save_optimizations,
    register,
    check_all,
    close,
    OPTIMIZATIONS_PATH,
)


def _create_test_db(tmpdir, n_bets=20, wr=0.7, price=0.45, conv=3):
    """Create a test DB with n_bets predictions at given WR."""
    db_path = os.path.join(tmpdir, "test.db")
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT,
        end_date TEXT, volume REAL, price_yes REAL,
        resolved INTEGER, outcome INTEGER
    )""")
    db.execute("""CREATE TABLE predictions (
        market_id TEXT, agent TEXT, estimate REAL, edge REAL,
        confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")

    n_wins = int(n_bets * wr)
    for i in range(n_bets):
        mid = f"m{i}"
        outcome = 1 if i < n_wins else 0
        db.execute(
            "INSERT INTO markets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, "Test?", "crypto", "2026-04-01", 1000, price, 1, outcome)
        )
        db.execute(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, "momentum_rule", 0.62, 0.12, "medium", "{}",
             f"2026-03-28T10:{i:02d}:00", 1, conv, "MEDIUM_VOL / NEUTRAL")
        )
    db.commit()
    db.close()
    return db_path


def test_compute_stats():
    """compute_stats returns correct aggregate stats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=20, wr=0.75, price=0.45, conv=3)
        stats = compute_stats(db_path)
        assert stats["bets"] == 20
        assert stats["wins"] == 15
        assert stats["wr"] == 75.0
        assert stats["wagered"] > 0


def test_compute_stats_with_since_filter():
    """compute_stats respects the 'since' date filter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=10, wr=0.8, price=0.50, conv=3)
        # All predictions are at 2026-03-28, so filtering after that returns nothing
        stats = compute_stats(db_path, since="2026-03-29T00:00:00")
        assert stats["bets"] == 0


def test_register_and_check(monkeypatch):
    """Register an optimization and check it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=30, wr=0.7, price=0.45, conv=3)
        opt_path = os.path.join(tmpdir, "optimizations.json")

        # Monkeypatch paths
        import optimization_tracker as ot
        monkeypatch.setattr(ot, "OPTIMIZATIONS_PATH", type(OPTIMIZATIONS_PATH)(opt_path))
        monkeypatch.setattr(ot, "DB_5M", type(ot.DB_5M)(db_path))

        # Register
        entry = register("test_opt", "test description", "post_wr < baseline_wr - 5", 20, "5m")
        assert entry is not None
        assert entry["baseline"]["bets"] == 30
        assert entry["baseline"]["wr"] == 70.0

        # Check — no new data since registration (registered_at is now, all data is before)
        alerts = check_all()
        assert len(alerts) >= 1
        # Should show progress (0/20 bets)
        assert any("0/20" in a for a in alerts), f"Expected progress alert, got {alerts}"


def test_close(monkeypatch):
    """Close an optimization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=10, wr=0.7, price=0.45, conv=3)
        opt_path = os.path.join(tmpdir, "optimizations.json")

        import optimization_tracker as ot
        monkeypatch.setattr(ot, "OPTIMIZATIONS_PATH", type(OPTIMIZATIONS_PATH)(opt_path))
        monkeypatch.setattr(ot, "DB_5M", type(ot.DB_5M)(db_path))

        register("test_close", "desc", "post_wr < 50", 10, "5m")
        result = close("test_close", "reverted", "WR dropped")
        assert result is not None
        assert result["status"] == "reverted"

        # Should not appear in active checks
        alerts = check_all()
        assert not any("test_close" in a for a in alerts)


def test_duplicate_registration_blocked(monkeypatch):
    """Can't register the same name twice while active."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=10, wr=0.7, price=0.45, conv=3)
        opt_path = os.path.join(tmpdir, "optimizations.json")

        import optimization_tracker as ot
        monkeypatch.setattr(ot, "OPTIMIZATIONS_PATH", type(OPTIMIZATIONS_PATH)(opt_path))
        monkeypatch.setattr(ot, "DB_5M", type(ot.DB_5M)(db_path))

        register("dup_test", "first", "post_wr < 50", 10, "5m")
        result = register("dup_test", "second", "post_wr < 50", 10, "5m")
        assert result is None  # blocked
