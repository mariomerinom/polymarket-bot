"""
pipeline_control.py — Load per-pipeline mode, bet size, and status.

Reads config/pipelines.json (checked into git, picked up by CI).

Mode values:
  "live"        — predictions run, real orders placed
  "live_canary" — live-capable canary mode; execution must apply extra gates
  "paper"       — predictions run, orders logged but not submitted
  "paused"      — pipeline exits immediately, nothing runs

Falls back to "paper" if the file is missing or the pipeline key is absent,
so a broken config never accidentally places live trades.
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "pipelines.json"

_DEFAULT = {"mode": "paper", "bet_size": None, "notes": ""}
_VALID_MODES = {"live", "live_canary", "paper", "paused"}
_VALID_TIMING_POLICIES = {
    "immediate",
    "delay_180_shadow",
    "delay_240_shadow",
    "delay_180_paper",
    "delay_240_paper",
    "delay_180_live_canary",
    "delay_240_live_canary",
}


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
            "timing_policy": _normalize_timing_policy(
                pipeline.get("timing_policy", "immediate")
            ),
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


def is_pipeline_live_canary(pipeline_name: str) -> bool:
    """True if pipeline is in explicit live-canary mode."""
    return load_pipeline_config(pipeline_name)["mode"] == "live_canary"


def get_bet_size_override(pipeline_name: str):
    """Return bet_size override or None if pipeline uses defaults."""
    return load_pipeline_config(pipeline_name)["bet_size"]


def get_timing_policy(pipeline_name: str) -> str:
    """Return BTC timing policy; defaults fail-closed to immediate."""
    return load_pipeline_config(pipeline_name).get("timing_policy", "immediate")


def _normalize_timing_policy(policy: str) -> str:
    if policy in _VALID_TIMING_POLICIES:
        return policy
    print(
        f"  [pipeline_control] WARNING: invalid timing_policy '{policy}', "
        "defaulting to 'immediate'"
    )
    return "immediate"


# ── Pipeline → DB path mapping ──────────────────────────────────────
# Mirrors the logic in tools/botsy_mcp.py so that modules needing pipeline
# discovery (e.g. consolidated_report.py) don't have to import the MCP
# package just to resolve a DB path.

_DATA_DIR = Path(__file__).parent.parent / "data"

_LEGACY_DB_NAMES = {
    "btc_5m": "predictions.db",
    "btc_15m": "predictions_15m.db",
    "eth_5m": "predictions_eth.db",
    "kalshi": "predictions_kalshi.db",
    "bybit": "predictions_bybit.db",
}

_EXCHANGES = {"bybit", "hl"}


def pipeline_to_db_path(name: str) -> Path:
    """Map a pipeline name to its DB file path. See tools/botsy_mcp.py."""
    if name in _LEGACY_DB_NAMES:
        return _DATA_DIR / _LEGACY_DB_NAMES[name]
    parts = name.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in _EXCHANGES:
        asset, exchange = parts
        return _DATA_DIR / f"predictions_{exchange}_{asset}.db"
    return _DATA_DIR / f"predictions_{name}.db"


def discover_pipelines(only_existing: bool = True) -> dict:
    """Return {pipeline_name: db_path} for all pipelines in config/pipelines.json.

    If only_existing=True (default), filter out pipelines whose DB file is
    missing on disk — matches the MCP _discover_pipelines behavior.
    """
    result = {}
    try:
        data = json.loads(CONFIG_PATH.read_text())
        for name in data.get("pipelines", {}):
            path = pipeline_to_db_path(name)
            if not only_existing or path.exists():
                result[name] = path
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return result


# ── Asset roll-up helper ─────────────────────────────────────────────

def pipeline_to_asset(name: str) -> str:
    """Map a pipeline name to its underlying asset for roll-up.

    BTC = btc_5m, btc_15m, bybit, hl, kalshi (kalshi is BTC binary markets)
    ETH = eth_5m, eth_bybit, eth_hl
    SOL = sol_bybit, sol_hl
    DOGE = doge_bybit, doge_hl
    """
    lowered = name.lower()
    if lowered.startswith("eth"):
        return "ETH"
    if lowered.startswith("sol"):
        return "SOL"
    if lowered.startswith("doge"):
        return "DOGE"
    # btc_5m, btc_15m, bybit, hl, kalshi all trade BTC
    return "BTC"
