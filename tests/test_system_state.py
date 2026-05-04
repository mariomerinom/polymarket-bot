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
        _insert_order(db, pnl=-50, minutes_ago=0)           # today, even near UTC midnight
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


class TestSignalEhrLiveGate:
    """Auto-suspend live mode when 7d rolling signal EHR drifts negative.

    Added 2026-04-21 after FAK pilot on btc_5m took −$159 on day 1 — the
    signal EHR had silently drifted from +0.035 to −0.082 over 48h and
    we didn't catch it in time. This gate would have prevented the pilot
    from going live in the first place.
    """

    def _insert_predictions_with_outcomes(self, db, n, ehr_target, price=0.55):
        """Create n conv>=3 predictions where the EHR equals ehr_target.

        Uses predict_UP (estimate > 0.5) so the EHR formula becomes
        (outcome - price). With fixed price, control wins/losses to
        tune the EHR: target = win_rate - price.
        """
        from datetime import datetime, timezone, timedelta
        # Fraction that win to produce target EHR
        win_frac = max(0.0, min(1.0, price + ehr_target))
        n_wins = int(round(n * win_frac))
        for i in range(n):
            ts_pred = (datetime.now(timezone.utc) - timedelta(hours=24 + i)).isoformat()
            ts_res = (datetime.now(timezone.utc) - timedelta(hours=23 + i)).isoformat()
            mid = f"sig_mkt_{i}"
            outcome = 1 if i < n_wins else 0
            db.execute(
                "INSERT INTO markets (id, price_yes, resolved, outcome) "
                "VALUES (?, ?, 1, ?)",
                (mid, price, outcome),
            )
            db.execute(
                "INSERT INTO predictions (market_id, agent, estimate, edge, "
                "confidence, reasoning, predicted_at, cycle, "
                "conviction_score, regime) "
                "VALUES (?, 'm', 0.62, 0.12, 'high', 'x', ?, 1, 3, 'r')",
                (mid, ts_pred),
            )
        db.commit()

    def test_ehr_computed_for_all_modes(self, db, monkeypatch):
        """EHR fields are populated regardless of mode (paper or live).
        Only the BLOCKER firing depends on mode."""
        from system_state import get_system_state
        import system_state
        self._insert_predictions_with_outcomes(db, n=60, ehr_target=-0.08)
        # Force paper mode explicitly to isolate the field-computation path
        monkeypatch.setattr(system_state, "_trading_enabled_for",
                            lambda name: False)
        state = get_system_state(db, "btc_5m")
        assert state.signal_ehr_n >= 50
        assert state.signal_ehr_7d is not None
        assert state.signal_ehr_7d < 0

    def test_live_with_negative_ehr_blocks(self, db, monkeypatch):
        """Patch is_pipeline_live to simulate live mode, verify blocker."""
        from system_state import get_system_state
        import system_state
        self._insert_predictions_with_outcomes(db, n=60, ehr_target=-0.08)
        monkeypatch.setattr(system_state, "_trading_enabled_for",
                            lambda name: True)
        state = get_system_state(db, "btc_5m")
        assert state.trading_enabled is True
        assert state.signal_ehr_7d < 0
        assert state.signal_ehr_n >= 50
        # Blocker must fire
        blocker_msg = " ".join(state.blockers)
        assert "signal_ehr_negative_7d" in blocker_msg
        assert state.can_trade is False

    def test_positive_ehr_does_not_block(self, db, monkeypatch):
        """Live mode + positive 7d EHR → no EHR blocker."""
        from system_state import get_system_state
        import system_state
        self._insert_predictions_with_outcomes(db, n=60, ehr_target=+0.05)
        monkeypatch.setattr(system_state, "_trading_enabled_for",
                            lambda name: True)
        state = get_system_state(db, "btc_5m")
        assert state.signal_ehr_7d is not None
        assert state.signal_ehr_7d >= 0
        blocker_msg = " ".join(state.blockers)
        assert "signal_ehr_negative_7d" not in blocker_msg

    def test_insufficient_sample_does_not_block(self, db, monkeypatch):
        """Live + negative EHR but only 30 bets (< 50) → no blocker."""
        from system_state import get_system_state
        import system_state
        self._insert_predictions_with_outcomes(db, n=30, ehr_target=-0.10)
        monkeypatch.setattr(system_state, "_trading_enabled_for",
                            lambda name: True)
        state = get_system_state(db, "btc_5m")
        assert state.signal_ehr_n == 30
        blocker_msg = " ".join(state.blockers)
        assert "signal_ehr_negative_7d" not in blocker_msg

    def test_paper_mode_exempt_from_ehr_gate(self, db, monkeypatch):
        """Paper mode: EHR-negative does not block. Paper should keep
        generating predictions for monitoring even when signal weakens."""
        from system_state import get_system_state
        import system_state
        monkeypatch.setattr(system_state, "_trading_enabled_for",
                            lambda name: False)
        self._insert_predictions_with_outcomes(db, n=100, ehr_target=-0.15)
        state = get_system_state(db, "btc_5m")
        assert state.trading_enabled is False
        blocker_msg = " ".join(state.blockers)
        assert "signal_ehr_negative_7d" not in blocker_msg


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


