#!/usr/bin/env python3
"""
Kelly Criterion simulation against our resolved bets.

Computes optimal bet sizing using Kelly formula, then replays
historical bets under different sizing strategies to compare
P&L, drawdown, and risk-adjusted returns.

No production code is changed. Analysis only.

Usage:
    python3 scripts/kelly_simulation.py
    python3 scripts/kelly_simulation.py --bankroll 5000
    python3 scripts/kelly_simulation.py --output docs/kelly_analysis.md
"""

import sqlite3
import argparse
import math
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "predictions.db"

# Current fixed bet sizes by conviction tier
CURRENT_TIERS = {3: 50, 4: 100, 5: 200}


def load_resolved_bets(db_path=DB_PATH):
    """Load all resolved bets (conv >= 3) with outcome data."""
    db = sqlite3.connect(str(db_path))
    rows = db.execute("""
        SELECT
            p.predicted_at,
            p.estimate,
            p.conviction_score,
            p.regime,
            m.outcome,
            m.price_yes
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE p.conviction_score >= 3
          AND m.outcome IS NOT NULL
        ORDER BY p.predicted_at
    """).fetchall()
    db.close()

    bets = []
    for row in rows:
        predicted_at, estimate, conv, regime, outcome, price_yes = row
        direction = "UP" if estimate > 0.5 else "DOWN"
        won = (estimate > 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)

        # Compute net odds from market price
        # If we bet UP at price p, we pay p and win 1 (net = 1-p), lose p
        # If we bet DOWN at price p, we pay (1-p) and win p, lose (1-p)
        if direction == "UP":
            entry_price = price_yes if price_yes else 0.5
        else:
            entry_price = (1 - price_yes) if price_yes else 0.5

        # Net odds: what we win per dollar risked
        # Pay entry_price, win (1 - entry_price) net
        net_odds = (1 - entry_price) / entry_price if entry_price > 0 else 1.0

        # Regime category
        if regime and "TRENDING" in regime:
            regime_cat = "TRENDING"
        elif regime and "NEUTRAL" in regime:
            regime_cat = "NEUTRAL"
        else:
            regime_cat = "OTHER"

        bets.append({
            "predicted_at": predicted_at,
            "direction": direction,
            "conviction": conv,
            "regime": regime_cat,
            "won": won,
            "entry_price": entry_price,
            "net_odds": net_odds,
            "price_yes": price_yes,
        })

    return bets


def kelly_fraction(win_rate, net_odds):
    """
    Full Kelly: f* = (p * b - q) / b
    where p = win probability, q = 1-p, b = net odds (win/risk ratio)
    """
    if net_odds <= 0:
        return 0.0
    q = 1 - win_rate
    f = (win_rate * net_odds - q) / net_odds
    return max(0.0, f)  # Never go negative


def compute_kelly_by_group(bets, group_key):
    """Compute Kelly fraction for each group (conviction tier, regime, etc.)."""
    groups = {}
    for b in bets:
        key = b[group_key]
        if key not in groups:
            groups[key] = {"wins": 0, "total": 0, "odds_sum": 0}
        groups[key]["total"] += 1
        groups[key]["odds_sum"] += b["net_odds"]
        if b["won"]:
            groups[key]["wins"] += 1

    results = {}
    for key, g in sorted(groups.items()):
        wr = g["wins"] / g["total"] if g["total"] > 0 else 0
        avg_odds = g["odds_sum"] / g["total"] if g["total"] > 0 else 1.0
        f_star = kelly_fraction(wr, avg_odds)
        results[key] = {
            "win_rate": wr,
            "avg_odds": avg_odds,
            "kelly_full": f_star,
            "kelly_half": f_star / 2,
            "kelly_quarter": f_star / 4,
            "bets": g["total"],
            "wins": g["wins"],
        }
    return results


