"""
Tests for daily_report.py — daily morning analysis.
"""
import sys
import os
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from daily_report import (
    is_correct,
    analyze_summary,
    analyze_regime_distribution,
    analyze_direction,
    analyze_price_buckets,
    analyze_conviction_tiers,
    analyze_orders,
    generate_alerts,
    generate_report,
    format_report,
    get_daily_predictions,
    get_daily_resolved,
    rolling_trend,
    compute_decision_stats,
    check_decisions,
    DECISIONS,
    DECISIONS_15M,
)


def _create_test_db(tmpdir, predictions, markets):
    """Create a test database with given predictions and markets."""
    db_path = os.path.join(tmpdir, "test.db")
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT,
        end_date TEXT, volume REAL, price_yes REAL,
        resolved INTEGER, outcome INTEGER
    )""")
    db.execute("""CREATE TABLE predictions (
        market_id TEXT, agent TEXT, estimate REAL, edge REAL,
        confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    for m in markets:
        db.execute(
            "INSERT INTO markets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (m["id"], m.get("question", "Test?"), m.get("category", "crypto"),
             m.get("end_date", "2026-04-01"), m.get("volume", 1000),
             m["price_yes"], m["resolved"], m["outcome"])
        )
    for p in predictions:
        db.execute(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p["market_id"], p.get("agent", "momentum_rule"), p["estimate"],
             abs(p["estimate"] - 0.5), p.get("confidence", "medium"),
             p.get("reasoning", "{}"), p["predicted_at"],
             p.get("cycle", 1), p.get("conviction_score", 3),
             p.get("regime", "HIGH_VOL / NEUTRAL"))
        )
    db.commit()
    db.close()
    return db_path


def _sample_data(date_str="2026-03-26"):
    """Create sample predictions and markets for testing."""
    markets = [
        {"id": "m1", "price_yes": 0.45, "resolved": 1, "outcome": 1},  # UP wins
        {"id": "m2", "price_yes": 0.55, "resolved": 1, "outcome": 1},  # UP wins
        {"id": "m3", "price_yes": 0.40, "resolved": 1, "outcome": 0},  # DOWN wins
        {"id": "m4", "price_yes": 0.60, "resolved": 1, "outcome": 0},  # UP loses
        {"id": "m5", "price_yes": 0.50, "resolved": 0, "outcome": None},  # unresolved
    ]
    predictions = [
        {"market_id": "m1", "estimate": 0.62, "predicted_at": f"{date_str}T10:00:00",
         "conviction_score": 4, "regime": "HIGH_VOL / TRENDING"},
        {"market_id": "m2", "estimate": 0.62, "predicted_at": f"{date_str}T11:00:00",
         "conviction_score": 3, "regime": "HIGH_VOL / NEUTRAL"},
        {"market_id": "m3", "estimate": 0.38, "predicted_at": f"{date_str}T12:00:00",
         "conviction_score": 3, "regime": "MEDIUM_VOL / NEUTRAL"},
        {"market_id": "m4", "estimate": 0.62, "predicted_at": f"{date_str}T13:00:00",
         "conviction_score": 3, "regime": "HIGH_VOL / NEUTRAL"},
        {"market_id": "m5", "estimate": 0.50, "predicted_at": f"{date_str}T14:00:00",
         "conviction_score": 0, "regime": "LOW_VOL / MEAN_REVERTING"},
    ]
    return markets, predictions


def test_is_correct():
    """Basic direction correctness check."""
    assert is_correct(0.62, 1) is True   # predict UP, went UP
    assert is_correct(0.62, 0) is False  # predict UP, went DOWN
    assert is_correct(0.38, 0) is True   # predict DOWN, went DOWN
    assert is_correct(0.38, 1) is False  # predict DOWN, went UP


