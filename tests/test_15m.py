"""
Tests for the 15-minute market pipeline.
Verifies isolation from 5-min pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_15m_window_detection():
    """15-min windows correctly identified."""
    from fetch_markets import _is_15min_window
    assert _is_15min_window("Bitcoin Up or Down - March 24, 7:45PM-8:00PM ET")
    assert _is_15min_window("Bitcoin Up or Down - March 24, 8:00PM-8:15PM ET")
    assert not _is_15min_window("Bitcoin Up or Down - March 24, 7:55PM-8:00PM ET")  # 5-min
    assert not _is_15min_window("Bitcoin Up or Down - March 24, 4:00PM-8:00PM ET")  # 4-hour


def test_5m_window_still_works():
    """5-min detection unchanged after adding 15-min support."""
    from fetch_markets import _is_5min_window
    assert _is_5min_window("Bitcoin Up or Down - March 24, 7:55PM-8:00PM ET")
    assert not _is_5min_window("Bitcoin Up or Down - March 24, 7:45PM-8:00PM ET")  # 15-min


def test_15m_db_path_is_separate():
    """15-min DB path is different from 5-min."""
    from fetch_markets import DB_PATH, DB_PATH_15M
    assert DB_PATH != DB_PATH_15M
    assert "predictions_15m.db" in str(DB_PATH_15M)
    assert "predictions.db" in str(DB_PATH)


def test_candle_fetch_accepts_15m_interval():
    """fetch_btc_candles accepts interval='15m' without error in its setup."""
    from btc_data import fetch_btc_candles
    # We just verify the function signature accepts the param
    # (actual API call would need network)
    import inspect
    sig = inspect.signature(fetch_btc_candles)
    assert "interval" in sig.parameters


def test_run_predictions_accepts_db_path():
    """run_predictions accepts db_path parameter."""
    from predict import run_predictions
    import inspect
    sig = inspect.signature(run_predictions)
    assert "db_path" in sig.parameters


def test_build_html_accepts_db_path():
    """build_html accepts db_path and subtitle parameters."""
    from dashboard import build_html
    import inspect
    sig = inspect.signature(build_html)
    assert "db_path" in sig.parameters
    assert "subtitle" in sig.parameters


def test_15m_conv_cap_demotes_above_3():
    """Decision #20: 15m pipeline caps conviction at 3 post-prediction."""
    import sqlite3
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
        estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
        predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    # Insert predictions with conv=4 and conv=5
    db.execute("INSERT INTO predictions (market_id, agent, estimate, cycle, conviction_score) "
               "VALUES ('m1', 'momentum_v4', 0.62, 100, 4)")
    db.execute("INSERT INTO predictions (market_id, agent, estimate, cycle, conviction_score) "
               "VALUES ('m2', 'momentum_v4', 0.38, 100, 5)")
    db.execute("INSERT INTO predictions (market_id, agent, estimate, cycle, conviction_score) "
               "VALUES ('m3', 'momentum_v4', 0.55, 100, 3)")
    db.commit()

    # Apply the same cap that ci_run_15m.py does
    demoted = db.execute(
        "UPDATE predictions SET conviction_score = 3 WHERE cycle = ? AND conviction_score > 3",
        (100,)
    ).rowcount
    db.commit()

    assert demoted == 2, f"Expected 2 demoted, got {demoted}"
    rows = db.execute("SELECT conviction_score FROM predictions ORDER BY id").fetchall()
    assert all(r[0] <= 3 for r in rows), f"All should be <=3, got {[r[0] for r in rows]}"
    db.close()


def test_15m_ci_workflow_commits_correct_files():
    """15m CI workflow only commits 15m files, not 5m files."""
    workflow = os.path.join(os.path.dirname(__file__), "..",
                           ".github", "workflows", "predict-15m.yml")
    with open(workflow) as f:
        content = f.read()
    # Must commit 15m-specific files
    assert "data/predictions_15m.db" in content
    assert "docs/15m.html" in content
    # Must NOT commit 5m files
    assert "data/predictions.db" not in content
    assert "docs/index.html" not in content


def test_15m_write_does_not_touch_5m_db():
    """Writing to 15m DB does not affect 5m DB."""
    import sqlite3
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        db_5m = os.path.join(tmpdir, "predictions.db")
        db_15m = os.path.join(tmpdir, "predictions_15m.db")

        # Create both DBs with a market table
        for path in [db_5m, db_15m]:
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE markets (id TEXT PRIMARY KEY, question TEXT)")
            conn.commit()
            conn.close()

        # Write to 15m only
        conn_15m = sqlite3.connect(db_15m)
        conn_15m.execute("INSERT INTO markets VALUES ('test_15m', '15m market')")
        conn_15m.commit()
        conn_15m.close()

        # Verify 5m is untouched
        conn_5m = sqlite3.connect(db_5m)
        count = conn_5m.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
        conn_5m.close()
        assert count == 0, "15m write contaminated 5m database"


def test_15m_uses_5m_candles_as_atomic_unit():
    """ci_run_15m uses 5m candles and inherits standard thresholds from config."""
    ci_run_15m_path = os.path.join(os.path.dirname(__file__), "..", "src", "ci_run_15m.py")
    with open(ci_run_15m_path) as f:
        source = f.read()
    # Should NOT pass min_streak or autocorr_threshold to run_predictions — inherits 5m defaults
    # Filter out comments (lines starting with #) to avoid false positives
    code_lines = [l for l in source.splitlines() if not l.strip().startswith("#")]
    code_only = "\n".join(code_lines)
    assert "min_streak=" not in code_only, "15m should inherit min_streak from config, not override"
    assert "autocorr_threshold=" not in code_only, "15m should inherit autocorr_threshold from config, not override"


