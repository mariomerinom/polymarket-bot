"""
test_fill_diagnostic.py — Lever B: fill_diagnostic table + recording API.

TDD: written BEFORE the implementation in src/fill_diagnostic.py.

Contract:
  - init_table(db) creates the table idempotently
  - record(db, **kwargs) inserts one row
  - All required fields are nullable except id, timestamp, pipeline, result
  - Result codes are an enum-like set (validated on insert)

Reference: docs/specs/stochastic/spec_fill_adverse_selection.md (Instrumentation)
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    return db


class TestSchema:

    def test_init_table_creates_schema(self):
        from fill_diagnostic import init_table
        db = _make_db()
        init_table(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(fill_diagnostic)").fetchall()}
        required = {
            "id", "order_id", "timestamp", "cycle", "pipeline",
            "decision_best_bid", "decision_best_ask", "decision_spread",
            "decision_top_ask_size", "decision_max_bet_2pct",
            "response_best_bid", "response_best_ask",
            "requested_size", "requested_limit",
            "filled_size", "filled_avg_price",
            "order_type", "cushion", "result",
            "outcome", "resolved_at",
        }
        missing = required - cols
        assert not missing, f"missing columns: {missing}"

    def test_init_table_is_idempotent(self):
        from fill_diagnostic import init_table
        db = _make_db()
        init_table(db)
        init_table(db)  # second call must not raise
        cols = {r[1] for r in db.execute("PRAGMA table_info(fill_diagnostic)").fetchall()}
        assert "result" in cols


class TestRecordAPI:

    def test_record_inserts_filled_full(self):
        from fill_diagnostic import init_table, record
        db = _make_db()
        init_table(db)
        record(
            db,
            order_id=42,
            cycle=1234,
            pipeline="btc_5m",
            decision_best_bid=0.50,
            decision_best_ask=0.51,
            decision_spread=0.01,
            decision_top_ask_size=100.0,
            decision_max_bet_2pct=80.0,
            requested_size=25.0,
            requested_limit=0.52,
            filled_size=25.0,
            filled_avg_price=0.515,
            order_type="fak",
            cushion=0.01,
            result="filled_full",
        )
        rows = db.execute("SELECT * FROM fill_diagnostic").fetchall()
        assert len(rows) == 1
        assert rows[0]["result"] == "filled_full"
        assert rows[0]["pipeline"] == "btc_5m"
        assert rows[0]["filled_size"] == 25.0
        assert rows[0]["cushion"] == 0.01
        assert rows[0]["timestamp"] is not None  # auto-populated

    def test_record_minimal_skip_row(self):
        """A skip row needs only pipeline + result; other fields nullable."""
        from fill_diagnostic import init_table, record
        db = _make_db()
        init_table(db)
        record(db, pipeline="btc_5m", result="skipped_cushion_eats_edge")
        row = db.execute("SELECT pipeline, result, requested_size FROM fill_diagnostic").fetchone()
        assert row["result"] == "skipped_cushion_eats_edge"
        assert row["requested_size"] is None

    def test_record_rejects_unknown_result_code(self):
        """Unknown result strings should raise rather than silently corrupt."""
        from fill_diagnostic import init_table, record
        db = _make_db()
        init_table(db)
        with pytest.raises(ValueError, match="result"):
            record(db, pipeline="btc_5m", result="totally_made_up_status")


class TestQueryHelpers:

    def test_fill_rate_among_fired(self):
        """fill_rate(db, pipeline) = filled_full+filled_partial / fired (excludes skips)."""
        from fill_diagnostic import init_table, record, fill_rate
        db = _make_db()
        init_table(db)
        for r in ["filled_full", "filled_full", "killed_fok",
                  "filled_partial", "skipped_cushion_eats_edge"]:
            record(db, pipeline="btc_5m", result=r)
        rate = fill_rate(db, "btc_5m")
        # 3 filled (full+partial), 1 killed → 4 fired → 75%
        # skip is excluded from denominator
        assert rate == pytest.approx(0.75, abs=0.01)


class TestDiagParser:
    def test_parses_decision_delay_and_orderbook_age_separately(self, tmp_path):
        from fill_diagnostic import parse_diag_lines, generate_report

        log = tmp_path / "loop.log"
        log.write_text(
            "DIAG|decision_delay_ms=31000|market=m1\n"
            "DIAG|orderbook_age_ms=1200\n"
            "DIAG|conv=3|drift=0.0100|decision_delay_ms=31000\n"
        )

        decision_delays, orderbook_ages, rtt_values, drift_by_conv = parse_diag_lines(log)
        assert decision_delays == [31000.0]
        assert orderbook_ages == [1200.0]
        assert rtt_values == []
        assert drift_by_conv[3] == [0.01]

        report = generate_report(
            decision_delays, orderbook_ages, rtt_values, drift_by_conv,
            min_samples=1,
        )
        assert "Decision delay (ms)" in report
        assert "Orderbook age at read (ms)" in report
        assert "Snapshot age" not in report
