"""
llm_inference.py — Thin wrapper around DigitalOcean Serverless Inference.

Shared structured-output client used by:
  - src/v4_diagnosis.py (V4 momentum decay diagnosis)
  - src/arb_classifier.py (Arb Phase 0 divergence classifier)
  - future LLM-backed diagnostic modules

Design invariants (enforced here, not downstream):
  - All output is JSON, validated against a minimal required-keys schema.
  - One retry on malformed JSON / schema mismatch, then LLMError.
  - Low temperature (0.1) and bounded max_tokens for cost + determinism.

NO AGENT BIAS: the LLM never outputs buy/sell/conviction. It describes,
classifies, and narrates only. Callers preserve the directional-bias
boundary (see CLAUDE.md, "No agent bias" rule).

Environment:
  DO_INFERENCE_API_KEY  required; raised as LLMError at call time if missing
  DO_INFERENCE_ENDPOINT optional, defaults to https://inference.do-ai.run
  DO_INFERENCE_MODEL    optional, defaults to llama3.3-70b-instruct
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

import config

_log = logging.getLogger("llm_inference")

_DEFAULT_ENDPOINT = "https://inference.do-ai.run"
_DEFAULT_MODEL = "llama3.3-70b-instruct"
_DEFAULT_TIMEOUT = getattr(config, "API_TIMEOUT_LLM", 30)


class LLMError(Exception):
    """Raised when LLM call fails unrecoverably."""

    pass


# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS llm_calibration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    input_ref TEXT NOT NULL,
    llm_output_json TEXT NOT NULL,
    actual_outcome_json TEXT,
    matched INTEGER,
    logged_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_calibration_task
    ON llm_calibration_log(task_name);
CREATE INDEX IF NOT EXISTS idx_llm_calibration_logged_at
    ON llm_calibration_log(logged_at);
"""


def init_table(db) -> None:
    """Create llm_calibration_log table if not present. Idempotent."""
    for stmt in SCHEMA_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            db.execute(s)
    db.commit()


# ── Env helpers ────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.getenv("DO_INFERENCE_API_KEY", "").strip()
    if not key:
        raise LLMError("DO_INFERENCE_API_KEY not set")
    return key


def _get_endpoint() -> str:
    return os.getenv("DO_INFERENCE_ENDPOINT", _DEFAULT_ENDPOINT).rstrip("/")


def _get_default_model() -> str:
    return os.getenv("DO_INFERENCE_MODEL", _DEFAULT_MODEL)


# ── Validation ─────────────────────────────────────────────────────

def _validate(output: dict, schema: Optional[dict]) -> None:
    """Minimal required-keys check. Raises LLMError on mismatch."""
    if schema is None:
        return
    if not isinstance(output, dict):
        raise LLMError(f"LLM output is not a dict: {type(output).__name__}")
    required = schema.get("required", []) if isinstance(schema, dict) else []
    for k in required:
        if k not in output:
            raise LLMError(f"LLM output missing required key: {k!r}")


# ── Core call ──────────────────────────────────────────────────────

def _call_once(
    prompt: str, model: str, max_tokens: int, temperature: float
) -> dict:
    """One raw call. Returns parsed JSON dict or raises LLMError."""
    key = _get_api_key()
    url = f"{_get_endpoint()}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You produce only valid JSON objects. No prose, no "
                    "markdown, no explanation outside the JSON object. If "
                    "a field is unknown, set it to null. Keep rationale "
                    "fields under 280 characters."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        resp = requests.post(
            url, headers=headers, json=body, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
    except Exception as e:
        raise LLMError(f"LLM HTTP call failed: {e}") from e

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"Unexpected LLM response shape: {e}") from e

    if not isinstance(content, str):
        raise LLMError(f"LLM content is not a string: {type(content).__name__}")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMError(
            f"LLM returned non-JSON content: {content[:200]!r}"
        ) from e


def classify_structured(
    prompt: str,
    schema: Optional[dict] = None,
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> dict:
    """
    Call DO Serverless Inference, return validated JSON dict.

    Args:
      prompt:      user-side prompt (system role added internally).
      schema:      optional {"required": [keys...]} — fails call if absent.
      model:       override model; defaults to env DO_INFERENCE_MODEL.
      max_tokens:  cap output tokens (cost + latency discipline).
      temperature: 0.1 default for deterministic structured output.

    Retries once on malformed JSON or schema mismatch, then raises LLMError.
    """
    model = model or _get_default_model()
    last_err: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            out = _call_once(prompt, model, max_tokens, temperature)
            _validate(out, schema)
            return out
        except LLMError as e:
            _log.warning(
                "llm_inference attempt %d failed: %s", attempt, e
            )
            last_err = e
    raise LLMError(f"LLM call failed after 2 attempts: {last_err}")


# ── Calibration log ────────────────────────────────────────────────

def log_calibration(
    db,
    task_name: str,
    input_ref: str,
    llm_output: dict,
    actual_outcome: Optional[dict] = None,
    matched: Optional[bool] = None,
) -> None:
    """Record an LLM call + optional ground truth for later calibration audit."""
    db.execute(
        """INSERT INTO llm_calibration_log
            (task_name, input_ref, llm_output_json, actual_outcome_json,
             matched, logged_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
        (
            task_name,
            input_ref,
            json.dumps(llm_output),
            json.dumps(actual_outcome) if actual_outcome is not None else None,
            int(matched) if matched is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
