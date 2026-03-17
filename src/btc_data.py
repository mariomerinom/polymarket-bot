"""
btc_data.py — Fetch recent BTC candlestick data from Binance public API.

Provides real price action context (OHLCV, trend, volatility) so prediction
agents can make informed estimates instead of guessing blind at 50%.
"""

import requests
import statistics
from datetime import datetime, timezone


BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
COINGECKO_FALLBACK = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"


def fetch_btc_candles(interval="5m", limit=12):
    """
    Fetch recent BTC 5-minute candles from Binance.
    Returns a dict with candles, summary stats, and derived signals.
    Falls back to CoinGecko if Binance is unavailable.
    """
    try:
        return _fetch_binance(interval, limit)
    except Exception as e:
        print(f"  Binance API failed ({e}), trying CoinGecko fallback...")
        try:
            return _fetch_coingecko()
        except Exception as e2:
            print(f"  CoinGecko also failed ({e2}), returning empty data")
            return None


def _fetch_binance(interval, limit):
    """Fetch from Binance public klines endpoint (no auth needed)."""
    resp = requests.get(BINANCE_KLINES, params={
        "symbol": "BTCUSDT",
        "interval": interval,
        "limit": limit,
    }, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    candles = []
    for k in raw:
        open_price = float(k[1])
        high = float(k[2])
        low = float(k[3])
        close = float(k[4])
        volume = float(k[5])
        open_time_ms = k[0]
        open_time = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc)

        body = abs(close - open_price)
        full_range = high - low
        direction = "UP" if close >= open_price else "DOWN"

        # Wick ratio: how much of the candle is wick vs body
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


def _fetch_coingecko():
    """Fallback: fetch from CoinGecko OHLC (less granular but free)."""
    resp = requests.get(COINGECKO_FALLBACK, params={
        "vs_currency": "usd",
        "days": "1",
    }, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    # CoinGecko returns [timestamp, open, high, low, close]
    # Take last 12 entries
    entries = raw[-12:] if len(raw) >= 12 else raw

    candles = []
    for entry in entries:
        ts, o, h, l, c = entry
        open_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        direction = "UP" if c >= o else "DOWN"
        body = abs(c - o)
        full_range = h - l
        wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
        body_pct = round((c - o) / o * 100, 4) if o > 0 else 0.0

        candles.append({
            "time": open_time.strftime("%H:%M"),
            "open": o, "high": h, "low": l, "close": c,
            "volume": 0,  # CoinGecko OHLC doesn't include volume
            "direction": direction,
            "body_pct": body_pct,
            "wick_ratio": wick_ratio,
        })

    if not candles:
        return None

    return _compute_summary(candles)


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
        return "## Recent BTC Price Action\n(Data unavailable — make your best estimate from the macro prior alone)\n"

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
    against the human macro bias. Returns dict with per-timeframe UP% and blend.
    """
    if intervals is None:
        intervals = {"7d": 2016, "24h": 288, "1h": 12}

    results = {}
    weights = {"7d": 0.5, "24h": 0.3, "1h": 0.2}
    blended = 0.0
    total_weight = 0.0

    for label, limit in intervals.items():
        try:
            resp = requests.get(BINANCE_KLINES, params={
                "symbol": "BTCUSDT",
                "interval": "5m",
                "limit": min(limit, 1000),  # Binance caps at 1000
            }, timeout=15)
            resp.raise_for_status()
            raw = resp.json()
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
