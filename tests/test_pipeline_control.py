"""Tests for pipeline_control.py — per-pipeline mode, bet size, and status."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestLoadPipelineConfig:
    def test_loads_valid_config(self, tmp_path, monkeypatch):
        config = {
            "pipelines": {
                "btc_5m": {"mode": "live", "bet_size": 25, "notes": "prod"},
                "eth_5m": {"mode": "paused", "bet_size": None, "notes": "stopped"},
            }
        }
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["mode"] == "live"
        assert result["bet_size"] == 25
        assert result["notes"] == "prod"

        result = pipeline_control.load_pipeline_config("eth_5m")
        assert result["mode"] == "paused"
        assert result["bet_size"] is None

    def test_missing_file_defaults_to_paper(self, tmp_path, monkeypatch):
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", tmp_path / "nope.json")

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["mode"] == "paper"
        assert result["bet_size"] is None

    def test_missing_key_defaults_to_paper(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"mode": "live"}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("unknown_pipeline")
        assert result["mode"] == "paper"

    def test_corrupt_json_defaults_to_paper(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text("NOT VALID JSON {{{")

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["mode"] == "paper"

    def test_invalid_mode_defaults_to_paper(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"mode": "turbo", "bet_size": 25}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["mode"] == "paper"

    def test_live_canary_mode_is_valid_but_not_full_live(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"mode": "live_canary", "bet_size": 10}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["mode"] == "live_canary"
        assert pipeline_control.is_pipeline_live_canary("btc_5m") is True
        assert pipeline_control.is_pipeline_live("btc_5m") is False

    def test_loads_timing_policy_default_immediate(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"mode": "paper"}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        assert pipeline_control.get_timing_policy("btc_5m") == "immediate"

    def test_loads_valid_delay_timing_policy(self, tmp_path, monkeypatch):
        config = {
            "pipelines": {
                "btc_5m": {
                    "mode": "paper",
                    "timing_policy": "delay_180_paper",
                }
            }
        }
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        assert pipeline_control.get_timing_policy("btc_5m") == "delay_180_paper"

    def test_bet_size_null_returns_none(self, tmp_path, monkeypatch):
        config = {"pipelines": {"eth_5m": {"mode": "paused", "bet_size": None}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.get_bet_size_override("eth_5m")
        assert result is None

    def test_bet_size_numeric_returns_value(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"mode": "live", "bet_size": 50}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.get_bet_size_override("btc_5m")
        assert result == 50


class TestModeHelpers:
    def test_is_pipeline_paused(self, tmp_path, monkeypatch):
        config = {"pipelines": {"eth_5m": {"mode": "paused"}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        assert pipeline_control.is_pipeline_paused("eth_5m") is True
        assert pipeline_control.is_pipeline_paused("btc_5m") is False  # missing → paper, not paused

    def test_is_pipeline_live(self, tmp_path, monkeypatch):
        config = {"pipelines": {
            "btc_5m": {"mode": "live"},
            "btc_15m": {"mode": "paper"},
            "eth_5m": {"mode": "paused"},
        }}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        assert pipeline_control.is_pipeline_live("btc_5m") is True
        assert pipeline_control.is_pipeline_live("btc_15m") is False
        assert pipeline_control.is_pipeline_live("eth_5m") is False

    def test_is_pipeline_live_canary(self, tmp_path, monkeypatch):
        config = {"pipelines": {
            "btc_5m": {"mode": "live_canary"},
            "btc_15m": {"mode": "live"},
            "eth_5m": {"mode": "paper"},
        }}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        assert pipeline_control.is_pipeline_live_canary("btc_5m") is True
        assert pipeline_control.is_pipeline_live_canary("btc_15m") is False
        assert pipeline_control.is_pipeline_live_canary("eth_5m") is False


class TestRealConfig:
    """Test the actual config/pipelines.json in the repo."""

    def test_config_file_exists(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        assert os.path.exists(cfg_path), "config/pipelines.json must exist"

    def test_config_valid_json(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        assert "pipelines" in data

    def test_all_pipelines_present(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        expected = {"btc_5m", "btc_15m", "eth_5m", "kalshi", "bybit", "hl",
                    "eth_bybit", "eth_hl", "sol_bybit", "sol_hl",
                    "doge_bybit", "doge_hl"}
        actual = set(data["pipelines"].keys())
        assert expected == actual, f"Missing pipelines: {expected - actual}"

    def test_each_pipeline_has_required_keys(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        for name, cfg in data["pipelines"].items():
            assert "mode" in cfg, f"{name} missing 'mode'"
            assert cfg["mode"] in ("live", "live_canary", "paper", "paused"), \
                f"{name} has invalid mode '{cfg['mode']}'"
            assert "bet_size" in cfg, f"{name} missing 'bet_size'"

    def test_eth_5m_is_paper(self):
        """ETH 5m reverted to paper 2026-04-05 — adverse selection bleeding unfilled winners."""
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        assert data["pipelines"]["eth_5m"]["mode"] == "paper"


class TestAgentToPipeline:
    def test_btc_default(self):
        from trade import _agent_to_pipeline
        assert _agent_to_pipeline("momentum_rule") == "btc_5m"

    def test_eth_agent(self):
        from trade import _agent_to_pipeline
        assert _agent_to_pipeline("momentum_eth") == "eth_5m"

    def test_bybit_agent(self):
        from trade import _agent_to_pipeline
        assert _agent_to_pipeline("momentum_bybit") == "bybit"

    def test_kalshi_agent(self):
        from trade import _agent_to_pipeline
        assert _agent_to_pipeline("momentum_kalshi") == "kalshi"