def test_analyze_summary():
    """Summary stats computed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        markets, predictions = _sample_data()
        db_path = _create_test_db(tmpdir, predictions, markets)

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        preds = get_daily_predictions(db, "2026-03-26")
        resolved = get_daily_resolved(db, "2026-03-26")
        db.close()

        summary = analyze_summary(preds, resolved)
        assert summary["total_predictions"] == 5
        assert summary["bets"] == 4  # m1-m4 have conv >= 3
        assert summary["skips"] == 1  # m5 has conv = 0
        # m1 (est=0.62, out=1) → correct, m2 (est=0.62, out=1) → correct,
        # m3 (est=0.38, out=0) → correct, m4 (est=0.62, out=0) → wrong
        assert summary["resolved_bets"] == 4
        assert summary["wins"] == 3
        assert summary["losses"] == 1


def test_analyze_regime_distribution():
    """Regime counts are correct."""
    predictions = [
        {"regime": "HIGH_VOL / TRENDING", "conviction_score": 4},
        {"regime": "HIGH_VOL / TRENDING", "conviction_score": 3},
        {"regime": "HIGH_VOL / NEUTRAL", "conviction_score": 0},
        {"regime": "LOW_VOL / MEAN_REVERTING", "conviction_score": 0},
    ]
    result = analyze_regime_distribution(predictions)
    assert result["HIGH_VOL / TRENDING"]["total"] == 2
    assert result["HIGH_VOL / TRENDING"]["bets"] == 2
    assert result["HIGH_VOL / NEUTRAL"]["skips"] == 1
    assert result["LOW_VOL / MEAN_REVERTING"]["total"] == 1


def test_analyze_direction():
    """Direction analysis splits UP/DOWN correctly."""
    resolved = [
        {"estimate": 0.62, "outcome": 1, "price_yes": 0.45, "conviction_score": 4},
        {"estimate": 0.62, "outcome": 0, "price_yes": 0.60, "conviction_score": 3},
        {"estimate": 0.38, "outcome": 0, "price_yes": 0.55, "conviction_score": 3},
    ]
    result = analyze_direction(resolved)
    assert result["UP"]["total"] == 2
    assert result["UP"]["wins"] == 1
    assert result["DOWN"]["total"] == 1
    assert result["DOWN"]["wins"] == 1


def test_analyze_price_buckets():
    """Price bucket analysis groups by range."""
    resolved = [
        {"estimate": 0.62, "outcome": 1, "price_yes": 0.25, "conviction_score": 3},
        {"estimate": 0.62, "outcome": 1, "price_yes": 0.45, "conviction_score": 4},
        {"estimate": 0.62, "outcome": 0, "price_yes": 0.65, "conviction_score": 3},
        {"estimate": 0.38, "outcome": 0, "price_yes": 0.75, "conviction_score": 3},
    ]
    result = analyze_price_buckets(resolved)
    assert result["0.15-0.30"]["total"] == 1
    assert result["0.15-0.30"]["wins"] == 1
    assert result["0.30-0.50"]["total"] == 1
    assert result["0.50-0.70"]["total"] == 1
    assert result["0.70-0.85"]["total"] == 1


def test_alerts_low_wr():
    """Alert fires when WR drops below 55%."""
    summary = {"resolved_bets": 10, "wr": 40, "pnl": -200, "bets": 10}
    rolling = [{"date": "2026-03-26", "bets": 10, "wr": 40, "pnl": -200}]
    alerts = generate_alerts(summary, rolling)
    assert any("55%" in a for a in alerts), f"Expected low WR alert, got {alerts}"
    assert any("loss" in a.lower() for a in alerts), f"Expected P&L alert, got {alerts}"


def test_alerts_no_bets():
    """Alert fires when no bets placed."""
    summary = {"resolved_bets": 0, "wr": 0, "pnl": 0, "bets": 0}
    rolling = [{"date": "2026-03-26", "bets": 0, "wr": 0, "pnl": 0}]
    alerts = generate_alerts(summary, rolling)
    assert any("No bets" in a for a in alerts)


def test_alerts_consecutive_losses():
    """Alert fires on 3+ consecutive losing days."""
    summary = {"resolved_bets": 5, "wr": 60, "pnl": 50, "bets": 5}
    rolling = [
        {"date": "2026-03-20", "bets": 5, "wr": 60, "pnl": 50},
        {"date": "2026-03-21", "bets": 5, "wr": 40, "pnl": -50},
        {"date": "2026-03-22", "bets": 5, "wr": 40, "pnl": -60},
        {"date": "2026-03-23", "bets": 5, "wr": 40, "pnl": -70},
        {"date": "2026-03-24", "bets": 5, "wr": 40, "pnl": -80},
    ]
    alerts = generate_alerts(summary, rolling)
    assert any("consecutive" in a.lower() for a in alerts), f"Expected losing streak alert, got {alerts}"


def test_generate_report_creates_file():
    """Full report generation creates output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        markets, predictions = _sample_data()
        db_path = _create_test_db(tmpdir, predictions, markets)
        output_dir = os.path.join(tmpdir, "daily")

        result = generate_report(
            date_str="2026-03-26",
            db_5m_path=db_path,
            db_15m_path="/nonexistent/db",  # 15m DB doesn't exist → skip
            output_dir=output_dir,
        )

        assert result is not None
        assert os.path.exists(result)

        content = open(result).read()
        assert "Daily Report" in content
        assert "2026-03-26" in content
        assert "5-Minute Pipeline" in content
        assert "Win rate" in content

        # Index should exist
        index_path = os.path.join(output_dir, "index.md")
        assert os.path.exists(index_path)
        index_content = open(index_path).read()
        assert "2026-03-26" in index_content


