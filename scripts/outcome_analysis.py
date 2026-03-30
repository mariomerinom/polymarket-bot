#!/usr/bin/env python3
"""
outcome_analysis.py — Raw outcome analysis for Polymarket "Up or Down" markets.

Phase 1 of first-principles signal discovery for SOL/ETH.
Analyzes resolved market outcomes WITHOUT any signal assumptions.

Backward: No pipeline files touched. Standalone script.
Present: Compute base rates, streak distributions, autocorrelation, time-of-day patterns.
Future: Surfaces in docs/outcome_analysis_{asset}.md. Enables Phase 2 pattern mining.

Usage:
    python3 scripts/outcome_analysis.py --asset Solana --days 30
    python3 scripts/outcome_analysis.py --asset Ethereum --days 30
    python3 scripts/outcome_analysis.py --asset Bitcoin --days 30  # baseline comparison
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

GAMMA_API = "https://gamma-api.polymarket.com"


def fetch_resolved_markets(start_date, end_date, window="5m", asset="Bitcoin"):
    """
    Fetch resolved "Up or Down" markets from Gamma API.
    Returns list of dicts with id, question, end_date, volume, outcome, price_yes.
    """
    target_seconds = 300 if window == "5m" else 900
    offset = 0
    limit = 500
    all_markets = []

    print(f"Fetching resolved {window} {asset} markets from {start_date} to {end_date}...")

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "order": "endDate",
            "ascending": "true",
            "closed": "true",
            "end_date_min": f"{start_date}T00:00:00Z",
            "end_date_max": f"{end_date}T23:59:59Z",
        }

        try:
            resp = requests.get(f"{GAMMA_API}/markets", params=params, timeout=30)
            resp.raise_for_status()
            markets = resp.json()
        except Exception as e:
            print(f"  API error at offset {offset}: {e}")
            break

        if not markets:
            break

        for m in markets:
            question = m.get("question", "")
            if asset not in question or "Up or Down" not in question:
                continue

            # Check window size
            window_secs = _parse_window(question)
            if window_secs != target_seconds:
                continue

            # Must be resolved
            raw_prices = m.get("outcomePrices", "")
            if not raw_prices:
                continue
            try:
                if isinstance(raw_prices, str):
                    prices = json.loads(raw_prices)
                else:
                    prices = raw_prices
                price_up = float(prices[0])
            except (json.JSONDecodeError, ValueError, IndexError):
                continue

            if price_up > 0.9:
                outcome = 1  # UP
            elif price_up < 0.1:
                outcome = 0  # DOWN
            else:
                continue  # Not fully resolved

            volume = float(m.get("volume", 0) or 0)
            end_date_val = m.get("endDate") or m.get("end_date_iso", "")

            all_markets.append({
                "id": m["id"],
                "question": question,
                "end_date": end_date_val,
                "volume": volume,
                "outcome": outcome,
            })

        if len(markets) < limit:
            break

        offset += limit
        time.sleep(0.05)

    # Sort by end_date for chronological analysis
    all_markets.sort(key=lambda x: x["end_date"])
    print(f"  Total: {len(all_markets)} resolved {asset} {window} markets")
    return all_markets


def _parse_window(question):
    """Parse time window from market question. Returns seconds."""
    import re
    match = re.search(r"(\d{1,2}):(\d{2})(AM|PM)\s*-\s*(\d{1,2}):(\d{2})(AM|PM)", question)
    if not match:
        return 0

    def to_minutes(h, m, ampm):
        h = int(h)
        m = int(m)
        if ampm == "PM" and h != 12:
            h += 12
        if ampm == "AM" and h == 12:
            h = 0
        return h * 60 + m

    start_mins = to_minutes(match.group(1), match.group(2), match.group(3))
    end_mins = to_minutes(match.group(4), match.group(5), match.group(6))
    diff = end_mins - start_mins
    if diff < 0:
        diff += 24 * 60
    return diff * 60


def analyze_outcomes(markets, asset):
    """Compute all outcome statistics."""
    if len(markets) < 10:
        return {"error": f"Only {len(markets)} markets — insufficient data"}

    outcomes = [m["outcome"] for m in markets]
    n = len(outcomes)

    # ── Base Rate ──
    up_count = sum(outcomes)
    down_count = n - up_count
    base_rate_up = up_count / n * 100

    # ── Streak Distribution ──
    streaks = []
    current_dir = outcomes[0]
    current_len = 1
    for i in range(1, n):
        if outcomes[i] == current_dir:
            current_len += 1
        else:
            streaks.append((current_dir, current_len))
            current_dir = outcomes[i]
            current_len = 1
    streaks.append((current_dir, current_len))

    streak_dist = Counter()
    for _, length in streaks:
        streak_dist[min(length, 8)] += 1  # cap at 8+

    up_streaks = [l for d, l in streaks if d == 1]
    down_streaks = [l for d, l in streaks if d == 0]

    # ── Autocorrelation (lag-1 through lag-5) ──
    autocorrs = {}
    for lag in range(1, 6):
        if n <= lag:
            break
        mean_o = sum(outcomes) / n
        var = sum((o - mean_o) ** 2 for o in outcomes) / n
        if var == 0:
            autocorrs[lag] = 0.0
            continue
        cov = sum(
            (outcomes[i] - mean_o) * (outcomes[i - lag] - mean_o)
            for i in range(lag, n)
        ) / (n - lag)
        autocorrs[lag] = round(cov / var, 4)

    # ── Time-of-Day Analysis ──
    hour_stats = defaultdict(lambda: {"total": 0, "up": 0})
    for m in markets:
        try:
            dt = datetime.fromisoformat(m["end_date"].replace("Z", "+00:00"))
            hour = dt.hour
            hour_stats[hour]["total"] += 1
            hour_stats[hour]["up"] += m["outcome"]
        except (ValueError, AttributeError):
            continue

    # ── Transition Probabilities ──
    # P(UP | prev was UP), P(UP | prev was DOWN), etc.
    transitions = {"up_after_up": 0, "down_after_up": 0, "up_after_down": 0, "down_after_down": 0}
    for i in range(1, n):
        prev = outcomes[i - 1]
        curr = outcomes[i]
        if prev == 1 and curr == 1:
            transitions["up_after_up"] += 1
        elif prev == 1 and curr == 0:
            transitions["down_after_up"] += 1
        elif prev == 0 and curr == 1:
            transitions["up_after_down"] += 1
        else:
            transitions["down_after_down"] += 1

    total_after_up = transitions["up_after_up"] + transitions["down_after_up"]
    total_after_down = transitions["up_after_down"] + transitions["down_after_down"]

    p_up_after_up = transitions["up_after_up"] / total_after_up * 100 if total_after_up else 0
    p_up_after_down = transitions["up_after_down"] / total_after_down * 100 if total_after_down else 0

    # ── Streak Outcome Prediction ──
    # After a streak of N same direction, what happens next?
    streak_predictions = {}
    for streak_len in [2, 3, 4, 5]:
        momentum_correct = 0  # streak continues
        contrarian_correct = 0  # streak breaks
        total = 0

        for i in range(streak_len, n):
            # Check if there was a streak of streak_len ending at i-1
            streak_ok = True
            direction = outcomes[i - 1]
            for j in range(i - streak_len, i):
                if outcomes[j] != direction:
                    streak_ok = False
                    break
            if not streak_ok:
                continue

            total += 1
            next_outcome = outcomes[i]
            if next_outcome == direction:
                momentum_correct += 1
            else:
                contrarian_correct += 1

        if total >= 10:
            streak_predictions[streak_len] = {
                "total": total,
                "momentum_wr": round(momentum_correct / total * 100, 1),
                "contrarian_wr": round(contrarian_correct / total * 100, 1),
            }

    # ── Volume analysis ──
    volumes = [m["volume"] for m in markets if m["volume"] > 0]
    avg_volume = statistics.mean(volumes) if volumes else 0
    median_volume = statistics.median(volumes) if volumes else 0

    return {
        "asset": asset,
        "total_markets": n,
        "base_rate": {
            "up_count": up_count,
            "down_count": down_count,
            "up_pct": round(base_rate_up, 1),
            "down_pct": round(100 - base_rate_up, 1),
        },
        "streaks": {
            "distribution": dict(sorted(streak_dist.items())),
            "avg_up_streak": round(statistics.mean(up_streaks), 2) if up_streaks else 0,
            "avg_down_streak": round(statistics.mean(down_streaks), 2) if down_streaks else 0,
            "max_up_streak": max(up_streaks) if up_streaks else 0,
            "max_down_streak": max(down_streaks) if down_streaks else 0,
        },
        "autocorrelation": autocorrs,
        "transitions": {
            "p_up_after_up": round(p_up_after_up, 1),
            "p_up_after_down": round(p_up_after_down, 1),
            "p_continuation": round((transitions["up_after_up"] + transitions["down_after_down"]) / (n - 1) * 100, 1),
            "p_reversal": round((transitions["down_after_up"] + transitions["up_after_down"]) / (n - 1) * 100, 1),
        },
        "streak_predictions": streak_predictions,
        "time_of_day": {
            h: {"total": s["total"], "up_pct": round(s["up"] / s["total"] * 100, 1) if s["total"] else 0}
            for h, s in sorted(hour_stats.items())
        },
        "volume": {
            "avg": round(avg_volume, 2),
            "median": round(median_volume, 2),
        },
    }


def format_report(analysis):
    """Format analysis as markdown."""
    if "error" in analysis:
        return f"# Outcome Analysis — {analysis.get('asset', 'Unknown')}\n\n**Error:** {analysis['error']}\n"

    a = analysis
    lines = []
    lines.append(f"# Outcome Analysis — {a['asset']}")
    lines.append(f"\n**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Markets analyzed:** {a['total_markets']}")
    lines.append("")

    # Base Rate
    lines.append("## Base Rate")
    lines.append("")
    lines.append(f"| Direction | Count | % |")
    lines.append(f"|-----------|-------|---|")
    lines.append(f"| UP | {a['base_rate']['up_count']} | {a['base_rate']['up_pct']}% |")
    lines.append(f"| DOWN | {a['base_rate']['down_count']} | {a['base_rate']['down_pct']}% |")
    lines.append("")
    bias = "neutral"
    if a['base_rate']['up_pct'] > 52:
        bias = "UP bias"
    elif a['base_rate']['up_pct'] < 48:
        bias = "DOWN bias"
    lines.append(f"**Assessment:** {bias} ({a['base_rate']['up_pct']}% UP)")
    lines.append("")

    # Autocorrelation
    lines.append("## Autocorrelation Profile")
    lines.append("")
    lines.append("| Lag | Autocorrelation | Interpretation |")
    lines.append("|-----|----------------|----------------|")
    for lag, ac in a["autocorrelation"].items():
        if ac > 0.15:
            interp = "TRENDING (momentum)"
        elif ac < -0.15:
            interp = "MEAN-REVERTING (contrarian)"
        else:
            interp = "NEUTRAL (no pattern)"
        lines.append(f"| {lag} | {ac:+.4f} | {interp} |")
    lines.append("")

    lag1 = a["autocorrelation"].get(1, 0)
    if lag1 > 0.10:
        lines.append(f"**Key finding:** Positive lag-1 autocorrelation ({lag1:+.4f}) suggests momentum signal may work.")
    elif lag1 < -0.10:
        lines.append(f"**Key finding:** Negative lag-1 autocorrelation ({lag1:+.4f}) suggests contrarian signal may work.")
    else:
        lines.append(f"**Key finding:** Near-zero lag-1 autocorrelation ({lag1:+.4f}) — no obvious directional persistence.")
    lines.append("")

    # Transition Probabilities
    lines.append("## Transition Probabilities")
    lines.append("")
    lines.append(f"| After | P(next UP) | P(next DOWN) |")
    lines.append(f"|-------|-----------|-------------|")
    lines.append(f"| UP | {a['transitions']['p_up_after_up']}% | {round(100 - a['transitions']['p_up_after_up'], 1)}% |")
    lines.append(f"| DOWN | {a['transitions']['p_up_after_down']}% | {round(100 - a['transitions']['p_up_after_down'], 1)}% |")
    lines.append("")
    lines.append(f"- **Continuation rate:** {a['transitions']['p_continuation']}%")
    lines.append(f"- **Reversal rate:** {a['transitions']['p_reversal']}%")
    lines.append("")

    # Streak Distribution
    lines.append("## Streak Distribution")
    lines.append("")
    lines.append(f"| Streak Length | Count | % of All Streaks |")
    lines.append(f"|--------------|-------|-----------------|")
    total_streaks = sum(a["streaks"]["distribution"].values())
    for length, count in sorted(a["streaks"]["distribution"].items()):
        label = f"{length}+" if length == 8 else str(length)
        pct = round(count / total_streaks * 100, 1) if total_streaks else 0
        lines.append(f"| {label} | {count} | {pct}% |")
    lines.append("")
    lines.append(f"- Avg UP streak: {a['streaks']['avg_up_streak']} | Max: {a['streaks']['max_up_streak']}")
    lines.append(f"- Avg DOWN streak: {a['streaks']['avg_down_streak']} | Max: {a['streaks']['max_down_streak']}")
    lines.append("")

    # Streak Predictions (momentum vs contrarian at each streak length)
    lines.append("## Signal Candidates: Momentum vs Contrarian by Streak Length")
    lines.append("")
    lines.append("After a streak of N, what happens next?")
    lines.append("")
    lines.append(f"| Streak ≥ N | Occurrences | Momentum WR | Contrarian WR | Better Signal |")
    lines.append(f"|-----------|-------------|-------------|---------------|---------------|")
    for streak_len, data in sorted(a["streak_predictions"].items()):
        better = "MOMENTUM" if data["momentum_wr"] > data["contrarian_wr"] else "CONTRARIAN"
        if abs(data["momentum_wr"] - data["contrarian_wr"]) < 3:
            better = "NEITHER (< 3pp gap)"
        lines.append(f"| ≥ {streak_len} | {data['total']} | {data['momentum_wr']}% | {data['contrarian_wr']}% | {better} |")
    lines.append("")

    # Time of Day
    lines.append("## Time-of-Day Pattern (UTC)")
    lines.append("")
    lines.append(f"| UTC Hour | Markets | UP % | Dead Zone? |")
    lines.append(f"|----------|---------|------|-----------|")
    for hour, stats in sorted(a["time_of_day"].items()):
        dead = ""
        if stats["total"] >= 8:
            if stats["up_pct"] > 65 or stats["up_pct"] < 35:
                dead = "SKEWED"
        lines.append(f"| {hour:02d} | {stats['total']} | {stats['up_pct']}% | {dead} |")
    lines.append("")

    # Volume
    lines.append("## Volume Profile")
    lines.append("")
    lines.append(f"- Average volume: ${a['volume']['avg']:.0f}")
    lines.append(f"- Median volume: ${a['volume']['median']:.0f}")
    lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append("## Summary & Next Steps")
    lines.append("")

    # Auto-generate recommendations
    recs = []
    if lag1 > 0.10:
        recs.append(f"- Positive autocorrelation ({lag1:+.4f}) → **test momentum signal** (ride streaks)")
    elif lag1 < -0.10:
        recs.append(f"- Negative autocorrelation ({lag1:+.4f}) → **test contrarian signal** (fade streaks)")
    else:
        recs.append(f"- Near-zero autocorrelation ({lag1:+.4f}) → **no obvious directional edge** from streak-following alone")

    best_streak = None
    best_wr = 0
    best_type = ""
    for streak_len, data in a["streak_predictions"].items():
        if data["momentum_wr"] > best_wr and data["total"] >= 30:
            best_wr = data["momentum_wr"]
            best_streak = streak_len
            best_type = "momentum"
        if data["contrarian_wr"] > best_wr and data["total"] >= 30:
            best_wr = data["contrarian_wr"]
            best_streak = streak_len
            best_type = "contrarian"

    if best_streak and best_wr > 52:
        recs.append(f"- Best raw signal: **{best_type} at streak ≥ {best_streak}** ({best_wr}% WR on {a['streak_predictions'][best_streak]['total']} occurrences)")
    else:
        recs.append(f"- No streak-based signal exceeds 52% WR on 30+ occurrences")

    cont_rate = a['transitions']['p_continuation']
    if cont_rate > 53:
        recs.append(f"- Continuation rate {cont_rate}% → market tends to persist (momentum-friendly)")
    elif cont_rate < 47:
        recs.append(f"- Continuation rate {cont_rate}% → market tends to reverse (contrarian-friendly)")
    else:
        recs.append(f"- Continuation rate {cont_rate}% → near 50/50 (no clear directional persistence)")

    for rec in recs:
        lines.append(rec)

    lines.append("")
    lines.append(f"**Decision gate:** Proceed to Phase 2 (pattern mining) if any signal candidate shows WR > 52% on 50+ occurrences.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Outcome analysis for Polymarket markets")
    parser.add_argument("--asset", type=str, default="Bitcoin",
                        help="Asset name (Bitcoin, Solana, Ethereum)")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days to analyze")
    parser.add_argument("--window", type=str, default="5m",
                        help="Market window (5m or 15m)")
    args = parser.parse_args()

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")

    # Fetch markets
    markets = fetch_resolved_markets(start_date, end_date, window=args.window, asset=args.asset)

    if not markets:
        print(f"No resolved {args.asset} markets found in the last {args.days} days.")
        sys.exit(1)

    # Analyze
    analysis = analyze_outcomes(markets, args.asset)

    # Format and write report
    report = format_report(analysis)
    asset_lower = args.asset.lower()
    out_path = Path(__file__).parent.parent / "docs" / f"outcome_analysis_{asset_lower}.md"
    out_path.write_text(report)
    print(f"\nReport written to {out_path}")

    # Also print to stdout
    print("\n" + "=" * 60)
    print(report)

    # Print JSON summary for programmatic use
    json_path = Path(__file__).parent.parent / "data" / f"outcome_analysis_{asset_lower}.json"
    json_path.write_text(json.dumps(analysis, indent=2))
    print(f"JSON data written to {json_path}")


if __name__ == "__main__":
    main()
