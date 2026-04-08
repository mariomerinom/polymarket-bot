#!/usr/bin/env python3
"""
signal_pnl.py — Read-only counterfactual P&L analysis from predictions.

Answers: "If we had bet $25 at conviction >= N on every prediction over the
last D days, assuming perfect fills at the stored market price, what would
WR and P&L look like — broken down by regime, direction, hour, and agent?"

This is the SIGNAL-quality analysis. It is intentionally decoupled from
fill quality (which lives in fill_diagnostic). Mixing the two is what
caused the live-trading loss spiral; keeping them separate is the fix.

Usage:
    python3 tools/signal_pnl.py                       # default: 30 days, conv>=3, BTC 5m
    python3 tools/signal_pnl.py --db data/predictions_eth.db --days 14
    python3 tools/signal_pnl.py --conviction 4 --bet 25
    python3 tools/signal_pnl.py --group regime,direction
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from config import POLYMARKET_FEE_FACTOR
except ImportError:
    POLYMARKET_FEE_FACTOR = 0.98


def hypothetical_pnl(direction: str, estimate: float, outcome: int,
                     price_yes: float, price_no: float, bet: float) -> float:
    """P&L assuming a $bet bet at the stored market price, fully filled."""
    if direction == "UP":
        execution_price = price_yes
        won = outcome == 1
    else:
        execution_price = price_no if price_no else round(1 - price_yes, 4)
        won = outcome == 0
    if execution_price <= 0 or execution_price >= 1:
        return 0.0  # malformed price, skip
    if won:
        return bet * (1.0 / execution_price - 1) * POLYMARKET_FEE_FACTOR
    return -bet


def hour_bucket(predicted_at: str) -> str:
    try:
        return datetime.fromisoformat(predicted_at.replace("Z", "+00:00")).strftime("%H")
    except Exception:
        return "??"


def fetch_predictions(db: sqlite3.Connection, days: int, min_conviction: int):
    """Fetch resolved predictions + whether each one became an order.

    Left-joins the orders table on prediction_id so we can distinguish
    'bet placed' (any order row exists) from 'signal-only' (skipped by
    should_trade / compute_order / book gates). This is the direct test
    for anti-selection: if skipped predictions outperform placed ones,
    our gates are choosing the wrong bets.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sql = """
        SELECT p.id, p.market_id, p.agent, p.estimate, p.regime,
               p.conviction_score, p.predicted_at,
               m.price_yes, m.price_no, m.outcome, m.resolved,
               (SELECT COUNT(*) FROM orders o WHERE o.prediction_id = p.id) AS placed
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE p.predicted_at >= ?
          AND p.conviction_score >= ?
          AND m.resolved = 1
          AND m.outcome IS NOT NULL
    """
    return db.execute(sql, (cutoff, min_conviction)).fetchall()


def analyze(rows, group_keys: list[str], bet: float):
    """Return list of (group_tuple, n, wins, wr, pnl) sorted by pnl desc."""
    buckets: dict[tuple, list] = defaultdict(list)
    for r in rows:
        direction = "UP" if r["estimate"] > 0.5 else "DOWN"
        pnl = hypothetical_pnl(
            direction, r["estimate"], r["outcome"],
            r["price_yes"], r["price_no"] or round(1 - r["price_yes"], 4),
            bet,
        )
        won = pnl > 0
        key = []
        for gk in group_keys:
            if gk == "regime":
                key.append(r["regime"] or "—")
            elif gk == "direction":
                key.append(direction)
            elif gk == "hour":
                key.append(hour_bucket(r["predicted_at"]))
            elif gk == "agent":
                key.append(r["agent"] or "—")
            elif gk == "conviction":
                key.append(str(r["conviction_score"]))
            elif gk == "placed":
                key.append("placed" if (r["placed"] or 0) > 0 else "skipped")
            else:
                key.append("?")
        buckets[tuple(key)].append((won, pnl))

    out = []
    for key, items in buckets.items():
        n = len(items)
        wins = sum(1 for w, _ in items if w)
        pnl = sum(p for _, p in items)
        out.append((key, n, wins, wins / n if n else 0, pnl))
    out.sort(key=lambda x: x[4], reverse=True)
    return out


def print_table(group_keys, results, bet):
    headers = group_keys + ["n", "wins", "wr%", "pnl$", "$/bet"]
    rows = [
        list(key) + [str(n), str(wins), f"{wr*100:.1f}", f"{pnl:+.2f}",
                     f"{pnl/n:+.2f}" if n else "—"]
        for key, n, wins, wr, pnl in results
    ]
    if not rows:
        print("(no rows)")
        return
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0))
              for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    total_n = sum(n for _, n, *_ in results)
    total_wins = sum(w for *_, w, _, _ in [(k, n, w, wr, p) for k, n, w, wr, p in results])
    total_pnl = sum(p for *_, p in results)
    print()
    print(f"TOTAL: n={total_n}  wins={total_wins}  "
          f"wr={total_wins/total_n*100:.1f}%  pnl={total_pnl:+.2f} (bet=${bet})")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/predictions.db")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--conviction", type=int, default=3,
                    help="min conviction_score (default 3)")
    ap.add_argument("--bet", type=float, default=25.0,
                    help="hypothetical bet size in dollars")
    ap.add_argument("--group", default="regime,direction",
                    help="comma-separated: regime,direction,hour,agent,conviction,placed")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = fetch_predictions(db, args.days, args.conviction)
    print(f"signal_pnl: db={args.db} days={args.days} "
          f"min_conviction={args.conviction} bet=${args.bet}")
    print(f"resolved predictions matching: {len(rows)}\n")

    group_keys = [g.strip() for g in args.group.split(",") if g.strip()]
    results = analyze(rows, group_keys, args.bet)
    print_table(group_keys, results, args.bet)
    db.close()


if __name__ == "__main__":
    main()
