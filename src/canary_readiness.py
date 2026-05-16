"""
canary_readiness.py — Fail-closed production canary gates.

`live_canary` is a real trading mode only after the execution and
infrastructure gates prove ready. Until then, callers should keep paper
behavior even if config/pipelines.json says live_canary.
"""

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).parent.parent
DATA_DIR = REPO_DIR / "data"
METRICS_PATH = DATA_DIR / "ws_metrics.json"

DISPATCH_P95_MAX_MS = 30_000
ORDERBOOK_AGE_P95_MAX_MS = 2_000
DISK_USED_MAX_PCT = 85.0
MIN_EHR_SAMPLE = 50
MIN_EXECUTION_EHR_SAMPLE = 10
MIN_DELAYED_EXECUTION_SAMPLE = 50
METRICS_SCHEMA_VERSION = 2
METRICS_MAX_AGE_S = 180
POLYMARKET_LAST_EVENT_MAX_AGE_S = 180


def btc5m_live_canary_blockers(
    db: sqlite3.Connection,
    *,
    metrics_path: Path = METRICS_PATH,
    disk_path: Path = REPO_DIR,
) -> list[str]:
    """Return blockers for BTC 5m live-canary activation.

    Empty list means the canary may place real orders. Any exception or
    missing evidence is treated as a blocker.
    """
    blockers = []

    try:
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        blockers.extend(state.blockers)
        if state.signal_ehr_n < MIN_EHR_SAMPLE or state.signal_ehr_7d is None:
            blockers.append(
                f"signal_ehr_insufficient_sample ({state.signal_ehr_n}/{MIN_EHR_SAMPLE})"
            )
        elif state.signal_ehr_7d <= 0:
            blockers.append(f"signal_ehr_not_positive ({state.signal_ehr_7d:+.4f})")
    except Exception as exc:
        blockers.append(f"system_state_unavailable ({exc})")

    exec_ehr, exec_n = _compute_execution_ehr_7d(db)
    if exec_n < MIN_EXECUTION_EHR_SAMPLE or exec_ehr is None:
        blockers.append(
            f"execution_ehr_insufficient_sample ({exec_n}/{MIN_EXECUTION_EHR_SAMPLE})"
        )
    elif exec_ehr < 0:
        blockers.append(f"execution_ehr_negative ({exec_ehr:+.4f} over {exec_n})")

    blockers.extend(_metrics_blockers(metrics_path))
    blockers.extend(_disk_blockers(disk_path))
    blockers.extend(_orphan_blockers(db))
    return blockers


def btc5m_live_canary_ready(db: sqlite3.Connection, **kwargs) -> bool:
    """True only when all BTC 5m canary gates are green."""
    return not btc5m_live_canary_blockers(db, **kwargs)


