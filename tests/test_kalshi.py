"""
test_kalshi.py — Tests for the Kalshi Phase 0 pipeline.

Validates market discovery, candle fetching, scoring, and dashboard integration
without requiring Kalshi API credentials (mock mode).
"""

import os
import sys
import sqlite3

import pytest

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

    def test_parse_strike_from_market_id(self):
        """Strike price is correctly parsed from Kalshi market ID format."""
        from kalshi_score import parse_strike_from_market_id

        assert parse_strike_from_market_id("BTCUSD-2604021350-84000") == 84000.0
        assert parse_strike_from_market_id("BTCUSD-2604100015-85500") == 85500.0
        assert parse_strike_from_market_id("BTCUSD-2604021435-85000") == 85000.0
        # Invalid formats return None
        assert parse_strike_from_market_id("invalid-id") is None
        assert parse_strike_from_market_id("test-1") is None

    def test_resolve_from_candle_above_strike(self):
        """Market resolves to 1 (yes) when BTC price >= strike."""
        from kalshi_score import _resolve_from_candle
        from datetime import datetime, timezone, timedelta

        # Expiry 5 minutes ago — within the candle window
        expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
        expiry_hhmm = expiry.strftime("%H:%M")
        prev_hhmm = (expiry - timedelta(minutes=5)).strftime("%H:%M")
        next_hhmm = (expiry + timedelta(minutes=5)).strftime("%H:%M")

        fake_candles = {
            "candles": [
                {"time": prev_hhmm, "open": 84500, "close": 85000, "high": 85100, "low": 84400},
                {"time": expiry_hhmm, "open": 85000, "close": 85200, "high": 85300, "low": 84900},
                {"time": next_hhmm, "open": 85200, "close": 85100, "high": 85400, "low": 85000},
            ],
            "current_price": 85100,
            "_window_seconds": 3600,
        }

        # Strike 84000, BTC at 85200 at expiry -> above strike -> outcome 1
        result = _resolve_from_candle(
            "BTCUSD-2604021350-84000",
            expiry.isoformat(),
            candle_data=fake_candles,
        )
        assert result == 1

    def test_resolve_from_candle_below_strike(self):
        """Market resolves to 0 (no) when BTC price < strike."""
        from kalshi_score import _resolve_from_candle
        from datetime import datetime, timezone, timedelta

        expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
        expiry_hhmm = expiry.strftime("%H:%M")
        prev_hhmm = (expiry - timedelta(minutes=5)).strftime("%H:%M")
        next_hhmm = (expiry + timedelta(minutes=5)).strftime("%H:%M")

        fake_candles = {
            "candles": [
                {"time": prev_hhmm, "open": 84500, "close": 84800, "high": 84900, "low": 84400},
                {"time": expiry_hhmm, "open": 84800, "close": 84900, "high": 85000, "low": 84700},
                {"time": next_hhmm, "open": 84900, "close": 84700, "high": 85000, "low": 84600},
            ],
            "current_price": 84700,
            "_window_seconds": 3600,
        }

        # Strike 85500, BTC at 84900 at expiry -> below strike -> outcome 0
        result = _resolve_from_candle(
            "BTCUSD-2604021350-85500",
            expiry.isoformat(),
            candle_data=fake_candles,
        )
        assert result == 0

    def test_resolve_from_candle_no_data_returns_none(self):
        """Returns None when candle data is unavailable (no hash fallback)."""
        from kalshi_score import _resolve_from_candle

        result = _resolve_from_candle(
            "BTCUSD-2604021350-84000",
            "2026-04-02T13:50:00+00:00",
            candle_data=None,
        )
        assert result is None

    def test_resolve_old_market_returns_none(self):
        """Markets older than the candle window are not resolved (prevents wrong-day matching)."""
        from kalshi_score import _resolve_from_candle
        from datetime import datetime, timezone, timedelta

        # Expiry 2 hours ago — outside 90-minute window
        old_expiry = datetime.now(timezone.utc) - timedelta(hours=2)

        fake_candles = {
            "candles": [
                {"time": "13:45", "open": 84500, "close": 85000, "high": 85100, "low": 84400},
            ],
            "current_price": 85000,
            "_window_seconds": 3600,  # 1 hour window
        }

        result = _resolve_from_candle(
            "BTCUSD-2604021350-84000",
            old_expiry.isoformat(),
            candle_data=fake_candles,
        )
        assert result is None, "Old markets must not resolve against current candle data"

    def test_no_hash_based_resolution(self):
        """Verify _mock_resolve (hash-based) no longer exists in kalshi_score."""
        import kalshi_score
        assert not hasattr(kalshi_score, "_mock_resolve"), \
            "Hash-based _mock_resolve must be removed — it produces random noise"


