"""
backfill_ta_features.py — Retroactively compute TA indicators for every prediction.

For each row in the Judge dataset, looks up the candles at that timestamp
from bybit_5m_18mo.csv and computes pure_ta indicators. Fills in what the
engine would have computed live.

Usage:
    python3 tools/backfill_ta_features.py
    python3 tools/backfill_ta_features.py --input data/judge_dataset_btc5m.csv --output data/judge_dataset_btc5m_enriched.csv
"""
from __future__ import annotations

import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pure_ta import compute_ta

TA_LOOKBACK = 30  # bars for TA computation


def load_candles(path: Path) -> List[dict]:
    """Load candle CSV sorted by timestamp."""
    candles = []
    with path.open() as f:
        for r in csv.DictReader(f):
            candles.append({
                "ts": int(r["ts"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            })
    candles.sort(key=lambda c: c["ts"])
    return candles


def build_ts_index(candles: List[dict]) -> Dict[int, int]:
    """Build {timestamp_ms: index} for O(1) lookup."""
    return {c["ts"]: i for i, c in enumerate(candles)}


def predicted_at_to_candle_ts(predicted_at: str) -> int:
    """Convert predicted_at ISO string to rounded 5m candle timestamp."""
    try:
        if "+" in predicted_at or "Z" in predicted_at:
            dt = datetime.fromisoformat(predicted_at.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(predicted_at).replace(tzinfo=timezone.utc)
        ts_ms = int(dt.timestamp() * 1000)
        return (ts_ms // 300_000) * 300_000  # round down to 5m
    except Exception:
        return 0


def compute_ta_at(candles: List[dict], ts_index: Dict[int, int],
                  candle_ts: int) -> Optional[dict]:
    """Compute TA indicators using candles up to (and including) candle_ts."""
    idx = ts_index.get(candle_ts)
    if idx is None:
        # Try nearest candle within 5 minutes
        for offset in [-300_000, 300_000, -600_000, 600_000]:
            idx = ts_index.get(candle_ts + offset)
            if idx is not None:
                break
    if idx is None:
        return None

    start = max(0, idx - TA_LOOKBACK + 1)
    window = candles[start:idx + 1]
    if len(window) < 21:  # minimum for pure_ta
        return None

    closes = [c["close"] for c in window]
    highs = [c["high"] for c in window]
    lows = [c["low"] for c in window]
    volumes = [c["volume"] for c in window]

    return compute_ta(closes, highs, lows, volumes)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Backfill TA features into Judge dataset")
    parser.add_argument("--input", default="data/judge_dataset_btc5m.csv")
    parser.add_argument("--output", default="data/judge_dataset_btc5m_enriched.csv")
    parser.add_argument("--candles", default="data/bybit_5m_18mo.csv")
    args = parser.parse_args()

    candle_path = ROOT / args.candles
    input_path = ROOT / args.input
    output_path = ROOT / args.output

    print(f"Loading candles from {candle_path}...")
    candles = load_candles(candle_path)
    ts_index = build_ts_index(candles)
    print(f"  {len(candles)} candles, index built")

    print(f"Loading dataset from {input_path}...")
    rows = []
    with input_path.open() as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames)
        for r in reader:
            rows.append(dict(r))
    print(f"  {len(rows)} rows")

    # TA feature keys from pure_ta
    ta_keys = ["rsi_14", "rsi_7", "bb_bandwidth", "bb_pctb", "z_score",
               "rvol", "obv_slope", "ema_ratio", "stoch_k", "stoch_d"]

    # Add new columns if not present
    for k in ta_keys:
        col = f"ta_{k}"
        if col not in headers:
            headers.append(col)

    # Backfill
    filled = 0
    missed = 0
    for i, row in enumerate(rows):
        predicted_at = row.get("predicted_at", "")
        candle_ts = predicted_at_to_candle_ts(predicted_at)

        ta = compute_ta_at(candles, ts_index, candle_ts)
        if ta:
            filled += 1
            for k in ta_keys:
                row[f"ta_{k}"] = ta.get(k, "nan")
        else:
            missed += 1
            for k in ta_keys:
                row[f"ta_{k}"] = "nan"

        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(rows)} processed ({filled} filled, {missed} missed)")

    print(f"\nDone: {filled} filled, {missed} missed ({filled/len(rows)*100:.1f}% coverage)")

    # Write enriched dataset
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"Wrote {output_path} ({len(rows)} rows, {len(headers)} columns)")


if __name__ == "__main__":
    main()
