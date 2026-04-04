from config import DEFAULT_CANDLE_LIMIT
from config import API_TIMEOUT_BYBIT
from config import SHADOW_CANDLE_LIMIT
from config import STREAK_AGREEMENT_MIN
"""
bybit_data.py — BTC candle data for Bybit perpetual futures pipeline.

Primary: Bybit /v5/market/kline (public, no auth).
Secondary: btc_data.fetch_btc_candles() (Kraken/Coinbase spot).

Always fetches both sources for perps-vs-spot consensus scoring.
Bybit perps candles are primary; spot provides cross-venue confirmation.
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

    Always fetches both Bybit perps and spot (Kraken/Coinbase) for
    cross-venue consensus. Bybit is primary; spot is secondary.
    Returns the same dict format as btc_data.fetch_btc_candles().
    """
    bybit_data = None
    try:
        bybit_data = _fetch_bybit_kline(symbol, interval, limit)
    except Exception as e:
        print(f"  Bybit kline API failed ({e})")

    # Always fetch spot for consensus (Kraken→Coinbase failover built in)
    interval_str = f"{interval}m" if not interval.endswith("m") else interval
    spot_data = None
    try:
        spot_data = fetch_btc_candles(interval=interval_str, limit=limit)
    except Exception as e:
        print(f"  Spot data fetch failed ({e})")

    primary = bybit_data or spot_data
    if primary is None:
        return None

    primary["consensus"] = _compute_perp_spot_consensus(bybit_data, spot_data)
    return primary


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


def _compute_perp_spot_consensus(bybit_data, spot_data):
    """
    Compare Bybit perps and spot (Kraken/Coinbase) candle data.

    Returns dict with consensus score and perps premium/discount.
    Same scoring as btc_data._compute_consensus():
      2 = both agree direction + both streak >= STREAK_AGREEMENT_MIN
      1 = single source or direction agrees but streaks differ
     -1 = directions disagree
      0 = no data
    """
    result = {
        "sources": 0,
        "streak_agree": None,
        "direction_agree": None,
        "streak_bybit": None,
        "streak_spot": None,
        "score": 0,
        "perps_premium_pct": None,
    }

    if bybit_data:
        result["sources"] += 1
        result["streak_bybit"] = {
            "direction": bybit_data["consecutive_dir_label"],
            "length": bybit_data["consecutive_direction"],
        }
    if spot_data:
        result["sources"] += 1
        result["streak_spot"] = {
            "direction": spot_data["consecutive_dir_label"],
            "length": spot_data["consecutive_direction"],
        }

    if result["sources"] < 2:
        result["score"] = 1 if result["sources"] == 1 else 0
        return result

    # Both available — compare
    b_dir = bybit_data["consecutive_dir_label"]
    s_dir = spot_data["consecutive_dir_label"]
    b_streak = bybit_data["consecutive_direction"]
    s_streak = spot_data["consecutive_direction"]

    result["direction_agree"] = b_dir == s_dir
    result["streak_agree"] = (
        b_dir == s_dir
        and b_streak >= STREAK_AGREEMENT_MIN
        and s_streak >= STREAK_AGREEMENT_MIN
    )

    if result["streak_agree"]:
        result["score"] = 2
    elif result["direction_agree"]:
        result["score"] = 1
    else:
        result["score"] = -1

    # Perps premium/discount (informational — log only, no action yet)
    bybit_close = bybit_data["current_price"]
    spot_close = spot_data["current_price"]
    if spot_close > 0:
        result["perps_premium_pct"] = round(
            (bybit_close - spot_close) / spot_close * 100, 4
        )

    return result


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
