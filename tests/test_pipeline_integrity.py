"""Tests for pipeline_integrity.py — per-cycle integrity checks."""

import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db():
    """Create an in-memory DB with markets + predictions + orders tables."""
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE markets (
        id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
        volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
        resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
    )""")
    db.execute("""CREATE TABLE predictions (
        id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
        edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
        cycle INTEGER, conviction_score INTEGER, regime TEXT
    )""")
    db.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY, market_id TEXT, prediction_id INTEGER,
        direction TEXT, size REAL, price_limit REAL, price_filled REAL,
        slippage_pct REAL, status TEXT DEFAULT 'pending', order_id TEXT,
        mode TEXT, reason TEXT, placed_at TEXT, filled_at TEXT,
        settled_at TEXT, pnl REAL, cycle INTEGER
    )""")
    return db


# ══════════════════════════════════════════════════════════════════════════════
# Table creation
# ══════════════════════════════════════════════════════════════════════════════

class TestEnsureIntegrityTable:
    def test_creates_table(self):
        from pipeline_integrity import ensure_integrity_table
        db = _make_db()
        ensure_integrity_table(db)
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='integrity_log'"
        ).fetchone()
        assert row is not None
        db.close()

    def test_idempotent(self):
        from pipeline_integrity import ensure_integrity_table
        db = _make_db()
        ensure_integrity_table(db)
        ensure_integrity_table(db)  # Should not raise
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Individual checks
# ══════════════════════════════════════════════════════════════════════════════

class TestFailedOrders:
    def test_no_failed_orders_ok(self):
        from pipeline_integrity import _check_failed_orders
        db = _make_db()
        result = _check_failed_orders(db, "btc_5m", 1)
        assert result["status"] == "OK"
        db.close()

    def test_detects_failed_order(self):
        from pipeline_integrity import _check_failed_orders
        db = _make_db()
        db.execute(
            "INSERT INTO orders (market_id, status, reason, cycle, placed_at) "
            "VALUES ('m1', 'failed', 'missing_clob_token_id', 1, '2026-04-04T00:00:00')"
        )
        result = _check_failed_orders(db, "btc_5m", 1)
        assert result["status"] == "WARN"
        assert "missing_clob_token_id" in result["detail"]
        db.close()

    def test_different_cycle_not_flagged(self):
        from pipeline_integrity import _check_failed_orders
        db = _make_db()
        db.execute(
            "INSERT INTO orders (market_id, status, reason, cycle, placed_at) "
            "VALUES ('m1', 'failed', 'some_error', 5, '2026-04-04T00:00:00')"
        )
        result = _check_failed_orders(db, "btc_5m", 10)  # Different cycle
        assert result["status"] == "OK"
        db.close()


