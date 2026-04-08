#!/usr/bin/env python3
"""
backfill_asset_daily.py — Populate asset_daily for N historical UTC days.

Pulls 5m bars from Bybit REST for each day, computes daily metrics, and
writes them to data/asset_daily.db. Idempotent: re-running overwrites.

Usage:
    python3 tools/backfill_asset_daily.py                    # default 30 days, BTC+ETH
    python3 tools/backfill_asset_daily.py --days 60
    python3 tools/backfill_asset_daily.py --assets BTC
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from asset_daily import compute_daily, fetch_bybit_day_5m, init_table, record

ASSET_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/asset_daily.db")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--assets", default="BTC,ETH",
                    help="comma-separated asset keys (BTC,ETH)")
    ap.add_argument("--category", default="linear",
                    help="Bybit category: linear|spot")
    args = ap.parse_args()

    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    for a in assets:
        if a not in ASSET_SYMBOLS:
            print(f"unknown asset: {a} (known: {list(ASSET_SYMBOLS)})")
            sys.exit(1)

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.db)
    init_table(db)

    today = datetime.now(timezone.utc).date()
    # Skip "today" because it's in-progress; backfill yesterday backwards.
    dates = [
        (today - timedelta(days=i + 1)).isoformat()
        for i in range(args.days)
    ]

    total_written = 0
    total_skipped = 0
    for asset in assets:
        symbol = ASSET_SYMBOLS[asset]
        prior_close = None
        # We walk oldest → newest so each day can reference the prior close.
        for date in reversed(dates):
            try:
                df = fetch_bybit_day_5m(symbol, date, category=args.category)
            except Exception as e:
                print(f"  {asset} {date}: FETCH ERROR {e}")
                total_skipped += 1
                continue
            if len(df) < 10:
                print(f"  {asset} {date}: only {len(df)} bars, skipping")
                total_skipped += 1
                continue
            metrics = compute_daily(df, prior_close=prior_close)
            record(db, asset=asset, date=date, metrics=metrics)
            prior_close = metrics["close"]
            total_written += 1
            print(
                f"  {asset} {date}: "
                f"body={metrics['body_pct']:+.4f} "
                f"rvol={metrics['realized_vol']:.4f} "
                f"label={metrics['trend_label']}"
            )
            time.sleep(0.1)  # be polite to Bybit

    print(f"\nwritten={total_written} skipped={total_skipped} db={args.db}")
    db.close()


if __name__ == "__main__":
    main()
