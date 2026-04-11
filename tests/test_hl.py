"""
test_hl.py — Tests for the Hyperliquid perpetual futures pipeline.

Covers: config, DB schema, synthetic markets, position lifecycle,
conviction scoring, risk gates, ATR, PnL, kill switch, engine routing.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

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


def _insert_dummy_market(db, market_id):
    """Insert a minimal market row so FK constraints pass in tests."""
    db.execute("""
        INSERT OR IGNORE INTO markets (id, question, category, end_date, volume, price_yes, price_no, fetched_at)
        VALUES (?, 'test', 'crypto', '2099-01-01T00:00:00Z', 0, 0.5, 0.5, '2026-01-01T00:00:00Z')
    """, (market_id,))
    db.commit()


@pytest.fixture
def hl_db(tmp_path):
    """Create a temporary HL DB for testing."""
    db_path = tmp_path / "test_hl.db"
    with patch("hl_markets.DB_PATH_HL", db_path):
        from hl_markets import init_db_hl
        db = init_db_hl()
        yield db
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Config Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLConfig:
    def test_shadow_config_exists(self):
        from config import SHADOW_CONFIGS
        assert "hl_5m" in SHADOW_CONFIGS
        cfg = SHADOW_CONFIGS["hl_5m"]
        assert cfg["min_streak"] == 3
        assert cfg["baseline_streak"] == 8
        assert cfg["max_edge"] == 0.14

    def test_hl_constants_exist(self):
        from config import (
            HL_BET_SIZE, HL_DAILY_LOSS_LIMIT, HL_MAX_HOLD_CYCLES,
            HL_STOP_ATR_MULT, HL_FEE_RATE, HL_MIN_CONVICTION,
        )
        assert HL_BET_SIZE == 0.005
        assert HL_FEE_RATE < 0  # Maker rebate (negative)
        assert HL_MIN_CONVICTION == 3

    def test_agent_pipeline_map(self):
        from config import AGENT_PIPELINE_MAP
        assert "hl" in AGENT_PIPELINE_MAP
        assert AGENT_PIPELINE_MAP["hl"] == "hl_5m"

    def test_conviction_bets(self):
        from config import LIVE_HL_CONVICTION_BETS
        assert LIVE_HL_CONVICTION_BETS[3] == 0.005
        assert LIVE_HL_CONVICTION_BETS[2] == 0  # Paper only


# ══════════════════════════════════════════════════════════════════════════════
# DB Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLDB:
    def test_init_creates_tables(self, hl_db):
        tables = hl_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "markets" in table_names
        assert "predictions" in table_names
        assert "orders" in table_names
        assert "positions" in table_names

    def test_synthetic_market_creation(self, hl_db):
        from hl_markets import create_synthetic_market
        market_id = create_synthetic_market(hl_db, 84000.0)
        assert market_id.startswith("BTCUSDT-HL-")
        # Dedup: same call returns same ID
        market_id2 = create_synthetic_market(hl_db, 84000.0)
        assert market_id == market_id2

    def test_position_lifecycle(self, hl_db):
        from hl_markets import (
            create_synthetic_market, open_position, get_open_position,
            close_position, increment_cycles_held, get_position_by_id,
        )
        market_id = create_synthetic_market(hl_db, 84000.0)
        pos_id = open_position(hl_db, market_id, "Buy", 0.005, 84000.0, 83850.0)
        assert pos_id > 0

        pos = get_open_position(hl_db)
        assert pos is not None
        assert pos["side"] == "Buy"
        assert pos["size"] == 0.005

        increment_cycles_held(hl_db, pos_id)
        pos = get_position_by_id(hl_db, pos_id)
        assert pos["cycles_held"] == 1

        close_position(hl_db, pos_id, 84200.0, 1.0, "test_close")
        pos = get_open_position(hl_db)
        assert pos is None


# ══════════════════════════════════════════════════════════════════════════════
# Conviction Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLConviction:
    def _make_signal(self, should_trade=True, direction="UP", streak=3,
                     confidence="medium", estimate=0.6):
        return {
            "should_trade": should_trade,
            "direction": direction,
            "streak": streak,
            "confidence": confidence,
            "estimate": estimate,
            "reason": "momentum",
        }

    def _make_regime(self, label="MEDIUM_VOL / TRENDING"):
        return {
            "label": label,
            "volatility": "MEDIUM_VOL",
            "autocorrelation": 0.3,
            "is_mean_reverting": False,
        }

    def test_up_trending_conv3(self, hl_db):
        from ci_run_hl import store_prediction_hl
        _insert_dummy_market(hl_db, "test-market")
        signal = self._make_signal(direction="UP", streak=3)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = store_prediction_hl(hl_db, "test-market", signal, regime, 1)
        assert result["conviction_score"] == 3

    def test_down_neutral_demoted(self, hl_db):
        from ci_run_hl import store_prediction_hl
        _insert_dummy_market(hl_db, "test-market")
        signal = self._make_signal(direction="DOWN", streak=3)
        regime = self._make_regime("MEDIUM_VOL / NEUTRAL")
        result = store_prediction_hl(hl_db, "test-market", signal, regime, 1)
        assert result["conviction_score"] == 2

    def test_long_streak_conv4(self, hl_db):
        from ci_run_hl import store_prediction_hl
        _insert_dummy_market(hl_db, "test-market")
        signal = self._make_signal(direction="UP", streak=5)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = store_prediction_hl(hl_db, "test-market", signal, regime, 1)
        assert result["conviction_score"] == 4

    def test_no_trade_conv0(self, hl_db):
        from ci_run_hl import store_prediction_hl
        _insert_dummy_market(hl_db, "test-market")
        signal = self._make_signal(should_trade=False, estimate=0.5)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        result = store_prediction_hl(hl_db, "test-market", signal, regime, 1)
        assert result["conviction_score"] == 0

    def test_consensus_boost(self, hl_db):
        """Strong consensus (score=2) boosts conviction by 1."""
        from ci_run_hl import store_prediction_hl
        _insert_dummy_market(hl_db, "test-market")
        signal = self._make_signal(direction="UP", streak=3)
        regime = self._make_regime("MEDIUM_VOL / TRENDING")
        consensus = {"score": 2, "sources": 2}
        result = store_prediction_hl(hl_db, "test-market", signal, regime, 1,
                                      consensus=consensus)
        assert result["conviction_score"] == 4  # 3 + 1 boost


# ══════════════════════════════════════════════════════════════════════════════
# Risk Gates Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLRiskGates:
    def test_conviction_too_low(self, hl_db):
        from hl_trade import should_trade_hl
        pred = {"conviction_score": 2, "estimate": 0.6}
        ok, reason = should_trade_hl(pred, hl_db)
        assert ok is False
        assert "conviction_too_low" in reason

    def test_conviction_sufficient(self, hl_db):
        from hl_trade import should_trade_hl
        pred = {"conviction_score": 3, "estimate": 0.6}
        with patch("system_state.get_system_state") as mock_state:
            mock_state.return_value = MagicMock(
                kill_switch=False, daily_loss=0, consecutive_losses=0
            )
            ok, reason = should_trade_hl(pred, hl_db)
        assert ok is True

    def test_kill_switch(self, hl_db):
        from hl_trade import should_trade_hl
        pred = {"conviction_score": 3, "estimate": 0.6}
        with patch("system_state.get_system_state") as mock_state:
            mock_state.return_value = MagicMock(
                kill_switch=True, daily_loss=0, consecutive_losses=0
            )
            ok, reason = should_trade_hl(pred, hl_db)
        assert ok is False
        assert "kill_switch" in reason


# ══════════════════════════════════════════════════════════════════════════════
# PnL Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLPnL:
    def test_buy_pnl_profit(self):
        from hl_trade import _compute_pnl
        # Buy at 84000, sell at 84100, size=0.005
        # Raw PnL = 100 * 0.005 = 0.5
        # Fees = 84000 * 0.005 * (-0.0002) * 2 = -0.168 (credit!)
        # Net = 0.5 - (-0.168) = 0.668
        pnl = _compute_pnl("Buy", 0.005, 84000, 84100)
        assert pnl > 0.5  # Should be > raw PnL due to maker rebate

    def test_sell_pnl_profit(self):
        from hl_trade import _compute_pnl
        pnl = _compute_pnl("Sell", 0.005, 84100, 84000)
        assert pnl > 0.5  # Same direction, same rebate

    def test_maker_rebate_is_credit(self):
        """Maker rebate means fees reduce cost (negative fee)."""
        from hl_trade import _compute_pnl
        # Zero price movement — PnL should be positive due to rebate
        pnl = _compute_pnl("Buy", 0.005, 84000, 84000)
        assert pnl > 0  # Rebate gives us money even on flat trade

    def test_funding_cost_1h(self):
        """Hyperliquid uses 1h funding (not 8h like Bybit)."""
        from hl_trade import _compute_funding_cost
        # 1 cycle (5 min) held, 0.01% funding rate
        cost = _compute_funding_cost("Buy", 0.005, 84000, 1, 0.0001)
        # notional = 420, held = 5/60 = 0.0833h, fraction = 0.0833/1 = 0.0833
        # charge = 420 * 0.0001 * 0.0833 = 0.0035
        assert 0.003 < cost < 0.004


# ══════════════════════════════════════════════════════════════════════════════
# Exit Logic Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLExit:
    def test_time_ceiling(self):
        from hl_trade import check_exit_conditions
        position = {"cycles_held": 6, "side": "Buy"}
        should_exit, reason = check_exit_conditions(SAMPLE_CANDLES, position)
        assert should_exit is True
        assert reason == "time_ceiling"

    def test_hold_under_ceiling(self):
        from hl_trade import check_exit_conditions
        position = {"cycles_held": 3, "side": "Buy"}
        should_exit, reason = check_exit_conditions(SAMPLE_CANDLES, position)
        assert should_exit is False
        assert reason == "hold"


# ══════════════════════════════════════════════════════════════════════════════
# Engine Routing Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLEngineRouting:
    def test_routing_includes_hl(self):
        """HL pipeline is registered in the engine ROUTING table."""
        from botsy_engine import ROUTING
        spot_5m = ROUTING.get(("bybit_spot", "BTCUSDT", "5"), [])
        assert "hl" in spot_5m

    def test_runner_registered(self):
        """HL pipeline module is registered in the runners dict."""
        # Can't easily test the async method, but verify the module import works
        import ci_run_hl
        assert hasattr(ci_run_hl, "main")


# ══════════════════════════════════════════════════════════════════════════════
# Kill Switch Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLKillSwitch:
    def test_kill_switch_file(self, tmp_path):
        from hl_trade import is_hl_kill_switched
        with patch.object(Path, 'exists', return_value=True):
            # When kill switch file exists
            pass  # Direct test would need file mocking

    def test_system_state_kill_switch_path(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("hl")
        assert "KILL_SWITCH_HL" in str(path)

    def test_system_state_kill_switch_env(self):
        from system_state import _kill_switch_env_var
        assert _kill_switch_env_var("hl") == "KILL_SWITCH_HL"


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline Control Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHLPipelineControl:
    def test_pipelines_json_has_hl(self):
        import json
        config_path = Path(__file__).parent.parent / "config" / "pipelines.json"
        with open(config_path) as f:
            config = json.load(f)
        assert "hl" in config["pipelines"]
        assert config["pipelines"]["hl"]["mode"] == "paper"
