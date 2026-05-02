"""Tests for shadow_indicators.py — RSI, OBV, VWAP shadow logging."""

import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shadow_indicators import (
    BTC5M_TRIAGE_WEAK_HOURS_UTC,
    compute_btc5m_signal_triage,
    compute_rsi,
    compute_obv_slope,
    compute_vwap_zscore,
    shadow_log_indicators,
)


# ---------------------------------------------------------------------------
# RSI tests
# ---------------------------------------------------------------------------

class TestRSI:
    def test_bullish_trending_up(self):
        # 20 candles steadily rising -> RSI should be high (>70)
        closes = [100 + i * 2 for i in range(20)]
        rsi = compute_rsi(closes, period=14)
        assert rsi > 70, f"Expected RSI > 70 for uptrend, got {rsi}"

    def test_bearish_trending_down(self):
        # 20 candles steadily falling -> RSI should be low (<30)
        closes = [200 - i * 2 for i in range(20)]
        rsi = compute_rsi(closes, period=14)
        assert rsi < 30, f"Expected RSI < 30 for downtrend, got {rsi}"

    def test_neutral_mixed(self):
        # Alternating up/down -> RSI near 50
        closes = [100 + (1 if i % 2 == 0 else -1) for i in range(20)]
        rsi = compute_rsi(closes, period=14)
        assert 30 < rsi < 70, f"Expected RSI near 50 for mixed, got {rsi}"

    def test_insufficient_data(self):
        closes = [100, 101, 102]
        rsi = compute_rsi(closes, period=14)
        assert rsi == 50.0, f"Expected 50.0 for insufficient data, got {rsi}"

    def test_flat_prices(self):
        closes = [100.0] * 20
        rsi = compute_rsi(closes, period=14)
        assert rsi == 50.0


# ---------------------------------------------------------------------------
# OBV tests
# ---------------------------------------------------------------------------

def _make_candles(closes, volumes=None):
    """Helper to build candle dicts from close prices."""
    if volumes is None:
        volumes = [100.0] * len(closes)
    candles = []
    for i, (c, v) in enumerate(zip(closes, volumes)):
        candles.append({
            "open": c - 0.5,
            "high": c + 1.0,
            "low": c - 1.0,
            "close": c,
            "volume": v,
            "time": f"{i:02d}:00",
        })
    return candles


class TestOBV:
    def test_positive_slope(self):
        # Rising closes -> volume accumulates positively -> positive slope
        closes = [100 + i for i in range(15)]
        candles = _make_candles(closes)
        slope = compute_obv_slope(candles)
        assert slope > 0, f"Expected positive OBV slope, got {slope}"

    def test_negative_slope(self):
        # Falling closes -> volume drains -> negative slope
        closes = [200 - i for i in range(15)]
        candles = _make_candles(closes)
        slope = compute_obv_slope(candles)
        assert slope < 0, f"Expected negative OBV slope, got {slope}"

    def test_insufficient_data(self):
        candles = _make_candles([100.0])
        slope = compute_obv_slope(candles)
        assert slope == 0.0


# ---------------------------------------------------------------------------
# VWAP tests
# ---------------------------------------------------------------------------

class TestVWAP:
    def test_price_above_vwap(self):
        # Last candle well above VWAP -> positive z-score
        closes = [100.0] * 14 + [120.0]
        candles = _make_candles(closes, volumes=[100] * 15)
        result = compute_vwap_zscore(candles)
        assert result["zscore"] > 0
        assert result["vwap"] is not None

    def test_price_below_vwap(self):
        # Last candle well below VWAP -> negative z-score
        closes = [100.0] * 14 + [80.0]
        candles = _make_candles(closes, volumes=[100] * 15)
        result = compute_vwap_zscore(candles)
        assert result["zscore"] < 0

    def test_strong_signal_down(self):
        # Extreme deviation above -> signal DOWN
        closes = [100.0] * 14 + [150.0]
        candles = _make_candles(closes, volumes=[100] * 15)
        result = compute_vwap_zscore(candles)
        assert result["signal"] == "DOWN"

    def test_strong_signal_up(self):
        # Extreme deviation below -> signal UP
        closes = [100.0] * 14 + [50.0]
        candles = _make_candles(closes, volumes=[100] * 15)
        result = compute_vwap_zscore(candles)
        assert result["signal"] == "UP"

    def test_no_signal_within_range(self):
        # Close near VWAP -> no signal
        closes = [100.0 + i * 0.01 for i in range(15)]
        candles = _make_candles(closes, volumes=[100] * 15)
        result = compute_vwap_zscore(candles)
        assert result["signal"] is None

    def test_insufficient_data(self):
        candles = _make_candles([100.0, 101.0])
        result = compute_vwap_zscore(candles)
        assert result["vwap"] is None


