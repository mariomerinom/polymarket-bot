"""
backtest_candles_15m.py — Backtest with REAL BTC candles (Coinbase historical).

Unlike the native backtest (which uses Polymarket outcome sequences as proxy),
this uses actual OHLCV candle data — the same signal the live bot sees.

Fetches historical 15m candles from Coinbase, pairs them with resolved Polymarket
markets by timestamp, and replays the momentum signal.

Usage:
    python3 scripts/backtest_candles_15m.py
    python3 scripts/backtest_candles_15m.py --days 14
"""

import argparse
import json
import math
import sqlite3
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "backtest.db"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 300}


# ── Fetch historical candles from Coinbase ──────────────────────────

def fetch_historical_candles(days=28, interval_seconds=900):
    """Fetch historical 15m candles from Coinbase by paginating."""
    now = int(time.time())
    start = now - (days * 24 * 60 * 60)
    all_candles = []

    print("Fetching %d days of 15m candles from Coinbase..." % days)

    cursor = start
    batch = 0
    while cursor < now:
        batch_end = min(cursor + 300 * interval_seconds, now)

        try:
            resp = requests.get(COINBASE_CANDLES, params={
                "granularity": interval_seconds,
                "start": cursor,
                "end": batch_end,
            }, timeout=15)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            print("  Error at batch %d: %s" % (batch, e))
            cursor = batch_end
            time.sleep(1)
            continue

        if not raw:
            cursor = batch_end
            continue

        for k in raw:
            # Coinbase: [time, low, high, open, close, volume]
            ts = int(k[0])
            all_candles.append({
                "time": ts,
                "open": float(k[3]),
                "high": float(k[2]),
                "low": float(k[1]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        batch += 1
        cursor = batch_end
        time.sleep(0.1)  # Rate limit

    # Deduplicate and sort
    seen = set()
    unique = []
    for c in all_candles:
        if c["time"] not in seen:
            seen.add(c["time"])
            unique.append(c)
    unique.sort(key=lambda x: x["time"])

    first = datetime.fromtimestamp(unique[0]["time"], tz=timezone.utc) if unique else None
    last = datetime.fromtimestamp(unique[-1]["time"], tz=timezone.utc) if unique else None
    print("  Got %d unique 15m candles" % len(unique))
    if first and last:
        print("  Range: %s to %s" % (first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")))

    return unique


# ── Regime detectors ────────────────────────────────────────────────

def compute_regime(candles, method="autocorr", autocorr_threshold=-0.20, hurst_threshold=0.4):
    """Compute regime from OHLCV candle closes (same as live bot)."""
    closes = [c["close"] for c in candles]
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]

    if len(returns) < 3:
        return {"is_mean_reverting": False, "autocorr": 0, "hurst": 0.5, "label": "UNKNOWN"}

    n = len(returns)
    mean_r = sum(returns) / n
    var = sum((r - mean_r) ** 2 for r in returns) / n

    # Autocorrelation
    autocorr = 0.0
    if var > 0:
        cov = sum((returns[i] - mean_r) * (returns[i-1] - mean_r) for i in range(1, n)) / (n - 1)
        autocorr = cov / var

    # Hurst
    hurst = 0.5
    if n >= 3 and var > 0:
        Y, cumsum = [], 0
        for r in returns:
            cumsum += (r - mean_r)
            Y.append(cumsum)
        R = max(Y) - min(Y)
        S = (sum((r - mean_r) ** 2 for r in returns) / n) ** 0.5
        if R > 0 and S > 0:
            hurst = math.log(R / S) / math.log(n)

    if method == "hurst":
        is_mr = hurst < hurst_threshold
    else:
        is_mr = autocorr < autocorr_threshold

    return {"is_mean_reverting": is_mr, "autocorr": autocorr, "hurst": hurst,
            "label": "%s/%s" % (method, "MR" if is_mr else "OK")}


# ── Momentum signal (same as live bot) ──────────────────────────────

def momentum_signal(candles, min_streak=2, min_exhaustion=1):
    """Exact copy of the live bot's momentum signal logic."""
    if len(candles) < 5:
        return None

    last_dir = "UP" if candles[-1]["close"] >= candles[-1]["open"] else "DOWN"
    streak = 1
    for i in range(len(candles) - 2, -1, -1):
        d = "UP" if candles[i]["close"] >= candles[i]["open"] else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed = streak if last_dir == "UP" else -streak
    if abs(signed) < min_streak:
        return None

    # Exhaustion signals
    compression = False
    if len(candles) >= 3:
        ranges = [c["high"] - c["low"] for c in candles[-3:]]
        compression = ranges[0] > ranges[1] > ranges[2] and ranges[2] > 0

    volumes = [c["volume"] for c in candles]
    avg_vol = sum(volumes) / len(volumes) if volumes else 1
    vol_ratio = candles[-1]["volume"] / avg_vol if avg_vol > 0 else 1.0
    volume_spike = vol_ratio > 1.8

    avg_range = sum(c["high"] - c["low"] for c in candles) / len(candles)
    last_range = candles[-1]["high"] - candles[-1]["low"]
    range_ratio = last_range / avg_range if avg_range > 0 else 1.0
    shrinking = range_ratio < 0.7

    exhaust_count = sum([compression, volume_spike, shrinking])
    if exhaust_count < min_exhaustion:
        return None

    direction = "UP" if signed > 0 else "DOWN"
    confidence = "high" if abs(signed) >= 5 or (volume_spike and compression) else "medium"
    conviction = 4 if direction == "UP" else 3

    return {
        "direction": direction, "conviction": conviction, "streak": signed,
        "confidence": confidence, "exhaustion_count": exhaust_count,
    }


# ── Replay ──────────────────────────────────────────────────────────

def replay_with_candles(candles, markets_db, regime_method="hurst",
                        min_streak=2, min_exhaustion=1, lookback=20):
    """
    For each resolved 15m Polymarket market, find the 20 candles that were
    available BEFORE that market resolved, run the signal, and compare.
    """
    db = sqlite3.connect(markets_db)
    markets = db.execute("""
        SELECT id, end_date, price_yes, outcome
        FROM markets WHERE window = '15m' AND outcome IS NOT NULL
        ORDER BY end_date ASC
    """).fetchall()
    db.close()

    # Index candles by timestamp for fast lookup
    candle_by_ts = {c["time"]: c for c in candles}
    candle_times = sorted(candle_by_ts.keys())

    bets, wins, pnl = 0, 0, 0.0
    skips_regime, skips_signal, skips_nodata = 0, 0, 0
    exhaustion_breakdown = {1: {"trades": 0, "wins": 0}, 2: {"trades": 0, "wins": 0}, 3: {"trades": 0, "wins": 0}}

    for market_id, end_date, price_yes, outcome in markets:
        # Parse market end time
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            end_ts = int(end_dt.timestamp())
        except (ValueError, AttributeError):
            continue

        # Avoid look-ahead bias: the market covers (end_ts - 15min) to end_ts.
        # We must only use candles that CLOSED before the market window opened.
        # Coinbase timestamps = candle START, so a candle at 2:30 closes at 2:45.
        # For a market ending at 3:00 (window 2:45-3:00), last safe candle starts
        # at 2:30 (closes at 2:45). So read_ts = end_ts - 2*15min = end_ts - 30min.
        read_ts = end_ts - (2 * 15 * 60)  # 30 min before end (safe from look-ahead)

        # Find lookback candles ending at or before read_ts
        relevant_times = [t for t in candle_times if t <= read_ts]
        if len(relevant_times) < lookback:
            skips_nodata += 1
            continue

        window_times = relevant_times[-lookback:]
        window_candles = [candle_by_ts[t] for t in window_times]

        # Regime
        regime = compute_regime(window_candles, method=regime_method)
        if regime["is_mean_reverting"]:
            skips_regime += 1
            continue

        # Signal
        sig = momentum_signal(window_candles, min_streak=min_streak, min_exhaustion=min_exhaustion)
        if sig is None:
            skips_signal += 1
            continue

        direction = sig["direction"]
        conviction = sig["conviction"]
        bet_size = CONVICTION_BETS.get(conviction, 75)
        exhaust_n = sig["exhaustion_count"]

        correct = (direction == "UP" and outcome == 1) or \
                  (direction == "DOWN" and outcome == 0)

        bets += 1
        if exhaust_n in exhaustion_breakdown:
            exhaustion_breakdown[exhaust_n]["trades"] += 1

        if correct:
            wins += 1
            if exhaust_n in exhaustion_breakdown:
                exhaustion_breakdown[exhaust_n]["wins"] += 1
            entry_price = price_yes if direction == "UP" else (1 - price_yes)
            # Use 0.50 as default since backtest DB uses fair-value assumption
            entry_price = max(entry_price, 0.01)
            pnl += bet_size * (1.0 / entry_price - 1)
        else:
            pnl -= bet_size

    wr = (wins / bets * 100) if bets > 0 else 0
    return {
        "bets": bets, "wins": wins, "wr": wr, "pnl": pnl,
        "skips_regime": skips_regime, "skips_signal": skips_signal,
        "skips_nodata": skips_nodata,
        "exhaustion": exhaustion_breakdown,
    }


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Backtest 15m with real BTC candles")
    parser.add_argument("--days", type=int, default=28, help="Days of candle history")
    args = parser.parse_args()

    # Fetch candles
    candles = fetch_historical_candles(days=args.days)
    if len(candles) < 100:
        print("Not enough candle data. Got %d candles." % len(candles))
        return

    # Check backtest DB has markets
    db = sqlite3.connect(DB_PATH)
    total_markets = db.execute(
        "SELECT COUNT(*) FROM markets WHERE window = '15m' AND outcome IS NOT NULL"
    ).fetchone()[0]
    db.close()

    if total_markets == 0:
        print("No 15m markets in backtest DB. Run backtest_native.py --days 28 --window 15m --fetch-only first.")
        return

    print()
    print("=" * 72)
    print("REAL CANDLE BACKTEST: 15m Momentum Signal")
    print("=" * 72)
    print("Candles: %d (Coinbase 15m OHLCV)" % len(candles))
    print("Markets: %d resolved 15m Polymarket BTC" % total_markets)
    print()

    # Run all configurations
    configs = [
        ("Autocorr + 1/3 exhaust (old)", "autocorr", 1),
        ("Autocorr + 2/3 exhaust", "autocorr", 2),
        ("Hurst + 1/3 exhaust (current)", "hurst", 1),
        ("Hurst + 2/3 exhaust (proposed)", "hurst", 2),
    ]

    print("%-40s %6s %5s %5s %10s" % ("Config", "WR", "Bets", "Wins", "P/L"))
    print("-" * 72)

    for name, method, min_ex in configs:
        r = replay_with_candles(candles, DB_PATH, regime_method=method,
                                min_exhaustion=min_ex)
        print("%-40s %5.1f%% %5d %5d %+9.0f" % (
            name, r["wr"], r["bets"], r["wins"], r["pnl"]))

        if "current" in name or "proposed" in name:
            print("  Skips: regime=%d, signal=%d, no_data=%d" % (
                r["skips_regime"], r["skips_signal"], r["skips_nodata"]))
            for ex_n, ex_data in sorted(r["exhaustion"].items()):
                if ex_data["trades"] > 0:
                    ex_wr = ex_data["wins"] / ex_data["trades"] * 100
                    print("  Exhaustion %d/3: %d trades, %.1f%% WR" % (
                        ex_n, ex_data["trades"], ex_wr))

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()
