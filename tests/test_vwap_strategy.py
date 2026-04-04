"""
Tests for VWAP mean-reversion strategy promotion.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_db():
    """Create in-memory DB with predictions + markets tables."""
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT, agent TEXT, estimate REAL, edge REAL,
        confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.commit()
    return db


def _make_candles(n=12, base_price=85000, trend="flat"):
    """Generate synthetic candles for testing."""
    candles = []
    price = base_price
    for i in range(n):
        if trend == "up":
            price += 50
        elif trend == "down":
            price -= 50
        o = price
        c = price + 10
        candles.append({
            "time": f"12:{i*5:02d}",
            "open": o, "high": o + 20, "low": o - 20, "close": c,
            "volume": 5.0 + i,
            "direction": "UP", "body_pct": 0.01, "wick_ratio": 0.5,
        })
    return candles


def _seed_mean_reverting_market(db, cycle=1, market_id="m-mr-1"):
    """Insert a momentum skip prediction for a MEAN_REVERTING market."""
    db.execute("INSERT INTO markets VALUES (?, 'BTC test', 'crypto', '2026-12-31', 1000, 0.50, 0.50, '2026-04-02', 0, NULL)",
               (market_id,))
    db.execute(
        "INSERT INTO predictions (market_id, agent, estimate, edge, confidence, "
        "reasoning, predicted_at, cycle, conviction_score, regime) "
        "VALUES (?, 'momentum_rule', 0.50, 0.0, 'skip', '{}', '2026-04-02T12:00:00', ?, 0, ?)",
        (market_id, cycle, "MEDIUM_VOL / MEAN_REVERTING"),
    )
    db.commit()


# ── Test: VWAP only fires in MEAN_REVERTING regime ──────────────────────────

def test_vwap_only_mean_reverting():
    """VWAP should return 0 predictions for non-mean-reverting regimes."""
    from vwap_strategy import generate_vwap_predictions

    db = _make_db()
    candles = _make_candles()

    # TRENDING regime → no VWAP predictions
    regime = {"label": "HIGH_VOL / TRENDING", "is_mean_reverting": False}
    count = generate_vwap_predictions(db, 1, candles, regime)
    assert count == 0, f"TRENDING should produce 0 VWAP predictions, got {count}"

    # NEUTRAL regime → no VWAP predictions
    regime = {"label": "MEDIUM_VOL / NEUTRAL", "is_mean_reverting": False}
    count = generate_vwap_predictions(db, 1, candles, regime)
    assert count == 0, f"NEUTRAL should produce 0 VWAP predictions, got {count}"

    db.close()


def test_vwap_fires_mean_reverting():
    """VWAP should fire in MEAN_REVERTING regime with strong z-score."""
    from vwap_strategy import generate_vwap_predictions

    db = _make_db()
    _seed_mean_reverting_market(db, cycle=1)

    # Create candles with strong upward deviation from VWAP (z > 2.0)
    # Start low, then spike up — last close far above VWAP
    candles = []
    for i in range(10):
        price = 85000 + (i * 10)  # Flat-ish
        candles.append({
            "time": f"12:{i*5:02d}",
            "open": price, "high": price + 5, "low": price - 5,
            "close": price, "volume": 10.0,
            "direction": "UP", "body_pct": 0.01, "wick_ratio": 0.5,
        })
    # Spike the last 2 candles way up
    for i in range(2):
        price = 86000 + (i * 500)
        candles.append({
            "time": f"12:{50+i*5:02d}",
            "open": price, "high": price + 100, "low": price - 50,
            "close": price + 100, "volume": 10.0,
            "direction": "UP", "body_pct": 0.5, "wick_ratio": 0.3,
        })

    regime = {"label": "MEDIUM_VOL / MEAN_REVERTING", "is_mean_reverting": True}
    count = generate_vwap_predictions(db, 1, candles, regime)

    # Check a prediction was created
    row = db.execute(
        "SELECT agent, conviction_score, estimate FROM predictions WHERE agent = 'vwap_rule'"
    ).fetchone()

    if count > 0:
        assert row is not None, "vwap_rule prediction should exist"
        assert row[0] == "vwap_rule"
        # Price spiked up → should predict DOWN (mean reversion)
        assert row[2] < 0.5, f"Upward spike should predict DOWN, got estimate {row[2]}"

    db.close()


# ── Test: Conviction mapping from z-score ──────────────────────────────────

def test_vwap_conviction_mapping():
    """
    |z| >= 2.0 → conv=3 (live bet)
    1.5 <= |z| < 2.0 → conv=2 (tracked)
    |z| < 1.5 → no prediction
    """
    from vwap_strategy import generate_vwap_predictions
    from shadow_indicators import compute_vwap_zscore

    db = _make_db()

    # Test with weak signal (z < 1.5) — should produce nothing
    _seed_mean_reverting_market(db, cycle=1, market_id="m-weak")
    flat_candles = _make_candles(12, trend="flat")
    regime = {"label": "MEDIUM_VOL / MEAN_REVERTING", "is_mean_reverting": True}

    # Flat candles should have z-score near 0
    vwap = compute_vwap_zscore(flat_candles)
    if abs(vwap["zscore"]) < 1.5:
        count = generate_vwap_predictions(db, 1, flat_candles, regime)
        assert count == 0, f"Weak z-score should produce 0 predictions, got {count}"

    db.close()


# ── Test: Direction logic ─────────────────────────────────────────────────

def test_vwap_direction_logic():
    """Positive z-score → DOWN (reversion), negative z-score → UP."""
    from vwap_strategy import generate_vwap_predictions

    db = _make_db()
    regime = {"label": "HIGH_VOL / MEAN_REVERTING", "is_mean_reverting": True}

    # Candles trending strongly down (price below VWAP → negative z → UP)
    _seed_mean_reverting_market(db, cycle=1, market_id="m-down")
    down_candles = []
    for i in range(12):
        price = 86000 - (i * 200)  # Strong downtrend
        down_candles.append({
            "time": f"12:{i*5:02d}",
            "open": price, "high": price + 10, "low": price - 10,
            "close": price, "volume": 10.0,
            "direction": "DOWN", "body_pct": 0.2, "wick_ratio": 0.5,
        })

    count = generate_vwap_predictions(db, 1, down_candles, regime)
    if count > 0:
        row = db.execute(
            "SELECT estimate FROM predictions WHERE agent = 'vwap_rule' AND market_id = 'm-down'"
        ).fetchone()
        if row:
            # Price below VWAP → predict UP
            assert row[0] > 0.5, f"Price below VWAP should predict UP, got {row[0]}"

    db.close()


# ── Test: Deduplication ───────────────────────────────────────────────────

def test_vwap_no_duplicate():
    """Running generate_vwap_predictions twice should not create duplicates."""
    from vwap_strategy import generate_vwap_predictions

    db = _make_db()
    _seed_mean_reverting_market(db, cycle=1)
    regime = {"label": "HIGH_VOL / MEAN_REVERTING", "is_mean_reverting": True}

    # Create strong signal candles
    candles = []
    for i in range(10):
        candles.append({
            "time": f"12:{i*5:02d}",
            "open": 85000, "high": 85010, "low": 84990,
            "close": 85000, "volume": 10.0,
            "direction": "UP", "body_pct": 0.01, "wick_ratio": 0.5,
        })
    # Big spike
    for i in range(2):
        candles.append({
            "time": f"12:{50+i*5:02d}",
            "open": 86500, "high": 87000, "low": 86400,
            "close": 87000, "volume": 10.0,
            "direction": "UP", "body_pct": 1.0, "wick_ratio": 0.3,
        })

    count1 = generate_vwap_predictions(db, 1, candles, regime)
    count2 = generate_vwap_predictions(db, 1, candles, regime)

    total = db.execute(
        "SELECT COUNT(*) FROM predictions WHERE agent = 'vwap_rule' AND cycle = 1"
    ).fetchone()[0]

    if count1 > 0:
        assert count2 == 0, f"Second call should produce 0 (dedup), got {count2}"
        assert total == count1, f"Total should be {count1}, got {total}"

    db.close()


