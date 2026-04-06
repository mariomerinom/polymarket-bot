"""Temporal tests for system_state — the missing test layer.

These tests advance time (or mutate world state mid-test) and re-check
system state. This is the layer that would have caught the 2026-04-06
incident before it shipped: the old tests asserted state at a single
moment; nothing tested "5 losses now + 9 hours later → state should
auto-reset".
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_db():
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
    from trade import ensure_orders_table
    ensure_orders_table(db)
    return db


def _insert_order_at(db, pnl, when: datetime):
    ts = when.isoformat()
    db.execute("""
        INSERT INTO orders (market_id, direction, size, status, mode,
            placed_at, settled_at, pnl)
        VALUES (?, 'UP', 25, 'settled', 'paper', ?, ?, ?)
    """, (f"mkt_{ts}_{pnl}", ts, ts, pnl))
    db.commit()


def _insert_prediction_at(db, conv, when: datetime, estimate=0.65):
    ts = when.isoformat()
    db.execute("""
        INSERT INTO predictions (market_id, agent, estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, 'momentum_btc', ?, ?, 'high', 'x', ?, 1, ?, 'trending')
    """, (f"pred_{ts}", estimate, abs(estimate - 0.5), ts, conv))
    db.commit()


@pytest.fixture
def db():
    d = _make_db()
    yield d
    d.close()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    monkeypatch.delenv("KILL_SWITCH_BYBIT", raising=False)
    yield


# ── The incident regression: temporal state transitions ─────────────────────

class TestBreakerAutoReset:
    """Reproduction of the 2026-04-06 deadlock and its fix."""

    def test_breaker_tripped_then_silence_auto_unlocks(self, db):
        """5 losses at T0 → can_trade=False.
        9 hours later → can_trade=True (auto-reset kicks in)."""
        from system_state import get_system_state
        now = datetime.now(timezone.utc)

        # T0: 5 losses just happened (minutes ago). Breaker should trip.
        for i in range(5):
            _insert_order_at(db, -25, now - timedelta(minutes=5 + i))
        state_t0 = get_system_state(db, "btc_5m")
        assert state_t0.can_trade is False
        assert state_t0.consecutive_losses == 5

        # Simulate "9 hours later": rewrite timestamps so all losses are
        # 9h in the past. Same data; the only thing that changed is time.
        db.execute("DELETE FROM orders")
        for i in range(5):
            _insert_order_at(db, -25, now - timedelta(hours=9, minutes=i))

        state_t1 = get_system_state(db, "btc_5m")
        assert state_t1.can_trade is True, (
            "Breaker must auto-reset after 8h of silence — otherwise "
            "deadlock (incident 2026-04-06)"
        )
        assert state_t1.consecutive_losses == 0

    def test_breaker_tripped_then_6h_silence_surfaces_warning(self, db):
        """5 losses + 6h silence → is_healthy=False with BREAKER LOCKED
        warning (before auto-reset kicks in at 8h)."""
        from system_state import get_system_state
        now = datetime.now(timezone.utc)
        for i in range(5):
            _insert_order_at(db, -25, now - timedelta(hours=6, minutes=i))
        state = get_system_state(db, "btc_5m")
        assert state.can_trade is False
        assert state.is_healthy is False
        assert any("BREAKER LOCKED" in w for w in state.health_warnings)

    def test_dashboard_and_engine_agree(self, db):
        """Any two callers of get_system_state must return the same
        numbers for the same DB at the same moment. This is the
        invariant the dashboard violated in the incident."""
        from system_state import get_system_state
        now = datetime.now(timezone.utc)
        for i in range(3):
            _insert_order_at(db, -25, now - timedelta(minutes=10 + i))

        engine_state = get_system_state(db, "btc_5m")
        dashboard_state = get_system_state(db, "btc_5m")

        assert engine_state.consecutive_losses == dashboard_state.consecutive_losses
        assert engine_state.daily_loss == dashboard_state.daily_loss
        assert engine_state.can_trade == dashboard_state.can_trade


class TestSilentFailure:
    """Qualifying signals but no orders — the health check we lacked."""

    def test_qualifying_signals_without_orders_is_unhealthy(self, db, monkeypatch):
        """3+ conv>=3 predictions today + 0 orders + trading enabled
        → is_healthy=False with SILENT FAILURE warning."""
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: True)
        now = datetime.now(timezone.utc)
        for i in range(4):
            _insert_prediction_at(db, conv=4, when=now - timedelta(minutes=10 + i))

        state = get_system_state(db, "btc_5m")
        assert state.is_healthy is False
        assert any("SILENT FAILURE" in w for w in state.health_warnings)

    def test_signals_with_orders_is_healthy(self, db, monkeypatch):
        """Same signal count but orders were placed → healthy."""
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: True)
        now = datetime.now(timezone.utc)
        for i in range(4):
            _insert_prediction_at(db, conv=4, when=now - timedelta(minutes=10 + i))
        # At least one order placed today
        _insert_order_at(db, +10, now - timedelta(minutes=5))

        state = get_system_state(db, "btc_5m")
        assert not any("SILENT FAILURE" in w for w in state.health_warnings)

    def test_paper_mode_never_silent_failure(self, db, monkeypatch):
        """In paper mode, no orders is expected — don't cry wolf."""
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: False)
        now = datetime.now(timezone.utc)
        for i in range(5):
            _insert_prediction_at(db, conv=4, when=now - timedelta(minutes=10 + i))

        state = get_system_state(db, "btc_5m")
        assert not any("SILENT FAILURE" in w for w in state.health_warnings)


class TestKillSwitchTransitions:
    """Kill switch toggle should reflect in state within one call."""

    def test_kill_switch_toggle_surfaces_immediately(self, db, monkeypatch):
        from system_state import get_system_state
        state_off = get_system_state(db, "btc_5m")
        assert state_off.can_trade is True

        monkeypatch.setenv("KILL_SWITCH", "true")
        state_on = get_system_state(db, "btc_5m")
        assert state_on.can_trade is False
        assert state_on.kill_switch is True


class TestStalePredictions:
    """Prediction pipeline wedged — last prediction > 15m ago."""

    def test_stale_predictions_flagged(self, db, monkeypatch):
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: False)
        now = datetime.now(timezone.utc)
        _insert_prediction_at(db, conv=1, when=now - timedelta(minutes=20))
        state = get_system_state(db, "btc_5m")
        assert any("STALE" in w for w in state.health_warnings)

    def test_fresh_predictions_not_flagged(self, db, monkeypatch):
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: False)
        now = datetime.now(timezone.utc)
        _insert_prediction_at(db, conv=1, when=now - timedelta(minutes=2))
        state = get_system_state(db, "btc_5m")
        assert not any("STALE" in w for w in state.health_warnings)
