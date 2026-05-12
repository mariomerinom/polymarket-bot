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


def _metrics_blockers(metrics_path: Path) -> list[str]:
    try:
        data = json.loads(Path(metrics_path).read_text())
    except Exception as exc:
        return [f"metrics_unavailable ({exc})"]

    blockers = []
    if (data.get("polymarket") or {}).get("status") != "connected":
        blockers.append("polymarket_feed_not_connected")

    dispatch = data.get("dispatch_latency_ms") or {}
    dispatch_p95 = dispatch.get("p95")
    if dispatch_p95 is None or dispatch_p95 >= DISPATCH_P95_MAX_MS:
        blockers.append(f"dispatch_p95_too_high ({dispatch_p95})")

    orderbook = data.get("orderbook_age_ms") or {}
    orderbook_p95 = orderbook.get("p95")
    if orderbook_p95 is None or orderbook_p95 >= ORDERBOOK_AGE_P95_MAX_MS:
        blockers.append(f"orderbook_age_p95_too_high ({orderbook_p95})")

    return blockers


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
