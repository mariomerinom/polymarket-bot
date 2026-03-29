"""
compare_regime_methods.py — Compare autocorrelation vs Hurst regime detection.

Runs both methods against the full 15m backtest dataset and produces a
side-by-side comparison with per-window consistency analysis.

Usage:
    python3 scripts/compare_regime_methods.py
    python3 scripts/compare_regime_methods.py --windows 5    # fewer windows
    python3 scripts/compare_regime_methods.py --fetch-fresh   # re-fetch from Polymarket
"""

import argparse
import sqlite3
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_PATH = Path(__file__).parent.parent / "data" / "backtest.db"
CONVICTION_BETS = {0: 0, 1: 0, 2: 0, 3: 75, 4: 200, 5: 300}


# ── Regime methods ───────────────────────────────────────────────────

def autocorr_regime(outcomes, threshold=-0.20):
    series = [1 if o == 1 else -1 for o in outcomes]
    n = len(series)
    mean = sum(series) / n
    var = sum((s - mean) ** 2 for s in series) / n
    if var == 0:
        return {"is_mean_reverting": False, "autocorr": 0.0, "hurst": 0.5}
    cov = sum((series[i] - mean) * (series[i-1] - mean) for i in range(1, n)) / (n - 1)
    autocorr = cov / var

    # Also compute hurst for comparison
    Y, cumsum = [], 0
    for s in series:
        cumsum += (s - mean)
        Y.append(cumsum)
    R = max(Y) - min(Y)
    S = (sum((s - mean)**2 for s in series) / n) ** 0.5
    hurst = math.log(R / S) / math.log(n) if R > 0 and S > 0 and n > 2 else 0.5

    return {"is_mean_reverting": autocorr < threshold, "autocorr": autocorr, "hurst": hurst}


def hurst_regime(outcomes, threshold=0.4):
    series = [1 if o == 1 else -1 for o in outcomes]
    n = len(series)
    mean = sum(series) / n
    var = sum((s - mean) ** 2 for s in series) / n
    if var == 0:
        return {"is_mean_reverting": False, "autocorr": 0.0, "hurst": 0.5}
    cov = sum((series[i] - mean) * (series[i-1] - mean) for i in range(1, n)) / (n - 1)
    autocorr = cov / var

    Y, cumsum = [], 0
    for s in series:
        cumsum += (s - mean)
        Y.append(cumsum)
    R = max(Y) - min(Y)
    S = (sum((s - mean)**2 for s in series) / n) ** 0.5
    hurst = math.log(R / S) / math.log(n) if R > 0 and S > 0 and n > 2 else 0.5

    return {"is_mean_reverting": hurst < threshold, "autocorr": autocorr, "hurst": hurst}


# ── Momentum signal ─────────────────────────────────────────────────