def test_generate_report_no_data():
    """Report returns None when no data for the date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        markets, predictions = _sample_data("2026-03-26")
        db_path = _create_test_db(tmpdir, predictions, markets)

        result = generate_report(
            date_str="2026-01-01",  # no predictions on this date
            db_5m_path=db_path,
            db_15m_path="/nonexistent/db",
            output_dir=os.path.join(tmpdir, "daily"),
        )
        assert result is None


def test_conviction_tier_analysis():
    """Conviction tiers are analyzed correctly."""
    resolved = [
        {"estimate": 0.62, "outcome": 1, "price_yes": 0.45, "conviction_score": 4},
        {"estimate": 0.62, "outcome": 1, "price_yes": 0.50, "conviction_score": 3},
        {"estimate": 0.62, "outcome": 0, "price_yes": 0.60, "conviction_score": 3},
        {"estimate": 0.50, "outcome": 1, "price_yes": 0.50, "conviction_score": 0},
    ]
    result = analyze_conviction_tiers(resolved)
    # conv=4 ($200): 1 bet, 1 win
    assert result["conv=4 ($200)"]["total"] == 1
    assert result["conv=4 ($200)"]["wins"] == 1
    # conv=3 ($75): 2 bets, 1 win 1 loss
    assert result["conv=3 ($75)"]["total"] == 2
    assert result["conv=3 ($75)"]["wins"] == 1
    # conv=0 ($0): 1 skip
    assert result["conv=0 ($0)"]["total"] == 1


# ── Decision alert tests ──────────────────────────────────────────────

def test_decision_1_is_closed():
    """Decision #1 ('Demote conv=4 to flat $75') was closed 2026-04-19
    as obsolete — live BTC sizing is already flat $25 across all tiers,
    so there's nothing to demote. This test guards against accidental
    re-enablement without re-evaluating the decision logic.
    """
    assert not any(d["id"] == 1 for d in DECISIONS), \
        "Decision #1 was closed as stale — re-enabling it requires " \
        "re-evaluating the check logic against the current flat-sizing regime"


def test_decision_alert_fires_when_ready():
    """Decision alert fires when stats cross the threshold.
    Uses Decision #6 (0.15-0.30 bucket) as the exemplar since
    Decision #1 was closed 2026-04-19.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 25 predictions in 0.15-0.30 bucket, predicting NO (est<0.5).
        # 20 markets resolve NO (outcome=0) = wins, 5 resolve YES = losses.
        # Gives 80% WR > 65% threshold.
        markets = []
        predictions = []
        for i in range(25):
            mid = f"m{i}"
            outcome = 0 if i < 20 else 1  # predicting NO; NO wins 20 of 25
            markets.append({"id": mid, "price_yes": 0.22, "resolved": 1, "outcome": outcome})
            predictions.append({
                "market_id": mid, "estimate": 0.22,
                "predicted_at": f"2026-03-26T{10 + i // 60}:{i % 60:02d}:00",
                "conviction_score": 3, "regime": "MEDIUM_VOL / NEUTRAL",
            })
        db_path = _create_test_db(tmpdir, predictions, markets)

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        stats = compute_decision_stats(db)
        db.close()

        assert stats["bucket_15_30_bets"] == 25
        assert stats["bucket_15_30_wr"] == 80.0

        # Decision #6 should fire (bucket_15_30 bets >= 20 AND WR > 65%)
        fired = [d for d in DECISIONS if d["id"] == 6 and d["check"](stats)]
        assert len(fired) == 1, f"Decision #6 should fire, stats: {stats}"