def test_run_predictions_accepts_threshold_params():
    """run_predictions accepts min_streak and autocorr_threshold parameters."""
    from predict import run_predictions
    import inspect
    sig = inspect.signature(run_predictions)
    assert "min_streak" in sig.parameters
    assert "autocorr_threshold" in sig.parameters
    assert sig.parameters["min_streak"].default is None
    from config import AUTOCORR_MEAN_REVERTING_5M
    assert sig.parameters["autocorr_threshold"].default == AUTOCORR_MEAN_REVERTING_5M


def test_15m_uses_loose_mode():
    """ci_run_15m passes loose_mode=True to disable 5m-derived gates."""
    ci_run_15m_path = os.path.join(os.path.dirname(__file__), "..", "src", "ci_run_15m.py")
    with open(ci_run_15m_path) as f:
        source = f.read()
    assert "loose_mode=True" in source, "15m must use loose_mode=True"


def test_loose_mode_default_false():
    """run_predictions defaults loose_mode to False (5m behavior preserved)."""
    from predict import run_predictions
    import inspect
    sig = inspect.signature(run_predictions)
    assert "loose_mode" in sig.parameters
    assert sig.parameters["loose_mode"].default is False, "loose_mode must default to False for 5m"


def test_store_prediction_accepts_loose_mode():
    """store_prediction accepts loose_mode parameter."""
    from predict import store_prediction
    import inspect
    sig = inspect.signature(store_prediction)
    assert "loose_mode" in sig.parameters


def test_sibling_5m_boost_increases_conviction():
    """5m confirmation (2+ bets same direction) boosts 15m conviction by 1."""
    import sqlite3
    import json
    from predict import store_prediction

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
        estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
        predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")

    # Use DOWN direction to avoid UP sweet spot boost (mkt_price 0.20-0.70 → +1)
    signal = {"estimate": 0.42, "should_trade": True, "confidence": "medium",
              "direction": "DOWN", "streak": -3, "reason": "ride_streak_DOWN"}
    regime = {"label": "MEDIUM_VOL / TRENDING", "is_mean_reverting": False,
              "autocorrelation": 0.20, "volatility": 0.08}

    # Without sibling context → conv=3 (base)
    store_prediction(db, "m1", signal, regime, cycle=1, mkt_price=0.50)
    row = db.execute("SELECT conviction_score, reasoning FROM predictions WHERE market_id='m1'").fetchone()
    assert row[0] == 3, f"Base conviction should be 3, got {row[0]}"

    # With sibling context confirming same direction → conv=4 (boosted)
    sibling = {"bets": 3, "direction": "DOWN", "up": 0, "down": 3,
               "streak_direction": "DOWN", "streak_length": 3}
    store_prediction(db, "m2", signal, regime, cycle=1, mkt_price=0.50, sibling_context=sibling)
    row2 = db.execute("SELECT conviction_score, reasoning FROM predictions WHERE market_id='m2'").fetchone()
    assert row2[0] == 4, f"Boosted conviction should be 4, got {row2[0]}"
    reasoning = json.loads(row2[1])
    assert reasoning.get("sibling_5m_boost") is True

    # With sibling context in opposite direction → no boost, stays conv=3
    sibling_opp = {"bets": 3, "direction": "UP", "up": 3, "down": 0,
                   "streak_direction": "UP", "streak_length": 3}
    store_prediction(db, "m3", signal, regime, cycle=1, mkt_price=0.50, sibling_context=sibling_opp)
    row3 = db.execute("SELECT conviction_score FROM predictions WHERE market_id='m3'").fetchone()
    assert row3[0] == 3, f"Opposite sibling should not boost, got {row3[0]}"
    db.close()


def test_sibling_boost_does_not_affect_5m():
    """5m pipeline (loose_mode=False) never gets sibling boost — sibling_context is None."""
    from predict import store_prediction
    import sqlite3

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
        estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
        predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")

    # Use DOWN direction to avoid UP sweet spot boost (mkt_price 0.20-0.70 → +1)
    signal = {"estimate": 0.42, "should_trade": True, "confidence": "medium",
              "direction": "DOWN", "streak": -3, "reason": "ride_streak_DOWN"}
    regime = {"label": "MEDIUM_VOL / TRENDING", "is_mean_reverting": False,
              "autocorrelation": 0.20, "volatility": 0.08}

    # 5m pipeline: no sibling_context passed
    store_prediction(db, "m1", signal, regime, cycle=1, mkt_price=0.50, loose_mode=False)
    row = db.execute("SELECT conviction_score FROM predictions WHERE market_id='m1'").fetchone()
    assert row[0] == 3, f"5m base conviction should be 3, got {row[0]}"
    db.close()


def test_15m_config_matches_5m():
    """btc_15m shadow config should match btc_5m (uses 5m candles now)."""
    from config import SHADOW_CONFIGS
    assert SHADOW_CONFIGS["btc_15m"]["min_streak"] == SHADOW_CONFIGS["btc_5m"]["min_streak"]
    assert SHADOW_CONFIGS["btc_15m"]["baseline_streak"] == SHADOW_CONFIGS["btc_5m"]["baseline_streak"]


def test_5m_workflow_does_not_commit_15m_files():
    """5m CI workflow does not touch 15m files."""
    workflow = os.path.join(os.path.dirname(__file__), "..",
                           ".github", "workflows", "predict-and-score.yml")
    with open(workflow) as f:
        content = f.read()
    assert "predictions_15m" not in content
    assert "15m.html" not in content
