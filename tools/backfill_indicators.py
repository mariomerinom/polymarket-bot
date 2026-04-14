#!/usr/bin/env python3
"""
backfill_indicators.py — Retroactively compute and store indicator snapshots
for historical predictions.

For each prediction in a DB:
1. Look up predicted_at timestamp
2. Find the candles that existed at that moment from the 18mo CSV
3. Run TAEngine.compute() on those candles
4. Generate indicator_snapshot() and patch the reasoning JSON

Deterministic: same candles → same indicators → same snapshot. This is
exactly what would have been stored if indicator logging shipped on day one.

Usage:
    # BTC 5m (default — uses spot_5m_18mo.csv)
    python3 tools/backfill_indicators.py

    # All DBs
    python3 tools/backfill_indicators.py --all

    # Specific DB
    python3 tools/backfill_indicators.py --db data/predictions_eth.db --asset ETH

    # Dry run (show what would change)
    python3 tools/backfill_indicators.py --dry-run
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
import pandas_ta as ta


ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

# CSV files keyed by asset
CANDLE_CSVS = {
    "BTC": DATA / "spot_5m_18mo.csv",
    # Bybit perps use the same BTC candles (correlated enough for indicators)
    "BTC_BYBIT": DATA / "bybit_5m_18mo.csv",
}

# DB files and their asset mapping
DB_CONFIGS = {
    "btc_5m": {"db": DATA / "predictions.db", "asset": "BTC", "csv_key": "BTC"},
    "btc_15m": {"db": DATA / "predictions_15m.db", "asset": "BTC", "csv_key": "BTC"},
    "eth_5m": {"db": DATA / "predictions_eth.db", "asset": "ETH", "csv_key": None},
    "btc_bybit": {"db": DATA / "predictions_bybit.db", "asset": "BTC", "csv_key": "BTC_BYBIT"},
}

# TAEngine minimum candle count
MIN_CANDLES = 21
# How many candles to use for indicator computation (same as live buffer)
CANDLE_WINDOW = 100


def load_candle_csv(csv_path: Path) -> pd.DataFrame:
    """Load 18mo candle CSV into a DataFrame with timestamp index."""
    print(f"  Loading {csv_path.name}...")
    df = pd.read_csv(csv_path)
    # Normalize column names (strip whitespace)
    df.columns = df.columns.str.strip()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts", "open", "high", "low", "close", "volume"])
    df = df.sort_values("ts").reset_index(drop=True)
    print(f"  Loaded {len(df):,} candles: {df['ts'].iloc[0]} → {df['ts'].iloc[-1]}")
    return df


def compute_indicators_at(candle_df: pd.DataFrame, timestamp_ms: int) -> dict | None:
    """Compute TAEngine-equivalent indicators using candles available at timestamp_ms.

    Returns the same dict structure as TAEngine.compute(), or None if
    insufficient candles before the given timestamp.
    """
    # Get candles up to and including this timestamp
    mask = candle_df["ts"] <= timestamp_ms
    available = candle_df[mask]

    if len(available) < MIN_CANDLES:
        return None

    # Take last CANDLE_WINDOW candles (same as live buffer)
    window = available.iloc[-CANDLE_WINDOW:].copy()

    # Set DatetimeIndex for VWAP
    window.index = pd.to_datetime(window["ts"], unit="ms", utc=True)
    window = window.sort_index()

    close = window["close"]
    high = window["high"]
    low = window["low"]
    volume = window["volume"]

    # --- Compute all indicators (same as TAEngine.compute) ---
    rsi_14 = ta.rsi(close, length=14)
    rsi_7 = ta.rsi(close, length=7)
    bbands = ta.bbands(close, length=20, std=2)
    vwap = ta.vwap(high, low, close, volume)
    obv = ta.obv(close, volume)
    stoch = ta.stoch(high, low, close, k=5, d=3)
    ema_9 = ta.ema(close, length=9)
    ema_21 = ta.ema(close, length=21)
    sma_20 = ta.sma(close, length=20)
    stdev_20 = ta.stdev(close, length=20)
    vol_mean_20 = volume.rolling(20).mean()

    # OBV slope
    obv_slope = None
    if obv is not None and len(obv.dropna()) >= 5:
        obv_last5 = obv.dropna().iloc[-5:].values
        try:
            obv_slope = float(np.polyfit(range(5), obv_last5, 1)[0])
        except (np.linalg.LinAlgError, ValueError):
            obv_slope = 0.0

    result = {}
    result["rsi_14"] = _last(rsi_14)
    result["rsi_7"] = _last(rsi_7)

    if bbands is not None and not bbands.empty:
        bb_row = bbands.iloc[-1]
        # pandas-ta column names vary by version: BBL_20_2.0 or BBL_20_2.0_2.0
        def _bb(prefix):
            for suffix in (f"{prefix}_20_2.0", f"{prefix}_20_2.0_2.0"):
                if suffix in bb_row.index:
                    return _safe(bb_row[suffix])
            return None
        result["bbands"] = {
            "lower": _bb("BBL"),
            "mid": _bb("BBM"),
            "upper": _bb("BBU"),
            "bandwidth": _bb("BBB"),
            "pctb": _bb("BBP"),
        }
    else:
        result["bbands"] = None

    result["vwap"] = _last(vwap)
    result["obv"] = _last(obv)
    result["obv_slope"] = obv_slope

    if stoch is not None and not stoch.empty:
        stoch_row = stoch.iloc[-1]
        result["stoch"] = {
            "k": _safe(stoch_row.get("STOCHk_5_3_3")),
            "d": _safe(stoch_row.get("STOCHd_5_3_3")),
        }
    else:
        result["stoch"] = None

    last_vol = _last(volume)
    mean_vol = _last(vol_mean_20)
    if last_vol is not None and mean_vol and mean_vol > 0:
        result["rvol"] = round(last_vol / mean_vol, 4)
    else:
        result["rvol"] = 1.0

    last_close = _last(close)
    last_sma = _last(sma_20)
    last_std = _last(stdev_20)
    if (last_close is not None and last_sma is not None
            and last_std is not None and last_std > 0):
        result["z_score"] = round((last_close - last_sma) / last_std, 4)
    else:
        result["z_score"] = 0.0

    result["ema_9"] = _last(ema_9)
    result["ema_21"] = _last(ema_21)
    result["candle_count"] = len(window)

    return result


def indicators_to_snapshot(indicators: dict, regime: dict | None,
                           candles_tail: list[dict]) -> dict:
    """Convert raw TAEngine indicators to flat snapshot (same as indicator_snapshot).

    Reimplemented here to avoid importing strategy lab code and needing
    a StrategyContext object. Produces identical output.
    """
    snap = {}
    ind = indicators or {}

    # Flat scalars
    for key in ("rsi_14", "rsi_7", "vwap", "obv", "obv_slope",
                "rvol", "z_score", "ema_9", "ema_21"):
        val = ind.get(key)
        if val is not None:
            snap[key] = round(float(val), 6)

    # Bollinger Bands
    bb = ind.get("bbands")
    if bb and isinstance(bb, dict):
        for sub_key in ("lower", "mid", "upper", "bandwidth", "pctb"):
            val = bb.get(sub_key)
            if val is not None:
                snap[f"bb_{sub_key}"] = round(float(val), 6)

    # Stochastic
    stoch = ind.get("stoch")
    if stoch and isinstance(stoch, dict):
        for sub_key in ("k", "d"):
            val = stoch.get(sub_key)
            if val is not None:
                snap[f"stoch_{sub_key}"] = round(float(val), 6)

    # Regime info
    if regime:
        if isinstance(regime, str):
            snap["regime_label"] = regime
        elif isinstance(regime, dict):
            snap["regime_label"] = regime.get("label", "")
            for rkey in ("autocorrelation", "volatility"):
                val = regime.get(rkey)
                if val is not None:
                    snap[f"regime_{rkey}"] = round(float(val), 6)
            snap["is_mean_reverting"] = regime.get("is_mean_reverting", False)

    # Candle-derived features
    if candles_tail and len(candles_tail) >= 2:
        c = candles_tail[-1]
        o = float(c.get("open", 0))
        cl = float(c.get("close", 0))
        h = float(c.get("high", 0))
        lo = float(c.get("low", 0))
        snap["candle_body_pct"] = round(abs(cl - o) / o * 100, 4) if o else 0
        snap["candle_range"] = round(abs(h - lo), 2)
        snap["candle_direction"] = c.get("direction", "UP" if cl >= o else "DOWN")

        # Streak length
        streak = 0
        last_dir = candles_tail[-1].get("direction", "")
        for candle in reversed(candles_tail):
            if candle.get("direction", "") == last_dir:
                streak += 1
            else:
                break
        snap["streak_length"] = streak
        snap["streak_direction"] = last_dir

    # EMA crossover state
    if snap.get("ema_9") and snap.get("ema_21"):
        snap["ema_cross"] = "BULLISH" if snap["ema_9"] > snap["ema_21"] else "BEARISH"

    return snap


def predicted_at_to_ms(predicted_at: str) -> int | None:
    """Convert ISO 8601 predicted_at string to milliseconds since epoch."""
    if not predicted_at:
        return None
    try:
        # Handle various formats
        predicted_at = predicted_at.strip()
        if predicted_at.endswith("Z"):
            predicted_at = predicted_at[:-1] + "+00:00"
        dt = datetime.fromisoformat(predicted_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def backfill_db(db_path: Path, candle_df: pd.DataFrame, dry_run: bool = False) -> dict:
    """Backfill indicator snapshots for all predictions in a database.

    Returns stats dict with counts.
    """
    if not db_path.exists():
        print(f"  SKIP: {db_path} not found")
        return {"total": 0, "patched": 0, "skipped": 0, "already_has": 0, "no_candles": 0}

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    # Get all predictions
    try:
        rows = db.execute(
            "SELECT id, predicted_at, reasoning, regime FROM predictions ORDER BY id"
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"  SKIP: {e}")
        db.close()
        return {"total": 0, "patched": 0, "skipped": 0, "already_has": 0, "no_candles": 0}

    stats = {"total": len(rows), "patched": 0, "skipped": 0, "already_has": 0, "no_candles": 0}
    updates = []

    # Pre-sort candle timestamps for binary search
    candle_ts = candle_df["ts"].values

    for row in rows:
        pred_id = row["id"]
        predicted_at = row["predicted_at"]
        reasoning_str = row["reasoning"]
        regime_str = row["regime"]

        # Parse existing reasoning
        try:
            reasoning = json.loads(reasoning_str) if reasoning_str else {}
        except (json.JSONDecodeError, TypeError):
            reasoning = {}

        # Check if already has full indicator snapshot
        existing_ind = reasoning.get("indicators", {})
        if existing_ind and "rsi_14" in existing_ind and "bb_bandwidth" in existing_ind:
            stats["already_has"] += 1
            continue

        # Convert predicted_at to ms
        ts_ms = predicted_at_to_ms(predicted_at)
        if ts_ms is None:
            stats["skipped"] += 1
            continue

        # Check if we have candle data for this timestamp
        if ts_ms < candle_ts[0] or ts_ms > candle_ts[-1]:
            stats["no_candles"] += 1
            continue

        # Compute indicators at this point in time
        indicators = compute_indicators_at(candle_df, ts_ms)
        if indicators is None:
            stats["no_candles"] += 1
            continue

        # Get candle tail for streak/body features
        mask = candle_df["ts"] <= ts_ms
        tail_df = candle_df[mask].iloc[-10:]
        candles_tail = tail_df.to_dict("records")

        # Parse regime from reasoning or column
        regime = reasoning.get("regime")
        if regime is None and regime_str:
            regime = {"label": regime_str}

        # Generate snapshot
        snapshot = indicators_to_snapshot(indicators, regime, candles_tail)

        # Patch reasoning
        reasoning["indicators"] = snapshot
        new_reasoning = json.dumps(reasoning)

        updates.append((new_reasoning, pred_id))
        stats["patched"] += 1

    # Write updates
    if updates and not dry_run:
        db.executemany("UPDATE predictions SET reasoning = ? WHERE id = ?", updates)
        db.commit()
        print(f"  Written {len(updates)} updates to {db_path.name}")
    elif updates and dry_run:
        print(f"  DRY RUN: would patch {len(updates)} predictions in {db_path.name}")

    db.close()
    return stats


def _last(series) -> float | None:
    """Get the last non-NaN value from a pandas Series."""
    if series is None:
        return None
    try:
        val = series.dropna().iloc[-1]
        return round(float(val), 6) if pd.notna(val) else None
    except (IndexError, TypeError):
        return None


def _safe(val) -> float | None:
    """Safely convert to float, returning None on failure."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return round(float(val), 6)
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Backfill indicator snapshots for historical predictions")
    parser.add_argument("--db", type=str, help="Specific DB path to backfill")
    parser.add_argument("--csv", type=str, help="Specific candle CSV to use")
    parser.add_argument("--all", action="store_true", help="Backfill all known DBs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--asset", type=str, default="BTC", help="Asset name (for --db mode)")
    args = parser.parse_args()

    print("=== Indicator Backfill ===\n")

    if args.db:
        # Single DB mode
        db_path = Path(args.db)
        csv_path = Path(args.csv) if args.csv else CANDLE_CSVS.get(args.asset)
        if csv_path is None or not csv_path.exists():
            print(f"ERROR: No candle CSV found for asset {args.asset}")
            print(f"  Available: {list(CANDLE_CSVS.keys())}")
            sys.exit(1)
        candle_df = load_candle_csv(csv_path)
        print(f"\nBackfilling {db_path.name}...")
        stats = backfill_db(db_path, candle_df, dry_run=args.dry_run)
        print(f"  Total: {stats['total']}, Patched: {stats['patched']}, "
              f"Already had: {stats['already_has']}, No candles: {stats['no_candles']}, "
              f"Skipped: {stats['skipped']}")

    elif args.all:
        # All DBs
        loaded_csvs = {}
        total_stats = {"total": 0, "patched": 0, "already_has": 0, "no_candles": 0, "skipped": 0}

        for name, cfg in DB_CONFIGS.items():
            csv_key = cfg["csv_key"]
            if csv_key is None:
                print(f"\n{name}: SKIP (no historical candle CSV for {cfg['asset']})")
                continue

            csv_path = CANDLE_CSVS[csv_key]
            if not csv_path.exists():
                print(f"\n{name}: SKIP ({csv_path.name} not found)")
                continue

            if csv_key not in loaded_csvs:
                loaded_csvs[csv_key] = load_candle_csv(csv_path)

            print(f"\nBackfilling {name} ({cfg['db'].name})...")
            stats = backfill_db(cfg["db"], loaded_csvs[csv_key], dry_run=args.dry_run)
            for k in total_stats:
                total_stats[k] += stats[k]
            print(f"  Total: {stats['total']}, Patched: {stats['patched']}, "
                  f"Already had: {stats['already_has']}, No candles: {stats['no_candles']}, "
                  f"Skipped: {stats['skipped']}")

        print(f"\n{'='*40}")
        print(f"Grand total: {total_stats['total']} predictions, "
              f"{total_stats['patched']} patched, "
              f"{total_stats['already_has']} already had indicators, "
              f"{total_stats['no_candles']} outside candle range")

    else:
        # Default: BTC 5m only
        csv_path = CANDLE_CSVS["BTC"]
        if not csv_path.exists():
            print(f"ERROR: {csv_path} not found")
            sys.exit(1)
        candle_df = load_candle_csv(csv_path)
        print(f"\nBackfilling predictions.db (BTC 5m)...")
        stats = backfill_db(DATA / "predictions.db", candle_df, dry_run=args.dry_run)
        print(f"  Total: {stats['total']}, Patched: {stats['patched']}, "
              f"Already had: {stats['already_has']}, No candles: {stats['no_candles']}, "
              f"Skipped: {stats['skipped']}")


if __name__ == "__main__":
    main()
