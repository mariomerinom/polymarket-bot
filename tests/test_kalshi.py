"""
test_kalshi.py — Tests for the Kalshi Phase 0 pipeline.

Validates market discovery, candle fetching, scoring, and dashboard integration
without requiring Kalshi API credentials (mock mode).
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestKalshiMarkets:
    """Tests for kalshi_markets.py."""

    def test_init_db_creates_tables(self, tmp_path):
        """DB initialization creates markets and predictions tables."""
        import kalshi_markets
        original = kalshi_markets.DB_PATH_KALSHI
        kalshi_markets.DB_PATH_KALSHI = tmp_path / "test_kalshi.db"
        try:
            db = kalshi_markets.init_db_kalshi()
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "markets" in table_names
            assert "predictions" in table_names
            db.close()
        finally:
            kalshi_markets.DB_PATH_KALSHI = original

    def test_mock_markets_returned(self):
        """Mock mode returns a non-empty list of markets."""
        from kalshi_markets import fetch_active_kalshi_markets
        markets = fetch_active_kalshi_markets(mock_mode=True)
        assert len(markets) > 0

    def test_market_schema(self):
        """All mock markets have required fields."""
        from kalshi_markets import fetch_active_kalshi_markets
        markets = fetch_active_kalshi_markets(mock_mode=True)
        required = {"id", "question", "end_date", "price_yes", "category"}
        for m in markets:
            assert required.issubset(m.keys()), f"Missing keys: {required - m.keys()}"

    def test_timeframe_filter(self):
        """Markets are filtered to 15m and 1h only."""
        from kalshi_markets import fetch_active_kalshi_markets
        markets = fetch_active_kalshi_markets(mock_mode=True)
        for m in markets:
            assert m.get("timeframe") in ("15m", "1h"), f"Unexpected timeframe: {m.get('timeframe')}"

    def test_store_and_retrieve(self, tmp_path):
        """Markets can be stored and retrieved from DB."""
        import kalshi_markets
        original = kalshi_markets.DB_PATH_KALSHI
        kalshi_markets.DB_PATH_KALSHI = tmp_path / "test_kalshi.db"
        try:
            db = kalshi_markets.init_db_kalshi()
            markets = kalshi_markets.fetch_active_kalshi_markets(mock_mode=True)
            kalshi_markets.store_markets_kalshi(db, markets)
            count = db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
            assert count == len(markets)
            db.close()
        finally:
            kalshi_markets.DB_PATH_KALSHI = original

    def test_mock_orderbook(self):
        """Mock orderbook returns valid bid/ask/mid."""
        from kalshi_markets import fetch_kalshi_orderbook
        ob = fetch_kalshi_orderbook("BTCUSD-TEST-12345", mock_mode=True)
        assert ob is not None
        assert 0 < ob["bid"] < ob["ask"] < 1
        assert ob["bid"] < ob["mid"] < ob["ask"]
        assert ob["spread"] > 0


class TestKalshiData:
    """Tests for kalshi_data.py."""

    def test_candles_returned(self):
        """fetch_kalshi_candles returns a dict with candles list."""
        from kalshi_data import fetch_kalshi_candles
        data = fetch_kalshi_candles(interval="15m", limit=12)
        assert data is not None
        assert "candles" in data
        assert len(data["candles"]) > 0

    def test_candle_format_compatible(self):
        """Candle dicts have open/high/low/close/volume."""
        from kalshi_data import fetch_kalshi_candles
        data = fetch_kalshi_candles(interval="15m", limit=12)
        if data and data["candles"]:
            candle = data["candles"][0]
            for key in ("open", "high", "low", "close"):
                assert key in candle, f"Missing key: {key}"

    def test_momentum_signal_accepts_candles(self):
        """predict.momentum_signal() works on Kalshi candle output."""
        from kalshi_data import fetch_kalshi_candles
        from predict import momentum_signal
        data = fetch_kalshi_candles(interval="15m", limit=12)
        if data and len(data["candles"]) >= 5:
            signal = momentum_signal(data["candles"], min_streak=2)
            assert "estimate" in signal
            assert 0 <= signal["estimate"] <= 1
            assert "should_trade" in signal


class TestKalshiScore:
    """Tests for kalshi_score.py."""

    def test_auto_resolve_empty_db(self, tmp_path):
        """auto_resolve_kalshi on empty DB returns 0 without crash."""
        import kalshi_markets
        original = kalshi_markets.DB_PATH_KALSHI
        kalshi_markets.DB_PATH_KALSHI = tmp_path / "test_kalshi.db"
        try:
            db = kalshi_markets.init_db_kalshi()
            from kalshi_score import auto_resolve_kalshi
            result = auto_resolve_kalshi(db)
            assert result == 0
            db.close()
        finally:
            kalshi_markets.DB_PATH_KALSHI = original

    def test_brier_scores_on_kalshi_db(self, tmp_path):
        """calculate_brier_scores works on Kalshi DB schema."""
        import kalshi_markets
        original = kalshi_markets.DB_PATH_KALSHI
        kalshi_markets.DB_PATH_KALSHI = tmp_path / "test_kalshi.db"
        try:
            db = kalshi_markets.init_db_kalshi()
            # Insert a resolved market and prediction
            db.execute("""
                INSERT INTO markets (id, question, category, end_date, volume, price_yes, resolved, outcome)
                VALUES ('test-1', 'Test market', 'crypto', '2026-01-01T00:00:00Z', 1000, 0.5, 1, 1)
            """)
            db.execute("""
                INSERT INTO predictions (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score, regime)
                VALUES ('test-1', 'momentum_kalshi', 0.62, 0.12, 'medium', '{}', '2026-01-01T00:00:00Z', 1, 2, 'LOW_VOL_TRENDING')
            """)
            db.commit()

            from score import calculate_brier_scores
            results = calculate_brier_scores(db)
            assert results is not None
            assert "momentum_kalshi" in results
            db.close()
        finally:
            kalshi_markets.DB_PATH_KALSHI = original


# TestKalshiNavBar removed — dashboard retired 2026-04-08
