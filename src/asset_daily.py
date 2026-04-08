"""
asset_daily.py — Daily OHLCV + derived metrics per asset.

Purpose: give the analysis layer a day-grain regime axis so we can answer
questions like "does our edge survive high-vol trending days vs low-vol chop?"
and "is the $1k BTC execution gap concentrated on a specific day type?".
Prerequisite for any regime-conditional sizing (Phase 3 Kelly).

This module is:
  - asset-agnostic (BTC, ETH, anything with 5m OHLCV bars)
  - pure (compute_daily is a function of a DataFrame, no I/O)
  - cheap (all metrics are pandas/numpy one-liners)
  - decoupled from the trade path — safe to ship without touching Lever B

Canonical metric groups:
  Volatility:   range_pct, true_range_pct, realized_vol, parkinson_vol
  Momentum:     body_pct, velocity, trend_label, intraday_drift, streak_len
  Liquidity:    volume_total, volume_zscore (vs 20d), vwap, vwap_close_dev,
                session_volume_skew

Usage:
    import pandas as pd
    from asset_daily import compute_daily, init_table, record

    df = pd.DataFrame(five_min_candles)   # needs: timestamp_ms, open, high, low, close, volume
    metrics = compute_daily(df, prior_close=prev_day_close)
    init_table(db)
    record(db, asset="BTC", date="2026-04-07", metrics=metrics)
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


# ── Schema ──────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS asset_daily (
    asset TEXT NOT NULL,
    date  TEXT NOT NULL,
    open  REAL, high REAL, low REAL, close REAL,
    -- volatility
    range_pct REAL,
    true_range_pct REAL,
    realized_vol REAL,
    parkinson_vol REAL,
    -- momentum / velocity
    body_pct REAL,
    velocity REAL,
    trend_label TEXT,
    intraday_drift REAL,
    -- liquidity / volume
    volume_total REAL,
    vwap REAL,
    vwap_close_dev REAL,
    session_volume_skew REAL,
    PRIMARY KEY (asset, date)
)
"""


def init_table(db) -> None:
    """Create asset_daily table if missing. Idempotent."""
    db.execute(SCHEMA_SQL)
    db.commit()


# ── Core computation ────────────────────────────────────────────────────────

# Velocity thresholds for trend_label. body_pct / realized_vol.
# Calibrated so a day that moves ~1 vol-unit in one direction is "up/down",
# 2+ vol-units is "strong". Tunable; this is the initial guess.
_VELOCITY_STRONG = 2.0
_VELOCITY_DIR = 0.5


def _classify_trend(velocity: float) -> str:
    if not np.isfinite(velocity):
        return "chop"
    if velocity >= _VELOCITY_STRONG:
        return "strong_up"
    if velocity >= _VELOCITY_DIR:
        return "up"
    if velocity <= -_VELOCITY_STRONG:
        return "strong_down"
    if velocity <= -_VELOCITY_DIR:
        return "down"
    return "chop"


