"""
V3 Stage 3 + 3.5 — Walk-Forward Backtest

Downloads historical BTC candles, constructs synthetic markets with known outcomes,
computes features, and simulates trades with realistic friction.

Stage 3: Backtest infrastructure + data download
Stage 3.5: Contrarian rule baseline (the bar ML must beat)
"""

import json
import math
import random
import sqlite3
import time
import requests
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.btc_data import _compute_summary
from src.v3.features import compute_features, feature_names, features_to_row
from src.v3.regime import compute_regime
from src.v3.config import ROUND_TRIP_FEE, SLIPPAGE_BUFFER, MIN_EDGE

COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
DB_PATH = Path(__file__).parent.parent.parent / "data" / "v3_backtest.db"


# ── Historical Data Download ────────────────────────────────────────────

def download_historical_candles(start_date, end_date, interval_s=300):
    """
    Download 5-min BTC candles from Coinbase for a date range.
    Paginates automatically (300 candles per request max).
    """
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    batch_size = 300 * interval_s  # seconds per batch

    all_candles = []
    cursor = start_ts

    while cursor < end_ts:
        batch_end = min(cursor + batch_size, end_ts)
        try:
            resp = requests.get(COINBASE_CANDLES, params={
                "granularity": interval_s,
                "start": cursor,
                "end": batch_end,
            }, timeout=15)
            resp.raise_for_status()
            raw = resp.json()

            for k in raw:
                ts = int(k[0])
                if ts < start_ts or ts > end_ts:
                    continue
                all_candles.append({
                    "timestamp": ts,
                    "open": float(k[3]),
                    "high": float(k[2]),
                    "low": float(k[1]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                })

            print(f"  Downloaded {len(raw)} candles "
                  f"({datetime.fromtimestamp(cursor, tz=timezone.utc).strftime('%m-%d %H:%M')} "
                  f"to {datetime.fromtimestamp(batch_end, tz=timezone.utc).strftime('%m-%d %H:%M')})")

        except Exception as e:
            print(f"  Error downloading batch: {e}")

        cursor = batch_end
        time.sleep(0.3)  # rate limit

    # Deduplicate and sort
    seen = set()
    unique = []
    for c in all_candles:
        if c["timestamp"] not in seen:
            seen.add(c["timestamp"])
            unique.append(c)
    unique.sort(key=lambda c: c["timestamp"])

    print(f"  Total: {len(unique)} unique candles")
    return unique


def candles_to_btc_format(raw_candles):
    """Convert raw candle dicts to the format expected by _compute_summary()."""
    formatted = []
    for c in raw_candles:
        o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
        body = abs(cl - o)
        full_range = h - l
        direction = "UP" if cl >= o else "DOWN"
        wick_ratio = round(1.0 - (body / full_range), 2) if full_range > 0 else 0.0
        body_pct = round((cl - o) / o * 100, 4) if o > 0 else 0.0
        dt = datetime.fromtimestamp(c["timestamp"], tz=timezone.utc)
        formatted.append({
            "time": dt.strftime("%H:%M"),
            "open": o, "high": h, "low": l, "close": cl,
            "volume": round(c["volume"], 2),
            "direction": direction, "body_pct": body_pct, "wick_ratio": wick_ratio,
        })
    return formatted


# ── Synthetic Market Construction ───────────────────────────────────────

def build_synthetic_markets(candles, lookback=20):
    """
    Build synthetic markets from historical candles.
    Each candle becomes a market: "Will BTC close UP in this 5-min window?"
    Outcome = 1 if close >= open, else 0.
    Context = previous `lookback` candles.
    """
    markets = []
    for i in range(lookback, len(candles)):
        target = candles[i]
        context = candles[i - lookback:i]

        # Compute implied UP probability from recent history
        recent_ups = sum(1 for c in context[-12:] if c["close"] >= c["open"])
        implied_up = recent_ups / 12

        outcome = 1 if target["close"] >= target["open"] else 0

        markets.append({
            "index": i,
            "timestamp": target["timestamp"],
            "target_candle": target,
            "context_candles": context,
            "outcome": outcome,
            "implied_price_yes": round(max(0.05, min(0.95, implied_up)), 3),
        })

    return markets


# ── Contrarian Rule (Stage 3.5 Baseline) ────────────────────────────────

def contrarian_rule_predict(features):
    """
    Simple contrarian rule from V2.1:
    - streak >= 3 same direction + check range shrinking → fade
    - volume ratio > 1.8 for confirmation
    Returns: (prediction_up_prob, should_trade)
    """
    streak = features.get("consecutive_streak", 0)
    compression = features.get("compression", 0)
    volume_ratio = features.get("volume_ratio", 1.0)
    range_ratio = features.get("range_ratio", 1.0)

    # No signal
    if abs(streak) < 3:
        return 0.5, False

    # Volume confirmation
    has_volume = volume_ratio > 1.8

    # Exhaustion signals: shrinking ranges or compression
    has_exhaustion = compression > 0 or range_ratio < 0.7

    if not (has_volume or has_exhaustion):
        return 0.5, False

    # Fade the streak
    if streak >= 3:
        # Streak is UP → predict DOWN
        return 0.38, True
    elif streak <= -3:
        # Streak is DOWN → predict UP
        return 0.62, True

    return 0.5, False


# ── Friction Simulation ─────────────────────────────────────────────────

def simulate_fill(edge, bet_size=75):
    """
    Simulate realistic trade with friction.
    Returns P&L after fees + random slippage.
    """
    # Random adverse slippage: 1-3 cents
    slippage = random.uniform(0.01, 0.03)
    effective_edge = edge - ROUND_TRIP_FEE - slippage

    return effective_edge, bet_size


# ── Walk-Forward Engine ─────────────────────────────────────────────────

def run_walkforward(markets, predict_fn, name="model",
                    warm_up=1000, bet_size=75, min_edge=0.05):
    """
    Run walk-forward simulation.

    Args:
        markets: list of synthetic markets
        predict_fn: function(features) -> (prob_up, should_trade)
        name: name for reporting
        warm_up: skip first N markets (training data)
        bet_size: fixed bet size in dollars
        min_edge: minimum edge after friction to trade

    Returns:
        dict with results
    """
    trades = []
    skipped = 0

    for i, market in enumerate(markets):
        if i < warm_up:
            continue

        # Compute features
        context_formatted = candles_to_btc_format(market["context_candles"])
        btc_summary = _compute_summary(context_formatted)
        regime = compute_regime(btc_summary)

        # Minimal book snapshot (not available historically)
        fake_book = {
            "midpoint": market["implied_price_yes"],
            "spread_pct": 0.02,
            "depth_imbalance": 0.0,
            "bid_depth_5pct": 2000,
            "ask_depth_5pct": 2000,
        }

        market_info = {
            "end_date": datetime.fromtimestamp(
                market["timestamp"], tz=timezone.utc
            ).isoformat(),
            "price_yes": market["implied_price_yes"],
        }

        features = compute_features(btc_summary, fake_book, market_info, regime)

        # Get prediction
        prob_up, should_trade = predict_fn(features)

        if not should_trade:
            skipped += 1
            continue

        # Determine direction and edge
        midpoint = market["implied_price_yes"]
        edge = abs(prob_up - midpoint)

        # Apply friction
        slippage = random.uniform(0.01, 0.03)
        net_edge = edge - ROUND_TRIP_FEE - slippage

        if net_edge < min_edge:
            skipped += 1
            continue

        # Determine if correct
        predicted_up = prob_up > 0.5
        actual_up = market["outcome"] == 1
        correct = predicted_up == actual_up

        pnl = bet_size * 0.96 if correct else -bet_size

        trades.append({
            "index": market["index"],
            "timestamp": market["timestamp"],
            "prob_up": prob_up,
            "midpoint": midpoint,
            "edge": edge,
            "net_edge": net_edge,
            "predicted_up": predicted_up,
            "actual_up": actual_up,
            "correct": correct,
            "pnl": pnl,
            "regime": regime["label"],
        })

    return _summarize_trades(trades, skipped, name, len(markets) - warm_up)


def _summarize_trades(trades, skipped, name, total_markets):
    """Compute summary statistics from trade list."""
    if not trades:
        return {
            "name": name,
            "total_markets": total_markets,
            "trades": 0,
            "skipped": skipped,
            "selectivity": 0,
            "win_rate": 0,
            "pnl": 0,
            "roi": 0,
            "max_drawdown": 0,
            "sharpe": 0,
            "trades_per_day": 0,
            "regime_breakdown": {},
            "trade_log": [],
        }

    correct = sum(1 for t in trades if t["correct"])
    wrong = len(trades) - correct
    total_pnl = sum(t["pnl"] for t in trades)
    wagered = len(trades) * 75  # approximate

    # Max drawdown
    cumulative = []
    running = 0
    for t in trades:
        running += t["pnl"]
        cumulative.append(running)
    peak = 0
    max_dd = 0
    for v in cumulative:
        peak = max(peak, v)
        max_dd = min(max_dd, v - peak)

    # Sharpe (daily)
    pnls = [t["pnl"] for t in trades]
    avg_pnl = sum(pnls) / len(pnls) if pnls else 0
    std_pnl = statistics.stdev(pnls) if len(pnls) >= 2 else 1
    sharpe = (avg_pnl / std_pnl) * math.sqrt(252 * 288 / len(trades)) if std_pnl > 0 else 0

    # Time span for trades/day
    if len(trades) >= 2:
        span_s = trades[-1]["timestamp"] - trades[0]["timestamp"]
        span_days = span_s / 86400 if span_s > 0 else 1
        trades_per_day = len(trades) / span_days
    else:
        trades_per_day = 0

    # Regime breakdown
    regime_stats = defaultdict(lambda: {"correct": 0, "wrong": 0, "pnl": 0})
    for t in trades:
        r = t["regime"]
        if t["correct"]:
            regime_stats[r]["correct"] += 1
        else:
            regime_stats[r]["wrong"] += 1
        regime_stats[r]["pnl"] += t["pnl"]

    return {
        "name": name,
        "total_markets": total_markets,
        "trades": len(trades),
        "skipped": skipped,
        "selectivity": len(trades) / total_markets * 100 if total_markets > 0 else 0,
        "correct": correct,
        "wrong": wrong,
        "win_rate": correct / len(trades) * 100 if trades else 0,
        "pnl": total_pnl,
        "wagered": wagered,
        "roi": total_pnl / wagered * 100 if wagered > 0 else 0,
        "max_drawdown": max_dd,
        "sharpe": round(sharpe, 2),
        "trades_per_day": round(trades_per_day, 1),
        "regime_breakdown": dict(regime_stats),
        "trade_log": trades,
    }


def print_results(results):
    """Print formatted backtest results."""
    r = results
    print(f"\n{'='*60}")
    print(f"  {r['name']} Backtest Results")
    print(f"{'='*60}")
    print(f"  Markets evaluated:  {r['total_markets']}")
    print(f"  Trades taken:       {r['trades']} ({r['selectivity']:.1f}% selectivity)")
    print(f"  Skipped:            {r['skipped']}")
    print(f"  Trades/day:         {r['trades_per_day']:.1f}")
    print()
    print(f"  Win rate:           {r['win_rate']:.1f}% ({r['correct']}W / {r['wrong']}L)")
    print(f"  P&L:                ${r['pnl']:+,.0f}")
    print(f"  Wagered:            ${r.get('wagered', 0):,}")
    print(f"  ROI:                {r['roi']:+.1f}%")
    print(f"  Max drawdown:       ${r['max_drawdown']:,.0f}")
    print(f"  Sharpe:             {r['sharpe']:.2f}")

    if r["regime_breakdown"]:
        print(f"\n  --- Regime Breakdown ---")
        for regime, stats in sorted(r["regime_breakdown"].items()):
            total = stats["correct"] + stats["wrong"]
            wr = stats["correct"] / total * 100 if total > 0 else 0
            print(f"  {regime:<30s}  {stats['correct']}W/{stats['wrong']}L  "
                  f"{wr:.0f}%  ${stats['pnl']:+,.0f}")
    print()


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="V3 Walk-Forward Backtest")
    parser.add_argument("--days", type=int, default=7, help="Days of history to download")
    parser.add_argument("--warm-up", type=int, default=500, help="Warm-up markets (no trades)")
    parser.add_argument("--bet-size", type=int, default=75, help="Fixed bet size ($)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for slippage")
    args = parser.parse_args()

    random.seed(args.seed)

    print("V3 Walk-Forward Backtest\n")

    # Download historical candles
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    print(f"Downloading {args.days} days of BTC candles ({start_date.strftime('%m-%d')} to {end_date.strftime('%m-%d')})...")

    candles = download_historical_candles(start_date, end_date)
    if not candles:
        print("ERROR: No candles downloaded")
        exit(1)

    # Build synthetic markets
    print(f"\nBuilding synthetic markets (lookback=20)...")
    markets = build_synthetic_markets(candles, lookback=20)
    ups = sum(1 for m in markets if m["outcome"] == 1)
    downs = len(markets) - ups
    print(f"  Total: {len(markets)} markets (UP={ups}, DOWN={downs}, base_rate={ups/len(markets)*100:.1f}%)")

    if len(markets) < args.warm_up + 50:
        print(f"WARNING: Only {len(markets)} markets, need {args.warm_up}+ warm-up. Reducing warm-up.")
        args.warm_up = max(0, len(markets) - 100)

    # Stage 3.5: Contrarian Rule Baseline
    print(f"\n--- Stage 3.5: Contrarian Rule Baseline ---")
    print(f"Warm-up: {args.warm_up} markets, then evaluate on {len(markets) - args.warm_up}")

    contrarian_results = run_walkforward(
        markets, contrarian_rule_predict,
        name="Contrarian Rule",
        warm_up=args.warm_up,
        bet_size=args.bet_size,
    )
    print_results(contrarian_results)

    print(f"This is the baseline ML must beat.")
    print(f"Bar: {contrarian_results['win_rate']:.1f}% win rate, "
          f"${contrarian_results['pnl']:+,.0f} P&L, "
          f"{contrarian_results['roi']:+.1f}% ROI")
