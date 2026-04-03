"""Tests for pipeline_control.py — per-pipeline pause/play and bet size overrides."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestLoadPipelineConfig:
    def test_loads_valid_config(self, tmp_path, monkeypatch):
        config = {
            "pipelines": {
                "btc_5m": {"enabled": True, "bet_size": 25, "notes": "prod"},
                "eth_5m": {"enabled": False, "bet_size": None, "notes": "paused"},
            }
        }
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["enabled"] is True
        assert result["bet_size"] == 25
        assert result["notes"] == "prod"

        result = pipeline_control.load_pipeline_config("eth_5m")
        assert result["enabled"] is False
        assert result["bet_size"] is None

    def test_missing_file_defaults_to_enabled(self, tmp_path, monkeypatch):
        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", tmp_path / "nope.json")

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["enabled"] is True
        assert result["bet_size"] is None

    def test_missing_key_defaults_to_enabled(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"enabled": True}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        # Key not in config → default enabled
        result = pipeline_control.load_pipeline_config("unknown_pipeline")
        assert result["enabled"] is True

    def test_corrupt_json_defaults_to_enabled(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text("NOT VALID JSON {{{")

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.load_pipeline_config("btc_5m")
        assert result["enabled"] is True

    def test_bet_size_null_returns_none(self, tmp_path, monkeypatch):
        config = {"pipelines": {"eth_5m": {"enabled": False, "bet_size": None}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.get_bet_size_override("eth_5m")
        assert result is None

    def test_bet_size_numeric_returns_value(self, tmp_path, monkeypatch):
        config = {"pipelines": {"btc_5m": {"enabled": True, "bet_size": 50}}}
        cfg_file = tmp_path / "pipelines.json"
        cfg_file.write_text(json.dumps(config))

        import pipeline_control
        monkeypatch.setattr(pipeline_control, "CONFIG_PATH", cfg_file)

        result = pipeline_control.get_bet_size_override("btc_5m")
        assert result == 50


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
        expected = {"btc_5m", "btc_15m", "eth_5m", "kalshi", "bybit"}
        actual = set(data["pipelines"].keys())
        assert expected == actual, f"Missing pipelines: {expected - actual}"

    def test_each_pipeline_has_required_keys(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        for name, cfg in data["pipelines"].items():
            assert "enabled" in cfg, f"{name} missing 'enabled'"
            assert "bet_size" in cfg, f"{name} missing 'bet_size'"
            assert isinstance(cfg["enabled"], bool), f"{name} 'enabled' must be bool"

    def test_eth_5m_is_paused(self):
        """ETH 5m was paused 2026-04-02 due to thin books and asymmetric losses."""
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "pipelines.json")
        with open(cfg_path) as f:
            data = json.load(f)
        assert data["pipelines"]["eth_5m"]["enabled"] is False


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
