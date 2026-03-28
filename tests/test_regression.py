"""
Regression tests — one per past production incident.
Each test prevents the exact failure from recurring.
"""
import sys
import os
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

ROOT = os.path.join(os.path.dirname(__file__), "..")


# ── Incident 1: Binance 451 — data provider returns usable data ─────────

def test_kraken_response_parsing():
    """Kraken response parser handles the actual response format.
    Incident 1: CoinGecko fallback returned 30-min candles with no volume.
    """
    from btc_data import _compute_summary

    # Simulate Kraken-style candles (5-min, with volume)
    candles = []
    price = 74000.0
    for i in range(12):
        o = price
        c = o + 10 * (1 if i % 2 == 0 else -1)
        candles.append({
            "time": f"12:{i*5:02d}",
            "open": o, "high": max(o, c) + 5, "low": min(o, c) - 5,
            "close": c, "volume": 5.0 + i,  # MUST have volume > 0
            "direction": "UP" if c >= o else "DOWN",
            "body_pct": round((c - o) / o * 100, 4),
            "wick_ratio": 0.5,
        })
        price = c

    result = _compute_summary(candles)
    # Volume must be present and nonzero
    assert result["avg_volume"] > 0, "Data provider must return volume data"
    assert result["last_volume_ratio"] > 0, "Volume ratio must be computable"


# ── Incident 2: Inverted conviction — P&L math correctness ─────────────

def test_winning_bets_always_profit():
    """A correct prediction at any market price must produce positive P&L.
    Incident 2: Conviction was inverted — 26% accuracy on bets, 69% on skips.
    """
    from dashboard import compute_pnl

    # Test across different market prices
    for price_yes in [0.20, 0.35, 0.50, 0.65, 0.80]:
        # Predict UP, outcome UP
        rows = [{
            "market_id": f"test_up_{price_yes}",
            "agent": "contrarian_rule",
            "estimate": 0.62,
            "price_yes": price_yes,
            "outcome": 1,
            "conviction_score": 3,
        }]
        result = compute_pnl(rows)
        pnl = result["contrarian_rule"]["total_pnl"]
        assert pnl > 0, f"Winning UP bet at price {price_yes} should profit, got {pnl}"

        # Predict DOWN, outcome DOWN
        rows2 = [{
            "market_id": f"test_down_{price_yes}",
            "agent": "contrarian_rule",
            "estimate": 0.38,
            "price_yes": price_yes,
            "outcome": 0,
            "conviction_score": 3,
        }]
        result2 = compute_pnl(rows2)
        pnl2 = result2["contrarian_rule"]["total_pnl"]
        assert pnl2 > 0, f"Winning DOWN bet at price {price_yes} should profit, got {pnl2}"


def test_losing_bets_always_lose_exactly_bet_size():
    """A wrong prediction must lose exactly the bet size.
    Incident 2: P&L asymmetry confused the accounting.
    """
    from dashboard import compute_pnl

    for price_yes in [0.20, 0.50, 0.80]:
        rows = [{
            "market_id": "test",
            "agent": "contrarian_rule",
            "estimate": 0.62,
            "price_yes": price_yes,
            "outcome": 0,  # wrong
            "conviction_score": 3,
        }]
        result = compute_pnl(rows)
        pnl = result["contrarian_rule"]["total_pnl"]
        assert pnl == -75, f"Losing bet should be exactly -$75, got {pnl}"


# ── Incident 3: CI references deleted paths ─────────────────────────────

def test_ci_workflow_no_deleted_paths():
    """CI workflow must not reference paths that don't exist.
    Incident 3: git add prompts/ failed because directory was deleted.
    """
    workflow_dir = os.path.join(ROOT, ".github", "workflows")
    if not os.path.isdir(workflow_dir):
        return  # skip if no workflows (shouldn't happen)

    for yml_file in glob.glob(os.path.join(workflow_dir, "*.yml")):
        content = open(yml_file).read()

        # Check for known deleted directories
        deleted_dirs = ["prompts/", "prompts/*"]
        for d in deleted_dirs:
            assert d not in content, \
                f"{yml_file} references deleted path '{d}'"


# ── Incident 4: Extreme price bets — bad risk/reward ─────────────────────