class TestOrphanedPredictions:
    def test_no_orphans_ok(self):
        from pipeline_integrity import _check_orphaned_predictions
        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )
        db.execute(
            "INSERT INTO orders (prediction_id, market_id, cycle, placed_at, status) "
            "VALUES (1, 'm1', 1, '2026-04-04', 'paper')"
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "OK"
        db.close()

    def test_detects_orphan(self):
        from pipeline_integrity import _check_orphaned_predictions
        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "WARN"
        assert "no terminal execution classification" in result["detail"]
        assert "missing_fill_diagnostic_table" in result["detail"]
        assert "1" in result["detail"]
        db.close()

    def test_conv2_not_orphaned(self):
        """Conv < 3 predictions should NOT be flagged as orphaned."""
        from pipeline_integrity import _check_orphaned_predictions
        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 2)"
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "OK"
        db.close()

    def test_breaker_tripped_not_orphaned(self):
        """When consecutive_loss_breaker is active, missing orders on
        conv>=3 predictions are correct behavior, not orphans. The
        daily report was flagging these as WARN which caused noise
        across the perp pipelines (2026-04-17 session finding).

        We simulate the trigger by adding a KILL_SWITCH file which
        system_state reads as a blocker. Avoids coupling to the specific
        live-vs-paper order-status filter in _compute_consecutive_losses.
        """
        import os
        import tempfile
        from pathlib import Path
        from pipeline_integrity import _check_orphaned_predictions

        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, "
            "cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )

        # Install KILL_SWITCH env var to force a blocker
        os.environ["KILL_SWITCH"] = "true"
        try:
            result = _check_orphaned_predictions(db, "btc_5m", 1)
        finally:
            os.environ.pop("KILL_SWITCH", None)

        # Should be OK (not WARN) because a blocker prevented the trade
        assert result["status"] == "OK", \
            f"Expected OK when blocker active, got {result}"
        assert "blocker" in result["detail"].lower()
        db.close()

    def test_no_blocker_still_flags_orphan(self):
        """Regression guard: when there's NO blocker, a missing order
        on conv>=3 IS still a real orphan and should WARN."""
        import os
        from pipeline_integrity import _check_orphaned_predictions

        # Ensure no env-based blockers
        os.environ.pop("KILL_SWITCH", None)

        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, "
            "cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "WARN"
        db.close()

    def test_fill_diagnostic_entry_not_orphaned(self):
        """Consciously-skipped predictions (thin book, low edge, etc.)
        write to fill_diagnostic with their prediction_id. These are NOT
        orphans — the trade was correctly declined. Added 2026-04-19 to
        stop the false-positive orphan alerts we saw on perp pipelines."""
        import os
        from pipeline_integrity import _check_orphaned_predictions
        import fill_diagnostic as fd

        os.environ.pop("KILL_SWITCH", None)

        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, "
            "cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )
        fd.init_table(db)
        fd.record(
            db, pipeline="btc_5m", result="skipped_thin_book",
            prediction_id=1, cycle=1,
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "OK", \
            f"Expected OK when fill_diagnostic records skip, got {result}"
        db.close()

    def test_no_diag_and_no_blocker_still_orphan(self):
        """Regression guard: with fill_diagnostic table present but no
        matching row for this prediction, orphan is still flagged."""
        import os
        from pipeline_integrity import _check_orphaned_predictions
        import fill_diagnostic as fd

        os.environ.pop("KILL_SWITCH", None)

        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, "
            "cycle, conviction_score) "
            "VALUES (1, 'm1', 'momentum', 0.65, 1, 3)"
        )
        fd.init_table(db)
        # Unrelated diagnostic row — filter must be on prediction_id
        fd.record(
            db, pipeline="btc_5m", result="skipped_thin_book",
            prediction_id=999, cycle=1,
        )
        result = _check_orphaned_predictions(db, "btc_5m", 1)
        assert result["status"] == "WARN", \
            f"Expected WARN with no matching diag entry, got {result}"
        assert "missing_terminal_classification" in result["detail"]
        db.close()

    def test_orphans_grouped_by_terminal_classification_cause(self):
        """Unexplained conv>=3 predictions are grouped by root cause."""
        import os
        from pipeline_integrity import _check_orphaned_predictions
        import fill_diagnostic as fd

        os.environ.pop("KILL_SWITCH", None)

        db = _make_db()
        fd.init_table(db)
        for pid in (1, 2):
            db.execute(
                "INSERT INTO predictions (id, market_id, agent, estimate, "
                "cycle, conviction_score) "
                "VALUES (?, ?, 'momentum', 0.65, 1, 3)",
                (pid, f"m{pid}"),
            )

        result = _check_orphaned_predictions(db, "btc_5m", 1)

        assert result["status"] == "WARN"
        assert "missing_terminal_classification: 2 prediction(s)" in result["detail"]
        assert "ids=1,2" in result["detail"]
        db.close()


