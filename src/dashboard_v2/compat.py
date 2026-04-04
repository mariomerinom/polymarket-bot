"""Backward-compatible exports for test suite.

These functions match the old dashboard.py signatures exactly.
They exist solely to keep tests/test_pnl.py passing.
"""

from collections import defaultdict
from config import (
    PAPER_BTC_CONVICTION_BETS, PAPER_ETH_CONVICTION_BETS,
    LIVE_BTC_CONVICTION_BETS, LIVE_ETH_CONVICTION_BETS,
    LIVE_START_DATE, CONVICTION_WEIGHT_CONTRARIAN, CONVICTION_WEIGHT_VOLUME,
)


def _get_bet_size(conv, predicted_at, asset="BTC"):
    date_str = (predicted_at or "")[:10]
    if date_str >= LIVE_START_DATE:
        tiers = LIVE_BTC_CONVICTION_BETS if asset == "BTC" else LIVE_ETH_CONVICTION_BETS
    else:
        tiers = PAPER_BTC_CONVICTION_BETS if asset == "BTC" else PAPER_ETH_CONVICTION_BETS
    return tiers.get(conv, 0)


def is_correct(estimate, outcome):
    return (estimate >= 0.5 and outcome == 1) or (estimate < 0.5 and outcome == 0)


def compute_pnl(resolved, unit_bet=100, conviction_bets=None, asset="BTC"):
    """Per-agent P&L simulation matching the old signature."""
    agents = defaultdict(lambda: {
        "total_pnl": 0.0, "total_wagered": 0.0, "num_bets": 0, "skipped": 0,
        "pnl_series": [], "gross_wins": 0.0, "gross_losses": 0.0,
        "num_wins": 0, "num_losses": 0, "bet_results": [], "max_drawdown": 0.0,
    })

    for row in resolved:
        agent = row["agent"]
        a = agents[agent]
        estimate = row["estimate"]
        outcome = row["outcome"]
        price_yes = row["price_yes"]
        conv = row.get("conviction_score") or 0
        bet_size = _get_bet_size(conv, row.get("predicted_at"), asset)

        if bet_size == 0:
            a["skipped"] += 1
            a["pnl_series"].append(a["total_pnl"])
            continue

        if estimate >= 0.5:
            if 0 < price_yes < 1:
                profit = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                profit = 0
        else:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                profit = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size
            else:
                profit = 0

        a["total_pnl"] += profit
        a["total_wagered"] += bet_size
        a["num_bets"] += 1
        a["pnl_series"].append(a["total_pnl"])

        won = profit > 0
        if won:
            a["gross_wins"] += profit
            a["num_wins"] += 1
        else:
            a["gross_losses"] += profit
            a["num_losses"] += 1
        a["bet_results"].append({
            "profit": round(profit, 2), "bet_size": bet_size,
            "price": price_yes, "won": won,
        })

    for a in agents.values():
        a["roi"] = (a["total_pnl"] / a["total_wagered"] * 100) if a["total_wagered"] > 0 else 0
        a["avg_win"] = (a["gross_wins"] / a["num_wins"]) if a["num_wins"] > 0 else 0
        a["avg_loss"] = (a["gross_losses"] / a["num_losses"]) if a["num_losses"] > 0 else 0
        peak = 0.0
        max_dd = 0.0
        for val in a["pnl_series"]:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        a["max_drawdown"] = max_dd

    return dict(agents)


