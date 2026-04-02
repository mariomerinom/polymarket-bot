"""
test_shadow_conviction.py — Tests for the shadow conviction scorer.

Validates strength signal computation, conviction tier mapping, and
the safety guarantee that shadow_log never raises.
"""

import os
import sys
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shadow_conviction_scorer import (
    strength_signal, conviction_from_estimate, shadow_log,
    SHADOW_CONFIGS, VOL_FLOOR,
)


def _make_candles(n, base=84000, step=50, volume=1000000):
    """Generate n synthetic UP-trending candles."""
    candles = []
    for i in range(n):
        o = base + i * step
        candles.append({
            "open": o, "high": o + 80, "low": o - 20,
            "close": o + step, "volume": volume,
        })
    return candles


def _make_flat_candles(n, price=84000, volume=1000000):
    """Generate n candles with near-zero movement."""
    candles = []
    for i in range(n):
        candles.append({
            "open": price, "high": price + 0.01, "low": price - 0.01,
            "close": price + 0.001, "volume": volume,
        })
    return candles


class TestStrengthSignal:
    """Tests for strength_signal()."""

    def test_returns_valid_structure(self):
        """Result has all required keys."""
        candles = _make_candles(12)
        result = strength_signal(candles, 5, "btc_5m")
        assert result is not None
        required = {
            "estimate", "confidence", "strength", "length_strength",
            "magnitude_strength", "net_return_pct", "realized_vol",
            "direction", "streak_len", "config_key",
        }
        assert required.issubset(result.keys())

    def test_strength_low_for_minimum_streak(self):
        """3-candle streak with small move → low strength."""
        candles = _make_candles(12, step=5)  # tiny moves
        result = strength_signal(candles, 3, "btc_5m")
        assert result is not None
        assert result["strength"] < 0.5

    def test_strength_high_for_max_streak(self):
        """8+ candle streak with large move → strength near 1.0."""
        candles = _make_candles(12, step=200)  # big moves
        result = strength_signal(candles, 8, "btc_5m")
        assert result is not None
        assert result["strength"] >= 0.8

    def test_magnitude_floor(self):
        """Near-zero volatility candles → vol floored, no infinity."""
        candles = _make_flat_candles(12)
        result = strength_signal(candles, 5, "btc_5m")
        assert result is not None
        assert result["realized_vol"] >= VOL_FLOOR
        assert math.isfinite(result["strength"])
        assert math.isfinite(result["magnitude_strength"])

    def test_direction_up(self):
        """Positive streak → estimate > 0.5."""
        candles = _make_candles(12)
        result = strength_signal(candles, 5, "btc_5m")
        assert result["estimate"] > 0.50
        assert result["direction"] == "UP"

    def test_direction_down(self):
        """Negative streak → estimate < 0.5."""
        candles = _make_candles(12)
        result = strength_signal(candles, -5, "btc_5m")
        assert result["estimate"] < 0.50
        assert result["direction"] == "DOWN"

    def test_zero_streak_returns_none(self):
        """Zero streak → None."""
        candles = _make_candles(12)
        assert strength_signal(candles, 0, "btc_5m") is None

    def test_empty_candles_returns_none(self):
        """Empty candles → None."""
        assert strength_signal([], 5, "btc_5m") is None

    def test_bad_config_returns_none(self):
        """Unknown config key → None."""
        candles = _make_candles(12)
        assert strength_signal(candles, 5, "nonexistent") is None

    def test_estimate_bounded(self):
        """Estimate stays within [0.36, 0.64] for btc_5m (max_edge=0.14)."""
        candles = _make_candles(20, step=500)
        result = strength_signal(candles, 15, "btc_5m")
        assert result is not None
        assert 0.36 <= result["estimate"] <= 0.64


class TestConvictionTierMapping:
    """Tests for conviction_from_estimate()."""

    def test_low_edge_gets_tier_2(self):
        """Small edge → tier 2."""
        tier = conviction_from_estimate(0.52, "btc_5m")
        assert tier == 2

    def test_medium_edge_gets_tier_3(self):
        """Medium edge → tier 3."""
        tier = conviction_from_estimate(0.56, "btc_5m")
        assert tier == 3

    def test_high_edge_gets_tier_4(self):
        """High edge → tier 4."""
        tier = conviction_from_estimate(0.59, "btc_5m")
        assert tier == 4

    def test_max_edge_gets_tier_5(self):
        """Maximum edge → tier 5."""
        tier = conviction_from_estimate(0.63, "btc_5m")
        assert tier == 5

    def test_no_edge_gets_tier_0(self):
        """Estimate at 0.50 → tier 0."""
        tier = conviction_from_estimate(0.50, "btc_5m")
        assert tier == 0

    def test_down_direction_same_tiers(self):
        """Below 0.50 maps the same way."""
        tier = conviction_from_estimate(0.37, "btc_5m")
        assert tier == 5

    def test_bad_config_returns_0(self):
        """Unknown config key → tier 0."""
        assert conviction_from_estimate(0.60, "nonexistent") == 0


class TestConfigs:
    """Tests for SHADOW_CONFIGS."""

    def test_all_configs_have_required_keys(self):
        """All config entries have the same required keys."""
        required = {
            "min_streak", "baseline_streak", "magnitude_multiplier",
            "max_edge", "high_confidence_threshold", "conv_thresholds",
        }
        for key, config in SHADOW_CONFIGS.items():
            assert required.issubset(config.keys()), f"{key} missing: {required - config.keys()}"

    def test_thresholds_are_sorted(self):
        """Conviction thresholds are in ascending order."""
        for key, config in SHADOW_CONFIGS.items():
            t = config["conv_thresholds"]
            assert t == sorted(t), f"{key} thresholds not sorted: {t}"

    def test_four_thresholds(self):
        """Each config has exactly 4 thresholds (for tiers 2/3/4/5)."""
        for key, config in SHADOW_CONFIGS.items():
            assert len(config["conv_thresholds"]) == 4, f"{key} has {len(config['conv_thresholds'])} thresholds"


class TestShadowLog:
    """Tests for shadow_log() safety."""

    def test_never_raises_on_bad_inputs(self):
        """shadow_log with None/bad inputs returns None without raising."""
        result = shadow_log(None, None, None, None, None, None, None, None)
        assert result is None

    def test_never_raises_on_missing_db(self):
        """shadow_log with valid signal but no DB returns the shadow dict."""
        candles = _make_candles(12)
        # Pass a mock-ish object that will fail on .execute()
        class FakeDB:
            def execute(self, *a, **kw):
                raise Exception("no db")
        result = shadow_log(FakeDB(), "mkt-1", candles, 5, "btc_5m", None, 3, 0.62)
        # Should still return the shadow dict (embedding fails silently)
        assert result is not None
        assert "conviction_tier" in result
        assert "strength" in result

    def test_returns_correct_structure(self):
        """shadow_log returns dict with expected keys on success."""
        candles = _make_candles(12)
        class FakeDB:
            def execute(self, *a, **kw):
                return type("Row", (), {"fetchone": lambda s: None})()
        result = shadow_log(FakeDB(), "mkt-1", candles, 5, "btc_5m", None, 3, 0.62)
        assert result is not None
        assert result["production_conviction"] == 3
        assert result["production_estimate"] == 0.62
        assert "conviction_tier" in result
