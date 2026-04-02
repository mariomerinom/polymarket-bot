"""
polymarket_pnl.py — Real P&L from Polymarket Data API.

Fetches actual trading activity (fills, redeems) for our wallet and computes
real P&L from actual USDC amounts. No simulation, no conviction-based sizing.

The Data API is public (no auth needed), just requires the wallet address.
"""

import json
import os
from collections import defaultdict
from urllib.request import urlopen, Request

DATA_API = "https://data-api.polymarket.com"
WALLET_ADDRESS = os.getenv(
    "POLYMARKET_WALLET_ADDRESS",
    "0x15799480043A8b509ADA283d30667a9530594Ffb",
)


def fetch_activity(wallet=None, limit=500):
    """Fetch all trading activity for a wallet from the Polymarket Data API.

    Returns list of activity dicts with keys: conditionId, type, usdcSize,
    price, side, title, timestamp, transactionHash, etc.
    """
    wallet = wallet or WALLET_ADDRESS
    if not wallet:
        return []

    url = f"{DATA_API}/activity?user={wallet}&limit={limit}"
    req = Request(url, headers={"User-Agent": "polymarket-bot/1.0"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def compute_real_pnl(activities, our_market_titles=None):
    """Compute real P&L from Polymarket activity data.

    Groups by conditionId (each market), sums TRADE costs and REDEEM payouts.

    Args:
        activities: list of activity dicts from fetch_activity()
        our_market_titles: optional set of market question strings to filter to.
            If None, includes all activity.

    Returns dict matching compute_pnl() shape for dashboard compatibility:
        {"portfolio": {"total_pnl", "total_wagered", "num_bets", ...}}
    """
    # Group by conditionId
    markets = defaultdict(lambda: {"trades": [], "redeems": [], "title": ""})
    for a in activities:
        cid = a.get("conditionId", "")
        if not cid:
            continue
        markets[cid]["title"] = a.get("title", "")
        if a.get("type") == "TRADE":
            markets[cid]["trades"].append(a)
        elif a.get("type") == "REDEEM":
            markets[cid]["redeems"].append(a)

    # Filter to our markets if specified
    if our_market_titles:
        filtered = {}
        for cid, m in markets.items():
            title = m["title"]
            if any(title in q or q in title for q in our_market_titles):
                filtered[cid] = m
        markets = filtered

    # Compute per-bet P&L
    pnl = 0.0
    wagered = 0.0
    wins = 0
    losses = 0
    gross_wins = 0.0
    gross_losses = 0.0
    pnl_series = []
    bet_results = []
    bets_chronological = []

    for cid, m in markets.items():
        if not m["trades"]:
            continue
        cost = sum(t.get("usdcSize", 0) for t in m["trades"])
        payout = sum(r.get("usdcSize", 0) for r in m["redeems"])
        profit = payout - cost
        ts = min(t.get("timestamp", 0) for t in m["trades"])
        avg_price = sum(t.get("price", 0) for t in m["trades"]) / len(m["trades"])

        bets_chronological.append({
            "timestamp": ts,
            "cost": cost,
            "payout": payout,
            "profit": round(profit, 2),
            "price": round(avg_price, 4),
            "won": payout > 0,
            "title": m["title"],
        })

    # Sort by timestamp for correct cumulative series
    bets_chronological.sort(key=lambda b: b["timestamp"])

    for bet in bets_chronological:
        wagered += bet["cost"]
        pnl += bet["profit"]
        pnl_series.append(round(pnl, 2))

        if bet["won"]:
            wins += 1
            gross_wins += bet["profit"]
        else:
            losses += 1
            gross_losses += bet["profit"]

        bet_results.append({
            "profit": bet["profit"],
            "bet_size": round(bet["cost"], 2),
            "price": bet["price"],
            "won": bet["won"],
        })

    # Max drawdown
    peak = 0.0
    max_dd = 0.0
    for val in pnl_series:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    num_bets = wins + losses
    roi = (pnl / wagered * 100) if wagered > 0 else 0
    avg_win = (gross_wins / wins) if wins > 0 else 0
    avg_loss = (gross_losses / losses) if losses > 0 else 0

    return {
        "portfolio": {
            "total_pnl": round(pnl, 2),
            "total_wagered": round(wagered, 2),
            "num_bets": num_bets,
            "num_wins": wins,
            "num_losses": losses,
            "gross_wins": round(gross_wins, 2),
            "gross_losses": round(gross_losses, 2),
            "pnl_series": pnl_series,
            "bet_results": bet_results,
            "max_drawdown": round(max_dd, 2),
            "roi": round(roi, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "skipped": 0,
        },
    }


def fetch_real_pnl(db=None):
    """Convenience: fetch activity and compute real P&L.

    If db is provided, filters activity to markets in our database.
    """
    activities = fetch_activity()
    if not activities:
        return None

    our_titles = None
    if db:
        try:
            rows = db.execute("SELECT question FROM markets").fetchall()
            our_titles = set()
            for row in rows:
                q = row[0] if isinstance(row, (tuple, list)) else row["question"]
                our_titles.add(q)
        except Exception:
            pass

    result = compute_real_pnl(activities, our_market_titles=our_titles)
    if result.get("portfolio", {}).get("num_bets", 0) == 0:
        return None
    return result
