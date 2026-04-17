"""Tests for intraday_regime_gate.py."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import intraday_regime_gate as igr


def _mk_candles(open_price, high, low, n=10):
    """Build a list of `n` candle dicts with given open/high/low extremes."""
    candles = [{"open": open_price, "high": open_price, "low": open_price,
                "close": open_price}]
    for _ in range(n - 2):
        candles.append({"open": open_price, "high": open_price,
                        "low": open_price, "close": open_price})
    # Place the extreme high/low in the final bar
    candles.append({"open": open_price, "high": high, "low": low,
                    "close": open_price})
    return candles


# Historical distribution — mean 0.025, std roughly 0.010
NORMAL_HIST = [0.020, 0.025, 0.030, 0.022, 0.028, 0.024, 0.026,
               0.021, 0.027, 0.023, 0.025, 0.024, 0.026, 0.022,
               0.028, 0.020, 0.030, 0.023, 0.025, 0.027, 0.024,
               0.026, 0.022, 0.028, 0.021, 0.029, 0.024, 0.025,
               0.026, 0.023]  # 30 samples


# ── Morning exemption ────────────────────────────────────────────────


class TestMorningExemption:

    def test_before_cutoff_never_gates(self):
        """3:00 UTC, 4.5% range (very high z) — exempt."""
        candles = _mk_candles(open_price=70000, high=73150, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles,
            asset="BTC",
            asof_utc=datetime(2026, 4, 7, 3, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert "morning_exemption" in result["reason"]

    def test_at_cutoff_gates(self):
        """At exactly 12:00 UTC, morning exemption no longer applies."""
        candles = _mk_candles(open_price=70000, high=73500, low=70000)  # 5% range
        result = igr.evaluate_intraday_range_gate(
            candles=candles,
            asset="BTC",
            asof_utc=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        # 5% range vs 2.5% mean w/ std~0.003 = very high z, gates
        assert result["gated"] is True


# ── Insufficient data ────────────────────────────────────────────────


class TestInsufficientData:

    def test_no_candles_no_gate(self):
        result = igr.evaluate_intraday_range_gate(
            candles=[], asset="BTC",
            asof_utc=datetime(2026, 4, 7, 15, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert "insufficient_candles" in result["reason"]

    def test_too_few_candles_no_gate(self):
        """< 5 candles → exempt."""
        candles = _mk_candles(open_price=70000, high=71000, low=69000, n=3)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 15, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert "insufficient_candles" in result["reason"]

    def test_no_history_no_gate(self):
        candles = _mk_candles(open_price=70000, high=73500, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 15, 0, tzinfo=timezone.utc),
            historical_ranges_pct=[],
        )
        assert result["gated"] is False
        assert "insufficient_history" in result["reason"]

    def test_short_history_no_gate(self):
        candles = _mk_candles(open_price=70000, high=73500, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 15, 0, tzinfo=timezone.utc),
            historical_ranges_pct=[0.02, 0.03, 0.025],  # only 3
        )
        assert result["gated"] is False
        assert "insufficient_history" in result["reason"]


# ── Gate firing ──────────────────────────────────────────────────────


class TestGateFiring:

    def test_high_range_gates(self):
        """5% intraday range vs 2.5% historical mean → z well above 1.5."""
        candles = _mk_candles(open_price=70000, high=73500, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is True
        assert result["range_z"] > 1.5
        assert "range_z" in result["reason"]

    def test_normal_range_does_not_gate(self):
        """2.5% range ≈ mean → z near 0."""
        candles = _mk_candles(open_price=70000, high=71750, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert abs(result["range_z"]) < 1.0

    def test_low_range_does_not_gate(self):
        """Very calm day — 1% range, negative z, no gate."""
        candles = _mk_candles(open_price=70000, high=70700, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert result["range_z"] < 0

    def test_custom_threshold(self):
        """With threshold=3.0, the same high-range day might not gate."""
        candles = _mk_candles(open_price=70000, high=72100, low=70000)  # 3% range
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
            threshold_z=3.0,
        )
        assert result["gated"] is False


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:

    def test_bad_open_price_no_gate(self):
        bad = [{"open": 0, "high": 1000, "low": 900}] * 10
        result = igr.evaluate_intraday_range_gate(
            candles=bad, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert "bad_open_price" in result["reason"]

    def test_malformed_candle_no_gate(self):
        bad = [{"open": 70000}] * 10  # missing high/low
        result = igr.evaluate_intraday_range_gate(
            candles=bad, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=NORMAL_HIST,
        )
        assert result["gated"] is False
        assert "candle_parse_error" in result["reason"]

    def test_zero_std_no_gate(self):
        """If all historical ranges identical, std=0 — cannot compute z."""
        candles = _mk_candles(open_price=70000, high=73500, low=70000)
        result = igr.evaluate_intraday_range_gate(
            candles=candles, asset="BTC",
            asof_utc=datetime(2026, 4, 7, 20, 0, tzinfo=timezone.utc),
            historical_ranges_pct=[0.025] * 10,
        )
        assert result["gated"] is False
        assert "zero_std" in result["reason"]


# ── fetch_historical_ranges_pct ──────────────────────────────────────


class TestFetchHistory:

    def test_fetches_from_asset_daily(self, tmp_path):
        import sqlite3
        db = sqlite3.connect(":memory:")
        db.execute("""
            CREATE TABLE asset_daily (
                asset TEXT NOT NULL, date TEXT NOT NULL,
                range_pct REAL, PRIMARY KEY (asset, date)
            )
        """)
        for i, rp in enumerate([0.02, 0.025, 0.03, 0.022]):
            db.execute(
                "INSERT INTO asset_daily (asset, date, range_pct) VALUES (?, ?, ?)",
                ("BTC", f"2026-04-{i+1:02d}", rp),
            )
        db.commit()
        result = igr.fetch_historical_ranges_pct(db, "BTC", days=30)
        assert len(result) == 4
        # Should exclude a given date
        result2 = igr.fetch_historical_ranges_pct(
            db, "BTC", exclude_date="2026-04-03", days=30)
        assert len(result2) == 3
        assert 0.03 not in result2

    def test_missing_table_returns_empty(self):
        import sqlite3
        db = sqlite3.connect(":memory:")
        assert igr.fetch_historical_ranges_pct(db, "BTC") == []
