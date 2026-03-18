"""
V3 Stage 4 — Backtest Regime-Filtered Contrarian Rule

Reprocesses 14-day data with regime filter applied.
Compares: plain contrarian vs regime-filtered contrarian.
Stores all results in SQLite for future querying.

Usage:
    PYTHONPATH=. python src/v3/stage4_regime_backtest.py
"""

import json
import random
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.btc_data import _compute_summary
from src.v3.backtest import (
    download_historical_candles,
    build_synthetic_markets,
    candles_to_btc_format,
    run_walkforward,
    contrarian_rule_predict,
    print_results,
    ROUND_TRIP_FEE,
)
from src.v3.features import compute_features, features_to_row
from src.v3.regime import compute_regime
from src.v3.config import ROUND_TRIP_FEE, SLIPPAGE_BUFFER, MIN_EDGE

DB_PATH = Path(__file__).parent.parent.parent / "data" / "v3_regime_backtest.db"


def regime_filtered_contrarian(features):
    """
    Contrarian rule WITH regime filter:
    - Skip if mean-reverting (autocorrelation < -0.15)
    - Otherwise same contrarian logic
    """
    # Regime gate
    autocorr = features.get("autocorrelation", 0.0)
    if autocorr < -0.15:
        return 0.5, False  # skip mean-reverting

    # Same contrarian rule
    return contrarian_rule_predict(features)


def enhanced_contrarian(features):
    """
    Enhanced contrarian: regime filter + V3.1 exhaustion rules.
    Requires at least 2 of 3 exhaustion signals (per consultant spec).
    """
    # Regime gate
    autocorr = features.get("autocorrelation", 0.0)
    if autocorr < -0.15:
        return 0.5, False

    streak = features.get("consecutive_streak", 0)
    if abs(streak) < 3:
        return 0.5, False

    # Count exhaustion signals (V3.1 spec: need at least 2 of 3)
    compression = features.get("compression", 0)
    volume_ratio = features.get("volume_ratio", 1.0)
    range_ratio = features.get("range_ratio", 1.0)
    wick_upper = features.get("wick_upper_ratio", 0)
    wick_lower = features.get("wick_lower_ratio", 0)

    exhaustion_count = 0

    # Signal 1: shrinking ranges / compression
    if compression > 0 or range_ratio < 0.7:
        exhaustion_count += 1

    # Signal 2: significant wick rejection (> 1.8x body)
    if streak >= 3 and wick_upper > 1.8:  # UP streak, upper wick = rejection
        exhaustion_count += 1
    elif streak <= -3 and wick_lower > 1.8:  # DOWN streak, lower wick = rejection
        exhaustion_count += 1

    # Signal 3: volume spike
    if volume_ratio > 1.8:
        exhaustion_count += 1

    if exhaustion_count < 2:
        return 0.5, False

    # Fade the streak
    if streak >= 3:
        return 0.38, True
    elif streak <= -3:
        return 0.62, True

    return 0.5, False


