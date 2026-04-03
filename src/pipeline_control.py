"""
pipeline_control.py — Load per-pipeline enabled/disabled and bet size overrides.

Reads config/pipelines.json (checked into git, picked up by CI).
Falls back to "enabled" if the file is missing or the pipeline key is absent,
so a broken config never silently kills all trading.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "pipelines.json"

_DEFAULT = {"enabled": True, "bet_size": None, "notes": ""}


def load_pipeline_config(pipeline_name: str) -> dict:
    """
    Returns {"enabled": bool, "bet_size": float|None, "notes": str}.

    Safe defaults: if file missing or key absent, pipeline is ENABLED
    (fail-open for predictions, fail-closed for new money risk).
    """
    try:
        data = json.loads(CONFIG_PATH.read_text())
        pipeline = data.get("pipelines", {}).get(pipeline_name, _DEFAULT)
        return {
            "enabled": pipeline.get("enabled", True),
            "bet_size": pipeline.get("bet_size"),
            "notes": pipeline.get("notes", ""),
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"  [pipeline_control] WARNING: Could not load config for "
              f"'{pipeline_name}': {e}. Defaulting to enabled.")
        return dict(_DEFAULT)


def get_bet_size_override(pipeline_name: str):
    """Return bet_size override or None if pipeline uses defaults."""
    return load_pipeline_config(pipeline_name)["bet_size"]
