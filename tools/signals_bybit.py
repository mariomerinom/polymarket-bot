"""
signals_bybit.py — Alternative signal families for Bybit BTCUSDT perp.

After Phase 2 proved the streak-momentum signal is dead on this venue
(28.6% WR in ride, 29.0% in fade, both after fees), we test three
fundamentally different signal families identified by the alternative-
signals research agent:

    1. volbreakout   — volatility compression → expansion breakout
    2. vwap_mr       — z-score mean reversion from rolling VWAP
    3. xexch_leadlag — cross-exchange lead/lag (Coinbase leads Bybit)

Each signal takes a window of recent candles and optionally an
auxiliary second-venue window for (3). Returns the same shape as
`predict.momentum_signal`:

    {"should_trade": bool, "direction": "UP"|"DOWN", "reason": str}

This module has NO external dependencies on src/predict.py so the
backtest harness can test each signal in isolation.
"""

from __future__ import annotations

import math
from typing import Optional


# ── Helpers ──────────────────────────────────────────────────────────────────

def _stdev(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1)
    return math.sqrt(v)


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


# ── Signal 1: Volatility Breakout ────────────────────────────────────────────
#
# Hypothesis: after a low-vol compression, the first large-range bar
# signals the start of a directional expansion. Momentum streak signals
# fire on bar 3+ (after the move). Breakout fires on bar 1.
#
# Entry rule:
#   - realized vol of last N bars is in the bottom quintile of the last
#     4*N bars (compression state)
#   - current bar range > 1.8 × avg abs body_pct over last N bars
#     (expansion trigger)
#   - direction = sign of the breakout bar
#
# Exit (applied by the harness, not here): time ceiling or mean-revert
# back through the pre-breakout mid.

def volbreakout_signal(
    window,
    *,
    compress_lookback: int = 20,
    compress_ref: int = 80,
    expansion_mult: float = 1.8,
    compress_pctile: float = 0.25,
    **_,
):
    n = len(window)
    if n < compress_ref + 1:
        return {"should_trade": False, "direction": None,
                "reason": "insufficient_history"}

    # Rolling bar ranges as vol proxy
    ranges = [c["high"] - c["low"] for c in window]
    recent_ranges = ranges[-compress_lookback:]
    reference = ranges[-compress_ref - compress_lookback:-compress_lookback]
    if not reference:
        return {"should_trade": False, "direction": None,
                "reason": "no_reference"}

    recent_vol = _mean(recent_ranges)
    sorted_ref = sorted(reference)
    cutoff_idx = int(len(sorted_ref) * compress_pctile)
    compression_cutoff = sorted_ref[max(0, cutoff_idx - 1)]

    in_compression = recent_vol <= compression_cutoff
    if not in_compression:
        return {"should_trade": False, "direction": None,
                "reason": "no_compression"}

    # Is the current bar an expansion?
    current = window[-1]
    recent_candles = window[-compress_lookback:]
    avg_abs_body = _mean([abs(c.get("body_pct", 0.0)) for c in recent_candles])
    current_body = abs(current.get("body_pct", 0.0))
    if avg_abs_body <= 0 or current_body < expansion_mult * avg_abs_body:
        return {"should_trade": False, "direction": None,
                "reason": "no_expansion"}

    direction = "UP" if current["close"] >= current["open"] else "DOWN"
    return {
        "should_trade": True,
        "direction": direction,
        "reason": "volbreakout",
        "meta": {
            "compression_ratio": recent_vol / (_mean(reference) or 1.0),
            "expansion_mult": current_body / (avg_abs_body or 1.0),
        },
    }


# ── Signal 2: VWAP Mean Reversion ────────────────────────────────────────────
#
# Hypothesis: BTCUSDT 5m shows lag-1 autocorr = -0.0171 and VR(5) = 0.939.
# Mean reversion is real at the tape level but too weak for streak-based
# signals to monetize after fees. A z-score deviation from rolling VWAP
# gives a direct, non-streak-based entry that triggers on the tail of
# the distribution (where the reversion effect is strongest).
#
# Entry rule:
#   - compute volume-weighted average price over trailing vwap_window bars
#   - z-score = (close - vwap) / stdev(close - vwap over vwap_window)
#   - z >= +entry_z → SELL (price too high → revert down)
#   - z <= -entry_z → BUY  (price too low  → revert up)

