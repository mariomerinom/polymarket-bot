"""
Tests for centralized config.py — validate invariants between coupled constants.

The 0.62/0.38 and 0.08 max_edge bugs both came from hardcoded values
that silently violated assumptions in other files. These tests prevent that.
"""
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import (
    SHADOW_CONFIGS, EDGE_THRESHOLD, VOL_FLOOR,
    PRICE_GATE_UPPER, PRICE_GATE_LOWER, PRICE_SWEET_SPOT_LOW, PRICE_SWEET_SPOT_HIGH,
    BTC_VOL_LOW, BTC_VOL_HIGH, ETH_VOL_LOW, ETH_VOL_HIGH,
    LIVE_START_DATE, LIVE_BTC_CONVICTION_BETS, LIVE_ETH_CONVICTION_BETS,
    LIVE_KALSHI_CONVICTION_BETS, PAPER_BTC_CONVICTION_BETS, PAPER_ETH_CONVICTION_BETS,
    VWAP_ZSCORE_STRONG, VWAP_ZSCORE_MODERATE, VWAP_EDGE_MULTIPLIER, VWAP_MAX_EDGE,
    POLYMARKET_FEE_FACTOR, BOOK_DEPTH_SAFETY_MARGIN, MIN_BET_SIZE,
    DOJI_BODY_FRACTION, HAMMER_WICK_RATIO, ENGULFING_BODY_RATIO,
    AUTOCORR_TRENDING, MAX_CONVICTION, CONFIDENCE_HIGH_STREAK,
)


class TestEdgeThresholdCoupling:
    """CRITICAL: max_edge must produce edge > EDGE_THRESHOLD at min_streak."""

    def test_btc_5m_clears_edge_gate(self):
        cfg = SHADOW_CONFIGS["btc_5m"]
        # At min_streak, length_strength = log(min_streak) / log(baseline_streak)
        length_strength = math.log(cfg["min_streak"]) / math.log(cfg["baseline_streak"])
        # Minimum edge = length_strength * max_edge (magnitude=1.0 best case)
        min_edge = length_strength * cfg["max_edge"]
        assert min_edge > EDGE_THRESHOLD, (
            f"BTC 5m: streak={cfg['min_streak']} produces edge={min_edge:.4f}, "
            f"below EDGE_THRESHOLD={EDGE_THRESHOLD}. Bump max_edge or lower threshold."
        )

    def test_eth_5m_clears_edge_gate(self):
        cfg = SHADOW_CONFIGS["eth_5m"]
        length_strength = math.log(cfg["min_streak"]) / math.log(cfg["baseline_streak"])
        min_edge = length_strength * cfg["max_edge"]
        assert min_edge > EDGE_THRESHOLD, (
            f"ETH 5m: streak={cfg['min_streak']} produces edge={min_edge:.4f}, "
            f"below EDGE_THRESHOLD={EDGE_THRESHOLD}. Bump max_edge or lower threshold."
        )

    def test_btc_15m_clears_edge_gate(self):
        cfg = SHADOW_CONFIGS["btc_15m"]
        length_strength = math.log(cfg["min_streak"]) / math.log(cfg["baseline_streak"])
        min_edge = length_strength * cfg["max_edge"]
        assert min_edge > EDGE_THRESHOLD, (
            f"BTC 15m: streak={cfg['min_streak']} produces edge={min_edge:.4f}, "
            f"below EDGE_THRESHOLD={EDGE_THRESHOLD}"
        )

    def test_kalshi_clears_edge_gate(self):
        cfg = SHADOW_CONFIGS["kalshi"]
        length_strength = math.log(cfg["min_streak"]) / math.log(cfg["baseline_streak"])
        min_edge = length_strength * cfg["max_edge"]
        assert min_edge > EDGE_THRESHOLD, (
            f"Kalshi: streak={cfg['min_streak']} produces edge={min_edge:.4f}, "
            f"below EDGE_THRESHOLD={EDGE_THRESHOLD}"
        )