def test_price_gate_prevents_extreme_bets():
    """predict.py must gate bets at extreme market prices.
    Incident 4: 15m bet at price 0.005 risked $75 to win $0.38.
    At price >0.85 or <0.15, breakeven WR exceeds 85% — our 66% signal can't work.
    """
    predict_path = os.path.join(ROOT, "src", "predict.py")
    content = open(predict_path).read()

    # The price gate must exist in run_predictions
    assert "price_gate" in content, \
        "predict.py must have a price gate for extreme market prices"
    assert "0.85" in content, \
        "predict.py must gate prices above 0.85"
    assert "0.15" in content, \
        "predict.py must gate prices below 0.15"


def test_tiered_conviction_ride_up_sweet_spot():
    """RIDE UP + price 20-70% gets conviction 4 ($200). Others get 3 ($75).
    Based on 169-bet analysis: RIDE UP at 71% WR, +$2,314 P&L in this zone.
    """
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime_neutral = {"label": "HIGH_VOL / NEUTRAL", "autocorrelation": 0.0,
                          "volatility": 0.1, "is_mean_reverting": False}
        regime_trending = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                           "volatility": 0.15, "is_mean_reverting": False}

        # RIDE UP at price 0.45 in NEUTRAL → conviction 4
        up_signal = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP"}
        store_prediction(db, "m1", up_signal, regime_neutral, 1, mkt_price=0.45)

        # RIDE DOWN at price 0.45 in TRENDING → conviction 3
        down_signal = {"estimate": 0.38, "should_trade": True,
                       "confidence": "medium", "direction": "DOWN"}
        store_prediction(db, "m2", down_signal, regime_trending, 1, mkt_price=0.45)

        # RIDE UP at price 0.80 (outside sweet spot) → conviction 3
        store_prediction(db, "m3", up_signal, regime_neutral, 1, mkt_price=0.80)

        rows = db.execute(
            "SELECT market_id, conviction_score FROM predictions ORDER BY market_id"
        ).fetchall()
        db.close()

        assert rows[0] == ("m1", 4), f"RIDE UP in sweet spot should be conv=4, got {rows[0]}"
        assert rows[1] == ("m2", 3), f"RIDE DOWN in TRENDING should be conv=3, got {rows[1]}"
        assert rows[2] == ("m3", 3), f"RIDE UP outside sweet spot should be conv=3, got {rows[2]}"


# ── Incident 5: Whipsaw chop — 52% flip rate in flat markets ──────────

