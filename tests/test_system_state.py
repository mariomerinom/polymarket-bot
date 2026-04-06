"""Contract tests for system_state — the single source of runtime truth.

These tests assert the CONTRACT, not the implementation. If any of these
fail after migrating callers, the contract drifted — fix the contract,
not the caller.

Today's incident (2026-04-06) is the regression target: dashboard and
engine returned different answers for "consecutive_losses" because they
had two implementations of the same computation. The contract forbids
that — there is exactly one implementation, and every caller must go
through it.
"""

import os
import sqlite3
import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_db():
    """In-memory DB matching the pipeline schema used by system_state."""
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


def _insert_order(db, pnl, minutes_ago, status="settled"):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    db.execute("""
        INSERT INTO orders (market_id, direction, size, status, mode,
            placed_at, settled_at, pnl)
        VALUES (?, 'UP', 25, ?, 'paper', ?, ?, ?)
    """, (f"mkt_{minutes_ago}_{pnl}", status, ts, ts, pnl))
    db.commit()


def _insert_prediction(db, conv, minutes_ago, estimate=0.65):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    db.execute("""
        INSERT INTO predictions (market_id, agent, estimate, edge, confidence,
            reasoning, predicted_at, cycle, conviction_score, regime)
        VALUES (?, 'momentum_btc', ?, ?, 'high', 'x', ?, 1, ?, 'trending')
    """, (f"pred_{minutes_ago}", estimate, abs(estimate - 0.5), ts, conv))
    db.commit()


@pytest.fixture
def db():
    d = _make_db()
    yield d
    d.close()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure kill switch env vars don't leak between tests."""
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    monkeypatch.delenv("KILL_SWITCH_BYBIT", raising=False)
    yield


# ── Contract tests ────────────────────────────────────────────────────────────

