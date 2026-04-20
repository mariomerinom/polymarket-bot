"""
relative_regime.py — Asset-relative regime classification (shadow, Phase A).

Problem: the current regime classifier uses absolute volatility thresholds
calibrated against BTC's distribution. Applied to higher-volatility assets
like SOL and DOGE, every cycle classifies as HIGH_VOL — pipelines spend
95%+ of time gated out.

Phase A: compute the regime relative to the asset's OWN 30-day distribution
of realized_vol from asset_daily.db, log it alongside the current regime,
but DO NOT change gating behavior. After a week of shadow data we'll
compare against the absolute-regime gate and decide whether to promote.

This module is read-only — no writes, no side effects. Fire-and-forget.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from statistics import mean, stdev
from typing import Optional

_DATA_DIR = Path(__file__).parent.parent / "data"
_ASSET_DAILY_DB = _DATA_DIR / "asset_daily.db"

# Z-score buckets. Calibrated conservatively: |z| >= 1.0 is HIGH by this
# measure, paralleling intraday_range_gate threshold philosophy.
LOW_REL_Z = -0.5
HIGH_REL_Z = 1.0


def classify_relative(realized_vol_today: float, historical_vols: list) -> dict:
    """Classify today's realized_vol against historical distribution.

    Returns dict:
      label: "LOW_VOL_REL" | "MEDIUM_VOL_REL" | "HIGH_VOL_REL"
      zscore: float | None
      n_history: int
      reason: str (diagnostic)
    """
    hist = [v for v in (historical_vols or []) if v is not None and v > 0]
    if len(hist) < 5:
        return {
            "label": None,
            "zscore": None,
            "n_history": len(hist),
            "reason": f"insufficient_history ({len(hist)}<5)",
        }
    mu = mean(hist)
    try:
        sd = stdev(hist)
    except Exception:
        sd = 0.0
    if sd <= 0:
        return {
            "label": None,
            "zscore": None,
            "n_history": len(hist),
            "reason": "zero_std",
        }
    z = (realized_vol_today - mu) / sd

    if z >= HIGH_REL_Z:
        label = "HIGH_VOL_REL"
    elif z <= LOW_REL_Z:
        label = "LOW_VOL_REL"
    else:
        label = "MEDIUM_VOL_REL"

    return {
        "label": label,
        "zscore": round(z, 3),
        "n_history": len(hist),
        "reason": f"z={z:+.2f} vs mu={mu:.4f} sd={sd:.4f}",
    }


def _fetch_history(asset: str, days: int = 30,
                   db_path: Optional[Path] = None) -> list:
    """Read last `days` realized_vol values from asset_daily.db for asset.

    Excludes rows where realized_vol is NULL. Returns newest-first list.
    """
    path = db_path or _ASSET_DAILY_DB
    if not Path(path).exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT realized_vol FROM asset_daily "
            "WHERE asset = ? AND realized_vol IS NOT NULL "
            "ORDER BY date DESC LIMIT ?",
            (asset, days),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def compute_shadow_regime(candles: list, asset: str,
                          db_path: Optional[Path] = None) -> dict:
    """High-level entry point: compute relative regime for an asset's
    current candles vs its own 30-day history.

    Returns the dict from classify_relative plus an `asset` field and
    the computed realized_vol.

    Always returns a dict — never raises. Safe to call from hot path.
    """
    result = {
        "asset": asset,
        "label": None,
        "zscore": None,
        "realized_vol": None,
        "n_history": 0,
        "reason": "not_computed",
    }
    try:
        if not candles or len(candles) < 10:
            result["reason"] = f"insufficient_candles ({len(candles) if candles else 0}<10)"
            return result

        # Compute realized vol from close-to-close log returns (same convention
        # as asset_daily.realized_vol)
        import math
        closes = [float(c["close"]) for c in candles if c.get("close")]
        if len(closes) < 10:
            result["reason"] = "insufficient_close_data"
            return result
        returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
            if closes[i - 1] > 0 and closes[i] > 0
        ]
        if len(returns) < 5:
            result["reason"] = "insufficient_returns"
            return result
        sd = stdev(returns) if len(returns) >= 2 else 0.0
        # Annualize-like scaling: daily rv estimate from 5m returns
        # ~= stdev(5m returns) * sqrt(288) for per-day. Match asset_daily's
        # scaling exactly isn't critical — we just need consistency with the
        # historical distribution we compare against.
        realized_vol = sd * (288 ** 0.5)
        result["realized_vol"] = round(realized_vol, 6)

        hist = _fetch_history(asset, db_path=db_path)
        cls = classify_relative(realized_vol, hist)
        result.update(cls)
        return result
    except Exception as e:
        result["reason"] = f"error: {e}"
        return result
