"""
test_perp_pipeline.py — Tests for the generic multi-symbol perp pipeline.

Tests:
  - TestPerpDB: init, synthetic market creation with different symbols
  - TestPerpConviction: UP trending, DOWN neutral demotion, HIGH_VOL gate
  - TestPerpConfig: all shadow configs exist, all pipeline map entries exist
  - TestEngineRouting: all new pipelines in ROUTING, all in runners
  - TestPipelineControl: all pipelines in pipelines.json
  - TestKillSwitchRouting: eth_bybit->KILL_SWITCH_BYBIT, sol_hl->KILL_SWITCH_HL
  - TestSystemStatePerp: _is_perp recognizes all perp pipelines
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

# Ensure src is importable
SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC))


# ── TestPerpDB ──────────────────────────────────────────────────────────────

class TestPerpDB:
    """Test generic DB initialization and market creation."""

    def test_init_creates_tables(self, tmp_path):
        """init_db_perp creates all 4 tables for any symbol/exchange."""
        import perp_markets
        original = perp_markets.DATA_DIR
        perp_markets.DATA_DIR = tmp_path
        try:
            db = perp_markets.init_db_perp("ETHUSDT", "bybit")
            tables = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "markets" in tables
            assert "predictions" in tables
            assert "orders" in tables
            assert "positions" in tables
            db.close()
        finally:
            perp_markets.DATA_DIR = original

    def test_db_path_format(self):
        """DB path follows data/predictions_{exchange}_{asset}.db pattern."""
        from perp_markets import get_db_path
        assert get_db_path("ETHUSDT", "bybit").name == "predictions_bybit_eth.db"
        assert get_db_path("SOLUSDT", "hl").name == "predictions_hl_sol.db"
        assert get_db_path("DOGEUSDT", "bybit").name == "predictions_bybit_doge.db"

    def test_synthetic_market_eth_bybit(self, tmp_path):
        """Synthetic market ID format: ETHUSDT-bybit-{timestamp}."""
        import perp_markets
        original = perp_markets.DATA_DIR
        perp_markets.DATA_DIR = tmp_path
        try:
            db = perp_markets.init_db_perp("ETHUSDT", "bybit")
            t = datetime(2026, 4, 11, 14, 15, 0, tzinfo=timezone.utc)
            mid = perp_markets.create_synthetic_market(
                db, "ETHUSDT", "bybit", 3600.0, cycle_time=t
            )
            assert mid == "ETHUSDT-bybit-2026-04-11T14:15:00Z"
            # Question mentions ETH
            row = db.execute("SELECT question FROM markets WHERE id = ?",
                             (mid,)).fetchone()
            assert "ETH" in row[0]
            db.close()
        finally:
            perp_markets.DATA_DIR = original

    def test_synthetic_market_sol_hl(self, tmp_path):
        """Synthetic market ID for SOL on Hyperliquid."""
        import perp_markets
        original = perp_markets.DATA_DIR
        perp_markets.DATA_DIR = tmp_path
        try:
            db = perp_markets.init_db_perp("SOLUSDT", "hl")
            t = datetime(2026, 4, 11, 10, 0, 0, tzinfo=timezone.utc)
            mid = perp_markets.create_synthetic_market(
                db, "SOLUSDT", "hl", 150.0, cycle_time=t
            )
            assert mid == "SOLUSDT-hl-2026-04-11T10:00:00Z"
            db.close()
        finally:
            perp_markets.DATA_DIR = original

    def test_synthetic_market_dedup(self, tmp_path):
        """Creating same market twice returns same ID without error."""
        import perp_markets
        original = perp_markets.DATA_DIR
        perp_markets.DATA_DIR = tmp_path
        try:
            db = perp_markets.init_db_perp("DOGEUSDT", "bybit")
            t = datetime(2026, 4, 11, 12, 0, 0, tzinfo=timezone.utc)
            mid1 = perp_markets.create_synthetic_market(
                db, "DOGEUSDT", "bybit", 0.17, cycle_time=t
            )
            mid2 = perp_markets.create_synthetic_market(
                db, "DOGEUSDT", "bybit", 0.18, cycle_time=t
            )
            assert mid1 == mid2
            count = db.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
            assert count == 1
            db.close()
        finally:
            perp_markets.DATA_DIR = original

    def test_position_lifecycle(self, tmp_path):
        """Open -> increment -> close lifecycle works."""
        import perp_markets
        original = perp_markets.DATA_DIR
        perp_markets.DATA_DIR = tmp_path
        try:
            db = perp_markets.init_db_perp("ETHUSDT", "bybit")
            mid = perp_markets.create_synthetic_market(
                db, "ETHUSDT", "bybit", 3600.0
            )
            pos_id = perp_markets.open_position(
                db, mid, "Buy", 0.05, 3600.0, 3550.0
            )
            pos = perp_markets.get_open_position(db)
            assert pos is not None
            assert pos["side"] == "Buy"

            perp_markets.increment_cycles_held(db, pos_id)
            pos = perp_markets.get_position_by_id(db, pos_id)
            assert pos["cycles_held"] == 1

            perp_markets.close_position(db, pos_id, 3650.0, 2.5, "time_ceiling")
            pos = perp_markets.get_open_position(db)
            assert pos is None
            db.close()
        finally:
            perp_markets.DATA_DIR = original


# ── TestPerpConviction ──────────────────────────────────────────────────────

class TestPerpConviction:
    """Test conviction scoring logic."""

    def test_up_trending_conv3(self):
        """UP signal in trending regime gets conviction 3."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": True, "direction": "UP", "streak": 3}
        regime = {"label": "MEDIUM_VOL / TRENDING"}
        assert compute_conviction(signal, regime) == 3

    def test_down_neutral_demotion(self):
        """DOWN+NEUTRAL is demoted to conviction 2 (no trade)."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": True, "direction": "DOWN", "streak": 3}
        regime = {"label": "MEDIUM_VOL / NEUTRAL"}
        assert compute_conviction(signal, regime) == 2

    def test_high_vol_not_demoted(self):
        """DOWN+HIGH_VOL/NEUTRAL is NOT demoted (HIGH_VOL exception)."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": True, "direction": "DOWN", "streak": 3}
        regime = {"label": "HIGH_VOL / NEUTRAL"}
        # HIGH_VOL in label prevents demotion
        assert compute_conviction(signal, regime) == 3

    def test_streak_5_gets_conv4(self):
        """Streak >= 5 gets conviction 4."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": True, "direction": "UP", "streak": 5}
        regime = {"label": "MEDIUM_VOL / TRENDING"}
        assert compute_conviction(signal, regime) == 4

    def test_consensus_boost(self):
        """Consensus score 2 boosts conviction from 3 to 4."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": True, "direction": "UP", "streak": 3}
        regime = {"label": "MEDIUM_VOL / TRENDING"}
        consensus = {"score": 2}
        assert compute_conviction(signal, regime, consensus) == 4

    def test_no_trade_gets_conv0(self):
        """Signal with should_trade=False gets conviction 0."""
        from ci_run_perp import compute_conviction
        signal = {"should_trade": False}
        regime = {"label": "LOW_VOL / NEUTRAL"}
        assert compute_conviction(signal, regime) == 0


