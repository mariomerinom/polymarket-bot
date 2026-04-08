"""Shared pytest fixtures.

Disables the BTC daily-regime gate (`src/regime_gate.py`) for the entire
test session. The gate downgrades conv>=3 predictions to conv=2 when
yesterday's BTC range_zscore exceeds the threshold; tests that assert
on conviction levels would otherwise be coupled to whatever live state
exists in `data/asset_daily.db` at run time.
"""
import os

os.environ.setdefault("BTC_REGIME_GATE_DISABLED", "1")
