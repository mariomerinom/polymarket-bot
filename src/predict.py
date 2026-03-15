"""
predict.py — Send markets to each agent (via Claude API) and store predictions.

This is the core of the autoresearch loop. Each agent prompt is loaded from
prompts/*.md and combined with market context to produce structured predictions.
"""

import anthropic
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"
MODEL = "claude-sonnet-4-6"  # Use sonnet for speed/cost; switch to opus for quality


def load_agent_prompts():
    """Load all agent prompt files from prompts/ directory."""
    agents = {}
    for prompt_file in PROMPTS_DIR.glob("*.md"):
        agent_name = prompt_file.stem
        agents[agent_name] = prompt_file.read_text()
    return agents


def build_market_context(market):
    """Format market data into context for the agent."""
    return f"""## Bitcoin 5-Minute Candle Prediction

- **Market:** {market['question']}
- **Current market price (UP):** {market['price_yes']:.1%}
- **Resolution time:** {market['end_date']}
- **Current time (UTC):** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}

Will Bitcoin close UP (>= open) or DOWN (< open) for this 5-minute candle?

Provide your analysis in the JSON format specified in your instructions.
Return ONLY valid JSON, no other text."""


def get_prediction(client, agent_name, agent_prompt, market):
    """Call Claude API with agent prompt + market context, return structured prediction."""
    market_context = build_market_context(market)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=agent_prompt,
        messages=[{"role": "user", "content": market_context}],
    )

    text = response.content[0].text.strip()
    # Extract JSON from response (handle markdown code blocks)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    prediction = json.loads(text)
    prediction["agent"] = agent_name
    prediction["market_id"] = market["id"]
    return prediction


def store_prediction(db, prediction, cycle):
    """Store a prediction in the database."""
    db.execute("""
        INSERT INTO predictions (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prediction["market_id"],
        prediction["agent"],
        prediction.get("estimate", 0),
        prediction.get("edge", 0),
        prediction.get("confidence", "low"),
        json.dumps(prediction),
        datetime.now(timezone.utc).isoformat(),
        cycle,
    ))
    db.commit()


def run_predictions(cycle=1, market_limit=5):
    """Main loop: fetch unresolved markets, run all agents, store predictions."""
    db = sqlite3.connect(DB_PATH)
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
    agents = load_agent_prompts()

    # Get markets to predict
    cursor = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes
        FROM markets WHERE resolved = 0
        ORDER BY end_date ASC LIMIT ?
    """, (market_limit,))
    markets = [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row))
               for row in cursor.fetchall()]

    if not markets:
        print("No unresolved markets found. Run fetch_markets.py first.")
        return

    print(f"Running {len(agents)} agents against {len(markets)} markets (cycle {cycle})")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        print(f"  Price:  {market['price_yes']:.0%}")

        for agent_name, agent_prompt in agents.items():
            try:
                prediction = get_prediction(client, agent_name, agent_prompt, market)
                store_prediction(db, prediction, cycle)
                est = prediction.get("estimate", "?")
                edge = prediction.get("edge", "?")
                print(f"    {agent_name:20s} → {est:.0%} (edge: {edge:+.0%})")
            except Exception as e:
                print(f"    {agent_name:20s} → ERROR: {e}")

    db.close()
    print(f"\nDone. Predictions stored in {DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