def test_decision_alert_silent_when_monitoring():
    """Decision alert does NOT fire when below sample threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Only 10 conv=4 bets — below the 50-bet minimum
        markets = []
        predictions = []
        for i in range(10):
            mid = f"m{i}"
            markets.append({"id": mid, "price_yes": 0.45, "resolved": 1, "outcome": 0})
            predictions.append({
                "market_id": mid, "estimate": 0.62,
                "predicted_at": f"2026-03-26T10:{i:02d}:00",
                "conviction_score": 4, "regime": "HIGH_VOL / TRENDING",
            })
        db_path = _create_test_db(tmpdir, predictions, markets)

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        stats = compute_decision_stats(db)
        db.close()

        assert stats["conv4_bets"] == 10  # below threshold of 50
        fired = [d for d in DECISIONS if d["id"] == 1 and d["check"](stats)]
        assert len(fired) == 0, "Decision #1 should NOT fire with only 10 bets"


def test_check_decisions_integration():
    """Full check_decisions returns alerts from real DB files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 5m DB with 25 bets in 0.50-0.70 bucket, only 12 wins (48% WR)
        markets = []
        predictions = []
        for i in range(25):
            mid = f"m{i}"
            outcome = 1 if i < 12 else 0  # 48% WR
            markets.append({"id": mid, "price_yes": 0.55, "resolved": 1, "outcome": outcome})
            predictions.append({
                "market_id": mid, "estimate": 0.62,
                "predicted_at": f"2026-03-26T10:{i:02d}:00",
                "conviction_score": 3, "regime": "HIGH_VOL / NEUTRAL",
            })
        db_5m = _create_test_db(tmpdir, predictions, markets)

        alerts = check_decisions(db_5m, "/nonexistent/15m.db")
        # Decision #2 should fire (0.50-0.70 WR 48% < 55% at 25+ bets)
        assert any("#2" in a for a in alerts), f"Expected decision #2 alert, got {alerts}"


def test_all_decisions_have_unique_ids():
    """Every decision in DECISIONS and DECISIONS_15M has a unique id."""
    all_ids = [d["id"] for d in DECISIONS] + [d["id"] for d in DECISIONS_15M]
    assert len(all_ids) == len(set(all_ids)), f"Duplicate decision IDs: {all_ids}"


def test_liquidity_section_in_report():
    """Liquidity Profile section appears when predictions have liquidity data."""
    import json
    from daily_report import format_report

    liq_data = {
        "token": "YES", "spread_pct": 1.5, "max_bet_2pct": 200,
        "max_bet_5pct": 800, "depth_levels": 30,
        "slippage_at_200": {"slippage_pct": 1.2},
    }
    data = {
        "summary": {"total_predictions": 5, "bets": 4, "skips": 1,
                     "resolved_bets": 4, "wins": 3, "losses": 1,
                     "wr": 75.0, "pnl": 100.0, "wagered": 400.0},
        "regimes": {},
        "directions": {},
        "price_buckets": {},
        "conviction": {},
        "liquidity": {
            "count": 3, "avg_spread": 1.5, "avg_max_bet_2pct": 200.0,
            "avg_max_bet_5pct": 800.0, "avg_depth_levels": 30.0,
            "avg_slip_200": 1.2, "spread_tight": 1, "spread_medium": 2,
            "spread_wide": 0, "exceeded_2pct": 0,
            "by_direction": {"YES": {"count": 3, "avg_spread": 1.5, "avg_max_bet": 200.0}},
        },
        "rolling": [],
        "alerts": [],
    }

    report = format_report("2026-03-29", data, None)
    assert "Liquidity Profile" in report
    assert "max bet @2%" in report.lower() or "max@2%" in report.lower() or "max bet" in report.lower()
    assert "Spread distribution" in report or "spread" in report.lower()


def test_liquidity_section_absent_without_data():
    """Liquidity Profile section is absent when no liquidity data exists."""
    from daily_report import format_report

    data = {
        "summary": {"total_predictions": 5, "bets": 4, "skips": 1,
                     "resolved_bets": 4, "wins": 3, "losses": 1,
                     "wr": 75.0, "pnl": 100.0, "wagered": 400.0},
        "regimes": {},
        "directions": {},
        "price_buckets": {},
        "conviction": {},
        "liquidity": None,
        "rolling": [],
        "alerts": [],
    }

    report = format_report("2026-03-29", data, None)
    assert "Liquidity Profile" not in report


