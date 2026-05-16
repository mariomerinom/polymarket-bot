"""Delayed BTC 5m FAK execution candidate tests."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE markets (
            id TEXT PRIMARY KEY,
            price_yes REAL,
            price_no REAL,
            end_date TEXT,
            fetched_at TEXT,
            resolved INTEGER DEFAULT 0,
            outcome INTEGER
        );
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY,
            market_id TEXT,
            estimate REAL,
            conviction_score INTEGER,
            predicted_at TEXT,
            cycle INTEGER,
            reasoning TEXT,
            agent TEXT
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
            poll_succeeded INTEGER DEFAULT 1,
            conviction_score INTEGER,
            mkt_mid REAL,
            mkt_best_bid REAL,
            mkt_best_ask REAL,
            mkt_spread REAL,
            orderbook_age_ms INTEGER
        );
    """)
    db.execute(
        "INSERT INTO markets VALUES "
        "('m1', 0.54, 0.46, '2026-05-13T12:05:00+00:00', "
        "'2026-05-13T12:00:00+00:00', 0, NULL)"
    )
    db.execute(
        "INSERT INTO predictions VALUES "
        "(1, 'm1', 0.65, 4, '2026-05-13T12:00:05+00:00', 10, '{}', "
        "'momentum_rule')"
    )
    db.execute(
        """INSERT INTO multi_poll_predictions
           (cycle, cycle_close_at, offset_seconds, predicted_at, market_id,
            asset, estimate, regime, poll_succeeded, conviction_score,
            mkt_mid, mkt_best_bid, mkt_best_ask, mkt_spread, orderbook_age_ms)
           VALUES (10, '2026-05-13T12:00:00+00:00', 180,
                   '2026-05-13T12:03:00+00:00', 'm1', 'BTC', 0.70,
                   'MEDIUM_VOL / NEUTRAL', 1, 4, 0.54, 0.53, 0.55,
                   0.02, 500)"""
    )
    db.commit()
    return db


def _config(tmp_path, policy):
    path = tmp_path / "pipelines.json"
    path.write_text(json.dumps({
        "pipelines": {
            "btc_5m": {
                "mode": "paper",
                "bet_size": 25,
                "timing_policy": policy,
            }
        }
    }))
    return path


def test_shadow_policy_records_would_place_but_creates_no_order(tmp_path, monkeypatch):
    import delayed_execution
    import pipeline_control

    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", _config(tmp_path, "delay_180_shadow"))
    monkeypatch.setattr(delayed_execution, "_get_tokens", lambda market_id: {"yes": "yes", "no": "no"})

    db = _db()
    result = delayed_execution.process_delayed_poll(db, 1, pipeline_name="btc_5m")

    assert result["state"] == "shadow_would_place"
    assert result["order_id"] is None
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_paper_policy_routes_one_order_through_fak_path(tmp_path, monkeypatch):
    import delayed_execution
    import pipeline_control

    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", _config(tmp_path, "delay_180_paper"))
    monkeypatch.setattr(delayed_execution, "_get_tokens", lambda market_id: {"yes": "yes", "no": "no"})

    db = _db()
    result = delayed_execution.process_delayed_poll(db, 1, pipeline_name="btc_5m")

    assert result["state"] == "paper_ordered"
    order = db.execute(
        "SELECT order_type, action, status, prediction_id FROM orders"
    ).fetchone()
    assert order["order_type"] == "fak"
    assert order["action"] == "fak_take"
    assert order["status"] == "paper"
    assert order["prediction_id"] == 1


def test_live_canary_policy_blocks_when_readiness_fails(tmp_path, monkeypatch):
    import delayed_execution
    import pipeline_control

    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", _config(tmp_path, "delay_180_live_canary"))
    monkeypatch.setattr(delayed_execution, "_get_tokens", lambda market_id: {"yes": "yes", "no": "no"})
    monkeypatch.setattr(
        delayed_execution,
        "_readiness_blockers",
        lambda db: ["delayed_ehr_insufficient_sample (0/50)"],
    )

    db = _db()
    result = delayed_execution.process_delayed_poll(db, 1, pipeline_name="btc_5m")

    assert result["state"] == "blocked"
    assert "readiness_blocked" in result["skip_reason"]
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_live_canary_failed_order_marks_candidate_failed(tmp_path, monkeypatch):
    import delayed_execution
    import pipeline_control

    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", _config(tmp_path, "delay_180_live_canary"))
    monkeypatch.setattr(delayed_execution, "_get_tokens", lambda market_id: None)
    monkeypatch.setattr(delayed_execution, "_readiness_blockers", lambda db: [])

    db = _db()
    result = delayed_execution.process_delayed_poll(db, 1, pipeline_name="btc_5m")

    assert result["state"] == "live_failed"
    assert result["skip_reason"] == "missing_clob_token_id"
    order = db.execute("SELECT status, reason FROM orders").fetchone()
    assert order["status"] == "failed"
    assert order["reason"] == "missing_clob_token_id"


def test_unexpected_delayed_exception_records_terminal_candidate():
    import delayed_execution

    db = _db()
    row = db.execute("SELECT * FROM multi_poll_predictions WHERE id = 1").fetchone()

    result = delayed_execution.record_unexpected_error(
        db,
        row,
        policy="delay_180_paper",
        error=RuntimeError("boom"),
    )

    assert result["state"] == "blocked"
    assert result["skip_reason"].startswith("unexpected_error")
    stored = db.execute(
        "SELECT state, skip_reason FROM btc5m_timing_candidates"
    ).fetchone()
    assert stored["state"] == "blocked"
    assert stored["skip_reason"].startswith("unexpected_error")


def test_immediate_execution_suppressed_in_delayed_paper_policy(tmp_path, monkeypatch):
    import delayed_execution
    import pipeline_control

    monkeypatch.setattr(pipeline_control, "CONFIG_PATH", _config(tmp_path, "delay_180_paper"))

    assert delayed_execution.should_suppress_immediate("btc_5m") is True


def test_live_fak_submission_uses_fak_order_type():
    from trade import _submit_fak_order

    client = MagicMock()
    client.create_market_order.return_value = "signed"
    client.post_order.return_value = {"success": True, "status": "MATCHED"}
    with patch("trade._init_clob_client", return_value=(client, "BUY", "SELL")):
        with patch("py_clob_client.clob_types.OrderType") as order_type:
            order_type.FAK = "FAK"
            order_type.FOK = "FOK"
            _submit_fak_order("tok", "BUY", 25, 0.55)

    assert client.post_order.call_args.kwargs["orderType"] == "FAK"
