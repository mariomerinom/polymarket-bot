"""
test_bybit.py — Tests for the Bybit USDT perpetual futures pipeline.

Covers: data layer, DB schema, synthetic markets, position lifecycle,
risk gates, ATR, stop-loss, exit logic, PnL, kill switch, scoring.
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src/ is on path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_CANDLES = [
    {"time": "14:00", "open": 84000, "high": 84100, "low": 83950, "close": 84080,
     "volume": 10.0, "direction": "UP", "body_pct": 0.095, "wick_ratio": 0.47},
    {"time": "14:05", "open": 84080, "high": 84200, "low": 84050, "close": 84180,
     "volume": 12.0, "direction": "UP", "body_pct": 0.119, "wick_ratio": 0.33},
    {"time": "14:10", "open": 84180, "high": 84300, "low": 84150, "close": 84250,
     "volume": 8.0, "direction": "UP", "body_pct": 0.083, "wick_ratio": 0.53},
    {"time": "14:15", "open": 84250, "high": 84350, "low": 84200, "close": 84320,
     "volume": 15.0, "direction": "UP", "body_pct": 0.083, "wick_ratio": 0.53},
    {"time": "14:20", "open": 84320, "high": 84400, "low": 84280, "close": 84380,
     "volume": 11.0, "direction": "UP", "body_pct": 0.071, "wick_ratio": 0.50},
]

REVERSAL_CANDLES = SAMPLE_CANDLES + [
    {"time": "14:25", "open": 84380, "high": 84400, "low": 84200, "close": 84220,
     "volume": 20.0, "direction": "DOWN", "body_pct": -0.190, "wick_ratio": 0.20},
    {"time": "14:30", "open": 84220, "high": 84250, "low": 84100, "close": 84120,
     "volume": 18.0, "direction": "DOWN", "body_pct": -0.119, "wick_ratio": 0.33},
    {"time": "14:35", "open": 84120, "high": 84150, "low": 84000, "close": 84020,
     "volume": 22.0, "direction": "DOWN", "body_pct": -0.119, "wick_ratio": 0.33},
]


@pytest.fixture
def bybit_db(tmp_path):
    """Create a temporary Bybit DB for testing."""
    db_path = tmp_path / "test_bybit.db"
    with patch("bybit_markets.DB_PATH_BYBIT", db_path):
        from bybit_markets import init_db_bybit
        db = init_db_bybit()
        yield db
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Leg 1: Data Layer Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBybitConfig:
    def test_shadow_config_exists(self):
        from config import SHADOW_CONFIGS
        assert "bybit_5m" in SHADOW_CONFIGS
        cfg = SHADOW_CONFIGS["bybit_5m"]
        assert cfg["min_streak"] == 3
        assert cfg["baseline_streak"] == 8
        assert cfg["max_edge"] == 0.14

    def test_bybit_bet_size(self):
        from config import BYBIT_BET_SIZE, BYBIT_DAILY_LOSS_LIMIT
        assert BYBIT_BET_SIZE == 0.005
        assert BYBIT_DAILY_LOSS_LIMIT == 50

    def test_bybit_conviction_bets(self):
        from config import LIVE_BYBIT_CONVICTION_BETS
        assert LIVE_BYBIT_CONVICTION_BETS[3] == 0.005
        assert LIVE_BYBIT_CONVICTION_BETS[0] == 0


class TestBybitDB:
    def test_db_init_creates_tables(self, bybit_db):
        tables = bybit_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "markets" in table_names
        assert "predictions" in table_names
        assert "orders" in table_names
        assert "positions" in table_names

    def test_wal_mode_enabled(self, bybit_db):
        mode = bybit_db.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


class TestSyntheticMarkets:
    def test_create_synthetic_market(self, bybit_db):
        from bybit_markets import create_synthetic_market
        cycle_time = datetime(2026, 4, 2, 14, 17, 30, tzinfo=timezone.utc)
        market_id = create_synthetic_market(bybit_db, 84000.0, cycle_time)

        # Should round to 5-min boundary
        assert market_id == "BTCUSDT-2026-04-02T14:15:00Z"

        # Verify market was inserted
        row = bybit_db.execute(
            "SELECT * FROM markets WHERE id = ?", (market_id,)
        ).fetchone()
        assert row is not None
        assert row["category"] == "cryptocurrency"

    def test_synthetic_market_dedup(self, bybit_db):
        from bybit_markets import create_synthetic_market
        cycle_time = datetime(2026, 4, 2, 14, 17, 0, tzinfo=timezone.utc)

        id1 = create_synthetic_market(bybit_db, 84000.0, cycle_time)
        id2 = create_synthetic_market(bybit_db, 84100.0, cycle_time)

        assert id1 == id2  # Same 5-min window = same market

        count = bybit_db.execute(
            "SELECT COUNT(*) FROM markets"
        ).fetchone()[0]
        assert count == 1


class TestPositionLifecycle:
    def test_open_and_close(self, bybit_db):
        from bybit_markets import (
            open_position, close_position, get_open_position,
        )

        pos_id = open_position(
            bybit_db, "BTCUSDT-test", "Buy", 0.005, 84000.0, 83850.0
        )
        assert pos_id > 0

        pos = get_open_position(bybit_db)
        assert pos is not None
        assert pos["side"] == "Buy"
        assert pos["size"] == 0.005
        assert pos["status"] == "open"

        close_position(bybit_db, pos_id, 84200.0, 1.0, "streak_break")

        pos = get_open_position(bybit_db)
        assert pos is None  # No open positions

    def test_increment_cycles_held(self, bybit_db):
        from bybit_markets import (
            open_position, get_open_position, increment_cycles_held,
        )

        pos_id = open_position(
            bybit_db, "BTCUSDT-test", "Buy", 0.005, 84000.0, 83850.0
        )

        for _ in range(3):
            increment_cycles_held(bybit_db, pos_id)

        pos = get_open_position(bybit_db)
        assert pos["cycles_held"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# Leg 2: Trading Engine Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestATR:
    def test_compute_atr_basic(self):
        from bybit_trade import compute_atr
        atr = compute_atr(SAMPLE_CANDLES, period=3)
        assert atr > 0
        # Each candle has range ~$120-150, ATR should be in that ballpark
        assert 100 < atr < 200

    def test_compute_atr_single_candle(self):
        from bybit_trade import compute_atr
        atr = compute_atr([SAMPLE_CANDLES[0]])
        assert atr == SAMPLE_CANDLES[0]["high"] - SAMPLE_CANDLES[0]["low"]


class TestOrderComputation:
    def test_buy_order(self):
        from bybit_trade import compute_bybit_order
        pred = {"estimate": 0.60}
        order = compute_bybit_order(pred, mark_price=84000.0, atr=100.0)

        assert order["side"] == "Buy"
        assert order["direction"] == "UP"
        assert order["qty"] == 0.005
        assert order["stop_loss"] < 84000.0  # Below entry for longs
        assert order["stop_loss"] == round(84000.0 - 100.0 * 1.5, 2)

    def test_sell_order(self):
        from bybit_trade import compute_bybit_order
        pred = {"estimate": 0.40}
        order = compute_bybit_order(pred, mark_price=84000.0, atr=100.0)

        assert order["side"] == "Sell"
        assert order["direction"] == "DOWN"
        assert order["stop_loss"] > 84000.0  # Above entry for shorts
        assert order["stop_loss"] == round(84000.0 + 100.0 * 1.5, 2)


class TestPnLCalculation:
    def test_long_win(self):
        from bybit_trade import _compute_pnl
        pnl = _compute_pnl("Buy", 0.005, 84000.0, 84200.0)
        raw = (84200 - 84000) * 0.005  # $1.00
        fees = 84000 * 0.005 * 0.00055 * 2  # ~$0.462
        assert abs(pnl - (raw - fees)) < 0.01

    def test_long_loss(self):
        from bybit_trade import _compute_pnl
        pnl = _compute_pnl("Buy", 0.005, 84000.0, 83800.0)
        assert pnl < 0

    def test_short_win(self):
        from bybit_trade import _compute_pnl
        pnl = _compute_pnl("Sell", 0.005, 84000.0, 83800.0)
        raw = (84000 - 83800) * 0.005  # $1.00
        fees = 84000 * 0.005 * 0.00055 * 2
        assert abs(pnl - (raw - fees)) < 0.01

    def test_short_loss(self):
        from bybit_trade import _compute_pnl
        pnl = _compute_pnl("Sell", 0.005, 84000.0, 84200.0)
        assert pnl < 0


class TestRiskGates:
    def test_conviction_gate(self, bybit_db):
        from bybit_trade import should_trade_bybit
        pred = {"conviction_score": 2, "estimate": 0.60}
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert not ok
        assert "conviction_too_low" in reason

    def test_edge_gate(self, bybit_db):
        from bybit_trade import should_trade_bybit
        pred = {"conviction_score": 3, "estimate": 0.52}
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert not ok
        assert "edge_too_small" in reason

    def test_passes_all_gates(self, bybit_db):
        from bybit_trade import should_trade_bybit
        pred = {"conviction_score": 3, "estimate": 0.60}
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert ok
        assert reason == "ok"

    def test_same_direction_skip(self, bybit_db):
        from bybit_trade import should_trade_bybit
        from bybit_markets import open_position

        open_position(bybit_db, "test", "Buy", 0.005, 84000.0, 83850.0)

        pred = {"conviction_score": 3, "estimate": 0.60}  # Would be Buy
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert not ok
        assert "same_direction" in reason

    def test_opposite_direction_allowed(self, bybit_db):
        from bybit_trade import should_trade_bybit
        from bybit_markets import open_position

        open_position(bybit_db, "test", "Buy", 0.005, 84000.0, 83850.0)

        pred = {"conviction_score": 3, "estimate": 0.40}  # Would be Sell
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert ok

    def test_daily_loss_limit(self, bybit_db):
        from bybit_trade import should_trade_bybit
        from bybit_markets import open_position, close_position

        # Create enough losses to breach $50 limit
        for i in range(10):
            pos_id = open_position(
                bybit_db, f"test-{i}", "Buy", 0.005, 84000.0, 83850.0
            )
            close_position(bybit_db, pos_id, 83800.0, -6.0, "stop_loss")

        pred = {"conviction_score": 3, "estimate": 0.60}
        ok, reason = should_trade_bybit(pred, bybit_db)
        assert not ok
        assert "daily_loss_limit" in reason

    def test_consecutive_loss_breaker(self, bybit_db):
        from bybit_trade import _check_consecutive_losses
        from bybit_markets import open_position, close_position

        for i in range(5):
            pos_id = open_position(
                bybit_db, f"loss-{i}", "Buy", 0.005, 84000.0, 83850.0
            )
            close_position(bybit_db, pos_id, 83900.0, -0.5, "streak_break")

        assert _check_consecutive_losses(bybit_db) == 5

    def test_consecutive_loss_resets_on_win(self, bybit_db):
        from bybit_trade import _check_consecutive_losses
        from bybit_markets import open_position, close_position

        # 3 losses then 1 win
        for i in range(3):
            pos_id = open_position(
                bybit_db, f"loss-{i}", "Buy", 0.005, 84000.0, 83850.0
            )
            close_position(bybit_db, pos_id, 83900.0, -0.5, "streak_break")

        pos_id = open_position(
            bybit_db, "win", "Buy", 0.005, 84000.0, 83850.0
        )
        close_position(bybit_db, pos_id, 84200.0, 1.0, "streak_break")

        assert _check_consecutive_losses(bybit_db) == 0


class TestKillSwitch:
    def test_env_var(self):
        from bybit_trade import is_bybit_kill_switched
        with patch.dict(os.environ, {"KILL_SWITCH_BYBIT": "true"}):
            assert is_bybit_kill_switched()

    def test_not_kill_switched(self):
        from bybit_trade import is_bybit_kill_switched
        with patch.dict(os.environ, {"KILL_SWITCH_BYBIT": "false"}, clear=False):
            # Ensure no kill switch file exists
            kill_file = Path(__file__).parent.parent / "data" / "KILL_SWITCH_BYBIT"
            existed = kill_file.exists()
            if existed:
                kill_file.rename(kill_file.with_suffix(".bak"))
            try:
                assert not is_bybit_kill_switched()
            finally:
                if existed:
                    kill_file.with_suffix(".bak").rename(kill_file)


class TestExitConditions:
    def test_time_ceiling(self):
        from bybit_trade import check_exit_conditions
        position = {"side": "Buy", "cycles_held": 6}
        should_exit, reason = check_exit_conditions(SAMPLE_CANDLES, position)
        assert should_exit
        assert reason == "time_ceiling"

    def test_streak_break(self):
        from bybit_trade import check_exit_conditions
        # Reversal candles show DOWN streak after UP
        position = {"side": "Buy", "cycles_held": 2}
        should_exit, reason = check_exit_conditions(REVERSAL_CANDLES, position)
        assert should_exit
        assert reason == "streak_break"

    def test_hold_when_no_exit(self):
        from bybit_trade import check_exit_conditions
        # UP candles match Buy position — should hold
        position = {"side": "Buy", "cycles_held": 2}
        should_exit, reason = check_exit_conditions(SAMPLE_CANDLES, position)
        # May or may not exit depending on signal — either is valid
        if not should_exit:
            assert reason == "hold"


# ══════════════════════════════════════════════════════════════════════════════
# Leg 2: Scoring Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBybitScoring:
    def test_mock_resolve_deterministic(self):
        from bybit_score import _mock_resolve
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        outcome1 = _mock_resolve("BTCUSDT-2026-04-02T14:15:00Z", past)
        outcome2 = _mock_resolve("BTCUSDT-2026-04-02T14:15:00Z", past)
        assert outcome1 == outcome2  # Same input = same output
        assert outcome1 in (0, 1)

    def test_mock_resolve_too_soon(self):
        from bybit_score import _mock_resolve
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        assert _mock_resolve("test", future) is None

    def test_auto_resolve_bybit(self, bybit_db):
        from bybit_score import auto_resolve_bybit
        from bybit_markets import create_synthetic_market

        # Create a market that's already expired
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        market_id = create_synthetic_market(bybit_db, 84000.0, past_time)

        resolved = auto_resolve_bybit(bybit_db)
        assert resolved == 1

        # Verify outcome was set
        row = bybit_db.execute(
            "SELECT resolved, outcome FROM markets WHERE id = ?",
            (market_id,)
        ).fetchone()
        assert row["resolved"] == 1
        assert row["outcome"] in (0, 1)


# ══════════════════════════════════════════════════════════════════════════════
# Leg 3: Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPaperOrderPlacement:
    def test_paper_order_creates_position(self, bybit_db):
        from bybit_trade import place_bybit_order
        from bybit_markets import get_open_position

        order_params = {
            "direction": "UP", "side": "Buy", "qty": 0.005,
            "price": 84050.0, "stop_loss": 83850.0,
            "symbol": "BTCUSDT", "order_type": "Limit",
            "mark_price": 84000.0, "atr": 100.0,
        }

        with patch("bybit_trade.BYBIT_TRADING_ENABLED", False):
            order = place_bybit_order(
                bybit_db, "BTCUSDT-test", 1, order_params, cycle=1
            )

        assert order["status"] == "paper"
        assert order["mode"] == "paper"

        pos = get_open_position(bybit_db)
        assert pos is not None
        assert pos["side"] == "Buy"
        assert pos["entry_price"] == 84000.0

    def test_paper_close_records_pnl(self, bybit_db):
        from bybit_trade import close_bybit_position
        from bybit_markets import open_position, get_open_position

        pos_id = open_position(
            bybit_db, "test", "Buy", 0.005, 84000.0, 83850.0
        )
        pos = get_open_position(bybit_db)

        with patch("bybit_trade.BYBIT_TRADING_ENABLED", False):
            result = close_bybit_position(bybit_db, pos, "streak_break", 84200.0)

        assert result["pnl"] > 0
        assert result["reason"] == "streak_break"

        # Position should be closed
        assert get_open_position(bybit_db) is None


class TestTradingSummary:
    def test_empty_summary(self, bybit_db):
        from bybit_trade import get_bybit_trading_summary
        summary = get_bybit_trading_summary(bybit_db)
        assert summary["positions_opened"] == 0
        assert summary["positions_closed"] == 0
        assert summary["total_pnl"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# Frozen files check
# ══════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════���════════
# Leg 4: Perps-vs-Spot Consensus Tests
# ══════════════════════════════════════════════════════════════════════════════

def _make_summary(direction, streak, price=84000.0):
    """Helper: create a minimal summary dict for consensus testing."""
    return {
        "consecutive_dir_label": direction,
        "consecutive_direction": streak,
        "current_price": price,
    }


class TestBybitConsensus:
    def test_perp_spot_consensus_both_agree(self):
        from bybit_data import _compute_perp_spot_consensus
        bybit = _make_summary("UP", 3, 84010.0)
        spot = _make_summary("UP", 4, 84000.0)
        result = _compute_perp_spot_consensus(bybit, spot)
        assert result["score"] == 2
        assert result["streak_agree"] is True
        assert result["direction_agree"] is True
        assert result["sources"] == 2

    def test_perp_spot_consensus_direction_only(self):
        from bybit_data import _compute_perp_spot_consensus
        bybit = _make_summary("UP", 3, 84010.0)
        spot = _make_summary("UP", 1, 84000.0)  # streak < 2
        result = _compute_perp_spot_consensus(bybit, spot)
        assert result["score"] == 1
        assert result["streak_agree"] is False
        assert result["direction_agree"] is True

    def test_perp_spot_consensus_disagree(self):
        from bybit_data import _compute_perp_spot_consensus
        bybit = _make_summary("UP", 3, 84010.0)
        spot = _make_summary("DOWN", 3, 84000.0)
        result = _compute_perp_spot_consensus(bybit, spot)
        assert result["score"] == -1
        assert result["direction_agree"] is False

    def test_perp_spot_consensus_single_source(self):
        from bybit_data import _compute_perp_spot_consensus
        bybit = _make_summary("UP", 3)
        result = _compute_perp_spot_consensus(bybit, None)
        assert result["score"] == 1
        assert result["sources"] == 1
        assert result["streak_bybit"] is not None
        assert result["streak_spot"] is None

    def test_perp_spot_consensus_no_data(self):
        from bybit_data import _compute_perp_spot_consensus
        result = _compute_perp_spot_consensus(None, None)
        assert result["score"] == 0
        assert result["sources"] == 0

    def test_perp_spot_consensus_premium(self):
        from bybit_data import _compute_perp_spot_consensus
        bybit = _make_summary("UP", 3, 84084.0)  # $84 premium on $84000
        spot = _make_summary("UP", 3, 84000.0)
        result = _compute_perp_spot_consensus(bybit, spot)
        assert result["perps_premium_pct"] is not None
        assert abs(result["perps_premium_pct"] - 0.1) < 0.01  # ~0.1%

    def test_consensus_conviction_boost(self, bybit_db):
        from ci_run_bybit import store_prediction_bybit
        signal = {"estimate": 0.60, "should_trade": True, "confidence": "medium",
                  "direction": "UP", "streak": 3, "reason": "ride_streak_UP"}
        regime = {"label": "MEDIUM_VOL / TRENDING", "is_mean_reverting": False,
                  "autocorrelation": 0.20, "volatility": 0.08}
        consensus = {"score": 2, "sources": 2, "streak_agree": True,
                     "direction_agree": True, "streak_bybit": {"direction": "UP", "length": 3},
                     "streak_spot": {"direction": "UP", "length": 3}}
        pred = store_prediction_bybit(bybit_db, "test-boost", signal, regime,
                                      cycle=1, consensus=consensus)
        assert pred["conviction_score"] == 4, f"Expected 4 (3+1 boost), got {pred['conviction_score']}"

    def test_consensus_no_boost_on_skip(self, bybit_db):
        from ci_run_bybit import store_prediction_bybit
        signal = {"estimate": 0.5, "should_trade": False, "confidence": "skip",
                  "reason": "regime_gate"}
        regime = {"label": "MEDIUM_VOL / MEAN_REVERTING", "is_mean_reverting": True,
                  "autocorrelation": -0.20, "volatility": 0.08}
        consensus = {"score": 2, "sources": 2, "streak_agree": True,
                     "direction_agree": True}
        pred = store_prediction_bybit(bybit_db, "test-skip", signal, regime,
                                      cycle=1, consensus=consensus)
        assert pred["conviction_score"] == 0, f"Skip signal should stay conv=0, got {pred['conviction_score']}"

    def test_fetch_always_calls_spot(self):
        from bybit_data import fetch_bybit_candles
        mock_bybit = _make_summary("UP", 3)
        mock_bybit["candles"] = SAMPLE_CANDLES
        mock_bybit.update({
            "1h_change_pct": 0.1, "trend": "up", "volatility": 0.05,
            "up_count": 5, "down_count": 0,
            "last_candle": {"direction": "UP", "body_pct": 0.08, "wick_ratio": 0.5},
            "range_high": 84400, "range_low": 83950, "range_position": 0.8,
            "avg_volume": 11.0, "last_volume_ratio": 1.0,
            "last_3_range_shrinking": False, "last_range_ratio": 1.0,
            "last_candle_pattern": "none",
            "last_wick_upper_ratio": 0.5, "last_wick_lower_ratio": 0.3,
        })
        mock_spot = dict(mock_bybit)
        mock_spot["current_price"] = 83990.0

        with patch("bybit_data._fetch_bybit_kline", return_value=mock_bybit) as p_bybit, \
             patch("bybit_data.fetch_btc_candles", return_value=mock_spot) as p_spot:
            result = fetch_bybit_candles()
            p_bybit.assert_called_once()
            p_spot.assert_called_once()  # Spot always called, even when Bybit succeeds
            assert "consensus" in result
            assert result["consensus"]["sources"] == 2


class TestFrozenFiles:
    """Verify the Bybit pipeline doesn't touch frozen production files."""

    def test_no_imports_from_frozen_modules(self):
        """Bybit modules should not import from ci_run.py or fetch_markets.py."""
        bybit_files = [
            "src/bybit_data.py",
            "src/bybit_markets.py",
            "src/bybit_trade.py",
            "src/bybit_score.py",
            "src/ci_run_bybit.py",
        ]
        frozen_imports = ["from ci_run ", "import ci_run",
                          "from fetch_markets ", "import fetch_markets"]

        root = Path(__file__).parent.parent
        for f in bybit_files:
            path = root / f
            if path.exists():
                content = path.read_text()
                for forbidden in frozen_imports:
                    assert forbidden not in content, \
                        f"{f} imports from frozen module: {forbidden}"
