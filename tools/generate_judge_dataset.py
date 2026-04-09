"""
generate_judge_dataset.py — Build the labeled training dataset for the ML Judge.

Walks historical 5m candles (both Bybit perp and spot), replaying the exact
production momentum_signal() + compute_regime_from_candles() logic at each bar.
At every signal-fire point, extracts a feature vector and labels it with the
next candle's directional outcome.

The Judge is a meta-classifier: it predicts P(momentum_signal_is_correct)
given the contextual substrate the rules ignore (TA indicators, daily regime,
funding, OI, temporal patterns).

Usage:
    python3 tools/generate_judge_dataset.py
    python3 tools/generate_judge_dataset.py --perp data/bybit_5m_18mo.csv --spot data/spot_5m_18mo.csv
    python3 tools/generate_judge_dataset.py --output data/judge_dataset.csv

Guardrails:
  - Label uses ONLY candles[i+1] (no lookahead)
  - Every row includes feature_ts and label_ts for audit
  - Built-in assertion: label_ts == feature_ts + 300_000 (5 minutes)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from predict import compute_regime_from_candles, momentum_signal
from shadow_conviction_scorer import strength_signal
from pure_ta import compute_ta

ROOT = Path(__file__).resolve().parent.parent
DAILY_DB = ROOT / "data" / "asset_daily.db"


# ── CSV loading (reuse backtest_bybit.py pattern) ──────────────────────────

def load_csv(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open() as f:
        for row in csv.DictReader(f):
            out.append({
                "ts": int(row["ts"]),
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "direction": row["direction"],
                "body_pct": float(row["body_pct"]),
                "wick_ratio": float(row["wick_ratio"]),
            })
    return out


def load_funding(path: Path) -> List[dict]:
    """Load funding rate CSV sorted by timestamp.
    Handles both 6mo format (col='rate') and 18mo format (col='funding_rate').
    """
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for row in csv.DictReader(f):
            rate = float(row.get("rate") or row.get("funding_rate", 0))
            out.append({"ts": int(row["ts"]), "rate": rate})
    return sorted(out, key=lambda r: r["ts"])


def load_oi(path: Path) -> List[dict]:
    """Load open interest CSV sorted by timestamp.
    Handles both 6mo format (col='oi') and 18mo format (col='open_interest').
    """
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for row in csv.DictReader(f):
            oi_val = float(row.get("oi") or row.get("open_interest", 0))
            out.append({"ts": int(row["ts"]), "oi": oi_val})
    return sorted(out, key=lambda r: r["ts"])


# ── Daily regime join ──────────────────────────────────────────────────────

def load_daily_regime(db_path: Path) -> Dict[str, dict]:
    """Load all BTC asset_daily rows as {date_str: row_dict}."""
    if not db_path.exists():
        return {}
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT * FROM asset_daily WHERE asset='BTC' ORDER BY date"
    ).fetchall()
    db.close()
    return {r["date"]: dict(r) for r in rows}


def get_prior_day_regime(daily: Dict[str, dict], ts_ms: int) -> dict:
    """Get the prior UTC day's regime metrics. Returns dict with NaN for missing."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    prior = (dt.date() - timedelta(days=1)).isoformat()
    row = daily.get(prior)
    if row is None:
        return {
            "daily_range_pct": float("nan"),
            "daily_realized_vol": float("nan"),
            "daily_velocity": float("nan"),
            "daily_body_pct": float("nan"),
            "daily_range_zscore": float("nan"),
            "daily_velocity_zscore": float("nan"),
            "daily_vwap_close_dev": float("nan"),
            "daily_session_volume_skew": float("nan"),
            "daily_trend_strong_up": 0,
            "daily_trend_up": 0,
            "daily_trend_chop": 0,
            "daily_trend_down": 0,
            "daily_trend_strong_down": 0,
        }
    trend = row.get("trend_label", "chop")
    return {
        "daily_range_pct": row.get("range_pct") or float("nan"),
        "daily_realized_vol": row.get("realized_vol") or float("nan"),
        "daily_velocity": row.get("velocity") or float("nan"),
        "daily_body_pct": row.get("body_pct") or float("nan"),
        "daily_range_zscore": row.get("range_zscore") if row.get("range_zscore") is not None else float("nan"),
        "daily_velocity_zscore": row.get("velocity_zscore") if row.get("velocity_zscore") is not None else float("nan"),
        "daily_vwap_close_dev": row.get("vwap_close_dev") or float("nan"),
        "daily_session_volume_skew": row.get("session_volume_skew") or float("nan"),
        "daily_trend_strong_up": 1 if trend == "strong_up" else 0,
        "daily_trend_up": 1 if trend == "up" else 0,
        "daily_trend_chop": 1 if trend == "chop" else 0,
        "daily_trend_down": 1 if trend == "down" else 0,
        "daily_trend_strong_down": 1 if trend == "strong_down" else 0,
    }


