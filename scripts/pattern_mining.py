#!/usr/bin/env python3
"""
pattern_mining.py — Phase 2: Find the ONE profitable pattern per asset.

Sweeps candidate signals (momentum, contrarian, with/without exhaustion,
with/without regime filtering) against resolved Polymarket markets.

Backward: No pipeline files touched. Standalone script. Imports read-only from backtest_native.
Present: Test all signal variants per asset, find best WR on 50+ bets.
Future: Surfaces in docs/pattern_mining_results.md. GO/NO-GO gate for Phase 3.

Usage:
    python3 scripts/pattern_mining.py --asset Solana --days 30
    python3 scripts/pattern_mining.py --asset Ethereum --days 30
    python3 scripts/pattern_mining.py --asset Bitcoin --days 30  # baseline
    python3 scripts/pattern_mining.py --all --days 30  # all three
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import from our codebase (read-only)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from backtest_native import native_regime

# Reuse the fetch function from outcome_analysis (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from outcome_analysis import fetch_resolved_markets


# ── Signal Variants ──────────────────────────────────────────────────

def signal_momentum(outcomes, volumes, min_streak=3):
    """Ride the streak (predict same direction as streak)."""
    streak_dir, streak_len = _get_streak(outcomes)
    if streak_len < min_streak:
        return None
    return {"direction": streak_dir, "type": "momentum", "streak": streak_len}


def signal_contrarian(outcomes, volumes, min_streak=3):
    """Fade the streak (predict opposite direction)."""
    streak_dir, streak_len = _get_streak(outcomes)
    if streak_len < min_streak:
        return None
    opp = "DOWN" if streak_dir == "UP" else "UP"
    return {"direction": opp, "type": "contrarian", "streak": streak_len}


def signal_momentum_exhaustion(outcomes, volumes, min_streak=3):
    """Momentum + at least 1 exhaustion signal."""
    streak_dir, streak_len = _get_streak(outcomes)
    if streak_len < min_streak:
        return None
    if not _has_exhaustion(outcomes, volumes):
        return None
    return {"direction": streak_dir, "type": "momentum+exhaust", "streak": streak_len}


def signal_contrarian_exhaustion(outcomes, volumes, min_streak=3):
    """Contrarian + at least 1 exhaustion signal."""
    streak_dir, streak_len = _get_streak(outcomes)
    if streak_len < min_streak:
        return None
    if not _has_exhaustion(outcomes, volumes):
        return None
    opp = "DOWN" if streak_dir == "UP" else "UP"
    return {"direction": opp, "type": "contrarian+exhaust", "streak": streak_len}


def signal_post_break_momentum(outcomes, volumes, min_streak=2):
    """After a streak breaks, ride the NEW direction."""
    if len(outcomes) < min_streak + 2:
        return None
    # Check: was there a streak that just broke?
    # i.e., outcomes[-2] broke from a prior streak, and outcomes[-1] continues the break direction
    curr_dir = "UP" if outcomes[-1] == 1 else "DOWN"
    prev_dir = "UP" if outcomes[-2] == 1 else "DOWN"
    if curr_dir != prev_dir:
        return None  # Not continuing yet

    # Check there was an opposite streak before the break
    break_point = len(outcomes) - 2
    opp_dir = "DOWN" if curr_dir == "UP" else "UP"
    opp_streak = 0
    for i in range(break_point - 1, -1, -1):
        d = "UP" if outcomes[i] == 1 else "DOWN"
        if d == opp_dir:
            opp_streak += 1
        else:
            break

    if opp_streak < min_streak:
        return None  # No significant prior streak to break from

    return {"direction": curr_dir, "type": "post_break", "streak": opp_streak}


def signal_market_lean(outcomes, volumes, prices, threshold=0.45):
    """
    Lean with the market: if market prices UP below threshold, bet DOWN.
    If market prices UP above (1-threshold), bet UP.
    Tests whether the market's pricing is a useful signal.
    """
    if not prices or len(prices) < 1:
        return None
    last_price = prices[-1]
    if last_price < threshold:
        return {"direction": "DOWN", "type": f"market_lean_{threshold}", "streak": 0}
    elif last_price > (1 - threshold):
        return {"direction": "UP", "type": f"market_lean_{threshold}", "streak": 0}
    return None  # Price in no-signal zone


# ── Helpers ──────────────────────────────────────────────────────────

def _get_streak(outcomes):
    """Count consecutive streak from end. Returns (direction, length)."""
    if not outcomes:
        return "UP", 0
    last_dir = "UP" if outcomes[-1] == 1 else "DOWN"
    streak = 1
    for i in range(len(outcomes) - 2, -1, -1):
        d = "UP" if outcomes[i] == 1 else "DOWN"
        if d == last_dir:
            streak += 1
        else:
            break
    return last_dir, streak


def _has_exhaustion(outcomes, volumes):
    """Check for exhaustion signals (same logic as native backtester)."""
    exhaustion = False

    # 1. Volume spike: last > 1.8x avg of last 5
    if len(volumes) >= 5:
        avg_vol = sum(volumes[-5:]) / 5
        if avg_vol > 0 and volumes[-1] / avg_vol > 1.8:
            exhaustion = True

    # 2. Volume decline: last 3 declining
    if len(volumes) >= 3:
        if volumes[-3] > volumes[-2] > volumes[-1] and volumes[-1] > 0:
            exhaustion = True

    # 3. Outcome compression: last 3 outcomes converging (alternating = compressing)
    if len(outcomes) >= 5:
        recent = outcomes[-5:]
        flips = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        if flips >= 3:  # High choppiness in last 5 = compressed/uncertain
            exhaustion = True

    return exhaustion


# ── Main Mining Engine ───────────────────────────────────────────────

def mine_patterns(markets, asset, lookback=20):
    """
    Run all signal variants against resolved markets.
    Returns dict of pattern → {bets, wins, wr, by_regime, by_direction}.
    """
    if len(markets) < lookback + 10:
        return {"error": f"Only {len(markets)} markets, need at least {lookback + 10}"}

    outcomes_window = []
    volumes_window = []

    # All signal variants to test
    signal_configs = []
    for min_streak in [2, 3, 4, 5]:
        signal_configs.append({
            "name": f"momentum_s{min_streak}",
            "fn": signal_momentum,
            "kwargs": {"min_streak": min_streak},
        })
        signal_configs.append({
            "name": f"contrarian_s{min_streak}",
            "fn": signal_contrarian,
            "kwargs": {"min_streak": min_streak},
        })
        signal_configs.append({
            "name": f"momentum_exhaust_s{min_streak}",
            "fn": signal_momentum_exhaustion,
            "kwargs": {"min_streak": min_streak},
        })
        signal_configs.append({
            "name": f"contrarian_exhaust_s{min_streak}",
            "fn": signal_contrarian_exhaustion,
            "kwargs": {"min_streak": min_streak},
        })

    # Post-break signals
    for min_streak in [2, 3, 4]:
        signal_configs.append({
            "name": f"post_break_s{min_streak}",
            "fn": signal_post_break_momentum,
            "kwargs": {"min_streak": min_streak},
        })

    # Results tracking
    results = {}
    for cfg in signal_configs:
        results[cfg["name"]] = {
            "bets": 0, "wins": 0,
            "regime_bets": defaultdict(int),
            "regime_wins": defaultdict(int),
            "dir_bets": defaultdict(int),
            "dir_wins": defaultdict(int),
            "regime_skip_would_bet": 0,
            "regime_skip_would_win": 0,
        }

    # Also track regime-filtered versions
    for cfg in signal_configs:
        results[cfg["name"] + "_RF"] = {
            "bets": 0, "wins": 0,
            "regime_bets": defaultdict(int),
            "regime_wins": defaultdict(int),
            "dir_bets": defaultdict(int),
            "dir_wins": defaultdict(int),
        }

    evaluated = 0

    for m in markets:
        outcome = m["outcome"]
        volume = m["volume"]

        if len(outcomes_window) < lookback:
            outcomes_window.append(outcome)
            volumes_window.append(volume)
            continue

        evaluated += 1
        context_outcomes = outcomes_window[-lookback:]
        context_volumes = volumes_window[-lookback:]

        # Compute regime
        regime = native_regime(context_outcomes)
        regime_label = regime["label"]
        is_mr = regime["is_mean_reverting"]

        for cfg in signal_configs:
            sig = cfg["fn"](context_outcomes, context_volumes, **cfg["kwargs"])

            if sig is not None:
                direction = sig["direction"]
                correct = (direction == "UP" and outcome == 1) or \
                          (direction == "DOWN" and outcome == 0)

                # Unfiltered
                r = results[cfg["name"]]
                r["bets"] += 1
                if correct:
                    r["wins"] += 1
                r["regime_bets"][regime_label] += 1
                if correct:
                    r["regime_wins"][regime_label] += 1
                r["dir_bets"][direction] += 1
                if correct:
                    r["dir_wins"][direction] += 1

                # Regime-filtered version
                if is_mr:
                    r["regime_skip_would_bet"] += 1
                    if correct:
                        r["regime_skip_would_win"] += 1
                else:
                    rf = results[cfg["name"] + "_RF"]
                    rf["bets"] += 1
                    if correct:
                        rf["wins"] += 1
                    rf["regime_bets"][regime_label] += 1
                    if correct:
                        rf["regime_wins"][regime_label] += 1
                    rf["dir_bets"][direction] += 1
                    if correct:
                        rf["dir_wins"][direction] += 1

        outcomes_window.append(outcome)
        volumes_window.append(volume)

    print(f"  Evaluated {evaluated} markets for {asset}")

    # Compile final results
    compiled = {}
    for name, r in results.items():
        if r["bets"] == 0:
            continue
        wr = round(r["wins"] / r["bets"] * 100, 1)
        entry = {
            "bets": r["bets"],
            "wins": r["wins"],
            "wr": wr,
            "by_regime": {},
            "by_direction": {},
        }
        for reg, cnt in r["regime_bets"].items():
            w = r["regime_wins"].get(reg, 0)
            entry["by_regime"][reg] = {
                "bets": cnt, "wins": w,
                "wr": round(w / cnt * 100, 1) if cnt else 0,
            }
        for d, cnt in r["dir_bets"].items():
            w = r["dir_wins"].get(d, 0)
            entry["by_direction"][d] = {
                "bets": cnt, "wins": w,
                "wr": round(w / cnt * 100, 1) if cnt else 0,
            }
        # Track regime-skip stats for unfiltered versions
        if "regime_skip_would_bet" in r and r["regime_skip_would_bet"] > 0:
            skip_bets = r["regime_skip_would_bet"]
            skip_wins = r["regime_skip_would_win"]
            entry["regime_skip"] = {
                "bets": skip_bets,
                "wr": round(skip_wins / skip_bets * 100, 1),
            }
        compiled[name] = entry

    return {"asset": asset, "evaluated": evaluated, "patterns": compiled}


def format_report(all_results):
    """Format multi-asset pattern mining results as markdown."""
    lines = []
    lines.append("# Pattern Mining Results — Phase 2")
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    for result in all_results:
        asset = result["asset"]
        lines.append(f"## {asset}")
        lines.append(f"\n**Markets evaluated:** {result['evaluated']}")
        lines.append("")

        if "error" in result:
            lines.append(f"**Error:** {result['error']}")
            lines.append("")
            continue

        patterns = result["patterns"]

        # Sort by WR descending, only show patterns with 30+ bets
        viable = [(name, p) for name, p in patterns.items() if p["bets"] >= 30]
        viable.sort(key=lambda x: x[1]["wr"], reverse=True)

        # Top-level comparison table
        lines.append("### All Patterns (≥ 30 bets)")
        lines.append("")
        lines.append("| Pattern | Bets | Wins | WR | vs 50% |")
        lines.append("|---------|------|------|-----|--------|")
        for name, p in viable:
            delta = f"+{p['wr'] - 50:.1f}pp" if p["wr"] >= 50 else f"{p['wr'] - 50:.1f}pp"
            marker = " **" if p["wr"] >= 54 else ""
            lines.append(f"| {name}{marker} | {p['bets']} | {p['wins']} | {p['wr']}% | {delta} |")
        lines.append("")

        # Top 5 breakdown
        top5 = viable[:5]
        for name, p in top5:
            lines.append(f"### {name} — {p['wr']}% WR ({p['bets']} bets)")
            lines.append("")

            # By direction
            if p["by_direction"]:
                lines.append("**By Direction:**")
                lines.append("")
                lines.append("| Direction | Bets | WR |")
                lines.append("|-----------|------|-----|")
                for d, stats in sorted(p["by_direction"].items()):
                    lines.append(f"| {d} | {stats['bets']} | {stats['wr']}% |")
                lines.append("")

            # By regime (top regimes only)
            if p["by_regime"]:
                lines.append("**By Regime:**")
                lines.append("")
                lines.append("| Regime | Bets | WR |")
                lines.append("|--------|------|-----|")
                sorted_regimes = sorted(p["by_regime"].items(), key=lambda x: x[1]["bets"], reverse=True)
                for reg, stats in sorted_regimes[:6]:
                    marker = " ***" if stats["wr"] >= 58 and stats["bets"] >= 15 else ""
                    lines.append(f"| {reg}{marker} | {stats['bets']} | {stats['wr']}% |")
                lines.append("")

            # Regime skip impact
            if "regime_skip" in p:
                skip = p["regime_skip"]
                lines.append(f"*Regime-filtered version skips {skip['bets']} bets at {skip['wr']}% WR in mean-reverting regimes.*")
                lines.append("")

    # Cross-asset summary
    lines.append("---")
    lines.append("")
    lines.append("## Cross-Asset Summary")
    lines.append("")
    lines.append("| Asset | Best Pattern | WR | Bets | Best Regime-Filtered | RF WR | RF Bets |")
    lines.append("|-------|-------------|-----|------|---------------------|-------|---------|")

    for result in all_results:
        if "error" in result:
            continue
        asset = result["asset"]
        patterns = result["patterns"]

        # Best unfiltered
        best_name, best_p = max(
            [(n, p) for n, p in patterns.items() if p["bets"] >= 30 and "_RF" not in n],
            key=lambda x: x[1]["wr"],
            default=("none", {"wr": 0, "bets": 0}),
        )

        # Best regime-filtered
        best_rf_name, best_rf_p = max(
            [(n, p) for n, p in patterns.items() if p["bets"] >= 30 and "_RF" in n],
            key=lambda x: x[1]["wr"],
            default=("none", {"wr": 0, "bets": 0}),
        )

        lines.append(
            f"| {asset} | {best_name} | {best_p['wr']}% | {best_p['bets']} "
            f"| {best_rf_name} | {best_rf_p['wr']}% | {best_rf_p['bets']} |"
        )

    lines.append("")

    # Decision gate
    lines.append("## Decision Gate")
    lines.append("")
    lines.append("| Asset | Best Pattern | WR | Bets | Verdict |")
    lines.append("|-------|-------------|-----|------|---------|")
    for result in all_results:
        if "error" in result:
            continue
        asset = result["asset"]
        patterns = result["patterns"]
        best_name, best_p = max(
            [(n, p) for n, p in patterns.items() if p["bets"] >= 50],
            key=lambda x: x[1]["wr"],
            default=("none", {"wr": 0, "bets": 0}),
        )
        if best_p["wr"] >= 55:
            verdict = "**GO** → Phase 3 paper trading"
        elif best_p["wr"] >= 52:
            verdict = "MARGINAL — needs more data or regime tuning"
        else:
            verdict = "NO-GO — no pattern beats 52%"
        lines.append(f"| {asset} | {best_name} | {best_p['wr']}% | {best_p['bets']} | {verdict} |")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Pattern mining for Polymarket markets")
    parser.add_argument("--asset", type=str, default=None,
                        help="Asset name (Bitcoin, Solana, Ethereum)")
    parser.add_argument("--all", action="store_true",
                        help="Run all three assets")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to analyze")
    parser.add_argument("--window", type=str, default="5m",
                        help="Market window (5m or 15m)")
    args = parser.parse_args()

    if not args.asset and not args.all:
        print("Specify --asset <name> or --all")
        sys.exit(1)

    assets = ["Bitcoin", "Solana", "Ethereum"] if args.all else [args.asset]

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    all_results = []
    for asset in assets:
        print(f"\n{'='*60}")
        print(f"Mining patterns for {asset}...")
        print(f"{'='*60}")

        markets = fetch_resolved_markets(start_date, end_date, window=args.window, asset=asset)
        if not markets:
            print(f"No resolved {asset} markets found.")
            all_results.append({"asset": asset, "error": "no markets found", "evaluated": 0, "patterns": {}})
            continue

        result = mine_patterns(markets, asset)
        all_results.append(result)

        # Print top patterns for this asset
        if "patterns" in result:
            viable = [(n, p) for n, p in result["patterns"].items() if p["bets"] >= 30]
            viable.sort(key=lambda x: x[1]["wr"], reverse=True)
            print(f"\n  Top 5 patterns for {asset}:")
            for name, p in viable[:5]:
                print(f"    {name}: {p['wr']}% WR on {p['bets']} bets")

    # Write reports
    report = format_report(all_results)
    out_path = Path(__file__).parent.parent / "docs" / "pattern_mining_results.md"
    out_path.write_text(report)
    print(f"\nReport written to {out_path}")

    # JSON data
    json_path = Path(__file__).parent.parent / "data" / "pattern_mining_results.json"
    # Convert defaultdicts to regular dicts for JSON serialization
    serializable = []
    for r in all_results:
        sr = dict(r)
        if "patterns" in sr:
            sp = {}
            for name, p in sr["patterns"].items():
                pp = dict(p)
                pp["by_regime"] = dict(pp.get("by_regime", {}))
                pp["by_direction"] = dict(pp.get("by_direction", {}))
                sp[name] = pp
            sr["patterns"] = sp
        serializable.append(sr)
    json_path.write_text(json.dumps(serializable, indent=2))
    print(f"JSON data written to {json_path}")

    print("\n" + "=" * 60)
    print(report)


if __name__ == "__main__":
    main()