def simulate_strategy(bets, sizing_fn, initial_bankroll=5000):
    """
    Replay bets with a given sizing function.
    sizing_fn(bet, bankroll) → dollar amount to wager.
    Returns dict with final bankroll, max drawdown, per-bet history.
    """
    bankroll = initial_bankroll
    peak = initial_bankroll
    max_drawdown = 0
    max_drawdown_pct = 0
    history = []
    total_wagered = 0

    for b in bets:
        wager = sizing_fn(b, bankroll)
        wager = min(wager, bankroll)  # Can't bet more than bankroll
        wager = max(0, wager)

        if wager <= 0:
            history.append({"bankroll": bankroll, "wager": 0, "pnl": 0})
            continue

        total_wagered += wager

        if b["won"]:
            pnl = wager * b["net_odds"]
        else:
            pnl = -wager

        bankroll += pnl

        if bankroll > peak:
            peak = bankroll
        drawdown = peak - bankroll
        drawdown_pct = drawdown / peak if peak > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct

        history.append({
            "bankroll": bankroll,
            "wager": wager,
            "pnl": pnl,
        })

    total_pnl = bankroll - initial_bankroll
    roi = total_pnl / initial_bankroll * 100 if initial_bankroll > 0 else 0

    # Simple Sharpe-like: mean return / stdev of returns
    returns = [h["pnl"] / h["wager"] for h in history if h["wager"] > 0]
    if len(returns) > 1:
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_ret = var ** 0.5
        sharpe = mean_ret / std_ret if std_ret > 0 else 0
    else:
        sharpe = 0

    return {
        "final_bankroll": round(bankroll, 2),
        "total_pnl": round(total_pnl, 2),
        "roi_pct": round(roi, 1),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct * 100, 1),
        "total_wagered": round(total_wagered, 2),
        "sharpe": round(sharpe, 3),
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="Kelly Criterion simulation")
    parser.add_argument("--bankroll", type=float, default=5000, help="Starting bankroll ($)")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Path to predictions DB")
    parser.add_argument("--output", type=str, default="docs/kelly_analysis.md", help="Output markdown path")
    args = parser.parse_args()

    print(f"Loading resolved bets from {args.db}...")
    bets = load_resolved_bets(args.db)
    print(f"  {len(bets)} resolved bets loaded")

    if not bets:
        print("No resolved bets found. Exiting.")
        return

    # Overall stats
    total = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / total
    avg_odds = sum(b["net_odds"] for b in bets) / total
    f_star = kelly_fraction(wr, avg_odds)

    print(f"\n{'='*60}")
    print(f"KELLY CRITERION ANALYSIS")
    print(f"{'='*60}")
    print(f"  Bets:        {total}")
    print(f"  Win rate:    {wr*100:.1f}%")
    print(f"  Avg odds:    {avg_odds:.3f} (avg net return per $1 risked)")
    print(f"  Full Kelly:  {f_star*100:.1f}% of bankroll per bet")
    print(f"  Half Kelly:  {f_star/2*100:.1f}%")
    print(f"  Quarter Kelly: {f_star/4*100:.1f}%")

    # Per-conviction Kelly
    print(f"\n--- Kelly by Conviction Tier ---")
    conv_kelly = compute_kelly_by_group(bets, "conviction")
    for key, v in conv_kelly.items():
        print(f"  Conv={key}: {v['bets']} bets, {v['win_rate']*100:.1f}% WR, "
              f"odds={v['avg_odds']:.3f}, full_kelly={v['kelly_full']*100:.1f}%")

    # Per-regime Kelly
    print(f"\n--- Kelly by Regime ---")
    regime_kelly = compute_kelly_by_group(bets, "regime")
    for key, v in regime_kelly.items():
        print(f"  {key}: {v['bets']} bets, {v['win_rate']*100:.1f}% WR, "
              f"odds={v['avg_odds']:.3f}, full_kelly={v['kelly_full']*100:.1f}%")

    # Per-direction Kelly
    print(f"\n--- Kelly by Direction ---")
    dir_kelly = compute_kelly_by_group(bets, "direction")
    for key, v in dir_kelly.items():
        print(f"  {key}: {v['bets']} bets, {v['win_rate']*100:.1f}% WR, "
              f"odds={v['avg_odds']:.3f}, full_kelly={v['kelly_full']*100:.1f}%")

    # Define sizing strategies
    bankroll = args.bankroll

    strategies = {
        "Current fixed tiers": lambda b, br: CURRENT_TIERS.get(b["conviction"], 50),
        "Full Kelly": lambda b, br: br * f_star,
        "Half Kelly": lambda b, br: br * (f_star / 2),
        "Quarter Kelly": lambda b, br: br * (f_star / 4),
        "Flat $50": lambda b, br: 50,
        "Flat $100": lambda b, br: 100,
    }

    # Conviction-aware Kelly: use per-tier Kelly fractions
    def conv_aware_kelly(b, br):
        tier = b["conviction"]
        if tier in conv_kelly:
            return br * conv_kelly[tier]["kelly_quarter"]
        return br * (f_star / 4)

    strategies["Conv-aware ¼ Kelly"] = conv_aware_kelly

    # Regime-aware Kelly: skip NEUTRAL, full send on TRENDING
    def regime_aware_kelly(b, br):
        regime = b["regime"]
        if regime in regime_kelly:
            return br * regime_kelly[regime]["kelly_quarter"]
        return br * (f_star / 4)

    strategies["Regime-aware ¼ Kelly"] = regime_aware_kelly

    # Simulate all
    print(f"\n{'='*60}")
    print(f"STRATEGY COMPARISON (starting bankroll: ${bankroll:,.0f})")
    print(f"{'='*60}")
    print(f"{'Strategy':<25} {'Final':>8} {'P&L':>9} {'ROI':>7} {'MaxDD':>7} {'DD%':>6} {'Sharpe':>7}")
    print(f"{'-'*25} {'-'*8} {'-'*9} {'-'*7} {'-'*7} {'-'*6} {'-'*7}")

    results = {}
    for name, fn in strategies.items():
        r = simulate_strategy(bets, fn, bankroll)
        results[name] = r
        print(f"{name:<25} ${r['final_bankroll']:>7,.0f} ${r['total_pnl']:>+8,.0f} "
              f"{r['roi_pct']:>+6.1f}% ${r['max_drawdown']:>6,.0f} "
              f"{r['max_drawdown_pct']:>5.1f}% {r['sharpe']:>7.3f}")

    # Write markdown output
    output_path = ROOT / args.output
    with open(output_path, "w") as f:
        f.write("# Kelly Criterion Analysis\n\n")
        f.write(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"> Dataset: {total} resolved bets from `predictions.db`\n")
        f.write(f"> Starting bankroll: ${bankroll:,.0f}\n\n")

        f.write("## Overall Kelly Fractions\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Win Rate | {wr*100:.1f}% |\n")
        f.write(f"| Avg Net Odds | {avg_odds:.3f} |\n")
        f.write(f"| Full Kelly (f*) | {f_star*100:.1f}% of bankroll |\n")
        f.write(f"| Half Kelly | {f_star/2*100:.1f}% |\n")
        f.write(f"| Quarter Kelly | {f_star/4*100:.1f}% |\n\n")

        f.write("## Kelly by Conviction Tier\n\n")
        f.write("| Tier | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |\n")
        f.write("|------|------|----|----------|------------|-------------------|\n")
        for key, v in conv_kelly.items():
            rec_dollar = bankroll * v["kelly_quarter"]
            f.write(f"| Conv={key} | {v['bets']} | {v['win_rate']*100:.1f}% | "
                    f"{v['avg_odds']:.3f} | {v['kelly_full']*100:.1f}% | "
                    f"${rec_dollar:,.0f} (={v['kelly_quarter']*100:.1f}%) |\n")

        f.write("\n## Kelly by Regime\n\n")
        f.write("| Regime | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |\n")
        f.write("|--------|------|----|----------|------------|-------------------|\n")
        for key, v in regime_kelly.items():
            rec_dollar = bankroll * v["kelly_quarter"]
            f.write(f"| {key} | {v['bets']} | {v['win_rate']*100:.1f}% | "
                    f"{v['avg_odds']:.3f} | {v['kelly_full']*100:.1f}% | "
                    f"${rec_dollar:,.0f} (={v['kelly_quarter']*100:.1f}%) |\n")

        f.write("\n## Kelly by Direction\n\n")
        f.write("| Direction | Bets | WR | Avg Odds | Full Kelly | Recommended (¼K) |\n")
        f.write("|-----------|------|----|----------|------------|-------------------|\n")
        for key, v in dir_kelly.items():
            rec_dollar = bankroll * v["kelly_quarter"]
            f.write(f"| {key} | {v['bets']} | {v['win_rate']*100:.1f}% | "
                    f"{v['avg_odds']:.3f} | {v['kelly_full']*100:.1f}% | "
                    f"${rec_dollar:,.0f} (={v['kelly_quarter']*100:.1f}%) |\n")

        f.write("\n## Strategy Comparison\n\n")
        f.write(f"Starting bankroll: **${bankroll:,.0f}** · {total} bets replayed in chronological order\n\n")
        f.write("| Strategy | Final | P&L | ROI | Max DD | DD% | Sharpe |\n")
        f.write("|----------|-------|-----|-----|--------|-----|--------|\n")
        for name, r in results.items():
            f.write(f"| {name} | ${r['final_bankroll']:,.0f} | "
                    f"${r['total_pnl']:+,.0f} | {r['roi_pct']:+.1f}% | "
                    f"${r['max_drawdown']:,.0f} | {r['max_drawdown_pct']:.1f}% | "
                    f"{r['sharpe']:.3f} |\n")

        f.write("\n## Interpretation\n\n")
        f.write("- **Full Kelly** maximizes long-run growth but has extreme drawdowns. "
                "Never use full Kelly in practice.\n")
        f.write("- **Quarter Kelly** is the standard conservative approach — captures ~75% "
                "of the growth rate with ~25% of the variance.\n")
        f.write("- **Conv-aware Kelly** sizes each bet based on that conviction tier's edge. "
                "Higher conviction = bigger bet, but only if the tier has proven edge.\n")
        f.write("- **Regime-aware Kelly** reduces or skips bets in NEUTRAL regime "
                "(where our edge is weakest) and sizes up in TRENDING.\n")
        f.write("- **Max drawdown %** is the peak-to-trough decline — this is what "
                "determines whether you can psychologically stay in the game.\n\n")

        # Recommendation
        best = min(results.items(), key=lambda x: -x[1]["total_pnl"])
        safest_profitable = min(
            [(n, r) for n, r in results.items() if r["total_pnl"] > 0],
            key=lambda x: x[1]["max_drawdown_pct"],
            default=None,
        )

        f.write("## Recommendation\n\n")
        if safest_profitable:
            n, r = safest_profitable
            f.write(f"**{n}** offers the best risk/reward tradeoff:\n")
            f.write(f"- P&L: ${r['total_pnl']:+,.0f} ({r['roi_pct']:+.1f}% ROI)\n")
            f.write(f"- Max drawdown: {r['max_drawdown_pct']:.1f}% (${r['max_drawdown']:,.0f})\n")
            f.write(f"- Sharpe: {r['sharpe']:.3f}\n\n")
        else:
            f.write("No profitable strategy found. Review edge quality before sizing up.\n\n")

        f.write("### Current vs Recommended Bet Sizes\n\n")
        f.write("| Conviction | Current | Quarter Kelly | Change |\n")
        f.write("|------------|---------|---------------|--------|\n")
        for tier in sorted(CURRENT_TIERS.keys()):
            current = CURRENT_TIERS[tier]
            if tier in conv_kelly:
                rec = bankroll * conv_kelly[tier]["kelly_quarter"]
                change = "↑" if rec > current else "↓" if rec < current else "="
                f.write(f"| {tier} | ${current} | ${rec:,.0f} | {change} |\n")
            else:
                f.write(f"| {tier} | ${current} | No data | — |\n")

        f.write(f"\n---\n*Analysis only. No production code was changed.*\n")

    print(f"\n  Report written to {output_path}")


if __name__ == "__main__":
    main()
