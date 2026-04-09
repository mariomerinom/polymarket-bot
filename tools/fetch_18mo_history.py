"""
fetch_18mo_history.py — Fetch 18 months of Bybit BTCUSDT data:
  1. Linear (perp) 5m candles  → data/bybit_5m_18mo.csv
  2. Spot 5m candles            → data/spot_5m_18mo.csv
  3. Funding rate history       → data/funding_18mo.csv
  4. Open interest (5m)         → data/oi_5m_18mo.csv

All endpoints are public (no auth). Uses same pagination/rate-limit
pattern as fetch_spot_history.py.

Usage:
    python3 tools/fetch_18mo_history.py
"""

from __future__ import annotations

import csv
import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

BYBIT_BASE = os.environ.get("BYBIT_BASE_URL", "https://api.bybit.com")
KLINE_URL = f"{BYBIT_BASE}/v5/market/kline"
FUNDING_URL = f"{BYBIT_BASE}/v5/market/funding/history"
OI_URL = f"{BYBIT_BASE}/v5/market/open-interest"

PAGE = 1000
INTERVAL_MIN = 5
MONTHS = 18
SYMBOL = "BTCUSDT"
SLEEP = 0.15  # rate limit


def _candle_from_raw(row) -> dict:
    ts = int(row[0])
    o = float(row[1])
    h = float(row[2])
    l = float(row[3])
    c = float(row[4])
    v = float(row[5])
    body = abs(c - o)
    rng = h - l
    return {
        "ts": ts,
        "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": round(v, 2),
        "direction": "UP" if c >= o else "DOWN",
        "body_pct": round((c - o) / o * 100, 4) if o else 0.0,
        "wick_ratio": round(1.0 - (body / rng), 2) if rng > 0 else 0.0,
    }


def fetch_klines(category: str, symbol: str, months: int, label: str) -> list[dict]:
    """Paginate kline backwards. category='spot' or 'linear'."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    candles = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        params = {
            "category": category,
            "symbol": symbol,
            "interval": str(INTERVAL_MIN),
            "limit": PAGE,
            "end": end_ms,
        }
        resp = requests.get(KLINE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit error: {data.get('retMsg')}")
        raw = data.get("result", {}).get("list", [])
        if not raw:
            break
        raw.sort(key=lambda r: int(r[0]))
        batch = [_candle_from_raw(r) for r in raw if int(r[0]) not in seen]
        if not batch:
            break
        for c in batch:
            seen.add(c["ts"])
        candles = batch + candles
        earliest = batch[0]["ts"]
        if page % 20 == 0 or page == 1:
            print(f"  [{label}] page {page}: {len(candles)} candles, earliest="
                  f"{datetime.fromtimestamp(earliest / 1000, tz=timezone.utc).date()}")
        if earliest <= cutoff:
            break
        end_ms = earliest - 1
        time.sleep(SLEEP)
    candles.sort(key=lambda c: c["ts"])
    return candles


def write_candles(candles: list[dict], path: Path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "time", "open", "high", "low", "close",
                     "volume", "direction", "body_pct", "wick_ratio"])
        for c in candles:
            w.writerow([c["ts"], c["time"], c["open"], c["high"], c["low"],
                        c["close"], c["volume"], c["direction"],
                        c["body_pct"], c["wick_ratio"]])
    print(f"  Wrote {len(candles)} rows → {path}")


def fetch_funding(symbol: str, months: int) -> list[dict]:
    """Fetch funding rate history. Paginated by endTime (no cursor)."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    records = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        params = {
            "category": "linear",
            "symbol": symbol,
            "limit": 200,
            "endTime": end_ms,
        }
        resp = requests.get(FUNDING_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit funding error: {data.get('retMsg')}")
        raw = data.get("result", {}).get("list", [])
        if not raw:
            break
        for r in raw:
            ts = int(r["fundingRateTimestamp"])
            if ts in seen:
                continue
            if ts < cutoff:
                continue
            seen.add(ts)
            records.append({
                "ts": ts,
                "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                "funding_rate": float(r["fundingRate"]),
            })
        earliest_ts = min(int(r["fundingRateTimestamp"]) for r in raw)
        if page % 20 == 0 or page == 1:
            print(f"  [funding] page {page}: {len(records)} records, earliest="
                  f"{datetime.fromtimestamp(earliest_ts / 1000, tz=timezone.utc).date()}")
        if earliest_ts <= cutoff:
            break
        end_ms = earliest_ts - 1
        time.sleep(SLEEP)
    records.sort(key=lambda r: r["ts"])
    return records


def write_funding(records: list[dict], path: Path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "time", "funding_rate"])
        for r in records:
            w.writerow([r["ts"], r["time"], r["funding_rate"]])
    print(f"  Wrote {len(records)} rows → {path}")