def compute_daily(df: pd.DataFrame, prior_close: Optional[float] = None) -> dict:
    """Compute one day of metrics from a 5m OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume]. Assumed
            sorted ascending by time. Represents exactly one UTC day
            (typically 288 rows of 5m bars, but works with any count >= 2).
        prior_close: previous day's close for true_range_pct. None → uses
            today's open as fallback (true_range collapses to range).

    Returns:
        dict of metric name → value. Safe to pass to record().
    """
    if df is None or len(df) < 2:
        raise ValueError("compute_daily requires >= 2 rows")
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"compute_daily missing columns: {missing}")

    o = float(df["open"].iloc[0])
    c = float(df["close"].iloc[-1])
    h = float(df["high"].max())
    l = float(df["low"].min())
    vol_total = float(df["volume"].sum())

    # ── Volatility ──────────────────────────────────────────────────────
    range_pct = (h - l) / o if o > 0 else 0.0

    ref_close = float(prior_close) if prior_close else o
    if ref_close > 0:
        tr = max(h - l, abs(h - ref_close), abs(l - ref_close))
        true_range_pct = tr / ref_close
    else:
        true_range_pct = range_pct

    closes = df["close"].to_numpy(dtype=float)
    log_rets = np.diff(np.log(closes[closes > 0])) if (closes > 0).all() else np.array([])
    # Annualize from 5m bars: 288 bars/day × 365 days ≈ 105k periods/yr.
    # But for day-over-day comparison we use per-day realized (not annualized).
    # Store the raw daily realized vol = std(log_returns) * sqrt(N_bars).
    if len(log_rets) >= 2:
        realized_vol = float(np.std(log_rets, ddof=1) * math.sqrt(len(log_rets)))
    else:
        realized_vol = 0.0

    # Parkinson: range-based vol estimator. More efficient than close-to-close.
    hl_ratio = df["high"].to_numpy(dtype=float) / df["low"].to_numpy(dtype=float)
    hl_ratio = hl_ratio[hl_ratio > 0]
    if len(hl_ratio) > 0:
        log_hl_sq = np.log(hl_ratio) ** 2
        parkinson_vol = float(math.sqrt(np.mean(log_hl_sq) / (4.0 * math.log(2.0))))
        parkinson_vol *= math.sqrt(len(hl_ratio))  # scale to day-total
    else:
        parkinson_vol = 0.0

    # ── Momentum / velocity ─────────────────────────────────────────────
    body_pct = (c - o) / o if o > 0 else 0.0
    velocity = body_pct / realized_vol if realized_vol > 0 else 0.0
    trend_label = _classify_trend(velocity)

    # intraday_drift: how much of the day's move held at close vs midday.
    # Sign agreement + magnitude tells us trend persistence.
    mid_idx = len(df) // 2
    mid_close = float(df["close"].iloc[mid_idx])
    intraday_drift = (c - mid_close) / o if o > 0 else 0.0

    # ── Liquidity ───────────────────────────────────────────────────────
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol_arr = df["volume"].to_numpy(dtype=float)
    tp_arr = typical.to_numpy(dtype=float)
    if vol_arr.sum() > 0:
        vwap = float(np.sum(tp_arr * vol_arr) / vol_arr.sum())
    else:
        vwap = float(typical.mean())
    vwap_close_dev = (c - vwap) / vwap if vwap > 0 else 0.0

    half = len(df) // 2
    v1 = float(df["volume"].iloc[:half].sum())
    v2 = float(df["volume"].iloc[half:].sum())
    total = v1 + v2
    session_volume_skew = (v2 - v1) / total if total > 0 else 0.0

    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "range_pct": range_pct,
        "true_range_pct": true_range_pct,
        "realized_vol": realized_vol,
        "parkinson_vol": parkinson_vol,
        "body_pct": body_pct,
        "velocity": velocity,
        "trend_label": trend_label,
        "intraday_drift": intraday_drift,
        "volume_total": vol_total,
        "vwap": vwap,
        "vwap_close_dev": vwap_close_dev,
        "session_volume_skew": session_volume_skew,
    }


# ── Persistence ─────────────────────────────────────────────────────────────


def record(db, *, asset: str, date: str, metrics: dict) -> None:
    """Insert or replace one (asset, date) row.

    Uses INSERT OR REPLACE so re-running backfill or a same-day rerun is
    idempotent.
    """
    init_table(db)
    db.execute("""
        INSERT OR REPLACE INTO asset_daily (
            asset, date, open, high, low, close,
            range_pct, true_range_pct, realized_vol, parkinson_vol,
            body_pct, velocity, trend_label, intraday_drift,
            volume_total, vwap, vwap_close_dev, session_volume_skew
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        asset, date,
        metrics["open"], metrics["high"], metrics["low"], metrics["close"],
        metrics["range_pct"], metrics["true_range_pct"],
        metrics["realized_vol"], metrics["parkinson_vol"],
        metrics["body_pct"], metrics["velocity"],
        metrics["trend_label"], metrics["intraday_drift"],
        metrics["volume_total"], metrics["vwap"],
        metrics["vwap_close_dev"], metrics["session_volume_skew"],
    ))
    db.commit()


# ── Bybit REST fetcher (used by engine hook + backfill) ─────────────────────


def fetch_bybit_day_5m(symbol: str, date: str,
                      category: str = "linear",
                      base_url: str = "https://api.bybit.com") -> pd.DataFrame:
    """Fetch 288 5m bars for one UTC day from Bybit.

    Args:
        symbol: Bybit API symbol, e.g. "BTCUSDT".
        date: "YYYY-MM-DD" UTC.
        category: "linear" (perp) or "spot".

    Returns:
        DataFrame sorted ascending with columns [timestamp_ms, open, high,
        low, close, volume].

    Notes:
        Bybit kline returns newest first; we reverse. Limit=288 covers a
        full UTC day of 5m bars. End-time is exclusive so we pad by one day.
    """
    import requests
    from datetime import datetime, timedelta, timezone

    start_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    resp = requests.get(
        f"{base_url}/v5/market/kline",
        params={
            "category": category,
            "symbol": symbol,
            "interval": "5",
            "start": start_ms,
            "end": end_ms,
            "limit": 288,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit kline error: {data.get('retMsg')}")

    raw = data.get("result", {}).get("list", [])
    if not raw:
        return pd.DataFrame(
            columns=["timestamp_ms", "open", "high", "low", "close", "volume"]
        )
    raw.sort(key=lambda x: int(x[0]))
    return pd.DataFrame([
        {
            "timestamp_ms": int(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        }
        for r in raw
    ])