# ── Funding / OI alignment ────────────────────────────────────────────────

def align_latest(sorted_rows: List[dict], ts_ms: int, value_key: str) -> float:
    """Binary search for most recent row <= ts_ms."""
    if not sorted_rows:
        return float("nan")
    lo, hi = 0, len(sorted_rows) - 1
    result = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_rows[mid]["ts"] <= ts_ms:
            result = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if result is None:
        return float("nan")
    return sorted_rows[result][value_key]


def compute_oi_change_1h(oi_rows: List[dict], ts_ms: int) -> float:
    """OI delta over prior 12 bars (1 hour)."""
    current = align_latest(oi_rows, ts_ms, "oi")
    past = align_latest(oi_rows, ts_ms - 3_600_000, "oi")
    if math.isnan(current) or math.isnan(past) or past == 0:
        return float("nan")
    return (current - past) / past


# ── Feature extraction ──────────────────────────────────────────────────────

def extract_features(
    window: List[dict],
    all_candles_to_i: List[dict],
    regime: dict,
    signal: dict,
    ta_lookback: int = 30,
    source: int = 0,
    daily: Optional[Dict[str, dict]] = None,
    funding: Optional[List[dict]] = None,
    oi: Optional[List[dict]] = None,
) -> dict:
    """Extract the full feature vector for one signal-fire point.

    All data is from candles[0:i+1] — no lookahead.
    """
    features: dict = {}

    # 1. Regime features
    features["autocorrelation"] = regime.get("autocorrelation", 0.0)
    features["volatility"] = regime.get("volatility", 0.0)
    features["is_mean_reverting"] = 1 if regime.get("is_mean_reverting") else 0

    # 2. Strength signal features
    signed_streak = signal.get("streak", 0)
    try:
        ss = strength_signal(window, signed_streak, "btc_5m", regime)
    except Exception:
        ss = None
    if ss:
        features["strength"] = ss.get("strength", 0.0)
        features["length_strength"] = ss.get("length_strength", 0.0)
        features["magnitude_strength"] = ss.get("magnitude_strength", 0.0)
        features["net_return_pct"] = ss.get("net_return_pct", 0.0)
        features["realized_vol_streak"] = ss.get("realized_vol", 0.0)
    else:
        features["strength"] = 0.0
        features["length_strength"] = 0.0
        features["magnitude_strength"] = 0.0
        features["net_return_pct"] = 0.0
        features["realized_vol_streak"] = 0.0

    # 3. TA indicators (from pure_ta, no pandas-ta needed)
    # Use recent candles for TA computation (at least 30 bars)
    recent = all_candles_to_i[-ta_lookback:] if len(all_candles_to_i) >= ta_lookback else all_candles_to_i
    closes = [c["close"] for c in recent]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    volumes = [c["volume"] for c in recent]

    ta = compute_ta(closes, highs, lows, volumes)
    if ta:
        features["rsi_14"] = ta.get("rsi_14", float("nan"))
        features["rsi_7"] = ta.get("rsi_7", float("nan"))
        features["bb_bandwidth"] = ta.get("bb_bandwidth", float("nan"))
        features["bb_pctb"] = ta.get("bb_pctb", float("nan"))
        features["z_score"] = ta.get("z_score", float("nan"))
        features["rvol"] = ta.get("rvol", float("nan"))
        features["obv_slope"] = ta.get("obv_slope", float("nan"))
        features["ema_ratio"] = ta.get("ema_ratio", float("nan"))
        features["stoch_k"] = ta.get("stoch_k", float("nan"))
        features["stoch_d"] = ta.get("stoch_d", float("nan"))
    else:
        for k in ["rsi_14", "rsi_7", "bb_bandwidth", "bb_pctb", "z_score",
                   "rvol", "obv_slope", "ema_ratio", "stoch_k", "stoch_d"]:
            features[k] = float("nan")

    # 4. Daily regime (prior-day join)
    ts_ms = all_candles_to_i[-1]["ts"]
    if daily:
        features.update(get_prior_day_regime(daily, ts_ms))

    # 5. Funding rate
    if funding:
        features["funding_rate"] = align_latest(funding, ts_ms, "rate")
    else:
        features["funding_rate"] = float("nan")

    # 6. OI change
    if oi:
        features["oi_change_1h"] = compute_oi_change_1h(oi, ts_ms)
    else:
        features["oi_change_1h"] = float("nan")

    # 7. Temporal (sin/cos encoded)
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    features["hour_sin"] = round(math.sin(2 * math.pi * dt.hour / 24), 6)
    features["hour_cos"] = round(math.cos(2 * math.pi * dt.hour / 24), 6)
    features["dow_sin"] = round(math.sin(2 * math.pi * dt.weekday() / 7), 6)
    features["dow_cos"] = round(math.cos(2 * math.pi * dt.weekday() / 7), 6)

    # 8. Source venue
    features["source"] = source

    # 9. Signal metadata (for audit, not model features)
    features["direction"] = signal.get("direction", "")
    features["streak"] = abs(signed_streak)

    return features