def compute_ensemble_pnl(resolved, unit_bet=100, conviction_bets=None, asset="BTC"):
    """Ensemble P&L matching the old signature."""
    WEIGHTS = {
        "momentum_rule": 1.0, "contrarian_rule": 1.0,
        "contrarian": CONVICTION_WEIGHT_CONTRARIAN,
        "volume_wick": CONVICTION_WEIGHT_VOLUME,
    }

    market_data = defaultdict(lambda: {
        "agents": [], "outcome": None, "price_yes": None,
        "conviction": 0, "predicted_at": "",
    })
    for row in resolved:
        md = market_data[row["market_id"]]
        md["agents"].append({"agent": row["agent"], "estimate": row["estimate"]})
        md["outcome"] = row["outcome"]
        md["price_yes"] = row["price_yes"]
        if row.get("conviction_score") is not None:
            md["conviction"] = row["conviction_score"]
        if row.get("predicted_at"):
            md["predicted_at"] = row["predicted_at"]

    total_pnl = 0.0
    total_wagered = 0.0
    num_bets = 0
    num_skipped = 0
    pnl_series = []

    for mid, md in market_data.items():
        conv = md["conviction"] or 0
        bet_size = _get_bet_size(conv, md["predicted_at"], asset)

        total_w = 0
        weighted_sum = 0
        for p in md["agents"]:
            w = WEIGHTS.get(p["agent"], 0.5)
            weighted_sum += w * p["estimate"]
            total_w += w
        ens_est = weighted_sum / total_w if total_w > 0 else 0.5

        if bet_size == 0:
            num_skipped += 1
            pnl_series.append(total_pnl)
            continue

        outcome = md["outcome"]
        price_yes = md["price_yes"]

        if ens_est >= 0.5:
            if 0 < price_yes < 1:
                profit = bet_size * (1.0 / price_yes - 1.0) if outcome == 1 else -bet_size
            else:
                profit = 0
        else:
            price_no = 1.0 - price_yes
            if 0 < price_no < 1:
                profit = bet_size * (1.0 / price_no - 1.0) if outcome == 0 else -bet_size
            else:
                profit = 0

        total_pnl += profit
        total_wagered += bet_size
        num_bets += 1
        pnl_series.append(total_pnl)

    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0
    return {
        "total_pnl": total_pnl, "total_wagered": total_wagered,
        "num_bets": num_bets, "num_skipped": num_skipped,
        "roi": roi, "pnl_series": pnl_series,
    }


def compute_ev_breakeven(agent_pnl):
    """EV and breakeven WR from agent P&L dict, matching old signature."""
    total_bets = 0
    total_wins = 0
    total_pnl = 0
    total_wagered = 0
    sum_avg_win = 0
    sum_avg_loss = 0
    n_agents = 0

    for agent, data in agent_pnl.items():
        total_bets += data.get("num_bets", 0)
        total_wins += data.get("num_wins", 0)
        total_pnl += data.get("total_pnl", 0)
        total_wagered += data.get("total_wagered", 0)
        if data.get("avg_win", 0) != 0 or data.get("avg_loss", 0) != 0:
            sum_avg_win += data.get("avg_win", 0)
            sum_avg_loss += data.get("avg_loss", 0)
            n_agents += 1

    if total_bets == 0:
        return {"total_bets": 0, "current_wr": 0, "breakeven_wr": 0.5,
                "ev": 0, "margin": 0, "roi": 0}

    current_wr = total_wins / total_bets
    avg_win = sum_avg_win / n_agents if n_agents > 0 else 0
    avg_loss = sum_avg_loss / n_agents if n_agents > 0 else 0

    if avg_win > 0 and avg_loss < 0:
        breakeven_wr = abs(avg_loss) / (avg_win + abs(avg_loss))
    elif avg_win > 0:
        breakeven_wr = 0
    else:
        breakeven_wr = 0.5

    ev = total_pnl / total_bets if total_bets > 0 else 0
    margin = current_wr - breakeven_wr
    roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0

    return {
        "total_bets": total_bets, "current_wr": current_wr,
        "breakeven_wr": breakeven_wr, "ev": ev, "margin": margin, "roi": roi,
    }


def build_distribution_svg(agent_pnl):
    """Minimal SVG placeholder for backward compat."""
    all_profits = []
    for agent, data in agent_pnl.items():
        for br in data.get("bet_results", []):
            all_profits.append(br["profit"])

    if not all_profits:
        return '<p>No data.</p>'

    wins = [p for p in all_profits if p > 0]
    losses = [p for p in all_profits if p <= 0]

    W, H = 400, 150
    svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
    svg += f'<text x="10" y="20" fill="#8b949e" font-size="11">Losses cluster at -$bet_size | Wins vary by entry price</text>'
    svg += '</svg>'
    return svg
