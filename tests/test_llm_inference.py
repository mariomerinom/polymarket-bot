"""Tests for llm_inference.py — shared DO Serverless Inference client.

External HTTP is always mocked. These tests assert the contract of the client
(structured-output, schema validation, retry, calibration logging), not the
behavior of DO or any specific model.
"""

import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest


class FakeResp:
    """Matches tests/test_candle_buffer.py::FakeResp contract."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _ok_response(content_dict_or_str):
    """Build a DO/OpenAI-style chat completion response."""
    if isinstance(content_dict_or_str, dict):
        content = json.dumps(content_dict_or_str)
    else:
        content = content_dict_or_str
    return {"choices": [{"message": {"content": content}}]}


# ── classify_structured — happy + schema ─────────────────────────────────


class TestClassifyStructured:
    def test_happy_path_returns_parsed_dict(self, monkeypatch):
        import requests
        import llm_inference

        expected = {"class": "lag", "rationale": "polymarket lagged", "confidence": 0.7}
        monkeypatch.setattr(
            requests, "post", lambda *a, **kw: FakeResp(_ok_response(expected))
        )
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-test")

        out = llm_inference.classify_structured(
            "prompt", schema={"required": ["class", "rationale"]}
        )
        assert out == expected

    def test_missing_api_key_raises(self, monkeypatch):
        import llm_inference

        monkeypatch.delenv("DO_INFERENCE_API_KEY", raising=False)
        with pytest.raises(llm_inference.LLMError):
            llm_inference.classify_structured("p", schema=None)

    def test_schema_missing_required_key_retries_then_raises(self, monkeypatch):
        import requests
        import llm_inference

        call_count = [0]

        def _post(*a, **kw):
            call_count[0] += 1
            return FakeResp(_ok_response({"class": "lag"}))  # missing 'rationale'

        monkeypatch.setattr(requests, "post", _post)
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-test")

        with pytest.raises(llm_inference.LLMError):
            llm_inference.classify_structured(
                "p", schema={"required": ["class", "rationale"]}
            )
        assert call_count[0] == 2, "must retry once on schema mismatch"

    def test_malformed_json_retries_then_succeeds(self, monkeypatch):
        import requests
        import llm_inference

        call_count = [0]

        def _post(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return FakeResp(_ok_response("not-a-json"))
            return FakeResp(_ok_response({"class": "lag"}))

        monkeypatch.setattr(requests, "post", _post)
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-test")

        out = llm_inference.classify_structured("p", schema={"required": ["class"]})
        assert out == {"class": "lag"}
        assert call_count[0] == 2

    def test_malformed_json_twice_raises(self, monkeypatch):
        import requests
        import llm_inference

        monkeypatch.setattr(
            requests, "post", lambda *a, **kw: FakeResp(_ok_response("bad"))
        )
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-test")

        with pytest.raises(llm_inference.LLMError):
            llm_inference.classify_structured("p", schema=None)

    def test_no_schema_accepts_any_valid_json(self, monkeypatch):
        import requests
        import llm_inference

        monkeypatch.setattr(
            requests,
            "post",
            lambda *a, **kw: FakeResp(_ok_response({"anything": 1, "else": "ok"})),
        )
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-test")

        out = llm_inference.classify_structured("p", schema=None)
        assert out == {"anything": 1, "else": "ok"}


# ── classify_structured — request shape ─────────────────────────────────


class TestRequestShape:
    def test_sends_bearer_and_json_mode(self, monkeypatch):
        import requests
        import llm_inference

        captured = {}

        def _post(url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers", {})
            captured["json"] = kw.get("json", {})
            captured["timeout"] = kw.get("timeout")
            return FakeResp(_ok_response({"class": "x"}))

        monkeypatch.setattr(requests, "post", _post)
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-abc")

        llm_inference.classify_structured("hello world", schema=None)

        assert "chat/completions" in captured["url"]
        assert captured["headers"].get("Authorization") == "Bearer sk-abc"
        assert captured["json"]["response_format"] == {"type": "json_object"}
        assert captured["timeout"] is not None and captured["timeout"] > 0

        msgs = captured["json"]["messages"]
        assert any("hello world" in m.get("content", "") for m in msgs)

    def test_respects_endpoint_override(self, monkeypatch):
        import requests
        import llm_inference

        captured = {}

        def _post(url, **kw):
            captured["url"] = url
            return FakeResp(_ok_response({"x": 1}))

        monkeypatch.setattr(requests, "post", _post)
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-abc")
        monkeypatch.setenv("DO_INFERENCE_ENDPOINT", "https://custom.example.com")

        llm_inference.classify_structured("p", schema=None)
        assert captured["url"].startswith("https://custom.example.com")

    def test_low_temperature_by_default(self, monkeypatch):
        """Structured output should default to a deterministic temperature."""
        import requests
        import llm_inference

        captured = {}

        def _post(url, **kw):
            captured["json"] = kw.get("json", {})
            return FakeResp(_ok_response({"x": 1}))

        monkeypatch.setattr(requests, "post", _post)
        monkeypatch.setenv("DO_INFERENCE_API_KEY", "sk-abc")

        llm_inference.classify_structured("p", schema=None)
        assert captured["json"]["temperature"] <= 0.3


# ── calibration log ─────────────────────────────────


class TestCalibrationLog:
    def test_init_creates_table_with_required_columns(self, tmp_path):
        import llm_inference

        db = sqlite3.connect(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        cols = {
            r[1] for r in db.execute("PRAGMA table_info(llm_calibration_log)").fetchall()
        }
        assert {
            "task_name",
            "input_ref",
            "llm_output_json",
            "actual_outcome_json",
            "matched",
            "logged_at",
        }.issubset(cols)

    def test_init_table_is_idempotent(self, tmp_path):
        import llm_inference

        db = sqlite3.connect(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        llm_inference.init_table(db)  # should not raise
        cols = db.execute("PRAGMA table_info(llm_calibration_log)").fetchall()
        assert len(cols) > 0

    def test_log_calibration_stores_output_as_json(self, tmp_path):
        import llm_inference

        db = sqlite3.connect(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        llm_inference.log_calibration(
            db,
            task_name="arb_classifier",
            input_ref="divergence_id:42",
            llm_output={"class": "lag", "confidence": 0.7},
        )

        rows = db.execute(
            "SELECT task_name, input_ref, llm_output_json, actual_outcome_json, matched "
            "FROM llm_calibration_log"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "arb_classifier"
        assert rows[0][1] == "divergence_id:42"
        assert json.loads(rows[0][2]) == {"class": "lag", "confidence": 0.7}
        assert rows[0][3] is None
        assert rows[0][4] is None

    def test_log_calibration_records_matched_bool(self, tmp_path):
        import llm_inference

        db = sqlite3.connect(str(tmp_path / "t.db"))
        llm_inference.init_table(db)
        llm_inference.log_calibration(
            db,
            task_name="t",
            input_ref="r",
            llm_output={"c": "a"},
            actual_outcome={"c": "a"},
            matched=True,
        )
        row = db.execute("SELECT matched FROM llm_calibration_log").fetchone()
        assert row[0] == 1
