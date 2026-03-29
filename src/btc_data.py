"""
btc_data.py — Fetch recent BTC candlestick data for prediction agents.

Primary: Kraken (US-regulated, no auth, no geo-blocking)
Fallback: Coinbase (US-based, no auth, 5-min candles with volume)

Provides OHLCV candles + micro-TA signals so agents can read price action.
"""

import requests
import statistics
import time
from datetime import datetime, timezone

KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"


def fetch_btc_candles(interval="5m", limit=12):
    """
    Fetch recent BTC candles at the given interval.
    Primary: Kraken. Fallback: Coinbase.
    Also fetches Coinbase in parallel for cross-exchange consensus.
    Returns a dict with candles, summary stats, derived signals, and consensus.

    interval: "5m" (default) or "15m"
    """
    # Parse interval to minutes for API params
    interval_minutes = int(interval.replace("m", ""))

    kraken_data = None
    coinbase_data = None

    # Fetch primary (Kraken)
    try:
        kraken_data = _fetch_kraken(limit, interval_minutes=interval_minutes)
    except Exception as e:
        print(f"  Kraken API failed ({e})")

    # Fetch secondary (Coinbase) — always, for consensus
    try:
        coinbase_data = _fetch_coinbase(limit, interval_minutes=interval_minutes)
    except Exception as e2:
        print(f"  Coinbase API failed ({e2})")

    # Use Kraken as primary, Coinbase as fallback
    primary = kraken_data or coinbase_data
    if primary is None:
        return None

    # Compute cross-exchange consensus
    primary["consensus"] = _compute_consensus(kraken_data, coinbase_data)

    return primary