# ── Main walk loop ─────────────────────────────────────────────────────────

def generate_dataset(
    candles: List[dict],
    source_label: int,
    window: int,
    daily: Dict[str, dict],
    funding: List[dict],
    oi: List[dict],
) -> List[dict]:
    """Walk candles, extract features + label at every signal fire."""
    rows = []
    for i in range(window, len(candles) - 1):
        win = candles[i - window + 1 : i + 1]
        regime = compute_regime_from_candles(win)
        signal = momentum_signal(win, min_streak=3, config_key="btc_5m")

        if not signal.get("should_trade"):
            continue
        if regime.get("is_mean_reverting"):
            continue

        # Extract features (no lookahead — only candles[0:i+1])
        features = extract_features(
            window=win,
            all_candles_to_i=candles[:i + 1],
            regime=regime,
            signal=signal,
            source=source_label,
            daily=daily,
            funding=funding,
            oi=oi,
        )

        # Label: did the NEXT candle go in the predicted direction?
        next_dir = candles[i + 1]["direction"]
        predicted_dir = signal["direction"]
        label = 1 if next_dir == predicted_dir else 0

        features["label"] = label
        features["feature_ts"] = candles[i]["ts"]
        features["label_ts"] = candles[i + 1]["ts"]

        rows.append(features)

    return rows


def validate_dataset(rows: List[dict]) -> None:
    """Guardrail: verify no lookahead bias."""
    errors = 0
    for i, r in enumerate(rows):
        delta = r["label_ts"] - r["feature_ts"]
        if delta != 300_000:  # 5 minutes in ms
            print(f"  WARN row {i}: label_ts - feature_ts = {delta}ms (expected 300000)")
            errors += 1
    if errors:
        print(f"  ⚠️ {errors} rows with unexpected timestamp gaps")
    else:
        print(f"  ✅ All {len(rows)} rows pass lookahead check (label_ts == feature_ts + 300s)")


