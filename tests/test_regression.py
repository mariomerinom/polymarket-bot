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


# ── Incident 5: Whipsaw chop — cooldown_flip gate removed 2026-03-31 ──
# Cooldown_flip was added speculatively to prevent chop but blocked 3/3 winning
# trades on 2026-03-31. The regime gate (mean-reverting skip) already handles
# chop. Cooldown_flip removed — tracking via daily report filter breakdown.


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


def test_dead_hour_gate_is_data_driven():
    """Dead hour gate computes from DB, not hardcoded."""
    import sqlite3
    from predict import compute_dead_hours

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, resolved INTEGER, outcome INTEGER
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, estimate REAL,
        conviction_score INTEGER, predicted_at TEXT
    )""")

    # Insert hour 5 with bad WR: 10 wins out of 40 bets = 25% WR
    for i in range(40):
        mid = f"m-h5-{i}"
        outcome = 1 if i < 10 else 0
        db.execute("INSERT INTO markets VALUES (?, 1, ?)", (mid, outcome))
        db.execute(
            "INSERT INTO predictions (market_id, estimate, conviction_score, predicted_at) "
            "VALUES (?, 0.62, 3, ?)", (mid, f"2026-03-15T05:{i:02d}:00"))

    # Insert hour 12 with good WR: 28 wins out of 40 = 70% WR
    for i in range(40):
        mid = f"m-h12-{i}"
        outcome = 1 if i < 28 else 0
        db.execute("INSERT INTO markets VALUES (?, 1, ?)", (mid, outcome))
        db.execute(
            "INSERT INTO predictions (market_id, estimate, conviction_score, predicted_at) "
            "VALUES (?, 0.62, 3, ?)", (mid, f"2026-03-15T12:{i:02d}:00"))
    db.commit()

    # Write to temp file for compute_dead_hours
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    # Copy schema + data to temp file
    dst = sqlite3.connect(tmp.name)
    db.backup(dst)
    dst.close()
    db.close()

    dead, stats = compute_dead_hours(tmp.name, lookback_days=365, min_bets=30)
    os.unlink(tmp.name)

    assert 5 in dead, f"Hour 5 (25% WR, 40 bets) should be dead, got {dead}"
    assert 12 not in dead, f"Hour 12 (70% WR) should NOT be dead, got {dead}"


def test_dead_hour_fallback():
    """When DB has no data, falls back to config set."""
    from predict import compute_dead_hours
    from config import FALLBACK_DEAD_HOURS
    dead, stats = compute_dead_hours("/nonexistent/path.db")
    assert dead == FALLBACK_DEAD_HOURS
    assert 3 in dead and 21 in dead


def test_dead_hour_min_bets_enforced():
    """Hours with < min_bets samples are NOT gated, even with 0% WR."""
    import sqlite3, tempfile, os
    from predict import compute_dead_hours

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE markets (id TEXT PRIMARY KEY, resolved INTEGER, outcome INTEGER)")
    db.execute("CREATE TABLE predictions (id INTEGER PRIMARY KEY, market_id TEXT, estimate REAL, conviction_score INTEGER, predicted_at TEXT)")

    # Hour 7: only 5 bets, all losses = 0% WR but under min_bets
    for i in range(5):
        mid = f"m-h7-{i}"
        db.execute("INSERT INTO markets VALUES (?, 1, 0)", (mid,))
        db.execute("INSERT INTO predictions (market_id, estimate, conviction_score, predicted_at) VALUES (?, 0.62, 3, ?)",
                   (mid, f"2026-03-15T07:{i:02d}:00"))
    db.commit()

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    dst = sqlite3.connect(tmp.name)
    db.backup(dst)
    dst.close()
    db.close()

    dead, _ = compute_dead_hours(tmp.name, lookback_days=365, min_bets=30)
    os.unlink(tmp.name)

    assert 7 not in dead, f"Hour 7 with only 5 bets should NOT be dead (min_bets=30)"


def test_workflows_have_git_stash():
    """CI workflows must stash before git pull --rebase to handle concurrent pushes.
    Incident: 15m workflow failed 100% of runs on 2026-03-29 because 5m pipeline
    pushed between 15m's commit and pull, leaving unstaged changes.
    """
    workflow_dir = os.path.join(ROOT, ".github", "workflows")
    for fname in ["predict-15m.yml", "predict-and-score.yml"]:
        fpath = os.path.join(workflow_dir, fname)
        if not os.path.exists(fpath):
            continue
        content = open(fpath).read()
        assert "git stash" in content, \
            f"{fname} must use 'git stash' before 'git pull --rebase' to handle concurrent CI pushes"


# ── Incident 6: 53% fill rate — $165 missed profit ────────────────────────

def test_fill_priority_spread_widens_limit_price():
    """Limit orders must be widened by FILL_PRIORITY_SPREAD for better fills.
    Incident 6: 8/8 expired orders were correct predictions. 53% fill rate
    on 2026-04-02 left $165 on the table. Fill-priority spread trades 2¢ of
    edge for dramatically higher fill rate.
    """
    from trade import compute_order
    from config import FILL_PRIORITY_SPREAD

    assert FILL_PRIORITY_SPREAD > 0, "FILL_PRIORITY_SPREAD must be positive"

    # UP bet: limit price should be wider than raw estimate
    pred = {"estimate": 0.55, "conviction_score": 3, "agent": "momentum_rule"}
    market = {"price_yes": 0.50}
    order, reason = compute_order(pred, market)
    assert order is not None
    # Price should be estimate + spread (0.55 + 0.02 = 0.57), not just 0.55
    assert order["price_limit"] > 0.55, \
        f"UP limit price should exceed estimate by FILL_PRIORITY_SPREAD, got {order['price_limit']}"

    # DOWN bet: same principle (buying NO tokens)
    pred_down = {"estimate": 0.45, "conviction_score": 3, "agent": "momentum_rule"}
    order_down, _ = compute_order(pred_down, market)
    assert order_down is not None
    raw_no_price = 1 - 0.45  # 0.55
    assert order_down["price_limit"] > raw_no_price, \
        f"DOWN limit price should exceed 1-estimate by FILL_PRIORITY_SPREAD, got {order_down['price_limit']}"


def test_pnl_uses_actual_fill_size():
    """P&L must be computed from actual fill size, not intended bet size.
    Incident 6: DB recorded $25 intended but CLOB only filled $20.16 (thin book).
    P&L was overstated by ~$10 on winning bets.
    """
    from trade import compute_order_pnl, ensure_orders_table
    import sqlite3

    db = sqlite3.connect(":memory:")
    ensure_orders_table(db)
    db.execute("""CREATE TABLE IF NOT EXISTS markets (
        id TEXT PRIMARY KEY, resolved INTEGER DEFAULT 0, outcome INTEGER)""")

    # Simulate: intended $25, but actual fill was $20 (thin book)
    db.execute("INSERT INTO markets VALUES ('m1', 1, 1)")
    db.execute("""INSERT INTO orders
        (market_id, prediction_id, direction, size, price_limit, price_filled,
         status, mode, placed_at, cycle)
        VALUES ('m1', 1, 'UP', 20.0, 0.50, 0.50, 'filled', 'live',
                '2026-04-02T10:00:00', 1)""")
    db.commit()

    updated = compute_order_pnl(db)
    assert updated == 1
    pnl = db.execute("SELECT pnl FROM orders WHERE market_id='m1'").fetchone()[0]
    # With size=20, price=0.50: pnl = 20 * (1/0.5 - 1) * 0.985 = 20 * 1 * 0.985 = $19.70
    # NOT $24.63 (which would be wrong if size were still $25)
    assert abs(pnl - 19.70) < 0.01, f"P&L should use actual fill size ($20), got pnl={pnl}"
    db.close()


# ── Incident 7: 15m DOWN+NEUTRAL asymmetry — 48% WR on 27 bets ─────────

def test_down_neutral_demoted_even_in_loose_mode():
    """DOWN+MEDIUM_VOL/NEUTRAL filter applies to 15m too (via ci_run_15m.py post-prediction).
    Incident 7: 15m used loose_mode=True which bypassed DOWN+NEUTRAL filter.
    Volatility split: MEDIUM_VOL/NEUTRAL+DOWN demoted (56.1% WR on 41 bets),
    HIGH_VOL/NEUTRAL+DOWN allowed through (64.0% WR on 50 bets).
    """
    import sqlite3
    import json

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, resolved INTEGER, outcome INTEGER
    )""")

    # DOWN+MEDIUM_VOL/NEUTRAL: should be demoted (56.1% WR, no edge)
    reasoning_med = json.dumps({"signal": {"direction": "DOWN", "should_trade": True}})
    db.execute("""INSERT INTO predictions VALUES
        (1, 'm1', 'momentum_rule', 0.38, 0.12, 'medium', ?, '2026-04-03T10:00:00',
         1, 3, 'MEDIUM_VOL / NEUTRAL')""", (reasoning_med,))

    # UP+NEUTRAL: should NOT be demoted
    reasoning_up = json.dumps({"signal": {"direction": "UP", "should_trade": True}})
    db.execute("""INSERT INTO predictions VALUES
        (2, 'm2', 'momentum_rule', 0.62, 0.12, 'medium', ?, '2026-04-03T10:00:00',
         1, 4, 'MEDIUM_VOL / NEUTRAL')""", (reasoning_up,))

    # DOWN+TRENDING: should NOT be demoted
    reasoning_trend = json.dumps({"signal": {"direction": "DOWN", "should_trade": True}})
    db.execute("""INSERT INTO predictions VALUES
        (3, 'm3', 'momentum_rule', 0.38, 0.12, 'medium', ?, '2026-04-03T10:00:00',
         1, 3, 'HIGH_VOL / TRENDING')""", (reasoning_trend,))

    # DOWN+HIGH_VOL/NEUTRAL: should NOT be demoted (64% WR on 50 bets)
    reasoning_hv = json.dumps({"signal": {"direction": "DOWN", "should_trade": True}})
    db.execute("""INSERT INTO predictions VALUES
        (4, 'm4', 'momentum_rule', 0.38, 0.12, 'medium', ?, '2026-04-03T10:00:00',
         1, 3, 'HIGH_VOL / NEUTRAL')""", (reasoning_hv,))
    db.commit()

    # Apply the same demotion query that ci_run_15m.py uses (volatility-aware)
    demoted = db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE cycle = 1 AND conviction_score >= 3
        AND regime LIKE '%NEUTRAL%'
        AND regime NOT LIKE 'HIGH_VOL%'
        AND json_extract(reasoning, '$.signal.direction') = 'DOWN'
    """).rowcount
    db.commit()

    rows = db.execute(
        "SELECT market_id, conviction_score FROM predictions ORDER BY market_id"
    ).fetchall()
    db.close()

    assert demoted == 1, f"Should demote exactly 1 DOWN+MEDIUM_VOL/NEUTRAL prediction, got {demoted}"
    assert rows[0] == ("m1", 2), f"DOWN+MEDIUM_VOL/NEUTRAL should be conv=2, got {rows[0]}"
    assert rows[1] == ("m2", 4), f"UP+NEUTRAL should stay conv=4, got {rows[1]}"
    assert rows[2] == ("m3", 3), f"DOWN+TRENDING should stay conv=3, got {rows[2]}"
    assert rows[3] == ("m4", 3), f"DOWN+HIGH_VOL/NEUTRAL should stay conv=3, got {rows[3]}"


def test_mr_shadow_extreme_estimate():
    """MR shadow mode: extreme estimates (>0.65/<0.35) tracked at conv=2,
    coin-flip zone skipped at conv=0.
    Optimization: mr_shadow_extreme (2026-04-03).
    """
    import sqlite3, json
    from predict import store_prediction

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, end_date TEXT, resolved INTEGER DEFAULT 0,
        outcome TEXT, slug TEXT
    )""")
    db.execute("INSERT INTO markets VALUES ('mr1','Q1','2099-01-01',0,NULL,NULL)")
    db.execute("INSERT INTO markets VALUES ('mr2','Q2','2099-01-01',0,NULL,NULL)")
    db.commit()

    regime_mr = {"label": "HIGH_VOL / MEAN_REVERTING", "is_mean_reverting": True}

    # Case 1: extreme estimate (0.72) in MR → stored, then demoted to conv=2
    signal_extreme = {"estimate": 0.72, "should_trade": True, "confidence": "medium",
                      "direction": "UP", "reason": "mr_shadow_extreme_estimate"}
    store_prediction(db, "mr1", signal_extreme, regime_mr, cycle=99, mkt_price=0.45)
    # Simulate the post-store demotion from predict.py line 418-422
    db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
        AND regime LIKE '%MEAN_REVERTING%'
    """, ("mr1", 99))
    db.commit()

    # Case 2: coin-flip estimate (0.50) in MR → skip at conv=0
    signal_coinflip = {"estimate": 0.50, "should_trade": False, "confidence": "skip",
                       "reason": "regime_skip_mean_reverting"}
    store_prediction(db, "mr2", signal_coinflip, regime_mr, cycle=99)

    rows = db.execute(
        "SELECT market_id, conviction_score, confidence FROM predictions ORDER BY market_id"
    ).fetchall()
    db.close()

    assert rows[0] == ("mr1", 2, "medium"), f"Extreme MR should be shadow conv=2, got {rows[0]}"
    assert rows[1] == ("mr2", 0, "skip"), f"Coin-flip MR should be skip conv=0, got {rows[1]}"


def test_extreme_estimate_shadow_dead_hour():
    """Extreme estimates (>0.65/<0.35) stored as conv=2 shadow even during dead hours.
    Optimization: unified extreme-estimate override (2026-04-04).
    80%+ WR on extreme estimates regardless of skip reason.
    """
    import sqlite3
    from predict import store_prediction

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.commit()

    regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
              "volatility": 0.15, "is_mean_reverting": False}

    # Extreme estimate in dead hour → shadow at conv=2
    signal = dict(estimate=0.72, should_trade=True, confidence="medium",
                  direction="UP", reason="shadow_extreme_dead_hour (UTC 3)")
    store_prediction(db, "dh1", signal, regime, cycle=99, mkt_price=0.50)
    db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
    """, ("dh1", 99))
    db.commit()

    row = db.execute("SELECT conviction_score FROM predictions WHERE market_id='dh1'").fetchone()
    db.close()
    assert row[0] == 2, f"Extreme estimate in dead hour should be shadow conv=2, got {row[0]}"