def _fetch_kraken(limit, interval_minutes=5):
    """Fetch from Kraken public OHLC endpoint (no auth needed).

    Returns [time, open, high, low, close, vwap, volume, count] arrays.
    Kraken returns all candles since `since` timestamp — we compute
    the right start time to get approximately `limit` candles.
    """
    since = int(time.time()) - (limit + 2) * interval_minutes * 60
    resp = requests.get(KRAKEN_OHLC, params={
        "pair": "XBTUSD",
        "interval": interval_minutes,
        "since": since,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error") and len(data["error"]) > 0:
        raise Exception(f"Kraken error: {data['error']}")

    # Response has result key with pair name (may vary: XXBTZUSD or XBTUSD)
    result = data.get("result", {})
    pair_key = None
    for key in result:
        if key != "last":
            pair_key = key
            break

    if not pair_key or not result[pair_key]:
        raise Exception("No candle data in Kraken response")

    raw = result[pair_key]
    # Take last `limit` candles
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
    """Fallback: Coinbase Exchange API (no auth needed for market data).

    Returns [time, low, high, open, close, volume] arrays (note different order).
    granularity in seconds (300 = 5-min, 900 = 15-min).
    """
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
    # Take last `limit`
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
    """
    Compare Kraken and Coinbase candle data for cross-exchange consensus.

    Returns dict with:
    - sources: how many exchanges returned data (0, 1, or 2)
    - streak_agree: both exchanges see the same streak direction
    - streak_kraken / streak_coinbase: per-exchange streak details
    - direction_agree: both see the same last-candle direction
    - score: 0 (no data), 1 (one source only), 2 (both agree), -1 (both disagree)
    """
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

    # Both sources available — compare
    k_dir = kraken_data["consecutive_dir_label"]
    c_dir = coinbase_data["consecutive_dir_label"]
    k_streak = kraken_data["consecutive_direction"]
    c_streak = coinbase_data["consecutive_direction"]

    result["direction_agree"] = k_dir == c_dir
    # Streak agreement: same direction AND both have streak >= 2
    result["streak_agree"] = (k_dir == c_dir and k_streak >= 2 and c_streak >= 2)

    if result["streak_agree"]:
        result["score"] = 2  # Strong consensus
    elif result["direction_agree"]:
        result["score"] = 1  # Weak consensus (direction matches but streaks differ)
    else:
        result["score"] = -1  # Disagreement

    return result


def _compute_summary(candles):
    """Compute derived stats from a list of candles."""
    closes = [c["close"] for c in candles]
    current_price = closes[-1]
    first_open = candles[0]["open"]

    # 1-hour change
    hour_change_pct = round((current_price - first_open) / first_open * 100, 3)

    # 5-min returns for volatility
    returns = []
    for i in range(1, len(closes)):
        ret = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        returns.append(ret)
    volatility = round(statistics.stdev(returns), 4) if len(returns) >= 2 else 0.0

    # Consecutive direction count
    consecutive = 1
    last_dir = candles[-1]["direction"]
    for i in range(len(candles) - 2, -1, -1):
        if candles[i]["direction"] == last_dir:
            consecutive += 1
        else:
            break

    # Trend: simple — more ups than downs in window
    ups = sum(1 for c in candles if c["direction"] == "UP")
    downs = len(candles) - ups
    if ups > downs + 2:
        trend = "up"
    elif downs > ups + 2:
        trend = "down"
    else:
        trend = "neutral"

    # Last candle details
    last = candles[-1]

    # --- Micro-TA fields (v2) ---

    # Range position: where current close sits in the 12-candle range (0=bottom, 1=top)
    range_high = max(c["high"] for c in candles)
    range_low = min(c["low"] for c in candles)
    range_span = range_high - range_low
    range_position = round((current_price - range_low) / range_span, 3) if range_span > 0 else 0.5

    # Volume analysis
    volumes = [c["volume"] for c in candles]
    avg_volume = sum(volumes) / len(volumes) if volumes else 1.0
    last_volume_ratio = round(last["volume"] / avg_volume, 2) if avg_volume > 0 else 1.0

    # Compression: are last 3 candle ranges shrinking?
    last_3_range_shrinking = False
    if len(candles) >= 3:
        ranges = [c["high"] - c["low"] for c in candles[-3:]]
        last_3_range_shrinking = ranges[0] > ranges[1] > ranges[2] and ranges[2] > 0

    # Average candle range for expansion detection
    avg_range = sum(c["high"] - c["low"] for c in candles) / len(candles) if candles else 0
    last_range = last["high"] - last["low"]
    last_range_ratio = round(last_range / avg_range, 2) if avg_range > 0 else 1.0

    # Candle pattern detection (last candle)
    last_body = abs(last["close"] - last["open"])
    last_full_range = last["high"] - last["low"]
    last_upper_wick = last["high"] - max(last["open"], last["close"])
    last_lower_wick = min(last["open"], last["close"]) - last["low"]

    # Wick ratios relative to body
    last_wick_upper_ratio = round(last_upper_wick / last_body, 2) if last_body > 0 else 0.0
    last_wick_lower_ratio = round(last_lower_wick / last_body, 2) if last_body > 0 else 0.0

    # Pattern classification
    last_candle_pattern = "none"
    if last_full_range > 0:
        body_frac = last_body / last_full_range
        if body_frac < 0.15 and last["wick_ratio"] > 0.7:
            last_candle_pattern = "doji"
        elif last["direction"] == "DOWN" and last_lower_wick > 2 * last_body and last_body > 0:
            last_candle_pattern = "hammer"
        elif last["direction"] == "UP" and last_upper_wick > 2 * last_body and last_body > 0:
            last_candle_pattern = "inv_hammer"

    # Engulfing detection (last 2 candles)
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
        # v2 micro-TA fields
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


def format_for_prompt(data):
    """Format BTC data as a readable string for injection into agent prompts."""
    if data is None:
        return "## Recent BTC Price Action\n(Data unavailable — use market_price as your estimate)\n"

    lines = [
        "## Recent BTC Price Action (last 1 hour, 5-min candles)",
        f"- **Current BTC price:** ${data['current_price']:,.0f}",
        f"- **1h change:** {data['1h_change_pct']:+.3f}%",
        f"- **Consecutive:** {data['consecutive_direction']} {data['consecutive_dir_label']} candles in a row",
        f"- **Volatility:** {data['volatility']:.4f}% per 5-min candle",
        f"- **Last candle:** {data['last_candle']['direction']} ({data['last_candle']['body_pct']:+.4f}%), wick ratio {data['last_candle']['wick_ratio']:.2f}",
        "",
        "## Micro-TA Signals (pre-computed)",
        f"- **Range position:** {data.get('range_position', 0.5):.2f} (0=bottom, 1=top of 12-candle range)",
        f"- **Last volume ratio:** {data.get('last_volume_ratio', 1.0):.2f}x average",
        f"- **Last range ratio:** {data.get('last_range_ratio', 1.0):.2f}x average (>2 = expansion)",
        f"- **Compression:** {'YES — last 3 ranges shrinking' if data.get('last_3_range_shrinking') else 'No'}",
        f"- **Candle pattern:** {data.get('last_candle_pattern', 'none')}",
        f"- **Upper wick/body ratio:** {data.get('last_wick_upper_ratio', 0):.1f}x",
        f"- **Lower wick/body ratio:** {data.get('last_wick_lower_ratio', 0):.1f}x",
        "",
        "| Time  | Open     | Close    | Dir  | Body%   | Wick  | Vol    |",
        "|-------|----------|----------|------|---------|-------|--------|",
    ]

    for c in data["candles"]:
        lines.append(
            f"| {c['time']} | {c['open']:>8,.0f} | {c['close']:>8,.0f} | {c['direction']:<4s} | {c['body_pct']:>+6.3f}% | {c['wick_ratio']:.2f}  | {c['volume']:>6.1f} |"
        )

    return "\n".join(lines)


def compute_rolling_bias(intervals=None):
    """
    Compute rolling UP% at multiple timeframes as an automatic sanity check
    against the human macro bias. Uses Kraken with Coinbase fallback.
    Returns dict with per-timeframe UP% and blend.
    """
    if intervals is None:
        intervals = {"7d": 2016, "24h": 288, "1h": 12}

    results = {}
    weights = {"7d": 0.5, "24h": 0.3, "1h": 0.2}
    blended = 0.0
    total_weight = 0.0

    for label, limit in intervals.items():
        try:
            # Kraken caps at 720 candles per request
            fetch_limit = min(limit, 720)
            since = int(time.time()) - (fetch_limit + 2) * 5 * 60
            resp = requests.get(KRAKEN_OHLC, params={
                "pair": "XBTUSD",
                "interval": 5,
                "since": since,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("error") and len(data["error"]) > 0:
                raise Exception(f"Kraken error: {data['error']}")

            result = data.get("result", {})
            pair_key = None
            for key in result:
                if key != "last":
                    pair_key = key
                    break

            raw = result.get(pair_key, []) if pair_key else []
            ups = sum(1 for k in raw if float(k[4]) >= float(k[1]))  # close >= open
            total = len(raw)
            up_pct = round(ups / total, 4) if total > 0 else 0.5
            results[label] = {"up_pct": up_pct, "candles": total}
            w = weights.get(label, 0)
            blended += up_pct * w
            total_weight += w
        except Exception as e:
            results[label] = {"up_pct": 0.5, "candles": 0, "error": str(e)}
            w = weights.get(label, 0)
            blended += 0.5 * w
            total_weight += w

    results["blended"] = round(blended / total_weight, 4) if total_weight > 0 else 0.5
    return results


if __name__ == "__main__":
    print("Fetching BTC candle data...")
    data = fetch_btc_candles()
    if data:
        print(format_for_prompt(data))
    else:
        print("Failed to fetch data from any source.")