class TestSystemStateShape:
    """The SystemState dataclass contract."""

    def test_get_system_state_returns_frozen_dataclass(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        # Must be frozen — immutability is part of the contract
        with pytest.raises(FrozenInstanceError):
            state.consecutive_losses = 999

    def test_state_has_required_fields(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        for field in [
            "pipeline_name", "computed_at", "trading_enabled", "kill_switch",
            "mode", "daily_loss", "daily_loss_limit", "consecutive_losses",
            "consecutive_loss_max", "can_trade", "blockers", "is_healthy",
            "health_warnings", "orders_today", "qualifying_signals_today",
        ]:
            assert hasattr(state, field), f"SystemState missing {field}"

    def test_pipeline_name_preserved(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        assert state.pipeline_name == "btc_5m"


class TestTradingMode:
    """Trading mode comes from pipeline_control — never TRADING_ENABLED global."""

    def test_trading_enabled_matches_pipeline_control(self, db, monkeypatch):
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: name == "btc_5m")
        state_btc = get_system_state(db, "btc_5m")
        state_eth = get_system_state(db, "eth_5m")
        assert state_btc.trading_enabled is True
        assert state_eth.trading_enabled is False
        assert state_btc.mode == "LIVE"
        assert state_eth.mode == "PAPER"


class TestKillSwitch:
    """Kill switch: env var or file."""

    def test_kill_switch_env_detected(self, db, monkeypatch):
        from system_state import get_system_state
        monkeypatch.setenv("KILL_SWITCH", "true")
        state = get_system_state(db, "btc_5m")
        assert state.kill_switch is True
        assert state.can_trade is False
        assert any("kill" in b.lower() for b in state.blockers)

    def test_kill_switch_file_detected(self, db, tmp_path, monkeypatch):
        from system_state import get_system_state
        import system_state as ss
        ks = tmp_path / "KILL_SWITCH"
        ks.write_text("1")
        monkeypatch.setattr(ss, "_kill_switch_file_path",
                            lambda pipeline: ks)
        state = get_system_state(db, "btc_5m")
        assert state.kill_switch is True


class TestConsecutiveLosses:
    """The incident target: consecutive losses must be computed ONCE."""

    def test_no_orders_returns_zero(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        assert state.consecutive_losses == 0
        assert state.seconds_since_last_settled is None

    def test_five_recent_losses_tripped(self, db):
        from system_state import get_system_state
        for i in range(5):
            _insert_order(db, pnl=-25, minutes_ago=10 + i)
        state = get_system_state(db, "btc_5m")
        assert state.consecutive_losses == 5
        assert state.can_trade is False
        assert any("consecutive" in b.lower() for b in state.blockers)

    def test_win_breaks_streak(self, db):
        from system_state import get_system_state
        _insert_order(db, pnl=-25, minutes_ago=10)
        _insert_order(db, pnl=-25, minutes_ago=20)
        _insert_order(db, pnl=+30, minutes_ago=30)  # most recent when ordered DESC is 10min
        # Ordered by settled_at DESC: 10min (loss), 20min (loss), 30min (win)
        # Streak counts from most recent: 2 losses
        state = get_system_state(db, "btc_5m")
        assert state.consecutive_losses == 2

    def test_consecutive_losses_auto_resets_after_8h(self, db):
        """Regression: 2026-04-06 incident — stale losses must auto-reset."""
        from system_state import get_system_state
        # 5 losses from 9h ago — all stale, should reset
        for i in range(5):
            _insert_order(db, pnl=-25, minutes_ago=9 * 60 + i)
        state = get_system_state(db, "btc_5m")
        assert state.consecutive_losses == 0
        assert state.can_trade is True


class TestDailyLoss:
    """Daily loss: only today, only losing orders."""

    def test_daily_loss_only_today(self, db):
        from system_state import get_system_state
        _insert_order(db, pnl=-50, minutes_ago=30)          # today
        _insert_order(db, pnl=-75, minutes_ago=60 * 48)     # 2 days ago — excluded
        state = get_system_state(db, "btc_5m")
        assert state.daily_loss == 50.0

    def test_daily_loss_excludes_wins(self, db):
        from system_state import get_system_state
        _insert_order(db, pnl=-25, minutes_ago=10)
        _insert_order(db, pnl=+30, minutes_ago=20)
        state = get_system_state(db, "btc_5m")
        assert state.daily_loss == 25.0


class TestCanTrade:
    """Final answer — the only field callers should branch on."""

    def test_clean_state_can_trade(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        assert state.can_trade is True
        assert state.blockers == []

    def test_kill_switch_blocks(self, db, monkeypatch):
        from system_state import get_system_state
        monkeypatch.setenv("KILL_SWITCH", "true")
        state = get_system_state(db, "btc_5m")
        assert state.can_trade is False

    def test_breaker_blocks(self, db):
        from system_state import get_system_state
        for i in range(5):
            _insert_order(db, pnl=-25, minutes_ago=10 + i)
        state = get_system_state(db, "btc_5m")
        assert state.can_trade is False

    def test_blockers_are_human_readable(self, db, monkeypatch):
        from system_state import get_system_state
        monkeypatch.setenv("KILL_SWITCH", "true")
        for i in range(5):
            _insert_order(db, pnl=-25, minutes_ago=10 + i)
        state = get_system_state(db, "btc_5m")
        # Multiple blockers should all show up
        assert len(state.blockers) >= 1
        for b in state.blockers:
            assert isinstance(b, str) and len(b) > 0


class TestActivityCounters:
    """Counters that feed silent-failure detection."""

    def test_qualifying_signals_today_counts_conv_ge_min(self, db):
        from system_state import get_system_state
        _insert_prediction(db, conv=4, minutes_ago=5)
        _insert_prediction(db, conv=3, minutes_ago=10)
        _insert_prediction(db, conv=1, minutes_ago=15)  # not qualifying
        state = get_system_state(db, "btc_5m")
        assert state.qualifying_signals_today == 2

    def test_orders_today_counts_all_statuses(self, db):
        from system_state import get_system_state
        _insert_order(db, pnl=-25, minutes_ago=5, status="settled")
        _insert_order(db, pnl=None, minutes_ago=10, status="filled")
        state = get_system_state(db, "btc_5m")
        assert state.orders_today == 2


class TestHealth:
    """Health check beyond 'cycle ran OK'."""

    def test_clean_state_is_healthy(self, db):
        from system_state import get_system_state
        state = get_system_state(db, "btc_5m")
        assert state.is_healthy is True
        assert state.health_warnings == []

    def test_silent_failure_detected(self, db, monkeypatch):
        """Qualifying signals but no orders placed → UNHEALTHY."""
        from system_state import get_system_state
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "is_pipeline_live",
                            lambda name: True)
        for i in range(4):
            _insert_prediction(db, conv=4, minutes_ago=10 + i * 5)
        state = get_system_state(db, "btc_5m")
        assert state.is_healthy is False
        assert any("SILENT" in w for w in state.health_warnings)
