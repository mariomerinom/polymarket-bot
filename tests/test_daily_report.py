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
    generate_alerts,
    generate_report,
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

def test_decision_alert_fires_when_ready():
    """Decision alert fires when stats cross the threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a DB with 60 conv=4 bets, only 30 wins (50% WR < 60% threshold)
        markets = []
        predictions = []
        for i in range(60):
            mid = f"m{i}"
            outcome = 1 if i < 30 else 0  # 50% WR
            markets.append({"id": mid, "price_yes": 0.45, "resolved": 1, "outcome": outcome})
            predictions.append({
                "market_id": mid, "estimate": 0.62,
                "predicted_at": f"2026-03-26T{10 + i // 60}:{i % 60:02d}:00",
                "conviction_score": 4, "regime": "HIGH_VOL / TRENDING",
            })
        db_path = _create_test_db(tmpdir, predictions, markets)

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        stats = compute_decision_stats(db)
        db.close()

        assert stats["conv4_bets"] == 60
        assert stats["conv4_wr"] == 50.0

        # Decision #1 should fire (conv4 >= 50 bets AND WR < 60%)
        fired = [d for d in DECISIONS if d["id"] == 1 and d["check"](stats)]
        assert len(fired) == 1, f"Decision #1 should fire, stats: {stats}"


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