class TestConfigConsistency:
    """Verify all config dicts have expected structure and sane values."""

    def test_all_shadow_configs_have_required_keys(self):
        required = {"min_streak", "baseline_streak", "magnitude_multiplier",
                     "max_edge", "high_confidence_threshold", "conv_thresholds"}
        for name, cfg in SHADOW_CONFIGS.items():
            missing = required - set(cfg.keys())
            assert not missing, f"SHADOW_CONFIGS[{name}] missing keys: {missing}"

    def test_conv_thresholds_are_sorted(self):
        for name, cfg in SHADOW_CONFIGS.items():
            thresholds = cfg["conv_thresholds"]
            assert thresholds == sorted(thresholds), (
                f"SHADOW_CONFIGS[{name}] conv_thresholds not sorted: {thresholds}"
            )

    def test_bet_sizing_dicts_have_same_keys(self):
        expected_keys = {0, 1, 2, 3, 4, 5}
        for name, d in [
            ("LIVE_BTC", LIVE_BTC_CONVICTION_BETS),
            ("LIVE_ETH", LIVE_ETH_CONVICTION_BETS),
            ("LIVE_KALSHI", LIVE_KALSHI_CONVICTION_BETS),
            ("PAPER_BTC", PAPER_BTC_CONVICTION_BETS),
            ("PAPER_ETH", PAPER_ETH_CONVICTION_BETS),
        ]:
            assert set(d.keys()) == expected_keys, f"{name} has wrong keys: {d.keys()}"

    def test_live_start_date_is_valid(self):
        from datetime import datetime
        dt = datetime.strptime(LIVE_START_DATE, "%Y-%m-%d")
        assert dt.year >= 2026

    def test_vol_thresholds_ordered(self):
        assert BTC_VOL_LOW < BTC_VOL_HIGH, "BTC vol thresholds out of order"
        assert ETH_VOL_LOW < ETH_VOL_HIGH, "ETH vol thresholds out of order"

    def test_price_gates_sane(self):
        assert 0 < PRICE_GATE_LOWER < 0.5
        assert 0.5 < PRICE_GATE_UPPER < 1.0
        assert PRICE_GATE_LOWER < PRICE_SWEET_SPOT_LOW
        assert PRICE_SWEET_SPOT_HIGH < PRICE_GATE_UPPER


class TestVWAPConfig:
    """VWAP thresholds are coupled to conviction mapping."""

    def test_strong_above_moderate(self):
        assert VWAP_ZSCORE_STRONG > VWAP_ZSCORE_MODERATE

    def test_edge_at_strong_clears_gate(self):
        edge = VWAP_ZSCORE_STRONG * VWAP_EDGE_MULTIPLIER
        assert edge > EDGE_THRESHOLD, (
            f"VWAP strong z={VWAP_ZSCORE_STRONG} produces edge={edge:.4f}, "
            f"below EDGE_THRESHOLD={EDGE_THRESHOLD}"
        )

    def test_max_edge_consistent(self):
        # VWAP max_edge should not exceed shadow scorer max_edge
        btc_max = SHADOW_CONFIGS["btc_5m"]["max_edge"]
        assert VWAP_MAX_EDGE <= btc_max


class TestRiskControls:
    """Verify risk control values are within sane bounds."""

    def test_fee_factor_sane(self):
        assert 0.95 < POLYMARKET_FEE_FACTOR < 1.0, f"Fee factor {POLYMARKET_FEE_FACTOR} out of range"

    def test_safety_margin_sane(self):
        assert 0.5 < BOOK_DEPTH_SAFETY_MARGIN <= 1.0

    def test_min_bet_positive(self):
        assert MIN_BET_SIZE > 0

    def test_candle_pattern_constants_sane(self):
        assert 0 < DOJI_BODY_FRACTION < 0.5, "Doji fraction should be small"
        assert HAMMER_WICK_RATIO >= 1.5, "Hammer wick ratio should be substantial"
        assert ENGULFING_BODY_RATIO > 1.0, "Engulfing needs body > previous"

    def test_autocorr_trending_positive(self):
        assert AUTOCORR_TRENDING > 0

    def test_max_conviction_and_high_streak(self):
        assert MAX_CONVICTION >= 3  # Must allow at least conv=3 (live bet threshold)
        assert CONFIDENCE_HIGH_STREAK >= 3
