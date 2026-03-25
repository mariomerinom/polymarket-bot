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