# ── TestPerpConfig ──────────────────────────────────────────────────────────

class TestPerpConfig:
    """Test config entries exist for all new pipelines."""

    EXPECTED_SHADOW_KEYS = [
        "eth_bybit_5m", "eth_hl_5m",
        "sol_bybit_5m", "sol_hl_5m",
        "doge_bybit_5m", "doge_hl_5m",
    ]

    EXPECTED_PIPELINE_MAP_KEYS = [
        "eth_bybit", "eth_hl",
        "sol_bybit", "sol_hl",
        "doge_bybit", "doge_hl",
    ]

    def test_shadow_configs_exist(self):
        """All new perp shadow configs are in SHADOW_CONFIGS."""
        from config import SHADOW_CONFIGS
        for key in self.EXPECTED_SHADOW_KEYS:
            assert key in SHADOW_CONFIGS, f"Missing shadow config: {key}"

    def test_shadow_configs_have_required_fields(self):
        """Shadow configs have all required fields."""
        from config import SHADOW_CONFIGS
        required = {"min_streak", "baseline_streak", "magnitude_multiplier",
                     "max_edge", "high_confidence_threshold", "conv_thresholds"}
        for key in self.EXPECTED_SHADOW_KEYS:
            cfg = SHADOW_CONFIGS[key]
            for field in required:
                assert field in cfg, f"{key} missing field: {field}"

    def test_agent_pipeline_map(self):
        """All new pipelines are in AGENT_PIPELINE_MAP."""
        from config import AGENT_PIPELINE_MAP
        for key in self.EXPECTED_PIPELINE_MAP_KEYS:
            assert key in AGENT_PIPELINE_MAP, f"Missing in AGENT_PIPELINE_MAP: {key}"

    def test_perp_bet_sizes(self):
        """Per-pair bet sizes are defined."""
        from config import PERP_ETH_BET_SIZE, PERP_SOL_BET_SIZE, PERP_DOGE_BET_SIZE
        assert PERP_ETH_BET_SIZE > 0
        assert PERP_SOL_BET_SIZE > 0
        assert PERP_DOGE_BET_SIZE > 0

    def test_all_pipeline_configs_exist(self):
        """ci_run_perp.ALL_CONFIGS has all 6 pipeline configs."""
        from ci_run_perp import ALL_CONFIGS
        expected = {"eth_bybit", "eth_hl", "sol_bybit", "sol_hl",
                    "doge_bybit", "doge_hl"}
        assert set(ALL_CONFIGS.keys()) == expected