# ── Trade execution / circuit breaker tests ──────────────────────────


def _create_db_with_orders(tmpdir, date_str, orders):
    """Create a test DB with orders table populated."""
    markets = [{"id": "m1", "price_yes": 0.45, "resolved": 1, "outcome": 1}]
    predictions = [
        {"market_id": "m1", "estimate": 0.62,
         "predicted_at": f"{date_str}T10:00:00", "conviction_score": 3},
    ]
    db_path = _create_test_db(tmpdir, predictions, markets)

    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id TEXT, prediction_id INTEGER, direction TEXT,
        size REAL, price_limit REAL, price_filled REAL, slippage_pct REAL,
        status TEXT DEFAULT 'pending', order_id TEXT, mode TEXT,
        reason TEXT, placed_at TEXT, filled_at TEXT, settled_at TEXT,
        pnl REAL, cycle INTEGER
    )""")
    for o in orders:
        db.execute("""
            INSERT INTO orders (market_id, direction, size, price_limit, status,
                                mode, placed_at, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (o.get("market_id", "m1"), o["direction"], o["size"],
              o.get("price_limit", 0.45), o.get("status", "settled"),
              o.get("mode", "paper"), o["placed_at"], o.get("pnl")))
    db.commit()
    db.close()
    return db_path


def test_orders_section_present_when_orders_exist():
    """Trade Execution section appears when orders exist."""
    date_str = "2026-03-28"
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = _create_db_with_orders(tmpdir, date_str, [
            {"direction": "UP", "size": 25, "placed_at": f"{date_str}T10:00:00", "pnl": 30.56},
            {"direction": "DOWN", "size": 25, "placed_at": f"{date_str}T11:00:00", "pnl": -25.00},
            {"direction": "UP", "size": 25, "placed_at": f"{date_str}T12:00:00", "pnl": 30.56},
        ])
        result = analyze_orders(db_path, date_str)
        assert result is not None
        assert result["count"] == 3
        assert result["total_wagered"] == 75
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["breaker_tripped"] is False

        # Verify it renders in the report
        data = {
            "summary": {"total_predictions": 3, "bets": 3, "skips": 0,
                         "resolved_bets": 3, "wins": 2, "losses": 1,
                         "wr": 66.7, "pnl": 36.12, "wagered": 75.0},
            "regimes": {}, "directions": {}, "price_buckets": {},
            "conviction": {}, "liquidity": None, "rolling": [],
            "orders": result, "alerts": [],
        }
        report = format_report(date_str, data, None)
        assert "Trade Execution" in report
        assert "Circuit Breaker" in report
        assert "OK" in report


def test_orders_section_absent_when_no_table():
    """Trade Execution section is absent when no orders table exists."""
    date_str = "2026-03-28"
    with tempfile.TemporaryDirectory() as tmpdir:
        markets = [{"id": "m1", "price_yes": 0.45, "resolved": 1, "outcome": 1}]
        predictions = [
            {"market_id": "m1", "estimate": 0.62,
             "predicted_at": f"{date_str}T10:00:00", "conviction_score": 3},
        ]
        db_path = _create_test_db(tmpdir, predictions, markets)

        result = analyze_orders(db_path, date_str)
        assert result is None


def test_circuit_breaker_alert_when_tripped():
    """Circuit breaker alert fires when daily loss >= limit."""
    date_str = "2026-03-28"
    with tempfile.TemporaryDirectory() as tmpdir:
        # 12 losses at $25 = $300 total loss → trips the $300 breaker
        orders_list = [
            {"direction": "UP", "size": 25, "placed_at": f"{date_str}T{10+i}:00:00", "pnl": -25.0}
            for i in range(12)
        ]
        db_path = _create_db_with_orders(tmpdir, date_str, orders_list)
        result = analyze_orders(db_path, date_str)

        assert result is not None
        assert result["breaker_tripped"] is True
        assert result["daily_loss"] >= 300

        # Verify alert fires
        summary = {"resolved_bets": 12, "wr": 0, "pnl": -300, "bets": 12}
        alerts = generate_alerts(summary, [], orders=result)
        assert any("TRIPPED" in a for a in alerts), f"Expected breaker alert, got {alerts}"


