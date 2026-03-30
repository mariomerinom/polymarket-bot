"""
eth_data.py — Fetch recent ETH candlestick data for prediction agents.

Primary: Kraken (US-regulated, no auth, no geo-blocking)
Fallback: Coinbase (US-based, no auth, 5-min candles with volume)

PARALLEL PIPELINE — does NOT touch btc_data.py.
"""

import requests
import statistics
import time
from datetime import datetime, timezone

KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/ETH-USD/candles"

# Kraken uses XETHZUSD for the ETH/USD pair
KRAKEN_PAIR = "ETHUSD"


def fetch_eth_candles(interval="5m", limit=12):
    """
    Fetch recent ETH candles at the given interval.
    Primary: Kraken. Fallback: Coinbase.
    Also fetches Coinbase in parallel for cross-exchange consensus.
    Returns a dict with candles, summary stats, derived signals, and consensus.

    interval: "5m" (default) or "15m"
    """
    interval_minutes = int(interval.replace("m", ""))

    kraken_data = None
    coinbase_data = None

    # Fetch primary (Kraken)
    try:
        kraken_data = _fetch_kraken(limit, interval_minutes=interval_minutes)
    except Exception as e:
        print(f"  Kraken ETH API failed ({e})")

    # Fetch secondary (Coinbase) — always, for consensus
    try:
        coinbase_data = _fetch_coinbase(limit, interval_minutes=interval_minutes)
    except Exception as e2:
        print(f"  Coinbase ETH API failed ({e2})")

    # Use Kraken as primary, Coinbase as fallback
    primary = kraken_data or coinbase_data
    if primary is None:
        return None

    # Compute cross-exchange consensus
    primary["consensus"] = _compute_consensus(kraken_data, coinbase_data)

    return primary


