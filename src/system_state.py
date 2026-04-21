"""
system_state.py — The ONE authoritative runtime state for a pipeline.

This module is the single source of truth for every "runtime fact" that
used to be re-derived independently across trade.py, daily_report.py,
and pipeline_integrity.py.

Historical incident (2026-04-06, dashboard era — dashboards retired
2026-04-08):
    - trade.py::_check_consecutive_losses  → 5 (blocked trading)
    - the (now-retired) dashboard breaker check → 0 (showed green)
    - Both queried the same DB. Both were "correct" by their own logic.
    - BTC 5m was locked out for 30+ hours while the dashboard lied.

Rule: no caller outside this module may query orders.pnl, daily_loss,
consecutive losses, or TRADING_ENABLED state directly. All reads go
through get_system_state(). Enforced by tests/test_state_invariants.py.

The module is READ-ONLY. It never writes to the DB. It never mutates
anything. SystemState is frozen.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from config import (
    CONSECUTIVE_LOSS_MAX,
    DAILY_LOSS_LIMIT,
    MAX_LOSS_LOOKBACK,
    MIN_CONVICTION,
)

# Auto-reset window — matches src/trade.py behavior. If this drifts, the
# incident (dashboard lie) recurs. Single constant here enforces parity.
CONSECUTIVE_LOSS_COOLDOWN_HOURS = 8

# Silent-failure threshold: if N qualifying signals fire today but 0
# orders are placed and trading is enabled, flag as unhealthy.
SILENT_FAILURE_SIGNAL_THRESHOLD = 3

# Signal-EHR live gate (added 2026-04-21 after FAK pilot on btc_5m took
# −$159 on day 1 — signal EHR had quietly drifted from +0.035 to −0.082
# over 48h before going live). When live-mode, require 7-day rolling
# signal EHR >= threshold on a minimum sample before allowing trades.
# Paper mode is unaffected — the gate only blocks LIVE trading.
SIGNAL_EHR_LIVE_GATE_THRESHOLD = 0.0  # strictly require non-negative
SIGNAL_EHR_LIVE_GATE_MIN_SAMPLE = 50  # minimum bets in 7d window to gate

# Stale prediction threshold for the health check.
STALE_PREDICTION_SECONDS = 15 * 60


# ── Kill switch ──────────────────────────────────────────────────────────────

def _kill_switch_file_path(pipeline_name: str) -> Path:
    """Location of the kill switch file for a given pipeline.

    Monkeypatched in tests. Pipelines with dedicated kill switches (bybit, hl)
    use a suffixed filename; everything else shares KILL_SWITCH.
    Per-pair pipelines (eth_bybit, sol_hl, etc.) share exchange-level switch.
    """
    base = Path(__file__).parent.parent / "data"
    if pipeline_name.startswith("bybit"):
        return base / "KILL_SWITCH_BYBIT"
    if pipeline_name.startswith("hl"):
        return base / "KILL_SWITCH_HL"
    # Generic perp: {asset}_{exchange} — route to exchange kill switch
    if "bybit" in pipeline_name:
        return base / "KILL_SWITCH_BYBIT"
    if "hl" in pipeline_name:
        return base / "KILL_SWITCH_HL"
    return base / "KILL_SWITCH"


def _kill_switch_env_var(pipeline_name: str) -> str:
    if pipeline_name.startswith("bybit"):
        return "KILL_SWITCH_BYBIT"
    if pipeline_name.startswith("hl"):
        return "KILL_SWITCH_HL"
    # Generic perp: {asset}_{exchange}
    if "bybit" in pipeline_name:
        return "KILL_SWITCH_BYBIT"
    if "hl" in pipeline_name:
        return "KILL_SWITCH_HL"
    return "KILL_SWITCH"


def _check_kill_switch(pipeline_name: str) -> bool:
    if _kill_switch_file_path(pipeline_name).exists():
        return True
    return os.environ.get(_kill_switch_env_var(pipeline_name), "").lower() == "true"


# ── Dataclass ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SystemState:
    """Authoritative runtime state snapshot for a pipeline. Immutable.

    Every caller that needs to answer "can we trade?", "are we healthy?",
    or "what's our current loss streak?" reads from here — never by
    re-querying the DB.
    """

    pipeline_name: str
    computed_at: datetime

    # Trading mode
    trading_enabled: bool
    kill_switch: bool
    mode: str  # "LIVE" | "PAPER"

    # Financial state
    daily_loss: float
    daily_loss_limit: float
    total_pnl_today: float

    # Breaker state
    consecutive_losses: int
    consecutive_loss_max: int
    breaker_cooldown_hours: int
    seconds_since_last_settled: Optional[float]

    # Activity state
    last_settled_at: Optional[datetime]
    last_prediction_at: Optional[datetime]
    last_qualifying_signal_at: Optional[datetime]
    orders_today: int
    qualifying_signals_today: int

    # Signal health — rolling 7d EHR, used for live-mode auto-gating
    signal_ehr_7d: Optional[float]
    signal_ehr_n: int

    # Final answers — the ONLY fields callers should branch on
    can_trade: bool
    blockers: List[str]
    is_healthy: bool
    health_warnings: List[str]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    # Always return tz-aware UTC (some legacy rows are naive)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _today_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _compute_signal_ehr_7d(db) -> tuple[Optional[float], int]:
    """Compute the 7-day rolling signal EHR for this pipeline's DB.

    Returns (ehr, n). ehr is None if n < 5 (insufficient data to report).
    Matches the formula in daily_report.analyze_ehr — signal EHR for
    conv>=3 predictions: avg((1*outcome - price_yes) if predict_YES else
    ((1-outcome) - (1-price_yes))) for resolved markets in last 7d.

    Safe: returns (None, 0) on any error; never raises.
    """
    try:
        if not _table_exists(db, "predictions") or not _table_exists(db, "markets"):
            return None, 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = db.execute("""
            SELECT COUNT(*) as n,
              AVG(CASE WHEN p.estimate > 0.5 THEN (1.0*m.outcome - m.price_yes)
                   ELSE ((1.0 - m.outcome) - (1.0 - m.price_yes)) END) as ehr
            FROM predictions p JOIN markets m ON p.market_id = m.id
            WHERE p.conviction_score >= 3 AND m.resolved = 1
              AND date(p.predicted_at) >= date(?, '-7 days')
              AND date(p.predicted_at) <= ?
        """, (today, today)).fetchone()
        if not row or not row[0] or row[0] < 5:
            return None, 0
        return round(row[1], 4) if row[1] is not None else None, int(row[0])
    except Exception:
        return None, 0


def _is_perp(pipeline_name: str) -> bool:
    """Perp pipelines track state in `positions`, not `orders`.

    Covers: bybit, hl, eth_bybit, eth_hl, sol_bybit, sol_hl, doge_bybit, doge_hl.
    """
    if pipeline_name.startswith("bybit") or pipeline_name.startswith("hl"):
        return True
    # Generic perp pipelines: {asset}_{exchange}
    perp_exchanges = ("_bybit", "_hl")
    return any(pipeline_name.endswith(suffix) for suffix in perp_exchanges)


# Backward compat alias
_is_bybit = _is_perp


def _table_exists(db, name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


# ── Individual read helpers ──────────────────────────────────────────────────

def _compute_consecutive_losses(db, now: datetime) -> tuple[int, Optional[datetime], Optional[float]]:
    """Return (streak, last_settled_at, seconds_since_last_settled).

    Applies the 8h auto-reset — if the last settled order is older than
    CONSECUTIVE_LOSS_COOLDOWN_HOURS, streak is 0 regardless of the raw
    loss sequence. Prevents permanent deadlock where the breaker blocks
    all trades so no win can reset it.
    """
    if not _table_exists(db, "orders"):
        return 0, None, None

    last = db.execute("""
        SELECT settled_at FROM orders
        WHERE status = 'settled' AND settled_at IS NOT NULL
        ORDER BY settled_at DESC LIMIT 1
    """).fetchone()

    last_settled_at = _parse_ts(last[0]) if last else None
    seconds_since = None
    if last_settled_at is not None:
        seconds_since = (now - last_settled_at).total_seconds()

    # Auto-reset
    if (
        seconds_since is not None
        and seconds_since > CONSECUTIVE_LOSS_COOLDOWN_HOURS * 3600
    ):
        return 0, last_settled_at, seconds_since

    rows = db.execute("""
        SELECT pnl FROM orders
        WHERE status = 'settled' AND pnl IS NOT NULL
        ORDER BY settled_at DESC LIMIT ?
    """, (MAX_LOSS_LOOKBACK,)).fetchall()

    streak = 0
    for (pnl,) in rows:
        if pnl is not None and pnl < 0:
            streak += 1
        else:
            break
    return streak, last_settled_at, seconds_since


def _compute_consecutive_losses_bybit(db, now: datetime) -> tuple[int, Optional[datetime], Optional[float]]:
    """Bybit variant — reads closed positions from the `positions` table."""
    if not _table_exists(db, "positions"):
        return 0, None, None

    last = db.execute("""
        SELECT closed_at FROM positions
        WHERE status = 'closed' AND closed_at IS NOT NULL
        ORDER BY closed_at DESC LIMIT 1
    """).fetchone()

    last_closed_at = _parse_ts(last[0]) if last else None
    seconds_since = None
    if last_closed_at is not None:
        seconds_since = (now - last_closed_at).total_seconds()

    # Auto-reset on stale streaks (same 8h rule as Polymarket)
    if (
        seconds_since is not None
        and seconds_since > CONSECUTIVE_LOSS_COOLDOWN_HOURS * 3600
    ):
        return 0, last_closed_at, seconds_since

    rows = db.execute("""
        SELECT pnl FROM positions
        WHERE status = 'closed' AND pnl IS NOT NULL
        ORDER BY closed_at DESC LIMIT ?
    """, (MAX_LOSS_LOOKBACK,)).fetchall()

    streak = 0
    for (pnl,) in rows:
        if pnl is not None and pnl < 0:
            streak += 1
        else:
            break
    return streak, last_closed_at, seconds_since


def _compute_daily_loss_bybit(db) -> tuple[float, float]:
    if not _table_exists(db, "positions"):
        return 0.0, 0.0
    today = _today_prefix()
    row = db.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0) AS loss,
            COALESCE(SUM(COALESCE(pnl, 0)), 0) AS total
        FROM positions
        WHERE closed_at LIKE ? AND status = 'closed'
    """, (f"{today}%",)).fetchone()
    loss = abs(row[0]) if row and row[0] else 0.0
    total = float(row[1]) if row and row[1] is not None else 0.0
    return loss, total


