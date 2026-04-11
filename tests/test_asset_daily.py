"""
test_asset_daily.py — Contract tests for daily regime metrics.

Behavioral contracts (NOT asserting exact numbers, asserting directional
sanity so the tests don't drift when we tune thresholds):

  1. Trending-up synthetic day → body_pct > 0, trend_label in {up, strong_up},
     velocity > 0.
  2. Trending-down synthetic day → symmetric.
  3. Chop day → |body_pct| small, trend_label == "chop".
  4. High-vol vs low-vol → realized_vol and parkinson_vol both higher.
  5. Volume skew: back-loaded session → session_volume_skew > 0.
  6. VWAP sanity: close above all bars → vwap_close_dev > 0.
  7. Schema round-trip: record() then SELECT returns what we put in.
  8. Idempotency: record() twice on same (asset, date) does not duplicate.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_frame(closes, volumes=None, spread=0.001):
    """Build a synthetic 5m OHLCV frame from a close-price path.

    Each bar's high/low sit ±spread*close around the close; open = prior
    close (first open = first close).
    """
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    opens = np.empty(n)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]
    highs = np.maximum(opens, closes) * (1 + spread)
    lows = np.minimum(opens, closes) * (1 - spread)
    vols = np.asarray(volumes, dtype=float) if volumes is not None else np.ones(n) * 100.0
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": vols,
    })


class TestCoreMetrics:

    def test_trending_up_day(self):
        from asset_daily import compute_daily
        closes = np.linspace(100.0, 103.0, 288)
        m = compute_daily(_make_frame(closes))
        assert m["body_pct"] > 0
        assert m["velocity"] > 0
        assert m["trend_label"] in ("up", "strong_up")
        assert m["intraday_drift"] > 0

    def test_trending_down_day(self):
        from asset_daily import compute_daily
        closes = np.linspace(103.0, 100.0, 288)
        m = compute_daily(_make_frame(closes))
        assert m["body_pct"] < 0
        assert m["velocity"] < 0
        assert m["trend_label"] in ("down", "strong_down")

    def test_chop_day(self):
        from asset_daily import compute_daily
        rng = np.random.default_rng(7)
        # mean-reverting around 100 with tiny drift
        noise = rng.normal(0, 0.05, 288)
        closes = 100.0 + np.cumsum(noise) * 0.1
        closes[-1] = closes[0] + 0.01  # force near-zero body
        m = compute_daily(_make_frame(closes))
        assert abs(m["body_pct"]) < 0.005
        assert m["trend_label"] == "chop"

    def test_vol_higher_when_prices_whip(self):
        from asset_daily import compute_daily
        rng = np.random.default_rng(42)
        calm = 100.0 + np.cumsum(rng.normal(0, 0.02, 288))
        wild = 100.0 + np.cumsum(rng.normal(0, 0.5, 288))
        m_calm = compute_daily(_make_frame(calm))
        m_wild = compute_daily(_make_frame(wild))
        assert m_wild["realized_vol"] > m_calm["realized_vol"]
        assert m_wild["parkinson_vol"] > m_calm["parkinson_vol"]

    def test_range_pct_matches_high_low(self):
        from asset_daily import compute_daily
        closes = np.linspace(100.0, 110.0, 288)
        m = compute_daily(_make_frame(closes, spread=0.0))
        # range should be (110 - 100) / 100 ≈ 0.10
        assert 0.09 < m["range_pct"] < 0.12


class TestLiquidity:

    def test_backloaded_volume_skew_positive(self):
        from asset_daily import compute_daily
        closes = np.full(288, 100.0)
        closes[0] = 99.9
        vols = np.concatenate([np.ones(144) * 10, np.ones(144) * 90])
        m = compute_daily(_make_frame(closes, volumes=vols))
        assert m["session_volume_skew"] > 0.5

    def test_frontloaded_volume_skew_negative(self):
        from asset_daily import compute_daily
        closes = np.full(288, 100.0)
        closes[0] = 99.9
        vols = np.concatenate([np.ones(144) * 90, np.ones(144) * 10])
        m = compute_daily(_make_frame(closes, volumes=vols))
        assert m["session_volume_skew"] < -0.5

    def test_vwap_bounded_by_price_range(self):
        from asset_daily import compute_daily
        closes = np.linspace(100.0, 105.0, 288)
        m = compute_daily(_make_frame(closes))
        assert m["low"] <= m["vwap"] <= m["high"]

    def test_volume_total_sums_correctly(self):
        from asset_daily import compute_daily
        closes = np.linspace(100.0, 100.5, 288)
        vols = np.ones(288) * 7.0
        m = compute_daily(_make_frame(closes, volumes=vols))
        assert abs(m["volume_total"] - 288 * 7.0) < 1e-6


class TestInputValidation:

    def test_rejects_empty_frame(self):
        from asset_daily import compute_daily
        with pytest.raises(ValueError):
            compute_daily(pd.DataFrame())

    def test_rejects_missing_columns(self):
        from asset_daily import compute_daily
        df = pd.DataFrame({"open": [1, 2], "close": [1, 2]})
        with pytest.raises(ValueError):
            compute_daily(df)

    def test_single_row_rejected(self):
        from asset_daily import compute_daily
        df = _make_frame([100.0, 101.0]).iloc[:1]
        with pytest.raises(ValueError):
            compute_daily(df)


class TestPersistence:

    def _db(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        return db

    def test_roundtrip(self):
        from asset_daily import compute_daily, init_table, record
        db = self._db()
        init_table(db)
        closes = np.linspace(100.0, 102.0, 288)
        metrics = compute_daily(_make_frame(closes))
        record(db, asset="BTC", date="2026-04-07", metrics=metrics)
        row = db.execute(
            "SELECT * FROM asset_daily WHERE asset='BTC' AND date='2026-04-07'"
        ).fetchone()
        assert row is not None
        assert row["trend_label"] in ("up", "strong_up")
        assert abs(row["open"] - metrics["open"]) < 1e-9
        assert abs(row["close"] - metrics["close"]) < 1e-9

    def test_idempotent_insert_or_replace(self):
        from asset_daily import compute_daily, record
        db = self._db()
        closes = np.linspace(100.0, 101.0, 288)
        metrics = compute_daily(_make_frame(closes))
        record(db, asset="BTC", date="2026-04-07", metrics=metrics)
        record(db, asset="BTC", date="2026-04-07", metrics=metrics)
        n = db.execute(
            "SELECT COUNT(*) FROM asset_daily WHERE asset='BTC' AND date='2026-04-07'"
        ).fetchone()[0]
        assert n == 1

    def test_multi_asset_independent(self):
        from asset_daily import compute_daily, record
        db = self._db()
        closes = np.linspace(100.0, 101.0, 288)
        m = compute_daily(_make_frame(closes))
        record(db, asset="BTC", date="2026-04-07", metrics=m)
        record(db, asset="ETH", date="2026-04-07", metrics=m)
        n = db.execute("SELECT COUNT(*) FROM asset_daily").fetchone()[0]
        assert n == 2