class TestApiHealth:
    def test_ok(self):
        from pipeline_integrity import _check_api_health
        result = _check_api_health(api_ok=True, data_fetched=True)
        assert result["status"] == "OK"

    def test_api_fail(self):
        from pipeline_integrity import _check_api_health
        result = _check_api_health(api_ok=False, data_fetched=False)
        assert result["status"] == "FAIL"

    def test_empty_data(self):
        from pipeline_integrity import _check_api_health
        result = _check_api_health(api_ok=True, data_fetched=False)
        assert result["status"] == "WARN"


class TestDbHealth:
    def test_memory_db_ok(self):
        """In-memory DBs report journal_mode=memory which is acceptable."""
        from pipeline_integrity import _check_db_health
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA foreign_keys=ON")
        result = _check_db_health(db)
        # memory journal mode is accepted
        assert result["status"] == "OK" or "journal_mode" not in result.get("detail", "")
        db.close()

    def test_detects_missing_fk(self):
        from pipeline_integrity import _check_db_health
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA busy_timeout=5000")
        # foreign_keys defaults to OFF
        result = _check_db_health(db)
        assert result["status"] == "WARN"
        assert "foreign_keys" in result["detail"]
        db.close()

    def test_detects_missing_timeout(self):
        from pipeline_integrity import _check_db_health
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=0")  # Explicitly set to 0
        result = _check_db_health(db)
        assert result["status"] == "WARN"
        assert "busy_timeout" in result["detail"]
        db.close()


class TestExpiredWouldWin:
    def test_no_expired(self):
        from pipeline_integrity import _check_expired_would_win
        db = _make_db()
        result = _check_expired_would_win(db, "btc_5m", today_date="2026-04-29")
        assert result["status"] == "OK"
        db.close()

    def test_detects_missed_win_placed_today(self):
        """An expired order placed TODAY that would have won → WARN."""
        from pipeline_integrity import _check_expired_would_win
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 1)"
        )
        db.execute(
            "INSERT INTO orders (market_id, direction, status, cycle, placed_at) "
            "VALUES ('m1', 'UP', 'expired', 1, '2026-04-29T15:00:00+00:00')"
        )
        result = _check_expired_would_win(db, "btc_5m", today_date="2026-04-29")
        assert result["status"] == "WARN"
        assert "1 expired" in result["detail"]
        db.close()

    def test_ignores_old_expired_orders(self):
        """REGRESSION: expired orders from prior days must NOT trigger today's
        alert. Pre-fix behavior: the query had no date filter, so the same
        11 GTC-era expired orders from 2026-04-02/04/05 re-fired the alarm
        every single day forever. Fixed 2026-04-29 (commit TBD).
        """
        from pipeline_integrity import _check_expired_would_win
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 1)"
        )
        # Two old expired-would-win orders (legacy GTC era)
        db.execute(
            "INSERT INTO orders (market_id, direction, status, cycle, placed_at) "
            "VALUES ('m1', 'UP', 'expired', 1, '2026-04-02T15:00:00+00:00')"
        )
        db.execute(
            "INSERT INTO orders (market_id, direction, status, cycle, placed_at) "
            "VALUES ('m1', 'UP', 'expired', 1, '2026-04-05T15:00:00+00:00')"
        )
        result = _check_expired_would_win(db, "btc_5m", today_date="2026-04-29")
        assert result["status"] == "OK", \
            f"Old expired orders should NOT trigger today's alert; got {result}"
        db.close()

    def test_today_filter_excludes_yesterday(self):
        """Boundary: an expired order placed yesterday must not count."""
        from pipeline_integrity import _check_expired_would_win
        db = _make_db()
        db.execute(
            "INSERT INTO markets (id, resolved, outcome) VALUES ('m1', 1, 1)"
        )
        db.execute(
            "INSERT INTO orders (market_id, direction, status, cycle, placed_at) "
            "VALUES ('m1', 'UP', 'expired', 1, '2026-04-28T23:59:59+00:00')"
        )
        result = _check_expired_would_win(db, "btc_5m", today_date="2026-04-29")
        assert result["status"] == "OK"
        db.close()


