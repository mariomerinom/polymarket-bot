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
    db_path_for_pipeline,
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


def test_check_all_handles_active_custom_baseline(monkeypatch):
    """Active registry entries with custom baselines should not crash checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=10, wr=0.7, price=0.45, conv=3)
        opt_path = os.path.join(tmpdir, "optimizations.json")

        import optimization_tracker as ot
        monkeypatch.setattr(ot, "OPTIMIZATIONS_PATH", type(OPTIMIZATIONS_PATH)(opt_path))
        monkeypatch.setattr(ot, "DB_5M", type(ot.DB_5M)(db_path))

        save_optimizations({
            "optimizations": [{
                "name": "custom_baseline_active",
                "description": "custom baseline payload",
                "registered_at": "2026-03-01T00:00:00+00:00",
                "pipeline": "5m",
                "status": "active",
                "min_sample": 50,
                "revert_condition": "post_wr < baseline_wr - 2",
                "baseline": {"note": "manual baseline"},
                "latest_check": None,
                "post_stats": None,
                "closed_at": None,
                "close_reason": None,
            }],
        })

        alerts = check_all()
        assert any("custom baseline" in a for a in alerts)


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


def _create_asset_daily_test_db(tmpdir):
    db_path = os.path.join(tmpdir, "asset_daily.db")
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE asset_daily (
        asset TEXT NOT NULL,
        date TEXT NOT NULL,
        range_zscore REAL,
        velocity_zscore REAL,
        body_pct REAL,
        trend_label TEXT,
        PRIMARY KEY (asset, date)
    )""")
    db.executemany(
        "INSERT INTO asset_daily VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("BTC", "2026-03-28", -1.2, 0.2, 0.002, "chop"),
            ("BTC", "2026-03-29", 1.8, 1.4, 0.04, "up"),
        ],
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


def test_daily_regime_filter_counts_quiet_tape_cohort():
    """Daily regime filters count only predictions on matching BTC day rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pred_db_path = _create_test_db(tmpdir, n_bets=10, wr=0.6, price=0.45, conv=3)
        asset_db_path = _create_asset_daily_test_db(tmpdir)

        db = sqlite3.connect(pred_db_path)
        db.execute(
            "UPDATE predictions SET predicted_at = ? WHERE market_id IN "
            "('m6', 'm7', 'm8', 'm9')",
            ("2026-03-29T10:00:00",),
        )
        db.commit()
        db.close()

        stats = compute_stats(
            pred_db_path,
            daily_regime_filter={
                "asset": "BTC",
                "range_zscore_lt": -0.5,
                "abs_velocity_zscore_lt": 0.75,
            },
            asset_daily_db_path=asset_db_path,
        )

        assert stats["bets"] == 6
        assert stats["wins"] == 6
        assert stats["wr"] == 100.0


def test_daily_regime_filter_counts_high_range_cohort():
    """Daily regime filters can track high-range protection candidates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pred_db_path = _create_test_db(tmpdir, n_bets=10, wr=0.6, price=0.45, conv=3)
        asset_db_path = _create_asset_daily_test_db(tmpdir)

        db = sqlite3.connect(pred_db_path)
        db.execute(
            "UPDATE predictions SET predicted_at = ? WHERE market_id IN "
            "('m6', 'm7', 'm8', 'm9')",
            ("2026-03-29T10:00:00",),
        )
        db.commit()
        db.close()

        stats = compute_stats(
            pred_db_path,
            daily_regime_filter={
                "asset": "BTC",
                "range_zscore_gte": 1.5,
            },
            asset_daily_db_path=asset_db_path,
        )

        assert stats["bets"] == 4
        assert stats["wins"] == 0
        assert stats["wr"] == 0.0


def test_regime_filter_counts_selected_regimes_only():
    """Regime filters isolate terrain cohorts without changing conviction rules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_test_db(tmpdir, n_bets=9, wr=0.67, price=0.45, conv=3)

        db = sqlite3.connect(db_path)
        db.execute(
            "UPDATE predictions SET regime = ? WHERE market_id IN ('m0', 'm1', 'm2')",
            ("LOW_VOL / NEUTRAL",),
        )
        db.execute(
            "UPDATE predictions SET regime = ? WHERE market_id IN ('m3', 'm4', 'm5')",
            ("LOW_VOL / TRENDING",),
        )
        db.execute(
            "UPDATE predictions SET regime = ? WHERE market_id IN ('m6', 'm7', 'm8')",
            ("HIGH_VOL / TRENDING",),
        )
        db.commit()
        db.close()

        stats = compute_stats(
            db_path,
            regime_filter=["LOW_VOL / NEUTRAL", "LOW_VOL / TRENDING"],
        )

        assert stats["bets"] == 6
        assert stats["wins"] == 6
        assert stats["wr"] == 100.0


def test_named_pipeline_db_resolution(monkeypatch):
    """Optimization checks can target non-BTC5M pipeline DBs by name."""
    import optimization_tracker as ot

    eth_path = type(ot.DB_5M)("/tmp/predictions_eth_test.db")
    monkeypatch.setitem(ot.PIPELINE_DBS, "eth_5m", eth_path)

    assert db_path_for_pipeline("5m") == ot.DB_5M
    assert db_path_for_pipeline("15m") == ot.DB_15M
    assert db_path_for_pipeline("eth_5m") == eth_path


def test_shadow_filters_map_exists():
    """All shadow filter keys map to valid filter parameters."""
    for name, filters in SHADOW_FILTERS.items():
        assert (
            "shadow_key" in filters
            or "agent_filter" in filters
            or "regime_filter" in filters
            or "daily_regime_filter" in filters
        ), \
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


def test_btc5m_quiet_daily_tape_shadow_filter_registered():
    """Quiet daily tape cohort is visible to optimization checks."""
    assert SHADOW_FILTERS["btc5m_quiet_daily_tape_shadow"] == {
        "daily_regime_filter": {
            "asset": "BTC",
            "range_zscore_lt": -0.5,
            "abs_velocity_zscore_lt": 0.75,
        },
    }


def test_promotion_terrain_shadow_filters_registered():
    """Promotion sprint terrain cohorts are visible to optimization checks."""
    assert SHADOW_FILTERS["bybit_btc_regime_filter_shadow"] == {
        "regime_filter": [
            "LOW_VOL / NEUTRAL",
            "LOW_VOL / TRENDING",
            "MEDIUM_VOL / TRENDING",
        ],
    }
    assert SHADOW_FILTERS["eth5m_low_vol_shadow"] == {
        "regime_filter": [
            "LOW_VOL / NEUTRAL",
            "LOW_VOL / TRENDING",
        ],
    }
    assert SHADOW_FILTERS["btc5m_high_range_protection_shadow"] == {
        "daily_regime_filter": {
            "asset": "BTC",
            "range_zscore_gte": 1.5,
        },
    }