# ── TestEngineRouting ───────────────────────────────────────────────────────

class TestEngineRouting:
    """Test engine ROUTING table and runners dict."""

    def test_routing_has_new_entries(self):
        """ROUTING table has entries for ETH, SOL, DOGE spot candles."""
        from botsy_engine import ROUTING
        # ETH perps piggybacking on existing ETH spot feed
        eth_route = ROUTING[("bybit_spot", "ETHUSDT", "5")]
        assert "eth_bybit" in eth_route
        assert "eth_hl" in eth_route

        # SOL new feed
        sol_route = ROUTING[("bybit_spot", "SOLUSDT", "5")]
        assert "sol_bybit" in sol_route
        assert "sol_hl" in sol_route

        # DOGE new feed
        doge_route = ROUTING[("bybit_spot", "DOGEUSDT", "5")]
        assert "doge_bybit" in doge_route
        assert "doge_hl" in doge_route

    def test_existing_routes_preserved(self):
        """Existing BTC/ETH routes are not broken."""
        from botsy_engine import ROUTING
        assert "btc_5m" in ROUTING[("bybit_spot", "BTCUSDT", "5")]
        assert "kalshi" in ROUTING[("bybit_spot", "BTCUSDT", "5")]
        assert "eth_5m" in ROUTING[("bybit_spot", "ETHUSDT", "5")]
        assert "bybit" in ROUTING[("bybit_linear", "BTCUSDT", "5")]


# ── TestPipelineControl ─────────────────────────────────────────────────────

class TestPipelineControl:
    """Test all new pipelines are in pipelines.json."""

    EXPECTED = ["eth_bybit", "eth_hl", "sol_bybit", "sol_hl",
                "doge_bybit", "doge_hl"]

    def test_all_in_pipelines_json(self):
        """All 6 new pipelines are in config/pipelines.json and non-live."""
        config_path = Path(__file__).parent.parent / "config" / "pipelines.json"
        data = json.loads(config_path.read_text())
        pipelines = data.get("pipelines", {})
        for name in self.EXPECTED:
            assert name in pipelines, f"Missing in pipelines.json: {name}"
            assert pipelines[name]["mode"] in ("paper", "paused"), \
                f"{name} should be paper or paused"
        assert pipelines["eth_bybit"]["mode"] == "paused"
        assert pipelines["eth_hl"]["mode"] == "paused"

    def test_pipeline_control_loads(self):
        """pipeline_control.load_pipeline_config returns non-live for new pipelines."""
        from pipeline_control import load_pipeline_config
        for name in self.EXPECTED:
            cfg = load_pipeline_config(name)
            assert cfg["mode"] in ("paper", "paused")


# ── TestKillSwitchRouting ───────────────────────────────────────────────────