def test_circuit_breaker_warning_at_60pct():
    """Circuit breaker warning fires when daily loss >= 60% of limit."""
    date_str = "2026-03-28"
    with tempfile.TemporaryDirectory() as tmpdir:
        # 8 losses at $25 = $200 loss → 67% of $300 limit → warning
        orders_list = [
            {"direction": "UP", "size": 25, "placed_at": f"{date_str}T{10+i}:00:00", "pnl": -25.0}
            for i in range(8)
        ]
        db_path = _create_db_with_orders(tmpdir, date_str, orders_list)
        result = analyze_orders(db_path, date_str)

        assert result is not None
        assert result["breaker_tripped"] is False
        assert result["breaker_pct"] >= 60

        summary = {"resolved_bets": 8, "wr": 0, "pnl": -200, "bets": 8}
        alerts = generate_alerts(summary, [], orders=result)
        assert any("breaker" in a.lower() and "%" in a for a in alerts), f"Expected warning, got {alerts}"
        assert not any("TRIPPED" in a for a in alerts), "Should be warning, not tripped"


# ── Multi-poll Phase A daily section ────────────────────────────────


def _make_multi_poll_db(tmpdir):
    """Create a DB with multi_poll_predictions + markets, schema-matched.

    Mirrors production schema including the 2026-04-30 orderbook columns
    (mkt_mid, mkt_best_bid, mkt_best_ask, mkt_spread, orderbook_age_ms).
    """
    db_path = os.path.join(tmpdir, "mp.db")
    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE markets (
            id TEXT PRIMARY KEY,
            question TEXT,
            end_date TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER
        );
        CREATE TABLE multi_poll_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INTEGER,
            cycle_close_at TEXT NOT NULL,
            offset_seconds INTEGER NOT NULL,
            predicted_at TEXT NOT NULL,
            market_id TEXT NOT NULL,
            asset TEXT,
            estimate REAL,
            regime TEXT,
            spot_at_poll REAL,
            in_flight_return_pct REAL,
            poll_succeeded INTEGER DEFAULT 1,
            market_resolved INTEGER,
            market_outcome INTEGER,
            won INTEGER,
            mkt_mid REAL,
            mkt_best_bid REAL,
            mkt_best_ask REAL,
            mkt_spread REAL,
            orderbook_age_ms INTEGER
        );
    """)
    return db_path, db


def test_analyze_multi_poll_returns_none_when_table_missing():
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db = sqlite3.connect(os.path.join(tmpdir, "empty.db"))
        assert analyze_multi_poll(db, "2026-04-29") is None
        db.close()


def test_analyze_multi_poll_returns_none_when_no_rows_for_date():
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        # No rows inserted at all
        assert analyze_multi_poll(db, "2026-04-29") is None
        db.close()


def test_analyze_multi_poll_returns_cells_with_wr():
    """Insert 25 directional polls in a single (offset, regime) cell,
    16 wins. Should return one cell with WR=64.0%."""
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        # 25 markets, all resolved: 16 won (estimate>0.5 + outcome=1),
        # 9 lost (estimate>0.5 + outcome=0)
        for i in range(25):
            mid = f"m{i}"
            outcome = 1 if i < 16 else 0
            db.execute(
                "INSERT INTO markets (id, resolved, outcome) "
                "VALUES (?, 1, ?)", (mid, outcome),
            )
            db.execute(
                "INSERT INTO multi_poll_predictions "
                "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                "market_id, asset, estimate, regime) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (i, "2026-04-29T12:00:00", 180,
                 "2026-04-29T12:03:00", mid, "BTC", 0.65,
                 "MEDIUM_VOL / NEUTRAL"),
            )
        db.commit()

        result = analyze_multi_poll(db, "2026-04-29")
        assert result is not None
        assert len(result["cells"]) == 1
        c = result["cells"][0]
        assert c["offset_seconds"] == 180
        assert c["regime"] == "MEDIUM_VOL / NEUTRAL"
        assert c["dir_resolved"] == 25
        assert c["dir_wins"] == 16
        assert c["wr_pct"] == 64.0
        db.close()


def test_analyze_multi_poll_filters_by_date():
    """Rows from a different date must not be counted."""
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        # 30 polls on 2026-04-29 (today)
        for i in range(30):
            db.execute(
                "INSERT INTO markets (id, resolved, outcome) "
                "VALUES (?, 1, 1)", (f"m{i}",),
            )
            db.execute(
                "INSERT INTO multi_poll_predictions "
                "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                "market_id, asset, estimate, regime) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (i, "2026-04-29T12:00:00", 180,
                 "2026-04-29T12:03:00", f"m{i}", "BTC", 0.65,
                 "MEDIUM_VOL / NEUTRAL"),
            )
        # 30 polls on 2026-04-30 (different date)
        for i in range(30, 60):
            db.execute(
                "INSERT INTO markets (id, resolved, outcome) "
                "VALUES (?, 1, 0)", (f"m{i}",),
            )
            db.execute(
                "INSERT INTO multi_poll_predictions "
                "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                "market_id, asset, estimate, regime) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (i, "2026-04-30T12:00:00", 180,
                 "2026-04-30T12:03:00", f"m{i}", "BTC", 0.65,
                 "MEDIUM_VOL / NEUTRAL"),
            )
        db.commit()

        # Only 2026-04-29 should be returned (all 30 wins)
        result = analyze_multi_poll(db, "2026-04-29")
        assert result is not None
        assert len(result["cells"]) == 1
        assert result["cells"][0]["dir_resolved"] == 30
        assert result["cells"][0]["dir_wins"] == 30
        db.close()


def test_realistic_pnl_buy_yes_win():
    """BUY YES at best_ask 0.55, $25 bet, market resolves YES.
    Shares = 25/0.55 = 45.45, gross profit = 45.45 - 25 = 20.45,
    fee = 0.5, net = +19.95."""
    from daily_report import _realistic_pnl_for_cell
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        db.execute("INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 1)")
        db.execute(
            "INSERT INTO multi_poll_predictions "
            "(cycle, cycle_close_at, offset_seconds, predicted_at, "
            "market_id, asset, estimate, regime, "
            "mkt_mid, mkt_best_bid, mkt_best_ask) "
            "VALUES (1, '2026-04-30T12:00:00', 180, '2026-04-30T12:03:00', "
            "'m1', 'BTC', 0.65, 'MEDIUM_VOL / NEUTRAL', 0.54, 0.53, 0.55)"
        )
        db.commit()
        result = _realistic_pnl_for_cell(db, "2026-04-30", 180, "MEDIUM_VOL / NEUTRAL")
        assert result["n_with_orderbook"] == 1
        assert abs(result["realistic_pnl"] - 19.95) < 0.01
        db.close()


def test_realistic_pnl_buy_yes_lose():
    """BUY YES, market resolves NO. Loss = -$25."""
    from daily_report import _realistic_pnl_for_cell
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        db.execute("INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 0)")
        db.execute(
            "INSERT INTO multi_poll_predictions "
            "(cycle, cycle_close_at, offset_seconds, predicted_at, "
            "market_id, asset, estimate, regime, "
            "mkt_mid, mkt_best_bid, mkt_best_ask) "
            "VALUES (1, '2026-04-30T12:00:00', 180, '2026-04-30T12:03:00', "
            "'m1', 'BTC', 0.65, 'MEDIUM_VOL / NEUTRAL', 0.54, 0.53, 0.55)"
        )
        db.commit()
        result = _realistic_pnl_for_cell(db, "2026-04-30", 180, "MEDIUM_VOL / NEUTRAL")
        assert result["n_with_orderbook"] == 1
        assert result["realistic_pnl"] == -25.00
        db.close()


def test_realistic_pnl_buy_no_uses_complement_of_best_bid():
    """estimate < 0.5 → BUY NO at (1 - best_bid). market resolves NO → win."""
    from daily_report import _realistic_pnl_for_cell
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        db.execute("INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 0)")
        db.execute(
            "INSERT INTO multi_poll_predictions "
            "(cycle, cycle_close_at, offset_seconds, predicted_at, "
            "market_id, asset, estimate, regime, "
            "mkt_mid, mkt_best_bid, mkt_best_ask) "
            "VALUES (1, '2026-04-30T12:00:00', 180, '2026-04-30T12:03:00', "
            "'m1', 'BTC', 0.35, 'MEDIUM_VOL / NEUTRAL', 0.46, 0.45, 0.47)"
        )
        db.commit()
        result = _realistic_pnl_for_cell(db, "2026-04-30", 180, "MEDIUM_VOL / NEUTRAL")
        assert result["n_with_orderbook"] == 1
        # NO entry = 1 - 0.45 = 0.55 → same math as buy_yes_win → +19.95
        assert abs(result["realistic_pnl"] - 19.95) < 0.01
        db.close()


def test_realistic_pnl_skips_polls_without_orderbook():
    """Rows with NULL orderbook fields don't count toward realistic_n."""
    from daily_report import _realistic_pnl_for_cell
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        db.execute("INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 1)")
        db.execute(
            "INSERT INTO multi_poll_predictions "
            "(cycle, cycle_close_at, offset_seconds, predicted_at, "
            "market_id, asset, estimate, regime) "
            "VALUES (1, '2026-04-30T12:00:00', 180, '2026-04-30T12:03:00', "
            "'m1', 'BTC', 0.65, 'MEDIUM_VOL / NEUTRAL')"
        )
        db.commit()
        result = _realistic_pnl_for_cell(db, "2026-04-30", 180, "MEDIUM_VOL / NEUTRAL")
        assert result["n_with_orderbook"] == 0
        db.close()