# ---------------------------------------------------------------------------
# BTC 5m signal triage shadow tests
# ---------------------------------------------------------------------------

class TestBTC5MSignalTriageShadow:
    def test_tags_current_btc5m_risk_cohorts_without_changing_trade_fields(self):
        reasoning = {
            "judge": {"should_bet": True, "p_success": 0.61, "threshold": 0.52}
        }

        tags = compute_btc5m_signal_triage(
            reasoning,
            predicted_at="2026-05-02T13:15:00+00:00",
            regime="MEDIUM_VOL / TRENDING",
            estimate=0.62,
            conviction=4,
            agent="momentum_rule",
        )

        assert "shadow_btc5m_trending_only" in tags
        assert "shadow_btc5m_weak_hour_filter" in tags
        assert "shadow_btc5m_conv4_up_recalibration" in tags
        assert "shadow_btc5m_judge_accept" in tags
        assert tags["shadow_btc5m_weak_hour_filter"]["hour_utc"] == 13
        assert tags["shadow_btc5m_weak_hour_filter"]["weak_hours_utc"] == sorted(
            BTC5M_TRIAGE_WEAK_HOURS_UTC
        )

    def test_ignores_non_production_or_low_conviction_predictions(self):
        tags = compute_btc5m_signal_triage(
            {"judge": {"should_bet": True}},
            predicted_at="2026-05-02T13:15:00+00:00",
            regime="MEDIUM_VOL / TRENDING",
            estimate=0.62,
            conviction=2,
            agent="vwap_meanrev",
        )

        assert tags == {}


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def _create_test_db():
    """Create an in-memory DB with predictions table."""
    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            agent TEXT,
            estimate REAL,
            edge REAL,
            confidence TEXT,
            reasoning TEXT,
            predicted_at TEXT,
            cycle INTEGER,
            conviction_score INTEGER,
            regime TEXT
        )
    """)
    return db


class TestShadowLogIntegration:
    def test_no_crash_on_empty_db(self):
        db = _create_test_db()
        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            mock_fetch.return_value = {
                "candles": _make_candles([100 + i for i in range(20)]),
            }
            result = shadow_log_indicators(db, cycle=999)
        assert result.get("summary", "").startswith("no predictions")

    def test_updates_reasoning_with_rsi(self):
        db = _create_test_db()
        reasoning = json.dumps({"mkt_price": 0.55, "signal": {"direction": "UP"}})
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.62, 0.12, "high", reasoning,
             "2026-01-01T00:00:00", 1, 3, "HIGH_VOL / NEUTRAL"),
        )
        db.commit()

        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            mock_fetch.return_value = {
                "candles": _make_candles([100 + i for i in range(20)]),
            }
            result = shadow_log_indicators(db, cycle=1)

        row = db.execute("SELECT reasoning FROM predictions WHERE id = 1").fetchone()
        updated = json.loads(row[0])
        assert "shadow_rsi_14" in updated
        assert isinstance(updated["shadow_rsi_14"], float)
        # Price in 0.50-0.70 -> OBV should also be present
        assert "shadow_obv_slope" in updated

    def test_vwap_creates_prediction_for_mean_reverting(self):
        db = _create_test_db()
        reasoning = json.dumps({"mkt_price": 0.55})
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.5, 0.0, "skip", reasoning,
             "2026-01-01T00:00:00", 1, 0, "HIGH_VOL / MEAN_REVERTING"),
        )
        db.commit()

        # Candles with last price far above VWAP -> DOWN signal
        closes = [100.0] * 19 + [150.0]
        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            mock_fetch.return_value = {"candles": _make_candles(closes)}
            shadow_log_indicators(db, cycle=1)

        vwap_rows = db.execute(
            "SELECT agent, estimate, conviction_score, reasoning "
            "FROM predictions WHERE agent = 'vwap_meanrev'"
        ).fetchall()
        assert len(vwap_rows) == 1
        assert vwap_rows[0][0] == "vwap_meanrev"
        assert vwap_rows[0][1] == 0.45  # DOWN signal
        assert vwap_rows[0][2] == 2  # paper only

    def test_shadow_never_modifies_estimate_or_conviction(self):
        db = _create_test_db()
        reasoning = json.dumps({"mkt_price": 0.60})
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.62, 0.12, "high", reasoning,
             "2026-01-01T00:00:00", 1, 4, "MEDIUM_VOL / NEUTRAL"),
        )
        db.commit()

        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            mock_fetch.return_value = {
                "candles": _make_candles([100 + i for i in range(20)]),
            }
            shadow_log_indicators(db, cycle=1)

        row = db.execute(
            "SELECT estimate, conviction_score FROM predictions WHERE id = 1"
        ).fetchone()
        assert row[0] == 0.62, "estimate must not change"
        assert row[1] == 4, "conviction must not change"

    def test_no_duplicate_vwap_predictions(self):
        db = _create_test_db()
        reasoning = json.dumps({"mkt_price": 0.55})
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.5, 0.0, "skip", reasoning,
             "2026-01-01T00:00:00", 1, 0, "HIGH_VOL / MEAN_REVERTING"),
        )
        db.commit()

        closes = [100.0] * 19 + [150.0]
        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            mock_fetch.return_value = {"candles": _make_candles(closes)}
            # Run twice on same cycle
            shadow_log_indicators(db, cycle=1)
            shadow_log_indicators(db, cycle=1)

        count = db.execute(
            "SELECT COUNT(*) FROM predictions WHERE agent = 'vwap_meanrev'"
        ).fetchone()[0]
        assert count == 1, f"Expected 1 VWAP prediction, got {count}"

    def test_shadow_log_accepts_candles_param(self):
        """When candles are passed directly, _fetch_candles is NOT called."""
        db = _create_test_db()
        reasoning = json.dumps({"mkt_price": 0.60})
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.62, 0.12, "high", reasoning,
             "2026-01-01T00:00:00", 1, 3, "MEDIUM_VOL / NEUTRAL"),
        )
        db.commit()

        candles = _make_candles([100 + i for i in range(20)])

        with patch("shadow_indicators._fetch_candles") as mock_fetch:
            result = shadow_log_indicators(db, cycle=1, candles=candles)

        # _fetch_candles must NOT have been called
        mock_fetch.assert_not_called()

        # Indicators should still be logged
        row = db.execute("SELECT reasoning FROM predictions WHERE id = 1").fetchone()
        updated = json.loads(row[0])
        assert "shadow_rsi_14" in updated
        assert isinstance(updated["shadow_rsi_14"], float)
        assert result.get("updated") == 1

    def test_logs_btc5m_signal_triage_shadow_flags(self):
        db = _create_test_db()
        reasoning = json.dumps({
            "mkt_price": 0.60,
            "judge": {"should_bet": True, "p_success": 0.62, "threshold": 0.52},
        })
        db.execute(
            "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
            "reasoning, predicted_at, cycle, conviction_score, regime) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("mkt1", "momentum_rule", 0.62, 0.12, "high", reasoning,
             "2026-05-02T13:15:00+00:00", 1, 4, "MEDIUM_VOL / TRENDING"),
        )
        db.commit()

        candles = _make_candles([100 + i for i in range(20)])
        shadow_log_indicators(db, cycle=1, candles=candles)

        row = db.execute("SELECT reasoning FROM predictions WHERE id = 1").fetchone()
        updated = json.loads(row[0])
        assert "shadow_btc5m_trending_only" in updated
        assert "shadow_btc5m_weak_hour_filter" in updated
        assert "shadow_btc5m_conv4_up_recalibration" in updated
        assert "shadow_btc5m_judge_accept" in updated

        estimate, conviction = db.execute(
            "SELECT estimate, conviction_score FROM predictions WHERE id = 1"
        ).fetchone()
        assert estimate == 0.62
        assert conviction == 4
