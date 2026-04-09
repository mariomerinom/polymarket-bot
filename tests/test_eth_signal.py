"""Tests for the ETH momentum signal — PARALLEL PIPELINE.

History: contrarian signal lost at 33.3% WR on 54 live predictions.
Momentum counterfactual: 66.7% on same bets. Flipped 2026-04-01.
Same V3→V4 pattern as BTC. Do NOT revert to contrarian.
"""

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


class TestMomentumSignalEth:
    """Verify the ETH momentum signal rides streak direction."""

    def test_ride_up_streak(self):
        """Streak of 5 UP candles → predict UP (ride it)."""
        from predict_eth import momentum_signal_eth
        candles = _make_candles(["DOWN", "DOWN", "UP", "UP", "UP", "UP", "UP"])
        sig = momentum_signal_eth(candles, min_streak=3)
        assert sig["should_trade"] is True
        assert sig["direction"] == "UP", "Should RIDE UP streak → predict UP"
        assert sig["estimate"] > 0.50 and sig["estimate"] <= 0.60

    def test_ride_down_streak(self):
        """Streak of 4 DOWN candles → predict DOWN (ride it)."""
        from predict_eth import momentum_signal_eth
        candles = _make_candles(["UP", "UP", "DOWN", "DOWN", "DOWN", "DOWN"])
        sig = momentum_signal_eth(candles, min_streak=3)
        assert sig["should_trade"] is True
        assert sig["direction"] == "DOWN", "Should RIDE DOWN streak → predict DOWN"
        assert sig["estimate"] < 0.50 and sig["estimate"] >= 0.40

    def test_no_signal_short_streak(self):
        """Streak of 2 (below min_streak=3) → no signal."""
        from predict_eth import momentum_signal_eth
        candles = _make_candles(["DOWN", "DOWN", "DOWN", "UP", "UP"])
        sig = momentum_signal_eth(candles, min_streak=3)
        assert not sig["should_trade"]
        assert "streak_too_short" in sig["reason"]

    def test_signal_matches_btc(self):
        """ETH momentum and BTC momentum should predict same direction on same data."""
        from predict_eth import momentum_signal_eth
        from predict import momentum_signal

        # Same candles fed to both signals
        candles = _make_candles(["DOWN", "DOWN", "UP", "UP", "UP", "UP", "UP"])

        btc_sig = momentum_signal(candles, min_streak=3)
        eth_sig = momentum_signal_eth(candles, min_streak=3)

        if btc_sig["should_trade"] and eth_sig["should_trade"]:
            assert btc_sig["direction"] == eth_sig["direction"], \
                "BTC momentum and ETH momentum must predict same direction"

    def test_agent_name_is_momentum_eth(self):
        """Predictions should be stored with agent='momentum_eth'."""
        import sqlite3
        from predict_eth import store_prediction_eth

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")

        signal = {"estimate": 0.62, "should_trade": True, "direction": "UP",
                  "confidence": "medium", "streak": 3,
                  "reason": "ride_streak_UP"}
        regime = {"label": "MEDIUM_VOL / NEUTRAL", "autocorrelation": 0.05,
                  "volatility": 0.08, "is_mean_reverting": False}

        store_prediction_eth(db, "test_market", signal, regime, cycle=1)

        row = db.execute("SELECT agent, conviction_score FROM predictions").fetchone()
        assert row[0] == "momentum_eth", f"Expected agent='momentum_eth', got '{row[0]}'"
        assert row[1] == 3, f"Medium confidence conviction should be 3, got {row[1]}"
        db.close()

    def test_high_confidence_stays_paper(self):
        """High confidence (streak >= 5) stays conv=2 — 20% WR on 5 bets."""
        import sqlite3
        from predict_eth import store_prediction_eth

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")

        signal = {"estimate": 0.62, "should_trade": True, "direction": "UP",
                  "confidence": "high", "streak": 5,
                  "reason": "ride_streak_UP"}
        regime = {"label": "LOW_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.03, "is_mean_reverting": False}

        store_prediction_eth(db, "test_market_2", signal, regime, cycle=1,
                             mkt_price=0.45)

        row = db.execute("SELECT conviction_score FROM predictions").fetchone()
        assert row[0] == 2, f"High confidence should stay conv=2 (paper), got {row[0]}"
        db.close()

    def test_medium_confidence_fires_live(self):
        """Medium confidence (streak 3-4) → conv=3 ($25 bets)."""
        import sqlite3
        from predict_eth import store_prediction_eth

        db = sqlite3.connect(":memory:")
        db.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT,
            estimate REAL, edge REAL, confidence TEXT, reasoning TEXT,
            predicted_at TEXT, cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")

        signal = {"estimate": 0.62, "should_trade": True, "direction": "UP",
                  "confidence": "medium", "streak": 3,
                  "reason": "ride_streak_UP"}
        regime = {"label": "MEDIUM_VOL / NEUTRAL", "autocorrelation": 0.05,
                  "volatility": 0.12, "is_mean_reverting": False}

        store_prediction_eth(db, "test_market_3", signal, regime, cycle=1,
                             mkt_price=0.50)

        row = db.execute("SELECT conviction_score FROM predictions").fetchone()
        assert row[0] == 3, f"Medium confidence should be conv=3, got {row[0]}"
        db.close()


class TestEthRegimeThresholds:
    """Decision #16: ETH uses recalibrated volatility thresholds."""

    def test_eth_regime_medium_vol(self):
        """Volatility between 0.10 and 0.20 should be MEDIUM_VOL with ETH thresholds."""
        from predict_eth import compute_regime_eth
        # Craft candles with ~0.15% stdev returns (between ETH LOW=0.10 and HIGH=0.20)
        candles = _make_candles(["UP", "DOWN", "UP", "DOWN", "UP", "DOWN", "UP"],
                                base_price=2000.0, range_pct=0.15)
        regime = compute_regime_eth(candles)
        assert "MEDIUM_VOL" in regime["label"] or "LOW_VOL" in regime["label"], \
            f"Expected LOW/MEDIUM_VOL for small ETH moves, got {regime['label']} (vol={regime['volatility']})"

    def test_eth_regime_not_always_high_vol(self):
        """With ETH thresholds, uniform small moves should not be HIGH_VOL."""
        from predict_eth import compute_regime_eth
        # Very small uniform moves → low volatility
        candles = []
        price = 2000.0
        for i in range(10):
            move = 0.5  # tiny $0.50 moves on $2000 → 0.025% returns
            d = "UP" if i % 2 == 0 else "DOWN"
            o = price
            c = price + move if d == "UP" else price - move
            candles.append({
                "time": f"{i:02d}:00", "open": o, "close": c,
                "high": max(o, c) + 0.1, "low": min(o, c) - 0.1,
                "volume": 100, "direction": d,
                "body_pct": round((c - o) / o * 100, 4), "wick_ratio": 0.1,
            })
            price = c
        regime = compute_regime_eth(candles)
        assert "HIGH_VOL" not in regime["label"], \
            f"Tiny moves should not be HIGH_VOL with ETH thresholds, got {regime['label']}"

    def test_eth_high_vol_threshold_higher_than_btc(self):
        """ETH HIGH_VOL threshold (0.20) is higher than BTC (0.12)."""
        from predict_eth import ETH_VOL_LOW, ETH_VOL_HIGH
        assert ETH_VOL_LOW == 0.10
        assert ETH_VOL_HIGH == 0.20
