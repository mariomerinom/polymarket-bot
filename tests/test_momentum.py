"""
Unit tests for the momentum signal logic.
V4: streak UP → predict UP (ride it), streak DOWN → predict DOWN (ride it).

History: V3 "contrarian" faded streaks and lost at 37% WR.
Inverting to momentum validated at 63% WR. Do NOT revert to fade.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from predict import momentum_signal


def _make_candles(directions, volumes=None):
    """Helper: create candle list from UP/DOWN directions."""
    candles = []
    price = 100.0
    for i, d in enumerate(directions):
        o = price
        if d == "UP":
            c = o + 0.5
        else:
            c = o - 0.5
        h = max(o, c) + 0.1
        l = min(o, c) - 0.1
        vol = (volumes[i] if volumes else 10.0)
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": vol})
        price = c
    return candles


def test_no_signal_short_streak():
    """Streak < 3 → no signal."""
    candles = _make_candles(["UP", "UP", "DOWN", "UP", "UP"])
    result = momentum_signal(candles)
    assert result["should_trade"] is False
    assert "streak_too_short" in result["reason"]


def test_no_signal_insufficient_data():
    """< 5 candles → no signal."""
    candles = _make_candles(["UP", "UP", "UP"])
    result = momentum_signal(candles)
    assert result["should_trade"] is False


def test_streak_3_up_with_compression():
    """3 UP candles with shrinking ranges → ride UP (momentum)."""
    candles = []
    price = 100.0
    # 7 mixed candles first
    for _ in range(7):
        candles.append({"open": price, "high": price + 1, "low": price - 1,
                        "close": price + 0.3, "volume": 10})
        price += 0.3
    # 3 UP candles with shrinking ranges (compression)
    for i, rng in enumerate([2.0, 1.5, 0.8]):
        o = price
        c = o + 0.3
        candles.append({"open": o, "high": o + rng/2, "low": o - rng/2,
                        "close": c, "volume": 10})
        price = c

    result = momentum_signal(candles)
    assert result["should_trade"] is True
    assert result["estimate"] == 0.62  # ride UP → predict UP (momentum)
    assert result["direction"] == "UP"


def test_streak_3_down_with_volume_spike():
    """3 DOWN candles with volume spike → ride DOWN (momentum)."""
    # 7 mixed, then 3 DOWN with last one having volume spike
    candles = []
    price = 100.0
    for _ in range(7):
        candles.append({"open": price, "high": price + 0.5, "low": price - 0.5,
                        "close": price - 0.1, "volume": 10})
        price -= 0.1
    for i in range(3):
        o = price
        c = o - 0.5
        vol = 25.0 if i == 2 else 10.0  # spike on last candle
        candles.append({"open": o, "high": o + 0.1, "low": c - 0.1,
                        "close": c, "volume": vol})
        price = c

    result = momentum_signal(candles)
    assert result["should_trade"] is True
    assert result["estimate"] == 0.38  # ride DOWN → predict DOWN (momentum)
    assert result["direction"] == "DOWN"


def test_streak_without_exhaustion_no_trade():
    """Streak ≥ 3 but no exhaustion signal → no trade."""
    candles = []
    price = 100.0
    # 10 candles, last 4 UP, all same range, no volume spike
    for _ in range(6):
        candles.append({"open": price, "high": price + 1, "low": price - 1,
                        "close": price + 0.1, "volume": 10})
        price += 0.1
    for _ in range(4):
        o = price
        c = o + 0.3
        candles.append({"open": o, "high": o + 1, "low": o - 1,
                        "close": c, "volume": 10})
        price = c

    result = momentum_signal(candles)
    assert result["should_trade"] is False
    assert "no_exhaustion" in result["reason"]


def test_high_confidence_streak_5():
    """Streak ≥ 5 → high confidence."""
    candles = []
    price = 100.0
    for _ in range(5):
        candles.append({"open": price, "high": price + 1, "low": price - 1,
                        "close": price - 0.1, "volume": 10})
        price -= 0.1
    # 5 UP candles with compression
    for i, rng in enumerate([3.0, 2.5, 2.0, 1.5, 0.8]):
        o = price
        c = o + 0.3
        candles.append({"open": o, "high": o + rng/2, "low": o - rng/2,
                        "close": c, "volume": 10})
        price = c

    result = momentum_signal(candles)
    assert result["should_trade"] is True
    assert result["confidence"] == "high"


def test_estimate_always_in_range():
    """Estimate must always be between 0 and 1."""
    test_cases = [
        _make_candles(["UP"] * 10),
        _make_candles(["DOWN"] * 10),
        _make_candles(["UP", "DOWN"] * 5),
        _make_candles(["UP"] * 5, volumes=[1, 1, 1, 1, 50]),
    ]
    for candles in test_cases:
        result = momentum_signal(candles)
        assert 0 <= result["estimate"] <= 1, f"estimate {result['estimate']} out of range"