def fetch_oi(symbol: str, months: int) -> list[dict]:
    """Fetch open interest at 5m intervals. Paginated by cursor."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    records = []
    seen = set()
    page = 0
    cursor = ""
    while True:
        page += 1
        params = {
            "category": "linear",
            "symbol": symbol,
            "intervalTime": "5min",
            "limit": 200,
        }
        if cursor:
            params["cursor"] = cursor
        else:
            params["endTime"] = end_ms
        resp = requests.get(OI_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit OI error: {data.get('retMsg')}")
        raw = data.get("result", {}).get("list", [])
        if not raw:
            break
        for r in raw:
            ts = int(r["timestamp"])
            if ts in seen:
                continue
            if ts < cutoff:
                continue
            seen.add(ts)
            records.append({
                "ts": ts,
                "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                "open_interest": float(r["openInterest"]),
            })
        earliest_ts = min(int(r["timestamp"]) for r in raw)
        if page % 100 == 0 or page == 1:
            print(f"  [OI] page {page}: {len(records)} records, earliest="
                  f"{datetime.fromtimestamp(earliest_ts / 1000, tz=timezone.utc).date()}")
        if earliest_ts <= cutoff:
            break
        next_cursor = data.get("result", {}).get("nextPageCursor", "")
        if not next_cursor:
            # Fall back to endTime pagination
            end_ms = earliest_ts - 1
            cursor = ""
        else:
            cursor = next_cursor
        time.sleep(SLEEP)
    records.sort(key=lambda r: r["ts"])
    return records


def write_oi(records: list[dict], path: Path):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "time", "open_interest"])
        for r in records:
            w.writerow([r["ts"], r["time"], r["open_interest"]])
    print(f"  Wrote {len(records)} rows → {path}")


def main():
    print(f"=== Fetching {MONTHS} months of Bybit {SYMBOL} data ===\n")

    # 1. Linear (perp) candles
    print("1/4  Linear (perp) 5m candles...")
    linear = fetch_klines("linear", SYMBOL, MONTHS, "linear")
    out_linear = DATA / "bybit_5m_18mo.csv"
    write_candles(linear, out_linear)
    print()

    # 2. Spot candles
    print("2/4  Spot 5m candles...")
    spot = fetch_klines("spot", SYMBOL, MONTHS, "spot")
    out_spot = DATA / "spot_5m_18mo.csv"
    write_candles(spot, out_spot)
    print()

    # 3. Funding rate
    print("3/4  Funding rate history...")
    funding = fetch_funding(SYMBOL, MONTHS)
    out_funding = DATA / "funding_18mo.csv"
    write_funding(funding, out_funding)
    print()

    # 4. Open interest
    print("4/4  Open interest (5m)...")
    oi = fetch_oi(SYMBOL, MONTHS)
    out_oi = DATA / "oi_5m_18mo.csv"
    write_oi(oi, out_oi)
    print()

    print("=== Summary ===")
    print(f"  Linear candles: {len(linear):,}")
    print(f"  Spot candles:   {len(spot):,}")
    print(f"  Funding rates:  {len(funding):,}")
    print(f"  OI records:     {len(oi):,}")
    print("\nDone.")


if __name__ == "__main__":
    main()