class TestKalshiConviction:
    """Tests for Kalshi Phase 1 conviction scoring."""

    def _make_signal(self, should_trade=True, direction="UP", streak=3,
                     confidence="medium", estimate=0.6):
        return {
            "should_trade": should_trade,
            "direction": direction,
            "streak": streak,
            "confidence": confidence,
            "estimate": estimate,
            "reason": "momentum" if should_trade else "no_streak",
        }

    def _make_regime(self, label="MEDIUM_VOL / TRENDING"):
        return {
            "label": label,
            "volatility": "MEDIUM_VOL",
            "autocorrelation": 0.3,
            "is_mean_reverting": False,
        }

    def _store(self, db, signal, regime):
        from ci_run_kalshi import store_prediction_kalshi
        return store_prediction_kalshi(
            db, "test-market-1", signal, regime, cycle=1,
        )

    @pytest.fixture
    def kalshi_db(self, tmp_path):
        import kalshi_markets
        original = kalshi_markets.DB_PATH_KALSHI
        kalshi_markets.DB_PATH_KALSHI = tmp_path / "test_kalshi.db"
        try:
            db = kalshi_markets.init_db_kalshi()
            # Insert a market for FK constraint
            db.execute("""
                INSERT INTO markets (id, question, category, end_date, volume, price_yes)
                VALUES ('test-market-1', 'test', 'crypto', '2099-01-01T00:00:00Z', 0, 0.5)
            """)
            db.commit()
            yield db
            db.close()
        finally:
            kalshi_markets.DB_PATH_KALSHI = original

    def test_conviction_up_trending_conv3(self, kalshi_db):
        """UP signal in TRENDING regime → conviction 3."""
        signal = self._make_signal(direction="UP", streak=3)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = self._store(kalshi_db, signal, regime)
        assert result["conviction_score"] == 3

    def test_conviction_down_neutral_demoted(self, kalshi_db):
        """DOWN signal in NEUTRAL regime → conviction 2 (demotion)."""
        signal = self._make_signal(direction="DOWN", streak=3)
        regime = self._make_regime("MEDIUM_VOL / NEUTRAL")
        result = self._store(kalshi_db, signal, regime)
        assert result["conviction_score"] == 2

    def test_conviction_long_streak_conv4(self, kalshi_db):
        """Streak >= 5 → conviction 4."""
        signal = self._make_signal(direction="UP", streak=5)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = self._store(kalshi_db, signal, regime)
        assert result["conviction_score"] == 4

    def test_conviction_no_trade_conv0(self, kalshi_db):
        """should_trade=False → conviction 0."""
        signal = self._make_signal(should_trade=False, estimate=0.5)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = self._store(kalshi_db, signal, regime)
        assert result["conviction_score"] == 0

    def test_conviction_high_vol_non_trending_skip(self, kalshi_db):
        """HIGH_VOL non-trending signal should still get conv=2 via DOWN+NEUTRAL
        or conv=3 but the regime gate in _run_predictions skips before store.
        Direct store with HIGH_VOL/NEUTRAL + DOWN → conv=2 (demotion)."""
        signal = self._make_signal(direction="DOWN", streak=3)
        regime = self._make_regime("HIGH_VOL / NEUTRAL")
        result = self._store(kalshi_db, signal, regime)
        # DOWN+NEUTRAL demotion excludes HIGH_VOL, so this should be conv=3
        # (the HIGH_VOL gate is in _run_predictions, not store_prediction)
        assert result["conviction_score"] == 3

    def test_conviction_down_neutral_excludes_high_vol(self, kalshi_db):
        """DOWN+NEUTRAL demotion only fires when HIGH_VOL is NOT in the label."""
        signal = self._make_signal(direction="DOWN", streak=3)
        # Non-HIGH_VOL NEUTRAL → demotion
        regime = self._make_regime("LOW_VOL / NEUTRAL")
        result = self._store(kalshi_db, signal, regime)
        assert result["conviction_score"] == 2


# TestKalshiNavBar removed — dashboard retired 2026-04-08