def test_analyze_multi_poll_includes_realistic_fields():
    """Cells include realistic_pnl + realistic_ev_per_bet when orderbook present.

    25 polls, 16 wins, all at best_ask=0.55:
      Per win: 25/0.55 shares × $1 - $25 - 2%×$25 = +$19.95...
      Per loss: -$25
      Total: 16 × 19.9545 + 9 × -25 = +94.27."""
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)
        for i in range(25):
            mid = f"m{i}"
            outcome = 1 if i < 16 else 0
            db.execute(
                "INSERT INTO markets (id, resolved, outcome) VALUES (?, 1, ?)",
                (mid, outcome),
            )
            db.execute(
                "INSERT INTO multi_poll_predictions "
                "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                "market_id, asset, estimate, regime, "
                "mkt_mid, mkt_best_bid, mkt_best_ask) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (i, "2026-04-30T12:00:00", 180,
                 "2026-04-30T12:03:00", mid, "BTC", 0.65,
                 "MEDIUM_VOL / NEUTRAL", 0.54, 0.53, 0.55),
            )
        db.commit()
        result = analyze_multi_poll(db, "2026-04-30")
        c = result["cells"][0]
        assert c["realistic_n"] == 25
        assert abs(c["realistic_pnl"] - 94.27) < 0.05
        assert abs(c["realistic_ev_per_bet"] - 3.77) < 0.05
        db.close()


