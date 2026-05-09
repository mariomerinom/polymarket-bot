"""
pipeline_integrity.py — Lightweight per-cycle integrity checks.

Called at the end of each CI runner. Writes results to an integrity_log
table in the pipeline's database. Designed to catch silent failures
before they cost money, with minimal complexity.

No external dependencies. No network calls. Pure DB queries + logic.
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


def ensure_integrity_table(db: sqlite3.Connection) -> None:
    """Create integrity_log table if it doesn't exist. Idempotent."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS integrity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            pipeline TEXT NOT NULL,
            cycle INTEGER,
            check_name TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT
        )
    """)
    db.commit()


def run_integrity_checks(
    db: sqlite3.Connection,
    pipeline: str,
    cycle: Optional[int] = None,
    api_ok: bool = True,
    data_fetched: bool = True,
) -> list:
    """
    Run all per-cycle checks and write results to integrity_log.

    Args:
        db: Open connection to the pipeline's database.
        pipeline: Pipeline identifier ('btc_5m', 'eth_5m', etc.).
        cycle: Current cycle number (None = infer from MAX(cycle)).
        api_ok: Whether the data API call succeeded this cycle.
        data_fetched: Whether candle/market data was non-empty.

    Returns:
        List of check result dicts: [{check_name, status, detail}, ...]
    """
    ensure_integrity_table(db)

    # Infer cycle if not provided
    if cycle is None:
        try:
            row = db.execute("SELECT MAX(cycle) FROM predictions").fetchone()
            cycle = row[0] if row and row[0] else 0
        except sqlite3.OperationalError:
            cycle = 0

    results = []
    checks = [
        lambda: _check_failed_orders(db, pipeline, cycle),
        lambda: _check_orphaned_predictions(db, pipeline, cycle),
        lambda: _check_api_health(api_ok, data_fetched),
        lambda: _check_db_health(db),
        lambda: _check_expired_would_win(db, pipeline),
        lambda: _check_kill_switch(pipeline),
        lambda: _check_system_state_health(db, pipeline),
    ]

    for check_fn in checks:
        try:
            result = check_fn()
            results.append(result)
            _log_result(db, pipeline, cycle, result)
        except Exception as e:
            error_result = {
                "check_name": "check_error",
                "status": "FAIL",
                "detail": f"Check raised: {e}",
            }
            results.append(error_result)
            _log_result(db, pipeline, cycle, error_result)

    return results


def _check_failed_orders(db, pipeline, cycle) -> dict:
    """Check for orders with status='failed' this cycle."""
    result = {"check_name": "failed_orders", "status": "OK", "detail": ""}

    # Check if orders table exists
    table = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
    ).fetchone()
    if not table:
        result["detail"] = "no orders table"
        return result

    # Check for positions table (Bybit uses this instead)
    if not table:
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='positions'"
        ).fetchone()
        if not table:
            result["detail"] = "no orders/positions table"
            return result

    rows = db.execute(
        "SELECT id, market_id, reason FROM orders WHERE cycle = ? AND status = 'failed'",
        (cycle,)
    ).fetchall()

    if rows:
        reasons = [f"#{r[0]}: {r[2]}" for r in rows]
        result["status"] = "WARN"
        result["detail"] = f"{len(rows)} failed order(s): {'; '.join(reasons)}"

    return result


def _check_orphaned_predictions(db, pipeline, cycle) -> dict:
    """Check for conv>=3 predictions with no matching order this cycle.

    Skip the alert if the pipeline has active blockers (kill switch,
    daily-loss limit, consecutive-loss breaker) — those are legitimate
    reasons to skip trading on a qualifying signal. Only alert when
    there's NO reason the trade shouldn't have happened.
    """
    result = {"check_name": "orphaned_predictions", "status": "OK", "detail": ""}

    # Check if orders table exists
    table = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orders'"
    ).fetchone()
    if not table:
        result["detail"] = "no orders table — cannot check"
        return result

    # If the pipeline has active blockers, predictions skipped by them
    # are not orphans — they're correctly-declined trades.
    try:
        from system_state import get_system_state
        state = get_system_state(db, pipeline or "btc_5m")
        if state.blockers:
            result["detail"] = (
                f"skipped (active blocker: {state.blockers[0]})"
            )
            return result
    except Exception:
        # system_state unavailable — fall through to legacy check
        pass

    # Build the skip-cross-reference. fill_diagnostic now carries
    # prediction_id (added 2026-04-19), so any conv>=3 prediction that
    # was consciously skipped for a recorded reason (thin-book, low-edge,
    # cushion) can be distinguished from a genuinely silent failure.
    diag_table_exists = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='fill_diagnostic'"
    ).fetchone()

    if diag_table_exists:
        rows = db.execute("""
            SELECT p.id, p.market_id, p.conviction_score,
                   CASE
                     WHEN EXISTS (
                       SELECT 1 FROM fill_diagnostic fd
                       WHERE fd.cycle = ? AND fd.prediction_id = p.id
                     )
                     THEN 'classified_skip'
                     ELSE 'missing_terminal_classification'
                   END AS cause
            FROM predictions p
            WHERE p.cycle = ? AND p.conviction_score >= 3
              AND p.id NOT IN (
                SELECT prediction_id FROM orders
                WHERE cycle = ? AND prediction_id IS NOT NULL)
        """, (cycle, cycle, cycle)).fetchall()
        rows = [r for r in rows if r[3] != "classified_skip"]
    else:
        rows = db.execute("""
            SELECT p.id, p.market_id, p.conviction_score,
                   'missing_fill_diagnostic_table' AS cause
            FROM predictions p
            WHERE p.cycle = ? AND p.conviction_score >= 3
              AND p.id NOT IN (
                SELECT prediction_id FROM orders
                WHERE cycle = ? AND prediction_id IS NOT NULL)
        """, (cycle, cycle)).fetchall()

    if rows:
        by_cause = {}
        for row in rows:
            cause = row[3] if len(row) > 3 else "unexplained"
            by_cause.setdefault(cause, []).append(str(row[0]))
        parts = []
        for cause, ids in sorted(by_cause.items()):
            shown = ",".join(ids[:5])
            suffix = f"; +{len(ids) - 5} more" if len(ids) > 5 else ""
            parts.append(f"{cause}: {len(ids)} prediction(s) ids={shown}{suffix}")
        result["status"] = "WARN"
        result["detail"] = (
            f"{len(rows)} conv>=3 prediction(s) with no terminal execution "
            f"classification: {'; '.join(parts)}"
        )

    return result


def _check_api_health(api_ok: bool, data_fetched: bool) -> dict:
    """Check if data API call succeeded and returned data."""
    if not api_ok:
        return {
            "check_name": "api_health",
            "status": "FAIL",
            "detail": "API call failed or threw exception",
        }
    if not data_fetched:
        return {
            "check_name": "api_health",
            "status": "WARN",
            "detail": "API succeeded but returned empty data",
        }
    return {"check_name": "api_health", "status": "OK", "detail": ""}


def _check_db_health(db) -> dict:
    """Verify database pragmas are correctly set."""
    issues = []

    journal = db.execute("PRAGMA journal_mode").fetchone()[0]
    if journal not in ("wal", "memory"):  # memory is fine for tests
        issues.append(f"journal_mode={journal} (expected wal)")

    timeout = db.execute("PRAGMA busy_timeout").fetchone()[0]
    if timeout == 0:
        issues.append("busy_timeout=0 (should be >0)")

    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    if fk != 1:
        issues.append("foreign_keys=OFF")

    if issues:
        return {
            "check_name": "db_health",
            "status": "WARN",
            "detail": "; ".join(issues),
        }
    return {"check_name": "db_health", "status": "OK", "detail": ""}


def _check_expired_would_win(
    db, pipeline, today_date: Optional[str] = None
) -> dict:
    """Check for expired orders that would have won — TODAY only.

    2026-04-29 fix: prior version had no date filter and re-flagged the
    same 11 expired orders from the pre-FAK GTC era (Apr 2-5) on every
    daily run forever. The check is per-cycle / per-day, so the right
    scope is "did anything go wrong today" — not "is there ANY expired
    order in history that would have won."

    `today_date` defaults to current UTC date; injectable for tests.
    """
    result = {"check_name": "expired_would_win", "status": "OK", "detail": ""}
    if today_date is None:
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check if both tables exist
    tables = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "orders" not in tables or "markets" not in tables:
        return result

    try:
        rows = db.execute("""
            SELECT COUNT(*) FROM orders o
            JOIN markets m ON o.market_id = m.id
            WHERE o.status = 'expired' AND m.resolved = 1
            AND date(o.placed_at) = ?
            AND ((o.direction = 'UP' AND m.outcome = 1)
                 OR (o.direction = 'DOWN' AND m.outcome = 0))
        """, (today_date,)).fetchone()

        count = rows[0] if rows else 0
        if count > 0:
            result["status"] = "WARN"
            result["detail"] = (
                f"{count} expired order(s) placed today would have won"
            )
    except sqlite3.OperationalError:
        pass  # Missing columns — skip gracefully

    return result


def _check_kill_switch(pipeline) -> dict:
    """Check if kill switch is active."""
    data_dir = Path(__file__).parent.parent / "data"

    # Determine which kill switch to check
    if pipeline == "bybit":
        file_name = "KILL_SWITCH_BYBIT"
        env_var = "KILL_SWITCH_BYBIT"
    else:
        file_name = "KILL_SWITCH"
        env_var = "KILL_SWITCH"

    kill_file = data_dir / file_name
    active = kill_file.exists() or os.getenv(env_var, "false").lower() == "true"

    if active:
        return {
            "check_name": "kill_switch",
            "status": "WARN",
            "detail": f"{file_name} is ACTIVE — trading halted",
        }
    return {"check_name": "kill_switch", "status": "OK", "detail": ""}


def _check_system_state_health(db, pipeline) -> dict:
    """Run the runtime state contract health check.

    Surfaces silent failures (qualifying signals but no orders) and
    breaker lockouts (5 losses + hours of silence before auto-reset).
    This is the check that would have caught the 2026-04-06 deadlock.
    """
    result = {"check_name": "system_state_health", "status": "OK", "detail": ""}
    try:
        from system_state import get_system_state, pipeline_is_healthy
        state = get_system_state(db, pipeline)
        healthy, warnings = pipeline_is_healthy(state)
        if not healthy:
            # SILENT FAILURE and BREAKER LOCKED are hard errors; STALE is soft.
            is_fail = any(
                ("SILENT FAILURE" in w or "BREAKER LOCKED" in w)
                for w in warnings
            )
            result["status"] = "FAIL" if is_fail else "WARN"
            result["detail"] = " | ".join(warnings)
    except Exception as e:
        result["status"] = "WARN"
        result["detail"] = f"system_state unavailable: {e}"
    return result


def _log_result(db, pipeline, cycle, result: dict) -> None:
    """Write a single check result to the integrity_log table."""
    now = datetime.now(timezone.utc).isoformat()
    db.execute("""
        INSERT INTO integrity_log (timestamp, pipeline, cycle, check_name, status, detail)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (now, pipeline, cycle, result["check_name"], result["status"], result["detail"]))
    db.commit()


