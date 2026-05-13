"""Tests for fail-closed BTC 5m live-canary readiness gates."""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db(signal_ehr=0.08, execution_ehr=0.04, n=60):
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, price_yes REAL, price_no REAL, end_date TEXT,
        fetched_at TEXT, resolved INTEGER, outcome INTEGER
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, estimate REAL,
        conviction_score INTEGER, predicted_at TEXT, cycle INTEGER,
        reasoning TEXT, agent TEXT
    )""")
    db.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY, market_id TEXT, prediction_id INTEGER,
        direction TEXT, price_limit REAL, price_filled REAL,
        status TEXT, placed_at TEXT, cycle INTEGER, pnl REAL, settled_at TEXT
    )""")
    now = datetime.now(timezone.utc)
    win_rate = 0.55 + execution_ehr
    signal_price = round(max(0.05, min(0.95, win_rate - signal_ehr)), 4)
    wins = round(n * win_rate)
    for i in range(1, n + 1):
        outcome = 1 if i <= wins else 0
        ts = (now - timedelta(days=1)).isoformat()
        db.execute(
            "INSERT INTO markets VALUES (?, ?, ?, ?, ?, 1, ?)",
            (f"m{i}", signal_price, 1 - signal_price, ts, ts, outcome),
        )
        db.execute(
            "INSERT INTO predictions VALUES (?, ?, 0.65, 3, ?, ?, '{}', 'momentum')",
            (i, f"m{i}", ts, i),
        )
        db.execute(
            "INSERT INTO orders VALUES (?, ?, ?, 'UP', 0.55, 0.55, "
            "'settled', ?, ?, 1.0, ?)",
            (i, f"m{i}", i, ts, i, ts),
        )
    db.commit()
    return db


def _metrics(tmp_path, *, dispatch_p95=1000, orderbook_p95=500, connected=True):
    path = tmp_path / "ws_metrics.json"
    path.write_text(json.dumps({
        "polymarket": {"status": "connected" if connected else "disconnected"},
        "dispatch_latency_ms": {"p95": dispatch_p95},
        "orderbook_age_ms": {"p95": orderbook_p95},
    }))
    return path


def test_btc5m_live_canary_ready_when_all_gates_green(tmp_path):
    from canary_readiness import btc5m_live_canary_blockers

    db = _make_db()

    with patch("canary_readiness.shutil.disk_usage") as usage:
        usage.return_value = (100, 20, 80)
        blockers = btc5m_live_canary_blockers(
            db,
            metrics_path=_metrics(tmp_path),
            disk_path=tmp_path,
        )

    assert blockers == []


def test_btc5m_live_canary_blocks_stale_orderbook(tmp_path):
    from canary_readiness import btc5m_live_canary_blockers

    db = _make_db()

    with patch("canary_readiness.shutil.disk_usage") as usage:
        usage.return_value = (100, 20, 80)
        blockers = btc5m_live_canary_blockers(
            db,
            metrics_path=_metrics(tmp_path, orderbook_p95=2500),
            disk_path=tmp_path,
        )

    assert any("orderbook_age_p95_too_high" in b for b in blockers)


def test_btc5m_live_canary_blocks_negative_execution_ehr(tmp_path):
    from canary_readiness import btc5m_live_canary_blockers

    db = _make_db(execution_ehr=-0.20)

    with patch("canary_readiness.shutil.disk_usage") as usage:
        usage.return_value = (100, 20, 80)
        blockers = btc5m_live_canary_blockers(
            db,
            metrics_path=_metrics(tmp_path),
            disk_path=tmp_path,
        )

    assert any("execution_ehr_negative" in b for b in blockers)


def test_live_canary_mode_stays_paper_when_readiness_blocks(tmp_path, monkeypatch):
    import pipeline_control
    import trade

    cfg = tmp_path / "pipelines.json"
    cfg.write_text(json.dumps({"pipelines": {"btc_5m": {"mode": "live_canary"}}}))
    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg)
    monkeypatch.setattr(trade, "run_shadow_logging", lambda db, cycle: None)
    monkeypatch.setattr(trade, "should_trade", lambda pred, db, pipeline_name: (False, "blocked"))

    db = _make_db(n=1)
    rows = trade.execute_trades(db, 1, pipeline_name="btc_5m")

    assert rows == []


def test_delayed_live_canary_blocks_without_paper_sample(tmp_path):
    from canary_readiness import btc5m_delayed_policy_blockers

    db = _make_db()
    db.execute("""
        CREATE TABLE btc5m_timing_candidates (
            id INTEGER PRIMARY KEY,
            state TEXT,
            would_fire INTEGER,
            pnl REAL,
            ehr REAL,
            orderbook_age_ms INTEGER,
            skip_reason TEXT,
            created_at TEXT
        )
    """)

    blockers = btc5m_delayed_policy_blockers(db)

    assert any("delayed_ehr_insufficient_sample" in b for b in blockers)


def test_delayed_live_canary_blocks_negative_delayed_ehr(tmp_path):
    from canary_readiness import btc5m_delayed_policy_blockers

    db = _make_db()
    db.execute("""
        CREATE TABLE btc5m_timing_candidates (
            id INTEGER PRIMARY KEY,
            state TEXT,
            would_fire INTEGER,
            pnl REAL,
            ehr REAL,
            orderbook_age_ms INTEGER,
            skip_reason TEXT,
            created_at TEXT
        )
    """)
    for i in range(50):
        db.execute(
            "INSERT INTO btc5m_timing_candidates "
            "(state, would_fire, pnl, ehr, orderbook_age_ms, created_at) "
            "VALUES ('paper_ordered', 1, -1.0, -0.02, 500, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
    db.commit()

    blockers = btc5m_delayed_policy_blockers(db)

    assert any("delayed_ehr_negative" in b for b in blockers)
