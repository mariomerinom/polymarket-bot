"""
Unit tests for BTC data fetching and parsing.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from btc_data import _compute_summary, format_for_prompt
import pytest


def _make_candles(n=12):
    """Create realistic candle data."""
    candles = []
    price = 74000.0
    for i in range(n):
        o = price
        h = o + 50 + i * 5
        l = o - 30 - i * 3
        c = o + 20 * (1 if i % 2 == 0 else -1)
        vol = 10.0 + i * 2
        direction = "UP" if c >= o else "DOWN"
        body = abs(c - o)
        full_range = h - l
        wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
        body_pct = round((c - o) / o * 100, 4) if o > 0 else 0.0
        candles.append({
            "time": f"{12+i//6}:{(i%6)*10:02d}",
            "open": o, "high": h, "low": l, "close": c,
            "volume": vol, "direction": direction,
            "body_pct": body_pct, "wick_ratio": wick_ratio,
        })
        price = c
    return candles


def test_compute_summary_keys():
    """Summary has all required keys."""
    candles = _make_candles()
    result = _compute_summary(candles)
    required = {
        "candles", "current_price", "1h_change_pct", "trend",
        "volatility", "consecutive_direction", "consecutive_dir_label",
        "up_count", "down_count", "last_candle",
        "range_high", "range_low", "range_position",
        "avg_volume", "last_volume_ratio",
        "last_3_range_shrinking", "last_range_ratio",
        "last_candle_pattern", "last_wick_upper_ratio", "last_wick_lower_ratio",
    }
    assert required.issubset(result.keys()), f"Missing: {required - result.keys()}"


def test_range_position_bounded():
    """Range position should be 0-1."""
    candles = _make_candles()
    result = _compute_summary(candles)
    assert 0 <= result["range_position"] <= 1


def test_volume_ratio_positive():
    """Volume ratio should be positive."""
    candles = _make_candles()
    result = _compute_summary(candles)
    assert result["last_volume_ratio"] > 0
    assert result["avg_volume"] > 0


def test_format_for_prompt_none():
    """format_for_prompt handles None gracefully."""
    result = format_for_prompt(None)
    assert "unavailable" in result.lower() or "market_price" in result.lower()


def test_format_for_prompt_valid():
    """format_for_prompt produces readable output."""
    candles = _make_candles()
    data = _compute_summary(candles)
    result = format_for_prompt(data)
    assert "BTC" in result
    assert "Current BTC price" in result
    assert "|" in result  # has table


def test_up_down_counts_sum():
    """up_count + down_count = total candles."""
    candles = _make_candles(12)
    result = _compute_summary(candles)
    assert result["up_count"] + result["down_count"] == 12


def test_trend_labels_valid():
    """Trend is one of up/down/neutral."""
    candles = _make_candles()
    result = _compute_summary(candles)
    assert result["trend"] in ("up", "down", "neutral")


def test_candle_pattern_valid():
    """Candle pattern is a known value."""
    valid = {"none", "doji", "hammer", "inv_hammer",
             "engulfing_bull", "engulfing_bear", "inside_bar"}
    candles = _make_candles()
    result = _compute_summary(candles)
    assert result["last_candle_pattern"] in valid
