"""
score.py — Calculate Brier scores for agents on resolved markets.

Brier score = (prediction - outcome)^2
Lower is better. 0.0 = perfect, 1.0 = worst possible.
"""

import sqlite3
import json
import requests
from pathlib import Path
from predict import V2_AGENTS

GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"


def mark_resolved(db, market_id, outcome):
    """Mark a market as resolved with outcome 1 (UP) or 0 (DOWN)."""
    db.execute("UPDATE markets SET resolved = 1, outcome = ? WHERE id = ?", (outcome, market_id))
    db.commit()
    print(f"Marked market {market_id} as resolved: {'UP' if outcome == 1 else 'DOWN'}")


def auto_resolve(db):
    """Check the Polymarket API for resolved markets and update the database."""
    cursor = db.execute("SELECT id, question FROM markets WHERE resolved = 0")
    unresolved = cursor.fetchall()
    if not unresolved:
        return 0

    resolved_count = 0
    for market_id, question in unresolved:
        try:
            resp = requests.get(f"{GAMMA_API}/markets/{market_id}")
            resp.raise_for_status()
            market = resp.json()

            if not market.get("closed"):
                continue

            raw_prices = market.get("outcomePrices", "[]")
            prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            price_yes = float(prices[0])

            # Resolved markets snap to 0 or 1
            if price_yes == 1.0:
                outcome = 1
            elif price_yes == 0.0:
                outcome = 0
            else:
                continue  # Closed but not yet fully resolved

            mark_resolved(db, market_id, outcome)
            resolved_count += 1
        except (requests.RequestException, ValueError, KeyError, IndexError):
            continue

    return resolved_count


def calculate_brier_scores(db):
    """Calculate Brier scores for all agents across resolved markets."""
    cursor = db.execute("""
        SELECT p.agent,
               p.estimate,
               m.outcome,
               m.price_yes,
               m.question,
               (p.estimate - m.outcome) * (p.estimate - m.outcome) AS brier_agent,
               (m.price_yes - m.outcome) * (m.price_yes - m.outcome) AS brier_market
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1
        ORDER BY p.agent, m.end_date
    """)

    results = {}
    for row in cursor.fetchall():
        agent, estimate, outcome, market_price, question, brier_agent, brier_market = row
        if agent not in results:
            results[agent] = {"scores": [], "total_brier": 0, "markets": 0, "vs_market": []}
        results[agent]["scores"].append({
            "question": question,
            "estimate": estimate,
            "outcome": outcome,
            "brier": brier_agent,
            "market_brier": brier_market,
        })
        results[agent]["total_brier"] += brier_agent
        results[agent]["markets"] += 1
        results[agent]["vs_market"].append(brier_agent - brier_market)

    return results


def print_scorecard(results):
    """Pretty-print the agent scorecard."""
    if not results:
        print("No resolved markets yet. Mark some markets as resolved first.")
        return None

    print("\n" + "=" * 70)
    print("AGENT SCORECARD")
    print("=" * 70)

    worst_agent = None
    worst_brier = -1

    for agent, data in sorted(results.items()):
        avg_brier = data["total_brier"] / data["markets"]
        avg_vs_market = sum(data["vs_market"]) / len(data["vs_market"])
        beat_market = "BEATING" if avg_vs_market < 0 else "LOSING TO"

        print(f"\n  {agent}")
        print(f"    Avg Brier:     {avg_brier:.4f}")
        print(f"    Markets:       {data['markets']}")
        print(f"    vs Market:     {avg_vs_market:+.4f} ({beat_market} market)")

        if agent not in V2_AGENTS:
            continue  # Only consider v2 agents for worst-performer selection
        if avg_brier > worst_brier:
            worst_brier = avg_brier
            worst_agent = agent

    print(f"\n  → WORST PERFORMER: {worst_agent} (Brier: {worst_brier:.4f})")
    print(f"  → This agent's prompt should be modified for the next cycle.")
    print("=" * 70)

    return worst_agent


def get_agent_brier(db, agent_name):
    """Get average Brier score for a specific agent."""
    cursor = db.execute("""
        SELECT AVG((p.estimate - m.outcome) * (p.estimate - m.outcome))
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND p.agent = ?
    """, (agent_name,))
    result = cursor.fetchone()
    return result[0] if result[0] is not None else None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolve", nargs=2, metavar=("MARKET_ID", "OUTCOME"),
                        help="Mark a market as resolved: --resolve MARKET_ID 0|1")
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)

    if args.resolve:
        mark_resolved(db, args.resolve[0], int(args.resolve[1]))

    results = calculate_brier_scores(db)
    print_scorecard(results)
    db.close()