def init_db(db_path):
    """Create results database."""
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT NOT NULL,
        market_index INTEGER,
        timestamp INTEGER,
        regime TEXT,
        autocorrelation REAL,
        volatility_state INTEGER,
        streak INTEGER,
        prob_up REAL,
        midpoint REAL,
        edge REAL,
        net_edge REAL,
        predicted_up INTEGER,
        actual_up INTEGER,
        correct INTEGER,
        pnl REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy TEXT NOT NULL,
        run_date TEXT,
        total_markets INTEGER,
        trades INTEGER,
        selectivity REAL,
        win_rate REAL,
        pnl REAL,
        wagered REAL,
        roi REAL,
        max_drawdown REAL,
        sharpe REAL,
        trades_per_day REAL,
        regime_breakdown TEXT
    )""")
    db.commit()
    return db


def store_results(db, strategy_name, results):
    """Store trade log and summary in DB."""
    # Store individual trades
    for t in results.get("trade_log", []):
        db.execute("""INSERT INTO trades
            (strategy, market_index, timestamp, regime, autocorrelation, volatility_state,
             streak, prob_up, midpoint, edge, net_edge, predicted_up, actual_up, correct, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy_name, t.get("index"), t.get("timestamp"), t.get("regime"),
             t.get("autocorrelation", 0), t.get("volatility_state", 1),
             t.get("streak", 0), t["prob_up"], t["midpoint"], t["edge"],
             t["net_edge"], int(t["predicted_up"]), int(t["actual_up"]),
             int(t["correct"]), t["pnl"]))

    # Store summary
    db.execute("""INSERT INTO summaries
        (strategy, run_date, total_markets, trades, selectivity, win_rate,
         pnl, wagered, roi, max_drawdown, sharpe, trades_per_day, regime_breakdown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (strategy_name, datetime.now(timezone.utc).isoformat(),
         results["total_markets"], results["trades"], results["selectivity"],
         results["win_rate"], results["pnl"], results.get("wagered", 0),
         results["roi"], results["max_drawdown"], results["sharpe"],
         results["trades_per_day"], json.dumps(results["regime_breakdown"])))

    db.commit()


def run_with_regime_tracking(markets, predict_fn, name, warm_up=500, bet_size=75):
    """
    Run walkforward with regime info stored in each trade for DB logging.
    """
    trades = []
    skipped = 0
    regime_skipped = defaultdict(int)

    for i, market in enumerate(markets):
        if i < warm_up:
            continue

        context_formatted = candles_to_btc_format(market["context_candles"])
        btc_summary = _compute_summary(context_formatted)
        regime = compute_regime(btc_summary)

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
        # Add regime info to features for the predict function
        features["autocorrelation"] = regime["autocorrelation"]
        features["volatility_state_val"] = regime["volatility_state"]

        prob_up, should_trade = predict_fn(features)

        if not should_trade:
            skipped += 1
            regime_skipped[regime["label"]] += 1
            continue

        midpoint = market["implied_price_yes"]
        edge = abs(prob_up - midpoint)
        slippage = random.uniform(0.01, 0.03)
        net_edge = edge - ROUND_TRIP_FEE - slippage

        if net_edge < MIN_EDGE:
            skipped += 1
            continue

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
            "autocorrelation": regime["autocorrelation"],
            "volatility_state": regime["volatility_state"],
            "streak": features.get("consecutive_streak", 0),
        })

    # Build summary
    total_markets = len(markets) - warm_up
    if not trades:
        return {
            "name": name, "total_markets": total_markets, "trades": 0,
            "skipped": skipped, "selectivity": 0, "correct": 0, "wrong": 0,
            "win_rate": 0, "pnl": 0, "wagered": 0, "roi": 0,
            "max_drawdown": 0, "sharpe": 0, "trades_per_day": 0,
            "regime_breakdown": {}, "trade_log": trades,
            "regime_skipped": dict(regime_skipped),
        }

    correct_count = sum(1 for t in trades if t["correct"])
    wrong_count = len(trades) - correct_count
    total_pnl = sum(t["pnl"] for t in trades)
    wagered = len(trades) * bet_size

    # Max drawdown
    running = 0
    peak = 0
    max_dd = 0
    for t in trades:
        running += t["pnl"]
        peak = max(peak, running)
        max_dd = min(max_dd, running - peak)

    # Sharpe
    import math, statistics
    pnls = [t["pnl"] for t in trades]
    avg_pnl = sum(pnls) / len(pnls)
    std_pnl = statistics.stdev(pnls) if len(pnls) >= 2 else 1
    sharpe = (avg_pnl / std_pnl) * math.sqrt(252 * 288 / len(trades)) if std_pnl > 0 else 0

    # Trades per day
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
        "correct": correct_count,
        "wrong": wrong_count,
        "win_rate": correct_count / len(trades) * 100,
        "pnl": total_pnl,
        "wagered": wagered,
        "roi": total_pnl / wagered * 100 if wagered > 0 else 0,
        "max_drawdown": max_dd,
        "sharpe": round(sharpe, 2),
        "trades_per_day": round(trades_per_day, 1),
        "regime_breakdown": dict(regime_stats),
        "regime_skipped": dict(regime_skipped),
        "trade_log": trades,
    }


def print_comparison(results_list):
    """Print side-by-side comparison table."""
    print(f"\n{'='*80}")
    print(f"  SIDE-BY-SIDE COMPARISON")
    print(f"{'='*80}")

    headers = [r["name"] for r in results_list]
    print(f"  {'Metric':<25s}", end="")
    for h in headers:
        print(f" {h:>20s}", end="")
    print()
    print(f"  {'-'*25}", end="")
    for _ in headers:
        print(f" {'-'*20}", end="")
    print()

    metrics = [
        ("Win rate", "win_rate", ".1f", "%"),
        ("ROI", "roi", ".1f", "%"),
        ("P&L", "pnl", ",.0f", "$"),
        ("Trades", "trades", "d", ""),
        ("Selectivity", "selectivity", ".1f", "%"),
        ("Trades/day", "trades_per_day", ".1f", ""),
        ("Sharpe", "sharpe", ".2f", ""),
        ("Max drawdown", "max_drawdown", ",.0f", "$"),
    ]

    for label, key, fmt, prefix in metrics:
        print(f"  {label:<25s}", end="")
        for r in results_list:
            val = r[key]
            if prefix == "$":
                print(f" ${val:>19{fmt}}", end="")
            elif prefix == "%":
                print(f" {val:>19{fmt}}%", end="")
            else:
                print(f" {val:>20{fmt}}", end="")
        print()

    # Delta row
    if len(results_list) >= 2:
        base = results_list[0]
        for i in range(1, len(results_list)):
            comp = results_list[i]
            print(f"\n  Delta vs {base['name']}:")
            wr_d = comp["win_rate"] - base["win_rate"]
            roi_d = comp["roi"] - base["roi"]
            pnl_d = comp["pnl"] - base["pnl"]
            print(f"    {comp['name']}: WR {wr_d:+.1f}pp | ROI {roi_d:+.1f}pp | P&L ${pnl_d:+,.0f}")


if __name__ == "__main__":
    import argparse
    import numpy as np

    parser = argparse.ArgumentParser(description="V3 Stage 4: Regime-Filtered Backtest")
    parser.add_argument("--days", type=int, default=14, help="Days of history")
    parser.add_argument("--warm-up", type=int, default=500, help="Warm-up markets")
    parser.add_argument("--bet-size", type=int, default=75, help="Fixed bet size ($)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 80)
    print("  V3 Stage 4: Regime-Filtered Contrarian Backtest")
    print("=" * 80)
    print()

    # Download data
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    print(f"Period: {start_date.strftime('%b %d')} to {end_date.strftime('%b %d, %Y')}")
    print(f"Downloading {args.days} days of BTC candles...\n")

    candles = download_historical_candles(start_date, end_date)
    if not candles:
        print("ERROR: No candles downloaded")
        exit(1)

    markets = build_synthetic_markets(candles, lookback=20)
    ups = sum(1 for m in markets if m["outcome"] == 1)
    print(f"\nMarkets: {len(markets)} (UP={ups}, DOWN={len(markets)-ups})")
    print(f"Warm-up: {args.warm_up} | Evaluate: {len(markets) - args.warm_up}")
    print(f"Bet size: ${args.bet_size} | Friction: {ROUND_TRIP_FEE*100:.1f}% + 1-3¢ slippage")

    # Initialize DB
    db = init_db(DB_PATH)
    # Clear previous runs
    db.execute("DELETE FROM trades")
    db.execute("DELETE FROM summaries")
    db.commit()

    # ── Strategy 1: Plain Contrarian (baseline) ──────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Strategy 1: Plain Contrarian (no regime filter)")
    print(f"{'─'*60}")

    r_plain = run_with_regime_tracking(
        markets, contrarian_rule_predict,
        name="Plain Contrarian",
        warm_up=args.warm_up, bet_size=args.bet_size,
    )
    print_results(r_plain)
    store_results(db, "plain_contrarian", r_plain)

    # ── Strategy 2: Regime-Filtered Contrarian ───────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Strategy 2: Regime-Filtered Contrarian (skip mean-reverting)")
    print(f"{'─'*60}")

    r_filtered = run_with_regime_tracking(
        markets, regime_filtered_contrarian,
        name="Regime-Filtered",
        warm_up=args.warm_up, bet_size=args.bet_size,
    )
    print_results(r_filtered)
    store_results(db, "regime_filtered", r_filtered)

    if r_filtered.get("regime_skipped"):
        print(f"  Markets skipped by regime filter:")
        for regime, count in sorted(r_filtered["regime_skipped"].items()):
            print(f"    {regime}: {count}")

    # ── Strategy 3: Enhanced Contrarian (2-of-3 exhaustion) ──────────────
    print(f"\n{'─'*60}")
    print(f"  Strategy 3: Enhanced Contrarian (V3.1 spec: 2-of-3 exhaustion)")
    print(f"{'─'*60}")

    r_enhanced = run_with_regime_tracking(
        markets, enhanced_contrarian,
        name="Enhanced (V3.1)",
        warm_up=args.warm_up, bet_size=args.bet_size,
    )
    print_results(r_enhanced)
    store_results(db, "enhanced_v31", r_enhanced)

    # ── Comparison ───────────────────────────────────────────────────────
    print_comparison([r_plain, r_filtered, r_enhanced])

    # ── Verdict ──────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  VERDICT")
    print(f"{'='*80}")

    best = max([r_plain, r_filtered, r_enhanced], key=lambda r: r["pnl"])
    print(f"\n  Best strategy by P&L: {best['name']}")
    print(f"    Win rate:    {best['win_rate']:.1f}%")
    print(f"    ROI:         {best['roi']:+.1f}%")
    print(f"    P&L:         ${best['pnl']:+,.0f}")
    print(f"    Trades/day:  {best['trades_per_day']:.0f}")
    print(f"    Max DD:      ${best['max_drawdown']:,.0f}")

    # Check if regime filter improved on baseline
    pnl_improvement = r_filtered["pnl"] - r_plain["pnl"]
    wr_improvement = r_filtered["win_rate"] - r_plain["win_rate"]
    dd_improvement = r_filtered["max_drawdown"] - r_plain["max_drawdown"]

    print(f"\n  Regime filter vs plain:")
    print(f"    P&L delta:      ${pnl_improvement:+,.0f}")
    print(f"    Win rate delta: {wr_improvement:+.1f}pp")
    print(f"    Max DD delta:   ${dd_improvement:+,.0f} ({'better' if dd_improvement > 0 else 'worse'})")

    if pnl_improvement > 0 and wr_improvement > 0:
        print(f"\n  ✓ PASS — Regime filter improves both P&L and win rate")
        print(f"    Proceed to Stage 5 (paper logging loop)")
    elif pnl_improvement > 0:
        print(f"\n  ~ MARGINAL — P&L improved but win rate didn't")
        print(f"    Consider: the filter helped P&L by avoiding losses, even if WR is flat")
    else:
        print(f"\n  ✗ FAIL — Regime filter did not improve P&L")
        print(f"    Reevaluate: autocorrelation threshold may need tuning")

    print(f"\n  Results stored in: {DB_PATH}")
    print(f"  Query with: sqlite3 {DB_PATH} 'SELECT strategy, win_rate, roi, pnl FROM summaries'")

    db.close()
