"""
fetch_spot_history.py — Fetch 6 months of Bybit BTCUSDT SPOT 5m candles
and cache to data/spot_5m_6mo.csv. Used by tools/backtest_bybit_alt.py
for the spot-vs-perp lead/lag signal.

Kraken's public OHLC only serves the most recent ~720 bars regardless
of `since`, so it's useless for historical backtesting. Bybit's own
spot endpoint supports full pagination, so we use Bybit spot as the
"leading venue" and Bybit linear perp as the "lagging venue". Not
cross-exchange in the literal sense, but spot and perp routinely
decouple (funding, basis) and the lead/lag hypothesis still applies.

Usage:
    python3 tools/fetch_spot_history.py
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_TOOLS))

from backtest_bybit import (  # noqa: E402
    _candle_from_raw,
    PAGE,
    INTERVAL_MIN,
    KLINE_URL,
)
import time
import requests
from datetime import timedelta

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "spot_5m_6mo.csv"


def fetch_spot_history(symbol: str, months: int = 6):
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int(
        (datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp()
        * 1000
    )
    candles = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        params = {
            "category": "spot",
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
        print(f"  page {page}: {len(candles)} total, earliest="
              f"{datetime.fromtimestamp(earliest / 1000, tz=timezone.utc).date()}")
        if earliest <= cutoff:
            break
        end_ms = earliest - 1
        time.sleep(0.15)
    candles.sort(key=lambda c: c["ts"])
    return candles


def main():
    print("Fetching Bybit BTCUSDT spot 5m history...")
    candles = fetch_spot_history("BTCUSDT", months=6)
    print(f"Fetched {len(candles)} candles.")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "time", "open", "high", "low", "close",
                    "volume", "direction", "body_pct", "wick_ratio"])
        for c in candles:
            w.writerow([
                c["ts"], c["time"], c["open"], c["high"], c["low"],
                c["close"], c["volume"], c["direction"],
                c["body_pct"], c["wick_ratio"],
            ])
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
