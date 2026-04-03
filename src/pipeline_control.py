"""
pipeline_control.py — Load per-pipeline mode, bet size, and status.

Reads config/pipelines.json (checked into git, picked up by CI).

Mode values:
  "live"   — predictions run, real orders placed
  "paper"  — predictions run, orders logged but not submitted
  "paused" — pipeline exits immediately, nothing runs

Falls back to "paper" if the file is missing or the pipeline key is absent,
so a broken config never accidentally places live trades.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "pipelines.json"

_DEFAULT = {"mode": "paper", "bet_size": None, "notes": ""}
_VALID_MODES = {"live", "paper", "paused"}


def load_pipeline_config(pipeline_name: str) -> dict:
    """
    Returns {"mode": str, "bet_size": float|None, "notes": str}.

    Safe defaults: if file missing or key absent, mode is "paper"
    (fail-closed — no accidental live trades from a broken config).
    """
    try:
        data = json.loads(CONFIG_PATH.read_text())
        pipeline = data.get("pipelines", {}).get(pipeline_name, _DEFAULT)
        mode = pipeline.get("mode", "paper")
        if mode not in _VALID_MODES:
            print(f"  [pipeline_control] WARNING: invalid mode '{mode}' "
                  f"for '{pipeline_name}', defaulting to 'paper'")
            mode = "paper"
        return {
            "mode": mode,
            "bet_size": pipeline.get("bet_size"),
            "notes": pipeline.get("notes", ""),
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"  [pipeline_control] WARNING: Could not load config for "
              f"'{pipeline_name}': {e}. Defaulting to paper.")
        return dict(_DEFAULT)


def is_pipeline_paused(pipeline_name: str) -> bool:
    """True if pipeline should not run at all."""
    return load_pipeline_config(pipeline_name)["mode"] == "paused"


def is_pipeline_live(pipeline_name: str) -> bool:
    """True if pipeline should place real orders."""
    return load_pipeline_config(pipeline_name)["mode"] == "live"


def get_bet_size_override(pipeline_name: str):
    """Return bet_size override or None if pipeline uses defaults."""
    return load_pipeline_config(pipeline_name)["bet_size"]
