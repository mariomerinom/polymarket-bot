"""
fetch_bybit_funding_oi.py — Fetch 6mo Bybit BTCUSDT linear perp funding
history and open-interest history. Caches to:
  data/funding_6mo.csv
  data/oi_5m_6mo.csv

Funding: /v5/market/funding/history — 200 rows per page, 8h cadence.
Open Interest: /v5/market/open-interest — 200 rows per page, 5min cadence
  (intervalTime="5min").

Both endpoints return newest-first and support pagination via cursor OR
via `endTime`. We use endTime to mirror the kline fetcher.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
FUNDING_CSV = ROOT / "data" / "funding_6mo.csv"
OI_CSV = ROOT / "data" / "oi_5m_6mo.csv"

BASE = "https://api.bybit.com"
SYMBOL = "BTCUSDT"


def fetch_funding(months: int = 6):
    """Returns list of {ts, fundingRate} chronological."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    rows = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        resp = requests.get(
            f"{BASE}/v5/market/funding/history",
            params={
                "category": "linear",
                "symbol": SYMBOL,
                "limit": 200,
                "endTime": end_ms,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit: {data.get('retMsg')}")
        lst = data.get("result", {}).get("list", [])
        if not lst:
            break
        batch = []
        for r in lst:
            ts = int(r["fundingRateTimestamp"])
            if ts in seen:
                continue
            seen.add(ts)
            batch.append({"ts": ts, "rate": float(r["fundingRate"])})
        if not batch:
            break
        batch.sort(key=lambda x: x["ts"])
        rows = batch + rows
        earliest = batch[0]["ts"]
        print(f"  funding page {page}: {len(rows)} total, earliest="
              f"{datetime.fromtimestamp(earliest/1000, tz=timezone.utc).date()}")
        if earliest <= cutoff:
            break
        end_ms = earliest - 1
        time.sleep(0.15)
    rows.sort(key=lambda x: x["ts"])
    return rows


def fetch_oi(months: int = 6):
    """Returns list of {ts, oi} at 5min cadence, chronological."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    rows = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        resp = requests.get(
            f"{BASE}/v5/market/open-interest",
            params={
                "category": "linear",
                "symbol": SYMBOL,
                "intervalTime": "5min",
                "limit": 200,
                "endTime": end_ms,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit: {data.get('retMsg')}")
        lst = data.get("result", {}).get("list", [])
        if not lst:
            break
        batch = []
        for r in lst:
            ts = int(r["timestamp"])
            if ts in seen:
                continue
            seen.add(ts)
            batch.append({"ts": ts, "oi": float(r["openInterest"])})
        if not batch:
            break
        batch.sort(key=lambda x: x["ts"])
        rows = batch + rows
        earliest = batch[0]["ts"]
        if page % 10 == 0:
            print(f"  oi page {page}: {len(rows)} total, earliest="
                  f"{datetime.fromtimestamp(earliest/1000, tz=timezone.utc).date()}")
        if earliest <= cutoff:
            break
        end_ms = earliest - 1
        time.sleep(0.15)
    rows.sort(key=lambda x: x["ts"])
    return rows


def main():
    print("Fetching funding...")
    f = fetch_funding(6)
    FUNDING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with FUNDING_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "rate"])
        for r in f:
            w.writerow([r["ts"], r["rate"]])
    print(f"Wrote {len(f)} funding rows → {FUNDING_CSV}")

    print("Fetching OI...")
    o = fetch_oi(6)
    with OI_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "oi"])
        for r in o:
            w.writerow([r["ts"], r["oi"]])
    print(f"Wrote {len(o)} OI rows → {OI_CSV}")


if __name__ == "__main__":
    main()
