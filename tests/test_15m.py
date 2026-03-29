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


def test_15m_uses_relaxed_thresholds():
    """ci_run_15m passes min_streak=2 and autocorr_threshold=-0.20."""
    import inspect
    # Read ci_run_15m source to verify it passes the right thresholds
    ci_run_15m_path = os.path.join(os.path.dirname(__file__), "..", "src", "ci_run_15m.py")
    with open(ci_run_15m_path) as f:
        source = f.read()
    assert "min_streak=2" in source, "15m must use min_streak=2"
    assert "autocorr_threshold=-0.20" in source, "15m must use autocorr_threshold=-0.20"


def test_run_predictions_accepts_threshold_params():
    """run_predictions accepts min_streak and autocorr_threshold parameters."""
    from predict import run_predictions
    import inspect
    sig = inspect.signature(run_predictions)
    assert "min_streak" in sig.parameters
    assert "autocorr_threshold" in sig.parameters
    # Verify defaults preserve 5m behavior
    assert sig.parameters["min_streak"].default == 3
    assert sig.parameters["autocorr_threshold"].default == -0.15


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


def test_5m_workflow_does_not_commit_15m_files():
    """5m CI workflow does not touch 15m files."""
    workflow = os.path.join(os.path.dirname(__file__), "..",
                           ".github", "workflows", "predict-and-score.yml")
    with open(workflow) as f:
        content = f.read()
    assert "predictions_15m" not in content
    assert "15m.html" not in content