def get_recent_integrity(db, hours: int = 24) -> list:
    """
    Query integrity_log for WARN/FAIL entries in the last N hours.
    Used by daily_report.py and dashboard.py.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = db.execute("""
            SELECT timestamp, pipeline, cycle, check_name, status, detail
            FROM integrity_log
            WHERE timestamp >= ? AND status != 'OK'
            ORDER BY timestamp DESC
        """, (cutoff,)).fetchall()
        return [
            {
                "timestamp": r[0], "pipeline": r[1], "cycle": r[2],
                "check_name": r[3], "status": r[4], "detail": r[5],
            }
            for r in rows
        ]
    except sqlite3.OperationalError:
        return []  # Table doesn't exist yet


def get_integrity_summary(db) -> dict:
    """
    Compute a summary for dashboard display.

    Returns:
        {status: green|yellow|red, checks_24h, warnings_24h,
         failures_24h, last_check, recent_issues}
    """
    summary = {
        "status": "green",
        "checks_24h": 0,
        "warnings_24h": 0,
        "failures_24h": 0,
        "last_check": None,
        "recent_issues": [],
    }

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        row = db.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status = 'WARN' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END),
                   MAX(timestamp)
            FROM integrity_log
            WHERE timestamp >= ?
        """, (cutoff,)).fetchone()

        if row and row[0]:
            summary["checks_24h"] = row[0]
            summary["warnings_24h"] = row[1] or 0
            summary["failures_24h"] = row[2] or 0
            summary["last_check"] = row[3]

        if summary["failures_24h"] > 0:
            summary["status"] = "red"
        elif summary["warnings_24h"] > 0:
            summary["status"] = "yellow"

        # Last 5 issues
        issues = db.execute("""
            SELECT check_name, status, detail
            FROM integrity_log
            WHERE timestamp >= ? AND status != 'OK'
            ORDER BY timestamp DESC
            LIMIT 5
        """, (cutoff,)).fetchall()
        summary["recent_issues"] = [
            f"[{r[1]}] {r[0]}: {r[2]}" for r in issues
        ]

    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet

    return summary
