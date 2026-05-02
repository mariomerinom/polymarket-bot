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
    SHADOW_FILTERS,
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


def _create_shadow_test_db(tmpdir):
    """Create a test DB with shadow indicator data in reasoning JSON.

    Returns db_path. Creates:
    - 5 predictions with shadow_rsi_14 in reasoning (3 wins, 2 losses)
    - 3 of those also have shadow_obv_slope (2 wins, 1 loss)
    - 2 predictions from agent='vwap_meanrev' (1 win, 1 loss)
    - 4 predictions with no shadow data at all (3 wins, 1 loss)
    """
    db_path = os.path.join(tmpdir, "shadow_test.db")
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

    preds = [
        # RSI-only predictions (conv=3, momentum_rule)
        ("m1", "momentum_rule", 0.62, 1, json.dumps({"shadow_rsi_14": 55.0}), 3),
        ("m2", "momentum_rule", 0.62, 1, json.dumps({"shadow_rsi_14": 60.0}), 3),
        ("m3", "momentum_rule", 0.62, 0, json.dumps({"shadow_rsi_14": 45.0}), 3),
        # RSI + OBV predictions (conv=3, momentum_rule)
        ("m4", "momentum_rule", 0.62, 1, json.dumps({"shadow_rsi_14": 50.0, "shadow_obv_slope": 0.5}), 3),
        ("m5", "momentum_rule", 0.62, 0, json.dumps({"shadow_rsi_14": 48.0, "shadow_obv_slope": -0.3}), 3),
        # OBV-only (no RSI — edge case)
        # not realistic but tests isolation
        # VWAP meanrev agent predictions (conv=2)
        ("m6", "vwap_meanrev", 0.55, 1, json.dumps({"signal": "vwap_mean_reversion"}), 2),
        ("m7", "vwap_meanrev", 0.55, 0, json.dumps({"signal": "vwap_mean_reversion"}), 2),
        # No shadow data (conv=3)
        ("m8", "momentum_rule", 0.62, 1, "{}", 3),
        ("m9", "momentum_rule", 0.62, 1, "{}", 3),
        ("m10", "momentum_rule", 0.62, 1, "{}", 3),
        ("m11", "momentum_rule", 0.62, 0, "{}", 3),
    ]

    for mid, agent, est, outcome, reasoning, conv in preds:
        db.execute(
            "INSERT INTO markets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, "Test?", "crypto", "2026-04-01", 1000, 0.45, 1, outcome)
        )
        db.execute(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mid, agent, est, 0.12, "medium", reasoning,
             "2026-03-28T10:00:00", 1, conv, "MEDIUM_VOL / NEUTRAL")
        )
    db.commit()
    db.close()
    return db_path


def test_shadow_rsi_filter():
    """Shadow RSI filter only counts predictions with shadow_rsi_14 in reasoning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_shadow_test_db(tmpdir)
        stats = compute_stats(db_path, shadow_key="shadow_rsi_14")
        # 5 predictions have shadow_rsi_14: m1(W), m2(W), m3(L), m4(W), m5(L)
        assert stats["bets"] == 5
        assert stats["wins"] == 3
        assert stats["wr"] == 60.0


def test_shadow_obv_filter():
    """Shadow OBV filter only counts predictions with shadow_obv_slope in reasoning."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_shadow_test_db(tmpdir)
        stats = compute_stats(db_path, shadow_key="shadow_obv_slope")
        # 2 predictions have shadow_obv_slope: m4(W), m5(L)
        assert stats["bets"] == 2
        assert stats["wins"] == 1
        assert stats["wr"] == 50.0


def test_shadow_vwap_agent_filter():
    """VWAP agent filter only counts vwap_meanrev predictions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_shadow_test_db(tmpdir)
        stats = compute_stats(db_path, agent_filter="vwap_meanrev")
        # 2 vwap_meanrev predictions: m6(W), m7(L)
        assert stats["bets"] == 2
        assert stats["wins"] == 1
        assert stats["wr"] == 50.0


def test_aggregate_excludes_low_conviction():
    """Default aggregate only counts conv>=3, excluding vwap_meanrev at conv=2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_shadow_test_db(tmpdir)
        stats = compute_stats(db_path)
        # 9 conv>=3 predictions: m1-m5 (shadow) + m8-m11 (no shadow)
        assert stats["bets"] == 9
        # Wins: m1, m2, m4, m8, m9, m10 = 6
        assert stats["wins"] == 6


def test_shadow_filters_map_exists():
    """All shadow filter keys map to valid filter parameters."""
    for name, filters in SHADOW_FILTERS.items():
        assert "shadow_key" in filters or "agent_filter" in filters, \
            f"{name} has no valid filter"


def test_btc5m_signal_triage_shadow_filters_registered():
    """BTC5M signal triage cohorts are visible to optimization checks."""
    expected = {
        "btc5m_trending_only_shadow": "shadow_btc5m_trending_only",
        "btc5m_weak_hour_shadow": "shadow_btc5m_weak_hour_filter",
        "btc5m_conv4_up_recalibration_shadow": (
            "shadow_btc5m_conv4_up_recalibration"
        ),
        "btc5m_judge_accept_shadow": "shadow_btc5m_judge_accept",
    }

    for name, shadow_key in expected.items():
        assert SHADOW_FILTERS[name] == {"shadow_key": shadow_key}