def btc5m_delayed_policy_blockers(db: sqlite3.Connection) -> list[str]:
    """Return blockers specific to delayed BTC 5m FAK promotion."""
    try:
        tables = {
            r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "btc5m_timing_candidates" not in tables:
            return [
                f"delayed_ehr_insufficient_sample (0/{MIN_DELAYED_EXECUTION_SAMPLE})"
            ]
        candidate_cols = {
            r[1] for r in db.execute(
                "PRAGMA table_info(btc5m_timing_candidates)"
            ).fetchall()
        }
        if {"orders", "markets"}.issubset(tables) and "order_id" in candidate_cols:
            rows = db.execute(
                """
                SELECT COALESCE(c.pnl, o.pnl) AS pnl,
                       COALESCE(
                           c.ehr,
                           CASE
                             WHEN o.direction = 'UP'
                               THEN m.outcome - COALESCE(o.price_filled, o.price_limit)
                             WHEN o.direction = 'DOWN'
                               THEN (1 - m.outcome) - COALESCE(o.price_filled, o.price_limit)
                           END
                       ) AS ehr,
                       c.orderbook_age_ms,
                       c.skip_reason
                FROM btc5m_timing_candidates c
                LEFT JOIN orders o ON o.id = c.order_id
                LEFT JOIN markets m ON m.id = c.market_id AND m.resolved = 1
                WHERE c.state IN ('paper_ordered', 'live_ordered')
                  AND c.would_fire = 1
                ORDER BY c.id DESC
                LIMIT 200
                """
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT pnl, ehr, orderbook_age_ms, skip_reason
                FROM btc5m_timing_candidates
                WHERE state IN ('paper_ordered', 'live_ordered')
                  AND would_fire = 1
                  AND ehr IS NOT NULL
                ORDER BY id DESC
                LIMIT 200
                """
            ).fetchall()
    except Exception as exc:
        return [f"delayed_candidates_unavailable ({exc})"]

    rows = [r for r in rows if r[1] is not None]
    blockers = []
    n = len(rows)
    if n < MIN_DELAYED_EXECUTION_SAMPLE:
        blockers.append(
            f"delayed_ehr_insufficient_sample ({n}/{MIN_DELAYED_EXECUTION_SAMPLE})"
        )
        return blockers

    avg_ehr = sum(float(r[1]) for r in rows) / n
    pnl = sum(float(r[0] or 0) for r in rows)
    ages = sorted(int(r[2]) for r in rows if r[2] is not None)
    p95_age = ages[int(len(ages) * 0.95)] if len(ages) >= 20 else (ages[-1] if ages else None)
    if avg_ehr < 0:
        blockers.append(f"delayed_ehr_negative ({avg_ehr:+.4f} over {n})")
    if pnl < 0:
        blockers.append(f"delayed_pnl_negative ({pnl:+.2f})")
    if p95_age is None or p95_age >= ORDERBOOK_AGE_P95_MAX_MS:
        blockers.append(f"delayed_orderbook_age_p95_too_high ({p95_age})")

    unexplained = _delayed_unexplained_count(db)
    if unexplained:
        blockers.append(f"delayed_unexplained_candidates ({unexplained})")
    return blockers


def _delayed_unexplained_count(db: sqlite3.Connection) -> int:
    try:
        row = db.execute(
            """
            SELECT COUNT(*)
            FROM btc5m_timing_candidates
            WHERE skip_reason IN ('unexpected_error', 'unexplained_no_order')
            """
        ).fetchone()
        return int(row[0] or 0)
    except Exception:
        return 0


def _metrics_blockers(metrics_path: Path) -> list[str]:
    try:
        data = json.loads(Path(metrics_path).read_text())
    except Exception as exc:
        return [f"metrics_unavailable ({exc})"]

    blockers = []
    schema = data.get("schema_version")
    if schema != METRICS_SCHEMA_VERSION:
        blockers.append(f"metrics_schema_stale ({schema})")

    written_age = _age_seconds(data.get("metrics_written_at"))
    if written_age is None:
        blockers.append("metrics_written_at_missing")
    elif written_age > METRICS_MAX_AGE_S:
        blockers.append(f"metrics_stale ({round(written_age)}s)")

    polymarket = data.get("polymarket") or {}
    if polymarket.get("status") != "connected":
        blockers.append("polymarket_feed_not_connected")
    last_event_age = _age_seconds(polymarket.get("last_event"))
    if last_event_age is None:
        blockers.append("polymarket_last_event_missing")
    elif last_event_age > POLYMARKET_LAST_EVENT_MAX_AGE_S:
        blockers.append(f"polymarket_last_event_stale ({round(last_event_age)}s)")

    dispatch = data.get("dispatch_latency_ms") or {}
    dispatch_p95 = dispatch.get("p95")
    if dispatch_p95 is None or dispatch_p95 >= DISPATCH_P95_MAX_MS:
        blockers.append(f"dispatch_p95_too_high ({dispatch_p95})")

    orderbook = data.get("orderbook_age_ms") or {}
    orderbook_p95 = orderbook.get("p95")
    if int(orderbook.get("samples") or 0) <= 0:
        blockers.append("orderbook_age_samples_missing")
    if orderbook_p95 is None or orderbook_p95 >= ORDERBOOK_AGE_P95_MAX_MS:
        blockers.append(f"orderbook_age_p95_too_high ({orderbook_p95})")

    cache = data.get("orderbook_cache") or {}
    fresh_tokens = int(cache.get("fresh_tokens_now") or 0)
    stale_tokens = int(cache.get("stale_tokens_now") or 0)
    if fresh_tokens <= 0:
        blockers.append("orderbook_fresh_tokens_missing")
    if stale_tokens > fresh_tokens:
        blockers.append(
            f"orderbook_stale_tokens_exceed_fresh ({stale_tokens}/{fresh_tokens})"
        )

    return blockers


def _age_seconds(value) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    except (TypeError, ValueError):
        return None


def _disk_blockers(disk_path: Path) -> list[str]:
    try:
        usage = shutil.disk_usage(disk_path)
    except Exception as exc:
        return [f"disk_usage_unavailable ({exc})"]
    if hasattr(usage, "total"):
        total = usage.total
        free = usage.free
    else:
        total = usage[0]
        free = usage[2]
    used_pct = ((total - free) / total) * 100
    if used_pct >= DISK_USED_MAX_PCT:
        return [f"disk_used_too_high ({used_pct:.1f}%)"]
    return []


def _orphan_blockers(db: sqlite3.Connection) -> list[str]:
    try:
        from pipeline_integrity import _check_orphaned_predictions
        row = db.execute("SELECT MAX(cycle) FROM predictions").fetchone()
        cycle = row[0] if row and row[0] is not None else 0
        result = _check_orphaned_predictions(db, "btc_5m", cycle)
        if result.get("status") != "OK":
            return [f"unexplained_orphaned_predictions ({result.get('detail', '')})"]
    except Exception as exc:
        return [f"orphan_check_unavailable ({exc})"]
    return []


def _compute_execution_ehr_7d(db: sqlite3.Connection) -> tuple[float | None, int]:
    try:
        tables = {
            r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {"orders", "predictions", "markets"}.issubset(tables):
            return None, 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = db.execute("""
            SELECT o.direction, COALESCE(o.price_filled, o.price_limit) AS price,
                   m.outcome
            FROM orders o
            JOIN predictions p ON p.id = o.prediction_id
            JOIN markets m ON m.id = p.market_id
            WHERE m.resolved = 1
              AND o.status IN ('filled', 'settled', 'paper', 'won', 'lost')
              AND date(o.placed_at) >= date(?, '-7 days')
              AND date(o.placed_at) <= ?
              AND o.direction IN ('UP', 'DOWN')
              AND price IS NOT NULL
        """, (today, today)).fetchall()
        if not rows:
            return None, 0
        values = []
        for direction, price, outcome in rows:
            price = float(price)
            outcome = int(outcome)
            if direction == "UP":
                values.append(outcome - price)
            else:
                values.append((1 - outcome) - (1 - price))
        return round(sum(values) / len(values), 4), len(values)
    except Exception:
        return None, 0