def main():
    parser = argparse.ArgumentParser(description="Generate Judge training dataset")
    parser.add_argument("--perp", default="data/bybit_5m_18mo.csv",
                        help="Perp candle CSV")
    parser.add_argument("--spot", default="data/spot_5m_18mo.csv",
                        help="Spot candle CSV")
    parser.add_argument("--funding", default="data/funding_18mo.csv",
                        help="Funding rate CSV")
    parser.add_argument("--oi", default="data/oi_5m_18mo.csv",
                        help="Open interest CSV")
    parser.add_argument("--output", default="data/judge_dataset.csv",
                        help="Output CSV path")
    parser.add_argument("--window", type=int, default=24,
                        help="Candle window for regime computation (default: 24)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    # Load supplementary data
    print("Loading daily regime data...")
    daily = load_daily_regime(DAILY_DB)
    print(f"  {len(daily)} daily rows")

    print("Loading funding rates...")
    funding = load_funding(root / args.funding)
    print(f"  {len(funding)} funding rows")

    print("Loading open interest...")
    oi = load_oi(root / args.oi)
    print(f"  {len(oi)} OI rows")

    all_rows = []

    # Walk perp candles
    perp_path = root / args.perp
    if perp_path.exists():
        print(f"\nLoading perp candles from {args.perp}...")
        perp_candles = load_csv(perp_path)
        print(f"  {len(perp_candles)} candles ({perp_candles[0]['time']} → {perp_candles[-1]['time']})")
        print("  Walking perp tape...")
        perp_rows = generate_dataset(perp_candles, source_label=0, window=args.window,
                                      daily=daily, funding=funding, oi=oi)
        print(f"  {len(perp_rows)} signal-fire rows from perp")
        all_rows.extend(perp_rows)
    else:
        # Fall back to 6mo file
        fallback = root / "data" / "bybit_5m_6mo.csv"
        if fallback.exists():
            print(f"\n18mo perp not found, falling back to {fallback}...")
            perp_candles = load_csv(fallback)
            print(f"  {len(perp_candles)} candles")
            print("  Walking perp tape...")
            perp_rows = generate_dataset(perp_candles, source_label=0, window=args.window,
                                          daily=daily, funding=funding, oi=oi)
            print(f"  {len(perp_rows)} signal-fire rows from perp")
            all_rows.extend(perp_rows)

    # Walk spot candles
    spot_path = root / args.spot
    if spot_path.exists():
        print(f"\nLoading spot candles from {args.spot}...")
        spot_candles = load_csv(spot_path)
        print(f"  {len(spot_candles)} candles ({spot_candles[0]['time']} → {spot_candles[-1]['time']})")
        print("  Walking spot tape...")
        spot_rows = generate_dataset(spot_candles, source_label=1, window=args.window,
                                      daily=daily, funding=funding, oi=oi)
        print(f"  {len(spot_rows)} signal-fire rows from spot")
        all_rows.extend(spot_rows)
    else:
        fallback = root / "data" / "spot_5m_6mo.csv"
        if fallback.exists():
            print(f"\n18mo spot not found, falling back to {fallback}...")
            spot_candles = load_csv(fallback)
            print(f"  {len(spot_candles)} candles")
            print("  Walking spot tape...")
            spot_rows = generate_dataset(spot_candles, source_label=1, window=args.window,
                                          daily=daily, funding=funding, oi=oi)
            print(f"  {len(spot_rows)} signal-fire rows from spot")
            all_rows.extend(spot_rows)

    if not all_rows:
        print("\n❌ No data generated. Check input files.")
        sys.exit(1)

    # Sort by timestamp
    all_rows.sort(key=lambda r: (r["feature_ts"], r["source"]))

    # Validate
    print(f"\n{'='*60}")
    print(f"Total rows: {len(all_rows)}")
    validate_dataset(all_rows)

    # Class balance
    wins = sum(1 for r in all_rows if r["label"] == 1)
    losses = len(all_rows) - wins
    print(f"Class balance: {wins} wins ({wins/len(all_rows)*100:.1f}%) / {losses} losses ({losses/len(all_rows)*100:.1f}%)")

    # Date range
    first_dt = datetime.fromtimestamp(all_rows[0]["feature_ts"] / 1000, tz=timezone.utc)
    last_dt = datetime.fromtimestamp(all_rows[-1]["feature_ts"] / 1000, tz=timezone.utc)
    print(f"Date range: {first_dt.date()} → {last_dt.date()}")

    # Source breakdown
    perp_n = sum(1 for r in all_rows if r["source"] == 0)
    spot_n = sum(1 for r in all_rows if r["source"] == 1)
    print(f"Sources: {perp_n} perp + {spot_n} spot")

    # Write CSV
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get all fieldnames from first row, ensure consistent ordering
    fieldnames = sorted(all_rows[0].keys())
    # Move key fields to front
    priority = ["feature_ts", "label_ts", "source", "direction", "streak", "label"]
    fieldnames = priority + [f for f in fieldnames if f not in priority]

    with output_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in all_rows:
            w.writerow(row)

    print(f"\n✅ Dataset written to {output_path} ({len(all_rows)} rows, {len(fieldnames)} columns)")
    print(f"   Columns: {', '.join(fieldnames)}")


if __name__ == "__main__":
    main()
