"""
Tests for cross-exchange consensus (Kraken + Coinbase).
Verifies consensus scoring and conviction boost logic.
"""
import sys
import os
import sqlite3
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_consensus_function_exists():
    """_compute_consensus is importable from btc_data."""
    from btc_data import _compute_consensus
    assert callable(_compute_consensus)


def test_consensus_both_agree():
    """Score=2 when both exchanges see the same streak direction with length >= 2."""
    from btc_data import _compute_consensus

    kraken = {"consecutive_dir_label": "UP", "consecutive_direction": 3}
    coinbase = {"consecutive_dir_label": "UP", "consecutive_direction": 4}

    result = _compute_consensus(kraken, coinbase)
    assert result["sources"] == 2
    assert result["streak_agree"] is True
    assert result["direction_agree"] is True
    assert result["score"] == 2


def test_consensus_disagree():
    """Score=-1 when exchanges see opposite directions."""
    from btc_data import _compute_consensus

    kraken = {"consecutive_dir_label": "UP", "consecutive_direction": 3}
    coinbase = {"consecutive_dir_label": "DOWN", "consecutive_direction": 2}

    result = _compute_consensus(kraken, coinbase)
    assert result["sources"] == 2
    assert result["streak_agree"] is False
    assert result["direction_agree"] is False
    assert result["score"] == -1


def test_consensus_weak_agreement():
    """Score=1 when direction matches but one streak is too short."""
    from btc_data import _compute_consensus

    kraken = {"consecutive_dir_label": "UP", "consecutive_direction": 3}
    coinbase = {"consecutive_dir_label": "UP", "consecutive_direction": 1}

    result = _compute_consensus(kraken, coinbase)
    assert result["sources"] == 2
    assert result["streak_agree"] is False  # coinbase streak < 2
    assert result["direction_agree"] is True
    assert result["score"] == 1  # weak


def test_consensus_single_source():
    """Score=1 when only one exchange is available."""
    from btc_data import _compute_consensus

    kraken = {"consecutive_dir_label": "UP", "consecutive_direction": 3}

    result = _compute_consensus(kraken, None)
    assert result["sources"] == 1
    assert result["score"] == 1
    assert result["streak_agree"] is None


def test_consensus_no_sources():
    """Score=0 when no exchanges are available."""
    from btc_data import _compute_consensus

    result = _compute_consensus(None, None)
    assert result["sources"] == 0
    assert result["score"] == 0


def test_conviction_boost_with_consensus():
    """Conviction bumps from 3→4 or 4→5 when consensus score=2."""
    from predict import store_prediction

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}
        signal_down = {"estimate": 0.38, "should_trade": True,
                       "confidence": "medium", "direction": "DOWN"}
        signal_up = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP"}

        strong_consensus = {"score": 2, "sources": 2, "streak_agree": True}
        no_consensus = {"score": -1, "sources": 2, "streak_agree": False}

        # DOWN + strong consensus → 3 → bumped to 4
        store_prediction(db, "m1", signal_down, regime, 1,
                         mkt_price=0.45, consensus=strong_consensus)

        # DOWN + no consensus → stays at 3
        store_prediction(db, "m2", signal_down, regime, 1,
                         mkt_price=0.45, consensus=no_consensus)

        # UP sweet spot + strong consensus → 4 → bumped to 5
        store_prediction(db, "m3", signal_up, regime, 1,
                         mkt_price=0.45, consensus=strong_consensus)

        # UP sweet spot + no consensus → stays at 4
        store_prediction(db, "m4", signal_up, regime, 1,
                         mkt_price=0.45, consensus=no_consensus)

        rows = db.execute(
            "SELECT market_id, conviction_score FROM predictions ORDER BY market_id"
        ).fetchall()
        db.close()

        results = {r[0]: r[1] for r in rows}
        assert results["m1"] == 4, f"DOWN+consensus should be 4, got {results['m1']}"
        assert results["m2"] == 3, f"DOWN+no_consensus should be 3, got {results['m2']}"
        assert results["m3"] == 5, f"UP+sweet+consensus should be 5, got {results['m3']}"
        assert results["m4"] == 4, f"UP+sweet+no_consensus should be 4, got {results['m4']}"


def test_conviction_5_capped():
    """Conviction never exceeds 5 even with all boosts."""
    from predict import store_prediction

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}
        signal_up = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP"}
        strong_consensus = {"score": 2, "sources": 2, "streak_agree": True}

        # UP sweet spot (conv=4) + consensus boost → 5, not 6
        store_prediction(db, "m1", signal_up, regime, 1,
                         mkt_price=0.45, consensus=strong_consensus)

        row = db.execute("SELECT conviction_score FROM predictions").fetchone()
        db.close()
        assert row[0] == 5, f"Conviction should cap at 5, got {row[0]}"


def test_consensus_stored_in_reasoning():
    """Consensus data is stored in the reasoning JSON."""
    from predict import store_prediction
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}
        signal = {"estimate": 0.62, "should_trade": True,
                  "confidence": "medium", "direction": "UP"}
        consensus = {"score": 2, "sources": 2, "streak_agree": True,
                     "streak_kraken": {"direction": "UP", "length": 3},
                     "streak_coinbase": {"direction": "UP", "length": 4}}

        store_prediction(db, "m1", signal, regime, 1,
                         mkt_price=0.45, consensus=consensus)

        row = db.execute("SELECT reasoning FROM predictions").fetchone()
        db.close()

        data = json.loads(row[0])
        assert "consensus" in data
        assert data["consensus"]["score"] == 2
        assert data["consensus"]["streak_kraken"]["direction"] == "UP"


def test_no_consensus_no_boost():
    """When consensus is None (e.g., btc_data failed), no conviction change."""
    from predict import store_prediction

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}
        signal = {"estimate": 0.38, "should_trade": True,
                  "confidence": "medium", "direction": "DOWN"}

        # No consensus passed → stays at base conviction
        store_prediction(db, "m1", signal, regime, 1, mkt_price=0.45, consensus=None)

        row = db.execute("SELECT conviction_score FROM predictions").fetchone()
        db.close()
        assert row[0] == 3, f"No consensus should leave conviction at 3, got {row[0]}"