def test_analyze_multi_poll_finds_best_t180():
    """When multiple regimes have T+180 data, best_t180 picks the highest WR."""
    from daily_report import analyze_multi_poll
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, db = _make_multi_poll_db(tmpdir)

        def _add_cell(regime, n_wins, n_total, offset=180):
            for i in range(n_total):
                mid = f"{regime[:5]}_{offset}_{i}"
                outcome = 1 if i < n_wins else 0
                db.execute(
                    "INSERT INTO markets (id, resolved, outcome) "
                    "VALUES (?, 1, ?)", (mid, outcome),
                )
                db.execute(
                    "INSERT INTO multi_poll_predictions "
                    "(cycle, cycle_close_at, offset_seconds, predicted_at, "
                    "market_id, asset, estimate, regime) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (i, "2026-04-29T12:00:00", offset,
                     "2026-04-29T12:03:00", mid, "BTC", 0.65, regime),
                )

        # HIGH_VOL/NEUTRAL: 70/100 wins → 70% WR (best)
        _add_cell("HIGH_VOL / NEUTRAL", 70, 100)
        # MEDIUM_VOL/NEUTRAL: 60/100 wins → 60% WR
        _add_cell("MEDIUM_VOL / NEUTRAL", 60, 100)
        db.commit()

        result = analyze_multi_poll(db, "2026-04-29")
        assert result["best_t180"] is not None
        assert result["best_t180"]["regime"] == "HIGH_VOL / NEUTRAL"
        assert result["best_t180"]["wr_pct"] == 70.0
        db.close()