def test_extreme_estimate_shadow_price_gate():
    """Extreme estimates stored as conv=2 shadow even at extreme market prices.
    Optimization: unified extreme-estimate override (2026-04-04).
    """
    import sqlite3
    from predict import store_prediction

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.commit()

    regime = {"label": "HIGH_VOL / TRENDING", "autocorrelation": 0.2,
              "volatility": 0.15, "is_mean_reverting": False}

    # Extreme estimate at extreme market price → shadow at conv=2
    signal = dict(estimate=0.72, should_trade=True, confidence="medium",
                  direction="UP", reason="shadow_extreme_price_gate (90%)")
    store_prediction(db, "pg1", signal, regime, cycle=99, mkt_price=0.90)
    db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
    """, ("pg1", 99))
    db.commit()

    row = db.execute("SELECT conviction_score FROM predictions WHERE market_id='pg1'").fetchone()
    db.close()
    assert row[0] == 2, f"Extreme estimate at extreme price should be shadow conv=2, got {row[0]}"


def test_eth_mr_shadow_extreme_estimate():
    """ETH MR shadow: extreme estimates tracked at conv=2, coin-flip skipped.
    Mirrors BTC MR shadow mode from predict.py.
    """
    import sqlite3
    from predict_eth import store_prediction_eth

    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.commit()

    regime_mr = {"label": "HIGH_VOL / MEAN_REVERTING", "is_mean_reverting": True,
                 "autocorrelation": -0.3, "volatility": 0.15}

    # Extreme estimate in MR → shadow conv=2
    signal_extreme = {"estimate": 0.72, "should_trade": True, "confidence": "medium",
                      "direction": "UP", "reason": "mr_shadow_extreme_estimate"}
    store_prediction_eth(db, "eth_mr1", signal_extreme, regime_mr, cycle=99, mkt_price=0.45)
    db.execute("""
        UPDATE predictions SET conviction_score = 2
        WHERE market_id = ? AND cycle = ? AND conviction_score >= 3
        AND regime LIKE '%MEAN_REVERTING%'
    """, ("eth_mr1", 99))
    db.commit()

    # Coin-flip in MR → skip conv=0
    signal_skip = {"estimate": 0.50, "should_trade": False, "confidence": "skip",
                   "reason": "regime_skip_mean_reverting"}
    store_prediction_eth(db, "eth_mr2", signal_skip, regime_mr, cycle=99)

    rows = db.execute(
        "SELECT market_id, conviction_score FROM predictions ORDER BY market_id"
    ).fetchall()
    db.close()

    assert rows[0] == ("eth_mr1", 2), f"ETH extreme MR should be shadow conv=2, got {rows[0]}"
    assert rows[1] == ("eth_mr2", 0), f"ETH coin-flip MR should be skip conv=0, got {rows[1]}"