class TestKillSwitchRouting:
    """Test kill switch file routing for new perp pipelines."""

    def test_eth_bybit_routes_to_bybit_switch(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("eth_bybit")
        assert path.name == "KILL_SWITCH_BYBIT"

    def test_sol_hl_routes_to_hl_switch(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("sol_hl")
        assert path.name == "KILL_SWITCH_HL"

    def test_doge_bybit_routes_to_bybit_switch(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("doge_bybit")
        assert path.name == "KILL_SWITCH_BYBIT"

    def test_doge_hl_routes_to_hl_switch(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("doge_hl")
        assert path.name == "KILL_SWITCH_HL"

    def test_existing_bybit_preserved(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("bybit")
        assert path.name == "KILL_SWITCH_BYBIT"

    def test_existing_hl_preserved(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("hl")
        assert path.name == "KILL_SWITCH_HL"

    def test_btc_5m_routes_to_default(self):
        from system_state import _kill_switch_file_path
        path = _kill_switch_file_path("btc_5m")
        assert path.name == "KILL_SWITCH"

    def test_env_var_routing(self):
        from system_state import _kill_switch_env_var
        assert _kill_switch_env_var("eth_bybit") == "KILL_SWITCH_BYBIT"
        assert _kill_switch_env_var("sol_hl") == "KILL_SWITCH_HL"
        assert _kill_switch_env_var("btc_5m") == "KILL_SWITCH"


# ── TestSystemStatePerp ────────────────────────────────────────────────────

class TestSystemStatePerp:
    """Test _is_perp recognizes all perp pipelines."""

    def test_recognizes_new_perp_pipelines(self):
        from system_state import _is_perp
        for name in ["eth_bybit", "eth_hl", "sol_bybit", "sol_hl",
                      "doge_bybit", "doge_hl"]:
            assert _is_perp(name), f"_is_perp should recognize {name}"

    def test_recognizes_existing_perp_pipelines(self):
        from system_state import _is_perp
        assert _is_perp("bybit")
        assert _is_perp("hl")

    def test_polymarket_is_not_perp(self):
        from system_state import _is_perp
        assert not _is_perp("btc_5m")
        assert not _is_perp("eth_5m")
        assert not _is_perp("kalshi")

    def test_backward_compat_alias(self):
        """_is_bybit is an alias for _is_perp."""
        from system_state import _is_bybit, _is_perp
        assert _is_bybit is _is_perp


# ── TestPnLComputation ──────────────────────────────────────────────────────

class TestPnLComputation:
    """Test PnL and funding cost computation."""

    def test_long_profit(self):
        from ci_run_perp import compute_pnl
        # Long 0.05 ETH, entry 3600, exit 3650, 0.02% fee
        pnl = compute_pnl("Buy", 0.05, 3600.0, 3650.0, 0.0002)
        # Raw: (3650-3600) * 0.05 = $2.50
        # Fees: 3600*0.05*0.0002*2 = $0.072
        assert pnl == pytest.approx(2.50 - 0.072, abs=0.001)

    def test_short_profit(self):
        from ci_run_perp import compute_pnl
        pnl = compute_pnl("Sell", 1.0, 150.0, 145.0, 0.0002)
        # Raw: (150-145) * 1.0 = $5.00
        # Fees: 150*1.0*0.0002*2 = $0.06
        assert pnl == pytest.approx(5.0 - 0.06, abs=0.001)

    def test_hl_maker_rebate(self):
        from ci_run_perp import compute_pnl
        # HL fee is negative (rebate)
        pnl = compute_pnl("Buy", 0.05, 3600.0, 3650.0, -0.0002)
        # Fees = 3600*0.05*(-0.0002)*2 = -$0.072 (credit, subtracted = adds)
        assert pnl > 2.50  # Better than no-fee

    def test_funding_cost(self):
        from ci_run_perp import compute_funding_cost
        # Long 0.05 ETH at 3600, 2 cycles, 0.01% funding, 8h interval
        cost = compute_funding_cost("Buy", 0.05, 3600.0, 2, 0.0001,
                                     funding_interval_hours=8)
        # notional=180, held=10min=0.1667h, fraction=0.1667/8=0.02083
        # charge=180*0.0001*0.02083 = 0.000375
        assert cost == pytest.approx(0.000375, abs=0.0001)
