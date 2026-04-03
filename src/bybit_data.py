from config import DEFAULT_CANDLE_LIMIT
from config import API_TIMEOUT_BYBIT
from config import SHADOW_CANDLE_LIMIT
"""
bybit_data.py — BTC candle data for Bybit perpetual futures pipeline.

Primary: Bybit /v5/market/kline (public, no auth).
Fallback: btc_data.fetch_btc_candles() (Kraken/Coinbase).

BTC is BTC regardless of venue — the momentum signal was trained on
Kraken/Coinbase candles and must see the same data distribution.
Bybit candles are offered as primary to reduce latency and capture
any venue-specific microstructure differences.
"""

import os
import requests
from datetime import datetime, timezone

from btc_data import fetch_btc_candles
from config import _env

BYBIT_BASE_URL = _env("BYBIT_BASE_URL", "https://api.bybit.com")
BYBIT_KLINE = f"{BYBIT_BASE_URL}/v5/market/kline"
BYBIT_TICKERS = f"{BYBIT_BASE_URL}/v5/market/tickers"
BYBIT_FUNDING = f"{BYBIT_BASE_URL}/v5/market/funding/history"


def fetch_bybit_candles(symbol="BTCUSDT", interval="5", limit=DEFAULT_CANDLE_LIMIT):
    """
    Fetch BTC candles for the Bybit pipeline.

    Primary: Bybit kline API (public, no auth).
    Fallback: btc_data.fetch_btc_candles() (Kraken/Coinbase).

    Returns the same dict format as btc_data.fetch_btc_candles().
    """
    try:
        data = _fetch_bybit_kline(symbol, interval, limit)
        if data:
            return data
    except Exception as e:
        print(f"  Bybit kline API failed ({e})")

    # Fallback to Kraken/Coinbase
    interval_str = f"{interval}m" if not interval.endswith("m") else interval
    return fetch_btc_candles(interval=interval_str, limit=limit)


def _fetch_bybit_kline(symbol, interval, limit):
    """Fetch from Bybit public kline endpoint (no auth needed)."""
    resp = requests.get(BYBIT_KLINE, params={
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }, timeout=API_TIMEOUT_BYBIT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("retCode") != 0:
        raise Exception(f"Bybit error: {data.get('retMsg', 'unknown')}")

    raw = data.get("result", {}).get("list", [])
    if not raw:
        raise Exception("No candle data in Bybit response")

    # Bybit returns newest first — reverse to chronological
    raw.sort(key=lambda x: int(x[0]))

    candles = []
    for k in raw:
        # Bybit: [startTime, open, high, low, close, volume, turnover]
        open_time = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc)
        open_price = float(k[1])
        high = float(k[2])
        low = float(k[3])
        close = float(k[4])
        volume = float(k[5])

        body = abs(close - open_price)
        full_range = high - low
        direction = "UP" if close >= open_price else "DOWN"
        wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
        body_pct = round((close - open_price) / open_price * 100, 4) if open_price > 0 else 0.0

        candles.append({
            "time": open_time.strftime("%H:%M"),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": round(volume, 2),
            "direction": direction,
            "body_pct": body_pct,
            "wick_ratio": wick_ratio,
        })

    if not candles:
        return None

    # Delegate to btc_data's _compute_summary for consistent output format
    from btc_data import _compute_summary
    return _compute_summary(candles)


def fetch_bybit_mark_price(symbol="BTCUSDT"):
    """Fetch current mark price for accurate entry/exit pricing."""
    try:
        resp = requests.get(BYBIT_TICKERS, params={
            "category": "linear",
            "symbol": symbol,
        }, timeout=API_TIMEOUT_BYBIT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            return None
        items = data.get("result", {}).get("list", [])
        if items:
            return float(items[0].get("markPrice", 0))
    except Exception as e:
        print(f"  Bybit mark price error: {e}")
    return None


def fetch_bybit_funding_rate(symbol="BTCUSDT"):
    """Fetch latest funding rate for dashboard logging."""
    try:
        resp = requests.get(BYBIT_FUNDING, params={
            "category": "linear",
            "symbol": symbol,
            "limit": 1,
        }, timeout=API_TIMEOUT_BYBIT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            return None
        items = data.get("result", {}).get("list", [])
        if items:
            return {
                "rate": float(items[0].get("fundingRate", 0)),
                "timestamp": items[0].get("fundingRateTimestamp", ""),
            }
    except Exception as e:
        print(f"  Bybit funding rate error: {e}")
    return None


if __name__ == "__main__":
    print("Bybit Data — candle fetch test")
    data = fetch_bybit_candles(interval="5", limit=DEFAULT_CANDLE_LIMIT)
    if data:
        print(f"  BTC: ${data['current_price']:,.2f}")
        print(f"  1h change: {data['1h_change_pct']:+.3f}%")
        print(f"  Trend: {data['trend']}")
        print(f"  Candles: {len(data['candles'])}")
    else:
        print("  No data returned")

    mark = fetch_bybit_mark_price()
    print(f"  Mark price: ${mark:,.2f}" if mark else "  Mark price: N/A")

    funding = fetch_bybit_funding_rate()
    if funding:
        print(f"  Funding rate: {funding['rate']:.6f}")
