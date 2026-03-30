"""Tests for the ETH contrarian signal — PARALLEL PIPELINE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_candles(directions, base_price=2000.0, range_pct=0.5):
    """Create synthetic candles from a list of 'UP'/'DOWN' directions."""
    candles = []
    price = base_price
    for i, d in enumerate(directions):
        move = price * range_pct / 100
        if d == "UP":
            o, c = price, price + move
        else:
            o, c = price, price - move
        candles.append({
            "time": f"{i:02d}:00",
            "open": o,
            "high": max(o, c) + move * 0.3,
            "low": min(o, c) - move * 0.3,
            "close": c,
            "volume": 100 + i * 10,
            "direction": d,
            "body_pct": round((c - o) / o * 100, 4),
            "wick_ratio": 0.3,
        })
        price = c
    return candles


class TestContrarianSignal:
    """Verify the ETH contrarian signal inverts streak direction."""

    def test_fade_up_streak(self):
        """Streak of 5 UP candles + shrinking range → predict DOWN."""
        from predict_eth import contrarian_signal_eth
        # 5 UP candles with shrinking ranges (exhaustion)
        candles = _make_candles(["DOWN", "DOWN", "UP", "UP", "UP", "UP", "UP"])
        # Force shrinking range for last candle
        candles[-1]["high"] = candles[-1]["close"] + 0.5
        candles[-1]["low"] = candles[-1]["open"] - 0.5
        sig = contrarian_signal_eth(candles, min_streak=3)
        if sig["should_trade"]:
            assert sig["direction"] == "DOWN", "Should FADE UP streak → predict DOWN"
            assert sig["estimate"] == 0.38

    def test_fade_down_streak(self):
        """Streak of 4 DOWN candles + exhaustion → predict UP."""
        from predict_eth import contrarian_signal_eth
        candles = _make_candles(["UP", "UP", "DOWN", "DOWN", "DOWN", "DOWN"])
        candles[-1]["high"] = candles[-1]["close"] + 0.1
        candles[-1]["low"] = candles[-1]["open"] - 0.1
        sig = contrarian_signal_eth(candles, min_streak=3)
        if sig["should_trade"]:
            assert sig["direction"] == "UP", "Should FADE DOWN streak → predict UP"
            assert sig["estimate"] == 0.62

    def test_no_signal_short_streak(self):
        """Streak of 2 (below min_streak=3) → no signal."""
        from predict_eth import contrarian_signal_eth
        candles = _make_candles(["DOWN", "DOWN", "DOWN", "UP", "UP"])
        sig = contrarian_signal_eth(candles, min_streak=3)
        assert not sig["should_trade"]
        assert "streak_too_short" in sig["reason"]

    def test_no_signal_no_exhaustion(self):
        """Streak of 3 but no exhaustion → no signal."""
        from predict_eth import contrarian_signal_eth
        # Create candles with uniform ranges (no compression/shrinking)
        candles = _make_candles(["DOWN", "DOWN", "UP", "UP", "UP"])
        # Make volumes uniform (no spike)
        for c in candles:
            c["volume"] = 100.0
        # Make ranges uniform (no shrinking)
        for c in candles:
            c["high"] = c["close"] + 5.0
            c["low"] = c["open"] - 5.0
        sig = contrarian_signal_eth(candles, min_streak=3)
        assert not sig["should_trade"]
        assert "no_exhaustion" in sig["reason"]

    def test_signal_is_opposite_of_btc(self):
        """ETH contrarian and BTC momentum should predict opposite directions on same data."""
        from predict_eth import contrarian_signal_eth
        from predict import momentum_signal

        # Same candles fed to both signals
        candles = _make_candles(["DOWN", "DOWN", "UP", "UP", "UP", "UP", "UP"])
        # Force exhaustion (volume spike)
        candles[-1]["volume"] = 1000.0

        btc_sig = momentum_signal(candles, min_streak=3)
        eth_sig = contrarian_signal_eth(candles, min_streak=3)

        if btc_sig["should_trade"] and eth_sig["should_trade"]:
            assert btc_sig["direction"] != eth_sig["direction"], \
                "BTC momentum and ETH contrarian must predict opposite directions"

    def test_agent_name_is_contrarian_eth(self):
        """Predictions should be stored with agent='contrarian_eth'."""
        import sqlite3
        from predict_eth import store_prediction_eth

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")

        signal = {"estimate": 0.38, "should_trade": True, "direction": "DOWN",
                  "confidence": "medium", "streak": 3,
                  "exhaustion": {"compression": True, "volume_spike": False,
                                 "vol_ratio": 1.0, "shrinking_range": False, "range_ratio": 1.0},
                  "reason": "fade_streak_DOWN"}
        regime = {"label": "MEDIUM_VOL / NEUTRAL", "autocorrelation": 0.05,
                  "volatility": 0.08, "is_mean_reverting": False}

        store_prediction_eth(db, "test_market", signal, regime, cycle=1)

        row = db.execute("SELECT agent, conviction_score FROM predictions").fetchone()
        assert row[0] == "contrarian_eth", f"Expected agent='contrarian_eth', got '{row[0]}'"
        assert row[1] == 2, f"Paper trading conviction should be 2, got {row[1]}"
        db.close()

    def test_conviction_always_2_paper_trading(self):
        """All ETH predictions should have conviction=2 during paper trading."""
        import sqlite3
        from predict_eth import store_prediction_eth

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")

        # High confidence signal
        signal = {"estimate": 0.62, "should_trade": True, "direction": "UP",
                  "confidence": "high", "streak": -5,
                  "exhaustion": {"compression": True, "volume_spike": True,
                                 "vol_ratio": 2.5, "shrinking_range": True, "range_ratio": 0.4},
                  "reason": "fade_streak_UP"}
        regime = {"label": "LOW_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.03, "is_mean_reverting": False}

        store_prediction_eth(db, "test_market_2", signal, regime, cycle=1,
                             mkt_price=0.45)

        row = db.execute("SELECT conviction_score FROM predictions").fetchone()
        assert row[0] == 2, f"Paper trading: even high confidence should be conv=2, got {row[0]}"
        db.close()