def momentum_signal(outcomes, volumes, prices, min_streak=2):
    last_dir = "UP" if outcomes[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(outcomes) - 2, -1, -1):
        d = "UP" if outcomes[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break

    signed = streak if last_dir == "UP" else -streak

    if abs(signed) < min_streak:
        return None

    # Exhaustion
    exhaustion = []
    if len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.8:
            exhaustion.append("volume_spike")
    if len(prices) >= 3:
        dist = [abs(p - 0.5) for p in prices[-3:]]
        if dist[0] > dist[1] > dist[2]:
            exhaustion.append("price_compression")
    if len(volumes) >= 3:
        if volumes[-3] > volumes[-2] > volumes[-1] and volumes[-1] > 0:
            exhaustion.append("volume_decline")

    if not exhaustion:
        return None

    direction = "UP" if signed > 0 else "DOWN"
    conviction = 4 if direction == "UP" else 3
    return {"direction": direction, "conviction": conviction, "streak": signed}


# ── Replay engine ────────────────────────────────────────────────────

def replay(db, regime_fn, label, num_windows=10, lookback=20):
    rows = db.execute("""
        SELECT id, end_date, volume, price_yes, outcome
        FROM markets WHERE window = '15m' AND outcome IS NOT NULL
        ORDER BY end_date ASC
    """).fetchall()

    if not rows:
        return None

    window_size = len(rows) // num_windows
    windows_data = []
    for i in range(num_windows):
        s = i * window_size
        e = (i + 1) * window_size if i < num_windows - 1 else len(rows)
        windows_data.append(rows[s:e])

    outcomes_h, volumes_h, prices_h = [], [], []
    total_bets, total_wins, total_pnl, total_wagered = 0, 0, 0.0, 0.0
    skips_regime, skips_signal = 0, 0
    window_results = []

    # Track disagreements between methods
    disagreements = {"autocorr_skip_hurst_trade": 0, "autocorr_trade_hurst_skip": 0,
                     "both_skip": 0, "both_trade": 0}

    for w_idx, w_rows in enumerate(windows_data):
        w_bets, w_wins, w_pnl = 0, 0, 0.0

        for row in w_rows:
            _, _, volume, price_yes, outcome = row

            if len(outcomes_h) < lookback:
                outcomes_h.append(outcome)
                volumes_h.append(volume)
                prices_h.append(price_yes)
                continue

            recent = outcomes_h[-lookback:]

            # Track disagreements
            a = autocorr_regime(recent)
            h = hurst_regime(recent)
            if a["is_mean_reverting"] and not h["is_mean_reverting"]:
                disagreements["autocorr_skip_hurst_trade"] += 1
            elif not a["is_mean_reverting"] and h["is_mean_reverting"]:
                disagreements["autocorr_trade_hurst_skip"] += 1
            elif a["is_mean_reverting"] and h["is_mean_reverting"]:
                disagreements["both_skip"] += 1
            else:
                disagreements["both_trade"] += 1

            # Apply this experiment's regime
            regime = regime_fn(recent)

            if regime["is_mean_reverting"]:
                skips_regime += 1
                outcomes_h.append(outcome)
                volumes_h.append(volume)
                prices_h.append(price_yes)
                continue

            sig = momentum_signal(recent, volumes_h[-lookback:], prices_h[-lookback:])

            if sig is None:
                skips_signal += 1
                outcomes_h.append(outcome)
                volumes_h.append(volume)
                prices_h.append(price_yes)
                continue

            direction = sig["direction"]
            conviction = sig["conviction"]
            bet_size = CONVICTION_BETS.get(conviction, 75)

            correct = (direction == "UP" and outcome == 1) or \
                      (direction == "DOWN" and outcome == 0)

            if direction == "UP":
                pnl = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                price_no = 1.0 - price_yes
                pnl = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size

            total_bets += 1
            w_bets += 1
            total_wagered += bet_size
            if correct:
                total_wins += 1
                w_wins += 1
            total_pnl += pnl
            w_pnl += pnl

            outcomes_h.append(outcome)
            volumes_h.append(volume)
            prices_h.append(price_yes)

        w_wr = (w_wins / w_bets * 100) if w_bets > 0 else 0
        window_results.append({"w": w_idx + 1, "bets": w_bets, "wins": w_wins,
                               "wr": w_wr, "pnl": w_pnl})

    wr = (total_wins / total_bets * 100) if total_bets > 0 else 0
    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0
    wrs = [w["wr"] for w in window_results if w["bets"] > 0]
    wr_std = (sum((w - sum(wrs)/len(wrs))**2 for w in wrs) / (len(wrs)-1)) ** 0.5 if len(wrs) >= 2 else 0

    return {
        "label": label, "bets": total_bets, "wins": total_wins, "wr": wr,
        "pnl": total_pnl, "wagered": total_wagered, "roi": roi, "wr_std": wr_std,
        "skips_regime": skips_regime, "skips_signal": skips_signal,
        "windows": window_results, "disagreements": disagreements,
    }


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare autocorr vs Hurst regime detection")
    parser.add_argument("--windows", type=int, default=10, help="Number of test windows")
    parser.add_argument("--fetch-fresh", action="store_true", help="Re-fetch markets from Polymarket")
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    if args.fetch_fresh:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from backtest_native import init_db, fetch_resolved_markets
        db = init_db(DB_PATH)
        end = datetime.now(timezone.utc) - timedelta(days=1)
        start = end - timedelta(days=28)
        fetch_resolved_markets(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                               window="15m", db=db)

    total = db.execute("SELECT COUNT(*) FROM markets WHERE window = '15m' AND outcome IS NOT NULL").fetchone()[0]

    if total == 0:
        print("No 15m markets in backtest DB. Run with --fetch-fresh first.")
        return

    print("=" * 72)
    print("REGIME METHOD COMPARISON: Autocorrelation vs Hurst Exponent")
    print("=" * 72)
    print("Dataset: %d resolved 15m BTC markets (28 days)" % total)
    print("Windows: %d chronological splits" % args.windows)
    print()

    # Run both methods
    r_auto = replay(db, autocorr_regime, "Autocorrelation (old)", num_windows=args.windows)
    r_hurst = replay(db, hurst_regime, "Hurst Exponent (new)", num_windows=args.windows)

    db.close()

    if not r_auto or not r_hurst:
        print("Error running replay.")
        return

    # Summary comparison
    print("-" * 72)
    print("%-30s %8s %8s" % ("Metric", "AUTOCORR", "HURST"))
    print("-" * 72)
    print("%-30s %7.1f%% %7.1f%%" % ("Win Rate", r_auto["wr"], r_hurst["wr"]))
    print("%-30s %8d %8d" % ("Total Bets", r_auto["bets"], r_hurst["bets"]))
    print("%-30s %8d %8d" % ("Wins", r_auto["wins"], r_hurst["wins"]))
    print("%-30s %+7.0f %+8.0f" % ("P&L ($)", r_auto["pnl"], r_hurst["pnl"]))
    print("%-30s %+7.1f%% %+7.1f%%" % ("ROI", r_auto["roi"], r_hurst["roi"]))
    print("%-30s %7.1f%% %7.1f%%" % ("WR Std (consistency)", r_auto["wr_std"], r_hurst["wr_std"]))
    print("%-30s %8d %8d" % ("Regime Skips", r_auto["skips_regime"], r_hurst["skips_regime"]))
    print("%-30s %8d %8d" % ("Signal Skips (no momentum)", r_auto["skips_signal"], r_hurst["skips_signal"]))

    # Delta
    print()
    print("-" * 72)
    print("IMPROVEMENT (Hurst vs Autocorr)")
    print("-" * 72)
    wr_delta = r_hurst["wr"] - r_auto["wr"]
    pnl_delta = r_hurst["pnl"] - r_auto["pnl"]
    bets_delta = r_hurst["bets"] - r_auto["bets"]
    print("  Win Rate:     %+.1f%% (%s)" % (wr_delta, "BETTER" if wr_delta > 0 else "WORSE"))
    print("  P&L:          $%+.0f (%s)" % (pnl_delta, "BETTER" if pnl_delta > 0 else "WORSE"))
    print("  More Bets:    %+d (Hurst lets more trades through)" % bets_delta)
    print("  Consistency:  %.1f%% vs %.1f%% std (%s)" % (
        r_hurst["wr_std"], r_auto["wr_std"],
        "MORE CONSISTENT" if r_hurst["wr_std"] < r_auto["wr_std"] else "LESS CONSISTENT"))

    # Disagreement analysis
    print()
    print("-" * 72)
    print("DISAGREEMENT ANALYSIS (where the methods differ)")
    print("-" * 72)
    d = r_hurst["disagreements"]
    total_decisions = sum(d.values())
    print("  Both agree TRADE:        %4d (%4.1f%%)" % (d["both_trade"], d["both_trade"]/total_decisions*100))
    print("  Both agree SKIP:         %4d (%4.1f%%)" % (d["both_skip"], d["both_skip"]/total_decisions*100))
    print("  Autocorr SKIP, Hurst OK: %4d (%4.1f%%) <-- Hurst captures these" % (
        d["autocorr_skip_hurst_trade"], d["autocorr_skip_hurst_trade"]/total_decisions*100))
    print("  Autocorr OK, Hurst SKIP: %4d (%4.1f%%) <-- Hurst blocks these" % (
        d["autocorr_trade_hurst_skip"], d["autocorr_trade_hurst_skip"]/total_decisions*100))

    # Per-window breakdown
    print()
    print("-" * 72)
    print("PER-WINDOW BREAKDOWN")
    print("-" * 72)
    print("%-8s | %-20s | %-20s | %s" % ("Window", "Autocorr", "Hurst", "Winner"))
    print("-" * 72)

    auto_wins_count = 0
    hurst_wins_count = 0
    for wa, wh in zip(r_auto["windows"], r_hurst["windows"]):
        a_str = "%d bets, %.0f%% WR, $%+.0f" % (wa["bets"], wa["wr"], wa["pnl"]) if wa["bets"] > 0 else "0 bets"
        h_str = "%d bets, %.0f%% WR, $%+.0f" % (wh["bets"], wh["wr"], wh["pnl"]) if wh["bets"] > 0 else "0 bets"

        if wh["pnl"] > wa["pnl"]:
            winner = "HURST"
            hurst_wins_count += 1
        elif wa["pnl"] > wh["pnl"]:
            winner = "AUTOCORR"
            auto_wins_count += 1
        else:
            winner = "TIE"

        print("%-8d | %-20s | %-20s | %s" % (wa["w"], a_str, h_str, winner))

    print("-" * 72)
    print("Hurst wins %d/%d windows, Autocorr wins %d/%d" % (
        hurst_wins_count, args.windows, auto_wins_count, args.windows))

    # Verdict
    print()
    print("=" * 72)
    if wr_delta > 0 and pnl_delta > 0:
        print("VERDICT: HURST IS BETTER (higher WR + better P&L)")
    elif wr_delta > 0:
        print("VERDICT: HURST HAS HIGHER WR but lower P&L - mixed result")
    elif pnl_delta > 0:
        print("VERDICT: HURST HAS BETTER P&L despite lower WR - sizing advantage")
    else:
        print("VERDICT: AUTOCORR IS BETTER on this dataset")
    print("=" * 72)


if __name__ == "__main__":
    main()