def _fetch_kraken(limit, interval_minutes=5):
    """Fetch ETH from Kraken public OHLC endpoint (no auth needed)."""
    since = int(time.time()) - (limit + 2) * interval_minutes * 60
    resp = requests.get(KRAKEN_OHLC, params={
        "pair": KRAKEN_PAIR,
        "interval": interval_minutes,
        "since": since,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error") and len(data["error"]) > 0:
        raise Exception(f"Kraken error: {data['error']}")

    # Response has result key with pair name (may vary: XETHZUSD or ETHUSD)
    result = data.get("result", {})
    pair_key = None
    for key in result:
        if key != "last":
            pair_key = key
            break

    if not pair_key or not result[pair_key]:
        raise Exception("No candle data in Kraken response")

    raw = result[pair_key]
    raw = raw[-limit:] if len(raw) > limit else raw

    candles = []
    for k in raw:
        # Kraken: [time, open, high, low, close, vwap, volume, count]
        open_time = datetime.fromtimestamp(int(k[0]), tz=timezone.utc)
        open_price = float(k[1])
        high = float(k[2])
        low = float(k[3])
        close = float(k[4])
        volume = float(k[6])

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

    return _compute_summary(candles)


def _fetch_coinbase(limit, interval_minutes=5):
    """Fallback: Coinbase Exchange API (no auth needed for market data)."""
    now = int(time.time())
    start = now - (limit + 2) * interval_minutes * 60

    resp = requests.get(COINBASE_CANDLES, params={
        "granularity": interval_minutes * 60,
        "start": start,
        "end": now,
    }, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    if not raw:
        raise Exception("Empty response from Coinbase")

    # Coinbase returns newest first — reverse to chronological
    raw.sort(key=lambda x: x[0])
    raw = raw[-limit:] if len(raw) > limit else raw

    candles = []
    for k in raw:
        # Coinbase: [time, low, high, open, close, volume]
        open_time = datetime.fromtimestamp(int(k[0]), tz=timezone.utc)
        low = float(k[1])
        high = float(k[2])
        open_price = float(k[3])
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

    return _compute_summary(candles)


def _compute_consensus(kraken_data, coinbase_data):
    """Compare Kraken and Coinbase ETH data for cross-exchange consensus."""
    result = {
        "sources": 0,
        "streak_agree": None,
        "direction_agree": None,
        "score": 0,
        "streak_kraken": None,
        "streak_coinbase": None,
    }

    if kraken_data:
        result["sources"] += 1
        result["streak_kraken"] = {
            "direction": kraken_data["consecutive_dir_label"],
            "length": kraken_data["consecutive_direction"],
        }
    if coinbase_data:
        result["sources"] += 1
        result["streak_coinbase"] = {
            "direction": coinbase_data["consecutive_dir_label"],
            "length": coinbase_data["consecutive_direction"],
        }

    if result["sources"] < 2:
        result["score"] = 1 if result["sources"] == 1 else 0
        return result

    k_dir = kraken_data["consecutive_dir_label"]
    c_dir = coinbase_data["consecutive_dir_label"]
    k_streak = kraken_data["consecutive_direction"]
    c_streak = coinbase_data["consecutive_direction"]

    result["direction_agree"] = k_dir == c_dir
    result["streak_agree"] = (k_dir == c_dir and k_streak >= 2 and c_streak >= 2)

    if result["streak_agree"]:
        result["score"] = 2
    elif result["direction_agree"]:
        result["score"] = 1
    else:
        result["score"] = -1

    return result


def _compute_summary(candles):
    """Compute derived stats from a list of candles."""
    closes = [c["close"] for c in candles]
    current_price = closes[-1]
    first_open = candles[0]["open"]

    hour_change_pct = round((current_price - first_open) / first_open * 100, 3)

    returns = []
    for i in range(1, len(closes)):
        ret = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        returns.append(ret)
    volatility = round(statistics.stdev(returns), 4) if len(returns) >= 2 else 0.0

    consecutive = 1
    last_dir = candles[-1]["direction"]
    for i in range(len(candles) - 2, -1, -1):
        if candles[i]["direction"] == last_dir:
            consecutive += 1
        else:
            break

    ups = sum(1 for c in candles if c["direction"] == "UP")
    downs = len(candles) - ups
    if ups > downs + 2:
        trend = "up"
    elif downs > ups + 2:
        trend = "down"
    else:
        trend = "neutral"

    last = candles[-1]

    range_high = max(c["high"] for c in candles)
    range_low = min(c["low"] for c in candles)
    range_span = range_high - range_low
    range_position = round((current_price - range_low) / range_span, 3) if range_span > 0 else 0.5

    volumes = [c["volume"] for c in candles]
    avg_volume = sum(volumes) / len(volumes) if volumes else 1.0
    last_volume_ratio = round(last["volume"] / avg_volume, 2) if avg_volume > 0 else 1.0

    last_3_range_shrinking = False
    if len(candles) >= 3:
        ranges = [c["high"] - c["low"] for c in candles[-3:]]
        last_3_range_shrinking = ranges[0] > ranges[1] > ranges[2] and ranges[2] > 0

    avg_range = sum(c["high"] - c["low"] for c in candles) / len(candles) if candles else 0
    last_range = last["high"] - last["low"]
    last_range_ratio = round(last_range / avg_range, 2) if avg_range > 0 else 1.0

    last_body = abs(last["close"] - last["open"])
    last_full_range = last["high"] - last["low"]
    last_upper_wick = last["high"] - max(last["open"], last["close"])
    last_lower_wick = min(last["open"], last["close"]) - last["low"]

    last_wick_upper_ratio = round(last_upper_wick / last_body, 2) if last_body > 0 else 0.0
    last_wick_lower_ratio = round(last_lower_wick / last_body, 2) if last_body > 0 else 0.0

    last_candle_pattern = "none"
    if last_full_range > 0:
        body_frac = last_body / last_full_range
        if body_frac < 0.15 and last["wick_ratio"] > 0.7:
            last_candle_pattern = "doji"
        elif last["direction"] == "DOWN" and last_lower_wick > 2 * last_body and last_body > 0:
            last_candle_pattern = "hammer"
        elif last["direction"] == "UP" and last_upper_wick > 2 * last_body and last_body > 0:
            last_candle_pattern = "inv_hammer"

    if len(candles) >= 2:
        prev = candles[-2]
        prev_body = abs(prev["close"] - prev["open"])
        if last_body > prev_body * 1.1 and last["direction"] != prev["direction"]:
            if last["direction"] == "UP":
                last_candle_pattern = "engulfing_bull"
            else:
                last_candle_pattern = "engulfing_bear"
        elif (last["high"] < prev["high"] and last["low"] > prev["low"]):
            last_candle_pattern = "inside_bar"

    return {
        "candles": candles,
        "current_price": current_price,
        "1h_change_pct": hour_change_pct,
        "trend": trend,
        "volatility": volatility,
        "consecutive_direction": consecutive,
        "consecutive_dir_label": last_dir,
        "up_count": ups,
        "down_count": downs,
        "last_candle": {
            "direction": last["direction"],
            "body_pct": last["body_pct"],
            "wick_ratio": last["wick_ratio"],
        },
        "range_high": range_high,
        "range_low": range_low,
        "range_position": range_position,
        "avg_volume": round(avg_volume, 2),
        "last_volume_ratio": last_volume_ratio,
        "last_3_range_shrinking": last_3_range_shrinking,
        "last_range_ratio": last_range_ratio,
        "last_candle_pattern": last_candle_pattern,
        "last_wick_upper_ratio": last_wick_upper_ratio,
        "last_wick_lower_ratio": last_wick_lower_ratio,
    }


if __name__ == "__main__":
    print("Fetching ETH candle data...")
    data = fetch_eth_candles()
    if data:
        print(f"  ETH: ${data['current_price']:,.2f} | 1h: {data['1h_change_pct']:+.3f}%")
        print(f"  Streak: {data['consecutive_direction']} {data['consecutive_dir_label']}")
        print(f"  Volatility: {data['volatility']:.4f}%")
    else:
        print("Failed to fetch data from any source.")