def _compute_orders_today_bybit(db) -> int:
    """Bybit 'orders today' := positions opened today."""
    if not _table_exists(db, "positions"):
        return 0
    today = _today_prefix()
    row = db.execute("""
        SELECT COUNT(*) FROM positions WHERE opened_at LIKE ?
    """, (f"{today}%",)).fetchone()
    return int(row[0]) if row else 0


def _compute_daily_loss(db) -> tuple[float, float]:
    """Return (daily_loss_abs, total_pnl_today)."""
    if not _table_exists(db, "orders"):
        return 0.0, 0.0
    today = _today_prefix()
    row = db.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END), 0) AS loss,
            COALESCE(SUM(COALESCE(pnl, 0)), 0) AS total
        FROM orders
        WHERE placed_at LIKE ?
          AND status IN ('filled', 'settled')
    """, (f"{today}%",)).fetchone()
    loss = abs(row[0]) if row and row[0] else 0.0
    total = float(row[1]) if row and row[1] is not None else 0.0
    return loss, total


def _compute_orders_today(db) -> int:
    if not _table_exists(db, "orders"):
        return 0
    today = _today_prefix()
    row = db.execute("""
        SELECT COUNT(*) FROM orders WHERE placed_at LIKE ?
    """, (f"{today}%",)).fetchone()
    return int(row[0]) if row else 0


def _compute_prediction_activity(db) -> tuple[int, Optional[datetime], Optional[datetime]]:
    """Return (qualifying_today, last_prediction_at, last_qualifying_at)."""
    if not _table_exists(db, "predictions"):
        return 0, None, None
    today = _today_prefix()

    try:
        return _compute_prediction_activity_impl(db, today)
    except Exception:
        # Legacy schemas without predicted_at/conviction_score — fail open
        return 0, None, None


def _compute_prediction_activity_impl(db, today):
    row = db.execute("""
        SELECT COUNT(*) FROM predictions
        WHERE predicted_at LIKE ? AND conviction_score >= ?
    """, (f"{today}%", MIN_CONVICTION)).fetchone()
    qualifying = int(row[0]) if row else 0

    last_any = db.execute("""
        SELECT predicted_at FROM predictions
        ORDER BY predicted_at DESC LIMIT 1
    """).fetchone()
    last_qual = db.execute("""
        SELECT predicted_at FROM predictions
        WHERE conviction_score >= ?
        ORDER BY predicted_at DESC LIMIT 1
    """, (MIN_CONVICTION,)).fetchone()

    return (
        qualifying,
        _parse_ts(last_any[0]) if last_any else None,
        _parse_ts(last_qual[0]) if last_qual else None,
    )


def _trading_enabled_for(pipeline_name: str) -> bool:
    """Source of truth for "are we live?". Always via pipeline_control."""
    try:
        from pipeline_control import is_pipeline_live
        return bool(is_pipeline_live(pipeline_name))
    except Exception:
        return False


# ── Public API ───────────────────────────────────────────────────────────────

def get_system_state(db, pipeline_name: str) -> SystemState:
    """The ONE authoritative state function.

    No caller is allowed to recompute any of these fields from the DB
    independently. If you need more state, add a field here — don't
    write a new query elsewhere.
    """
    now = datetime.now(timezone.utc)

    trading_enabled = _trading_enabled_for(pipeline_name)
    kill_switch = _check_kill_switch(pipeline_name)

    if _is_bybit(pipeline_name):
        consec, last_settled_at, seconds_since = _compute_consecutive_losses_bybit(db, now)
        daily_loss, total_pnl_today = _compute_daily_loss_bybit(db)
        orders_today = _compute_orders_today_bybit(db)
    else:
        consec, last_settled_at, seconds_since = _compute_consecutive_losses(db, now)
        daily_loss, total_pnl_today = _compute_daily_loss(db)
        orders_today = _compute_orders_today(db)
    qualifying_today, last_prediction_at, last_qualifying_at = (
        _compute_prediction_activity(db)
    )

    # Signal health — rolling 7d EHR
    signal_ehr_7d, signal_ehr_n = _compute_signal_ehr_7d(db)

    # Final answer: can we trade?
    blockers: List[str] = []
    if kill_switch:
        blockers.append("kill_switch_active")
    if daily_loss >= DAILY_LOSS_LIMIT:
        blockers.append(
            f"daily_loss_limit (${daily_loss:.0f} >= ${DAILY_LOSS_LIMIT:.0f})"
        )
    if consec >= CONSECUTIVE_LOSS_MAX:
        blockers.append(
            f"consecutive_loss_breaker ({consec} >= {CONSECUTIVE_LOSS_MAX})"
        )
    # Signal-EHR live gate: auto-suspend live mode when 7d rolling EHR
    # has drifted negative on a meaningful sample. Paper mode bypasses
    # this — we want paper to keep generating predictions for monitoring
    # even when the signal is weakened. Added 2026-04-21.
    if (
        trading_enabled
        and signal_ehr_7d is not None
        and signal_ehr_n >= SIGNAL_EHR_LIVE_GATE_MIN_SAMPLE
        and signal_ehr_7d < SIGNAL_EHR_LIVE_GATE_THRESHOLD
    ):
        blockers.append(
            f"signal_ehr_negative_7d ({signal_ehr_7d:+.4f} over "
            f"{signal_ehr_n} bets, threshold >={SIGNAL_EHR_LIVE_GATE_THRESHOLD:+.2f})"
        )
    can_trade = len(blockers) == 0

    # Health check — stricter than can_trade
    warnings: List[str] = []
    if (
        qualifying_today >= SILENT_FAILURE_SIGNAL_THRESHOLD
        and orders_today == 0
        and trading_enabled
    ):
        warnings.append(
            f"SILENT FAILURE: {qualifying_today} qualifying signals today "
            f"but 0 orders placed"
        )
    if (
        consec >= CONSECUTIVE_LOSS_MAX
        and seconds_since is not None
        and seconds_since > 6 * 3600
    ):
        warnings.append(
            f"BREAKER LOCKED: {consec} losses, "
            f"{seconds_since / 3600:.1f}h since last trade"
        )
    if last_prediction_at is not None:
        age = (now - last_prediction_at).total_seconds()
        if age > STALE_PREDICTION_SECONDS:
            warnings.append(
                f"STALE: last prediction was {age / 60:.0f}m ago"
            )
    is_healthy = len(warnings) == 0

    return SystemState(
        pipeline_name=pipeline_name,
        computed_at=now,
        trading_enabled=trading_enabled,
        kill_switch=kill_switch,
        mode="LIVE" if trading_enabled else "PAPER",
        daily_loss=daily_loss,
        daily_loss_limit=float(DAILY_LOSS_LIMIT),
        total_pnl_today=total_pnl_today,
        consecutive_losses=consec,
        consecutive_loss_max=int(CONSECUTIVE_LOSS_MAX),
        breaker_cooldown_hours=CONSECUTIVE_LOSS_COOLDOWN_HOURS,
        seconds_since_last_settled=seconds_since,
        last_settled_at=last_settled_at,
        last_prediction_at=last_prediction_at,
        last_qualifying_signal_at=last_qualifying_at,
        orders_today=orders_today,
        qualifying_signals_today=qualifying_today,
        signal_ehr_7d=signal_ehr_7d,
        signal_ehr_n=signal_ehr_n,
        can_trade=can_trade,
        blockers=blockers,
        is_healthy=is_healthy,
        health_warnings=warnings,
    )


def pipeline_is_healthy(state: SystemState) -> tuple[bool, List[str]]:
    """Health check accessor. Same data as state.is_healthy/warnings,
    exposed as a function for callers that prefer the verb form."""
    return state.is_healthy, list(state.health_warnings)