def vwap_mr_signal(
    window,
    *,
    vwap_window: int = 48,
    entry_z: float = 2.0,
    **_,
):
    n = len(window)
    if n < vwap_window:
        return {"should_trade": False, "direction": None,
                "reason": "insufficient_history"}

    tail = window[-vwap_window:]
    # Typical price × volume
    tpvs = [
        ((c["high"] + c["low"] + c["close"]) / 3.0) * (c.get("volume") or 0.0)
        for c in tail
    ]
    vols = [c.get("volume") or 0.0 for c in tail]
    vtotal = sum(vols)
    if vtotal <= 0:
        return {"should_trade": False, "direction": None,
                "reason": "no_volume"}
    vwap = sum(tpvs) / vtotal

    closes = [c["close"] for c in tail]
    residuals = [c - vwap for c in closes]
    sd = _stdev(residuals)
    if sd <= 0:
        return {"should_trade": False, "direction": None, "reason": "flat"}

    current = window[-1]["close"]
    z = (current - vwap) / sd

    if z >= entry_z:
        return {
            "should_trade": True, "direction": "DOWN",
            "reason": f"vwap_z_high_{z:.2f}", "meta": {"z": z, "vwap": vwap, "sd": sd},
        }
    if z <= -entry_z:
        return {
            "should_trade": True, "direction": "UP",
            "reason": f"vwap_z_low_{z:.2f}", "meta": {"z": z, "vwap": vwap, "sd": sd},
        }
    return {"should_trade": False, "direction": None,
            "reason": f"z_inside_{z:.2f}"}


# ── Signal 3: Cross-exchange lead/lag ────────────────────────────────────────
#
# Hypothesis: Coinbase and Kraken US-dollar spot BTC moves arrive 1–2
# 5m bars before the Bybit perp tape reacts. If the spot venue has a
# completed streak but Bybit has not yet followed, ride Bybit in the
# spot direction — but only for the next 1–2 bars, before the reversal
# hits.
#
# This signal takes an auxiliary window of spot candles aligned to the
# same timestamps as the Bybit window.

def xexch_leadlag_signal(
    window,
    *,
    spot_window=None,
    spot_streak_min: int = 2,
    bybit_max_streak: int = 1,
    **_,
):
    if spot_window is None or len(spot_window) < spot_streak_min:
        return {"should_trade": False, "direction": None,
                "reason": "no_spot_data"}
    if len(window) < spot_streak_min:
        return {"should_trade": False, "direction": None,
                "reason": "insufficient_history"}

    # Spot streak
    spot_dirs = [
        "UP" if c["close"] >= c["open"] else "DOWN"
        for c in spot_window[-spot_streak_min:]
    ]
    if len(set(spot_dirs)) != 1:
        return {"should_trade": False, "direction": None,
                "reason": "spot_no_streak"}
    spot_direction = spot_dirs[0]

    # Bybit recent bars — must NOT already have a matching streak of
    # length > bybit_max_streak (otherwise we're just riding momentum)
    bybit_tail = window[-(bybit_max_streak + 1):]
    bybit_dirs = [
        "UP" if c["close"] >= c["open"] else "DOWN"
        for c in bybit_tail
    ]
    matching_run = 0
    for d in reversed(bybit_dirs):
        if d == spot_direction:
            matching_run += 1
        else:
            break

    if matching_run > bybit_max_streak:
        return {"should_trade": False, "direction": None,
                "reason": f"bybit_already_following_{matching_run}"}

    return {
        "should_trade": True,
        "direction": spot_direction,
        "reason": f"spot_leads_{spot_streak_min}",
        "meta": {"spot_streak": spot_streak_min, "bybit_lag": matching_run},
    }
