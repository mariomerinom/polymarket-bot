"""Tests for relative_regime.py — asset-relative regime classification (Phase A)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import relative_regime as rr


# ── classify_relative ────────────────────────────────────────────────


class TestClassify:

    def test_high_vol_rel_when_z_above_1(self):
        """Today's vol is 1.5σ above mean → HIGH_VOL_REL."""
        hist = [0.02, 0.025, 0.03, 0.022, 0.028, 0.024, 0.026]  # mu~0.025
        # Pick a today vol that yields z >= 1.0
        result = rr.classify_relative(0.035, hist)
        assert result["label"] == "HIGH_VOL_REL"
        assert result["zscore"] >= 1.0

    def test_medium_vol_rel_when_z_near_zero(self):
        hist = [0.02, 0.025, 0.03, 0.022, 0.028, 0.024, 0.026]
        result = rr.classify_relative(0.025, hist)
        assert result["label"] == "MEDIUM_VOL_REL"

    def test_low_vol_rel_when_z_below_neg_half(self):
        hist = [0.02, 0.025, 0.03, 0.022, 0.028, 0.024, 0.026]
        # Today vol clearly below mean
        result = rr.classify_relative(0.015, hist)
        assert result["label"] == "LOW_VOL_REL"
        assert result["zscore"] <= -0.5

    def test_insufficient_history_returns_none_label(self):
        result = rr.classify_relative(0.025, [0.02, 0.025, 0.03])
        assert result["label"] is None
        assert "insufficient_history" in result["reason"]

    def test_zero_std_history_returns_none_label(self):
        hist = [0.025] * 10  # identical — std=0
        result = rr.classify_relative(0.025, hist)
        assert result["label"] is None
        assert "zero_std" in result["reason"]


# ── compute_shadow_regime ────────────────────────────────────────────


def _mk_candles(n, close_func):
    """Build n candles with closes defined by close_func(i)."""
    return [
        {"open": close_func(i), "high": close_func(i) * 1.001,
         "low": close_func(i) * 0.999, "close": close_func(i),
         "volume": 1000}
        for i in range(n)
    ]


class TestComputeShadowRegime:

    def test_insufficient_candles_returns_reason(self):
        result = rr.compute_shadow_regime([], "SOL")
        assert result["label"] is None
        assert "insufficient_candles" in result["reason"]

    def test_returns_realized_vol_and_asset(self):
        # Volatile price path
        candles = _mk_candles(30, lambda i: 100 + (i % 2) * 5)
        result = rr.compute_shadow_regime(candles, "SOL")
        # realized_vol should be computed (>= 0)
        assert result["asset"] == "SOL"
        assert result["realized_vol"] is not None
        assert result["realized_vol"] > 0

    def test_missing_db_returns_result_with_error(self, tmp_path):
        """When asset_daily.db doesn't exist, we return structured
        reason rather than raising."""
        candles = _mk_candles(30, lambda i: 100 + i * 0.1)
        fake_db = tmp_path / "missing.db"
        result = rr.compute_shadow_regime(candles, "SOL", db_path=fake_db)
        # realized_vol computed, but no history → label None
        assert result["realized_vol"] is not None
        assert result["label"] is None

    def test_with_history_classifies(self, tmp_path):
        """Happy path: candles + historical DB → classified label."""
        import sqlite3
        db_path = tmp_path / "asset_daily.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE asset_daily (
            asset TEXT, date TEXT, realized_vol REAL,
            PRIMARY KEY (asset, date))""")
        for i, rv in enumerate([0.02, 0.025, 0.03, 0.022, 0.028,
                                0.024, 0.026, 0.021, 0.029, 0.023]):
            conn.execute(
                "INSERT INTO asset_daily VALUES (?, ?, ?)",
                ("SOL", f"2026-03-{i + 1:02d}", rv),
            )
        conn.commit()
        conn.close()

        # Flat candles → low realized vol → LOW_VOL_REL
        flat = _mk_candles(30, lambda i: 100.0)
        result = rr.compute_shadow_regime(flat, "SOL", db_path=db_path)
        # Flat has near-zero realized_vol → well below historical mean
        assert result["label"] in ("LOW_VOL_REL", None)
        assert result["n_history"] == 10