class TestKillSwitch:
    def test_not_active(self):
        from pipeline_integrity import _check_kill_switch
        with patch.dict(os.environ, {"KILL_SWITCH": "false"}):
            result = _check_kill_switch("btc_5m")
        assert result["status"] == "OK"

    def test_env_active(self):
        from pipeline_integrity import _check_kill_switch
        with patch.dict(os.environ, {"KILL_SWITCH": "true"}):
            result = _check_kill_switch("btc_5m")
        assert result["status"] == "WARN"
        assert "ACTIVE" in result["detail"]

    def test_bybit_kill_switch(self):
        from pipeline_integrity import _check_kill_switch
        with patch.dict(os.environ, {"KILL_SWITCH_BYBIT": "true"}):
            result = _check_kill_switch("bybit")
        assert result["status"] == "WARN"
        assert "BYBIT" in result["detail"]


# ══════════════════════════════════════════════════════════════════════════════
# Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestRunIntegrityChecks:
    def test_writes_to_log(self):
        from pipeline_integrity import run_integrity_checks, ensure_integrity_table
        db = _make_db()
        results = run_integrity_checks(db, "btc_5m", cycle=1)
        assert len(results) > 0
        rows = db.execute("SELECT COUNT(*) FROM integrity_log").fetchone()
        assert rows[0] == len(results)
        db.close()

    def test_infers_cycle_when_none(self):
        from pipeline_integrity import run_integrity_checks
        db = _make_db()
        db.execute(
            "INSERT INTO predictions (id, market_id, agent, estimate, cycle, conviction_score) "
            "VALUES (1, 'm1', 'test', 0.6, 42, 2)"
        )
        results = run_integrity_checks(db, "btc_5m", cycle=None)
        # Should have inferred cycle=42
        row = db.execute("SELECT cycle FROM integrity_log LIMIT 1").fetchone()
        assert row[0] == 42
        db.close()


class TestGetRecentIntegrity:
    def test_returns_only_warnings(self):
        from pipeline_integrity import ensure_integrity_table, get_recent_integrity
        from datetime import datetime, timezone
        db = _make_db()
        ensure_integrity_table(db)
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO integrity_log (timestamp, pipeline, check_name, status, detail) "
            "VALUES (?, 'btc_5m', 'db_health', 'OK', 'all good')", (now,)
        )
        db.execute(
            "INSERT INTO integrity_log (timestamp, pipeline, check_name, status, detail) "
            "VALUES (?, 'btc_5m', 'failed_orders', 'WARN', '1 failed')", (now,)
        )
        results = get_recent_integrity(db, hours=24)
        assert len(results) == 1
        assert results[0]["status"] == "WARN"
        db.close()


class TestGetIntegritySummary:
    def test_green_when_clean(self):
        from pipeline_integrity import ensure_integrity_table, get_integrity_summary
        db = _make_db()
        ensure_integrity_table(db)
        summary = get_integrity_summary(db)
        assert summary["status"] == "green"
        db.close()

    def test_red_on_failure(self):
        from pipeline_integrity import ensure_integrity_table, get_integrity_summary
        from datetime import datetime, timezone
        db = _make_db()
        ensure_integrity_table(db)
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO integrity_log (timestamp, pipeline, check_name, status, detail) "
            "VALUES (?, 'btc_5m', 'api_health', 'FAIL', 'API down')", (now,)
        )
        summary = get_integrity_summary(db)
        assert summary["status"] == "red"
        assert summary["failures_24h"] == 1
        db.close()

    def test_yellow_on_warning(self):
        from pipeline_integrity import ensure_integrity_table, get_integrity_summary
        from datetime import datetime, timezone
        db = _make_db()
        ensure_integrity_table(db)
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO integrity_log (timestamp, pipeline, check_name, status, detail) "
            "VALUES (?, 'btc_5m', 'kill_switch', 'WARN', 'active')", (now,)
        )
        summary = get_integrity_summary(db)
        assert summary["status"] == "yellow"
        assert summary["warnings_24h"] == 1
        db.close()