class TestBybitState:
    """Bybit pipelines must read runtime state from the positions table,
    not orders. Regression guard: diag.py Trade Execution panel silently
    lied about Bybit state for the life of the retirement commit until
    Phase 0 of the Bybit pivot landed."""

    def _make_bybit_db(self):
        d = sqlite3.connect(":memory:")
        d.execute("""CREATE TABLE markets (
            id TEXT PRIMARY KEY, question TEXT, category TEXT, end_date TEXT,
            volume REAL, price_yes REAL, price_no REAL, fetched_at TEXT,
            resolved INTEGER DEFAULT 0, outcome INTEGER DEFAULT NULL
        )""")
        d.execute("""CREATE TABLE predictions (
            id INTEGER PRIMARY KEY, market_id TEXT, agent TEXT, estimate REAL,
            edge REAL, confidence TEXT, reasoning TEXT, predicted_at TEXT,
            cycle INTEGER, conviction_score INTEGER, regime TEXT
        )""")
        d.execute("""CREATE TABLE positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT, side TEXT, size REAL, entry_price REAL,
            stop_loss REAL, status TEXT DEFAULT 'open',
            opened_at TEXT, closed_at TEXT, close_price REAL,
            pnl REAL, cycles_held INTEGER DEFAULT 0,
            close_reason TEXT, bybit_order_id TEXT
        )""")
        return d

    def _insert_closed_position(self, d, pnl, minutes_ago):
        opened = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago + 5)).isoformat()
        closed = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
        d.execute("""
            INSERT INTO positions (market_id, side, size, entry_price, stop_loss,
                                   status, opened_at, closed_at, close_price, pnl,
                                   cycles_held, close_reason)
            VALUES (?, 'Buy', 0.005, 84000, 83850, 'closed',
                    ?, ?, 83900, ?, 3, 'streak_break')
        """, (f"mkt_{minutes_ago}_{pnl}", opened, closed, pnl))
        d.commit()

    def test_bybit_state_reads_positions_not_orders(self):
        from system_state import get_system_state
        d = self._make_bybit_db()
        try:
            for i in range(5):
                self._insert_closed_position(d, pnl=-5, minutes_ago=10 + i)
            state = get_system_state(d, "bybit")
            assert state.consecutive_losses == 5
            assert state.daily_loss == 25.0
            assert state.can_trade is False
            assert any("consecutive" in b.lower() for b in state.blockers)
        finally:
            d.close()

    def test_bybit_state_no_positions_table_safe(self):
        """Bybit DB with no positions table yet — must not crash."""
        from system_state import get_system_state
        d = sqlite3.connect(":memory:")
        try:
            state = get_system_state(d, "bybit")
            assert state.consecutive_losses == 0
            assert state.daily_loss == 0.0
            assert state.can_trade is True
        finally:
            d.close()

    def test_bybit_state_win_breaks_streak(self):
        from system_state import get_system_state
        d = self._make_bybit_db()
        try:
            self._insert_closed_position(d, pnl=-5, minutes_ago=30)
            self._insert_closed_position(d, pnl=-5, minutes_ago=20)
            self._insert_closed_position(d, pnl=+10, minutes_ago=10)
            state = get_system_state(d, "bybit")
            assert state.consecutive_losses == 0
        finally:
            d.close()

    def test_bybit_state_auto_resets_after_8h(self):
        from system_state import get_system_state
        d = self._make_bybit_db()
        try:
            for i in range(5):
                self._insert_closed_position(d, pnl=-5, minutes_ago=9 * 60 + i)
            state = get_system_state(d, "bybit")
            assert state.consecutive_losses == 0
            assert state.can_trade is True
        finally:
            d.close()

    def test_bybit_orders_today_counts_positions_opened(self):
        from system_state import get_system_state
        d = self._make_bybit_db()
        try:
            ts = datetime.now(timezone.utc).isoformat()
            d.execute("""
                INSERT INTO positions (market_id, side, size, entry_price,
                                       stop_loss, status, opened_at)
                VALUES ('m1', 'Buy', 0.005, 84000, 83850, 'open', ?)
            """, (ts,))
            d.execute("""
                INSERT INTO positions (market_id, side, size, entry_price,
                                       stop_loss, status, opened_at, closed_at,
                                       close_price, pnl)
                VALUES ('m2', 'Sell', 0.005, 84000, 84150, 'closed', ?, ?, 84100, -0.5)
            """, (ts, ts))
            d.commit()
            state = get_system_state(d, "bybit")
            assert state.orders_today == 2
        finally:
            d.close()


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