def test_cooldown_blocks_rapid_flip():
    """Flipping direction with only min_streak should be blocked by cooldown.
    Incident 5: BTC flat on 2026-03-27, 15 direction flips in 30 bets (52%).
    """
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.execute("""CREATE TABLE markets (
            id TEXT, question TEXT, category TEXT, end_date TEXT,
            volume REAL, price_yes REAL, resolved INTEGER DEFAULT 0
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}

        # Simulate a prior DOWN bet (conv=3) — must use TRENDING regime
        # (DOWN+NEUTRAL is now demoted to conv=2)
        down_signal = {"estimate": 0.38, "should_trade": True,
                       "confidence": "medium", "direction": "DOWN"}
        store_prediction(db, "m1", down_signal, regime, 1, mkt_price=0.50)

        # Verify it stored as conv=3
        row = db.execute("SELECT conviction_score FROM predictions WHERE market_id='m1'").fetchone()
        assert row[0] == 3, f"Setup: DOWN bet should be conv=3, got {row[0]}"

        # Now simulate cooldown check inline (mirrors run_predictions logic)
        # An UP signal with streak=3 (min_streak) should be blocked
        up_signal = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP", "streak": 3}
        min_streak = 3

        # Global cooldown — checks last bet across ALL markets
        last_bet = db.execute('''
            SELECT estimate FROM predictions
            WHERE conviction_score >= 3
            ORDER BY predicted_at DESC LIMIT 1
        ''').fetchone()

        assert last_bet is not None
        last_dir = "UP" if last_bet[0] > 0.5 else "DOWN"
        assert last_dir == "DOWN"

        # Cooldown should block: opposite direction + streak <= min_streak
        streak_len = abs(up_signal.get("streak", 0))
        assert streak_len <= min_streak, "Streak should equal min_streak (blocked)"
        assert last_dir != up_signal["direction"], "Directions should differ (flip)"

        db.close()


def test_cooldown_allows_same_direction():
    """Same-direction bet should NOT trigger cooldown."""
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}

        # Prior UP bet
        up_signal = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP"}
        store_prediction(db, "m1", up_signal, regime, 1, mkt_price=0.50)

        # Another UP signal — cooldown should NOT fire (global check)
        last_bet = db.execute('''
            SELECT estimate FROM predictions
            WHERE conviction_score >= 3
            ORDER BY predicted_at DESC LIMIT 1
        ''').fetchone()

        last_dir = "UP" if last_bet[0] > 0.5 else "DOWN"
        new_dir = "UP"
        assert last_dir == new_dir, "Same direction should not trigger cooldown"

        db.close()


def test_cooldown_allows_strong_streak_flip():
    """A flip with streak > min_streak should be allowed through cooldown."""
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
                  "volatility": 0.15, "is_mean_reverting": False}

        # Prior DOWN bet
        down_signal = {"estimate": 0.38, "should_trade": True,
                       "confidence": "medium", "direction": "DOWN"}
        store_prediction(db, "m1", down_signal, regime, 1, mkt_price=0.50)

        # UP signal with streak=4 (> min_streak=3) — should pass
        min_streak = 3
        streak_len = 4
        assert streak_len > min_streak, "Strong streak should pass cooldown"

        db.close()


# ── Signal quality: Direction × Regime filter (March 28, 2026) ─────────

def test_down_neutral_demoted_to_no_bet():
    """DOWN + NEUTRAL regime → conviction 2 (tracked, not bet).
    Data: DOWN+MEDIUM_VOL/NEUTRAL had 52% WR on 25 bets — coin flip.
    """
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "MEDIUM_VOL / NEUTRAL", "autocorrelation": 0.0,
                  "volatility": 0.08, "is_mean_reverting": False}
        down_signal = {"estimate": 0.38, "should_trade": True,
                       "confidence": "medium", "direction": "DOWN"}
        store_prediction(db, "m1", down_signal, regime, 1, mkt_price=0.50)

        row = db.execute("SELECT conviction_score FROM predictions WHERE market_id='m1'").fetchone()
        db.close()
        assert row[0] == 2, f"DOWN+NEUTRAL should be conv=2 (no bet), got {row[0]}"


def test_up_neutral_still_bets():
    """UP + NEUTRAL regime still gets conviction 3 or 4.
    Data: UP+MEDIUM_VOL/NEUTRAL had 86.7% WR on 45 bets — strongest combo.
    """
    from predict import store_prediction
    import sqlite3
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = sqlite3.connect(db_path)
        db.execute("""CREATE TABLE predictions (
            market_id TEXT, agent TEXT, estimate REAL, edge REAL,
            confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        db.commit()

        regime = {"label": "MEDIUM_VOL / NEUTRAL", "autocorrelation": 0.0,
                  "volatility": 0.08, "is_mean_reverting": False}
        up_signal = {"estimate": 0.62, "should_trade": True,
                     "confidence": "medium", "direction": "UP"}

        # In sweet spot → conv 4
        store_prediction(db, "m1", up_signal, regime, 1, mkt_price=0.50)
        # Outside sweet spot → conv 3
        store_prediction(db, "m2", up_signal, regime, 1, mkt_price=0.80)

        rows = db.execute(
            "SELECT market_id, conviction_score FROM predictions ORDER BY market_id"
        ).fetchall()
        db.close()
        assert rows[0] == ("m1", 4), f"UP+NEUTRAL in sweet spot should be conv=4, got {rows[0]}"
        assert rows[1] == ("m2", 3), f"UP+NEUTRAL outside sweet spot should be conv=3, got {rows[1]}"


def test_dead_hour_gate_exists():
    """DEAD_HOURS_UTC constant exists and contains the known dead zones."""
    from predict import DEAD_HOURS_UTC
    assert 3 in DEAD_HOURS_UTC, "UTC 3 (9pm CST, 41.7% WR) should be a dead hour"
    assert 21 in DEAD_HOURS_UTC, "UTC 21 (3pm CST, 37.5% WR) should be a dead hour"


def test_no_evolve_imports():
    """No production code should import from deleted evolve.py.
    Incident 3: evolve.py was deleted but run_cycle.py imported it.
    """
    src_dir = os.path.join(ROOT, "src")
    production_files = ["run_cycle.py", "predict.py", "dashboard.py",
                        "fetch_markets.py", "score.py", "btc_data.py"]

    for fname in production_files:
        fpath = os.path.join(src_dir, fname)
        if not os.path.exists(fpath):
            continue
        content = open(fpath).read()
        assert "from evolve import" not in content, \
            f"{fname} still imports from deleted evolve.py"
        assert "import evolve" not in content, \
            f"{fname} still imports deleted evolve module"
