"""
predict.py — Send markets to each agent (via Claude API) and store predictions.

v2: Agents receive macro bias context + micro-TA signals. After all agents
predict, a conviction score is computed from independent signal layers.
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

# v2 agents — 2-agent ensemble (pattern_reader dropped: anti-predictive in backtest)
V2_AGENTS = {"volume_wick", "contrarian"}


def load_agent_prompts():
    """Load v2 agent prompt files from prompts/ directory."""
    agents = {}
    for prompt_file in PROMPTS_DIR.glob("*.md"):
        agent_name = prompt_file.stem
        if agent_name in V2_AGENTS:
            agents[agent_name] = prompt_file.read_text()
    # Fallback: if no v2 agents found, load all (backward compat)
    if not agents:
        for prompt_file in PROMPTS_DIR.glob("*.md"):
            agents[prompt_file.stem] = prompt_file.read_text()
    return agents


def build_market_context(market, macro_context="", btc_context="", current_time=None):
    """Format market data into context for the agent. v2: macro context first."""
    if current_time is None:
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    elif hasattr(current_time, 'strftime'):
        current_time = current_time.strftime('%Y-%m-%d %H:%M')

    return f"""{macro_context}

{btc_context}

## Bitcoin 5-Minute Candle Prediction

- **Market:** {market['question']}
- **Current market price (UP):** {market['price_yes']:.1%}
- **Resolution time:** {market['end_date']}
- **Current time (UTC):** {current_time}

Will Bitcoin close UP (>= open) or DOWN (< open) for this 5-minute candle?

Provide your analysis in the JSON format specified in your instructions.
Return ONLY valid JSON, no other text."""


def get_prediction(client, agent_name, agent_prompt, market, btc_context="", macro_context="", current_time=None):
    """Call Claude API with agent prompt + market context, return structured prediction."""
    market_context = build_market_context(market, macro_context, btc_context, current_time)

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


def store_prediction(db, prediction, cycle, conviction_score=None, predicted_at=None):
    """Store a prediction in the database."""
    if predicted_at is None:
        predicted_at = datetime.now(timezone.utc).isoformat()

    # Try to store conviction_score if column exists
    try:
        db.execute("""
            INSERT INTO predictions (market_id, agent, estimate, edge, confidence, reasoning, predicted_at, cycle, conviction_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction["market_id"],
            prediction["agent"],
            prediction.get("estimate", 0),
            prediction.get("edge", 0),
            prediction.get("confidence", "low"),
            json.dumps(prediction),
            predicted_at,
            cycle,
            conviction_score,
        ))
    except sqlite3.OperationalError:
        # conviction_score column doesn't exist yet — store without it
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
            predicted_at,
            cycle,
        ))
    db.commit()


def run_predictions(cycle=1, market_limit=5, btc_data=None):
    """Main loop: fetch unresolved markets, run all agents, compute conviction, store."""
    from btc_data import fetch_btc_candles, format_for_prompt, compute_rolling_bias
    from conviction import load_macro_bias, compute_conviction, format_macro_for_prompt

    db = sqlite3.connect(DB_PATH)
    client = anthropic.Anthropic()
    agents = load_agent_prompts()

    # Ensure conviction_score column exists
    try:
        db.execute("ALTER TABLE predictions ADD COLUMN conviction_score INTEGER")
        db.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    # Load macro bias (human-in-the-loop)
    macro_bias = load_macro_bias()
    print(f"  Macro: {macro_bias['regime']} | Bias: {macro_bias['bias']} | Prior: {macro_bias['prior']:.2f}")

    # Compute rolling bias (automatic sanity check)
    rolling_bias = None
    try:
        rolling_bias = compute_rolling_bias()
        blended = rolling_bias.get("blended", 0.5)
        print(f"  Computed bias: {blended*100:.1f}% UP (blended)")
    except Exception as e:
        print(f"  Rolling bias unavailable: {e}")

    # Format macro context for agents
    macro_context = format_macro_for_prompt(macro_bias, rolling_bias)

    # Fetch BTC price data
    if btc_data is None:
        btc_data = fetch_btc_candles()
    btc_context = format_for_prompt(btc_data)

    # Get markets to predict
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.execute("""
        SELECT id, question, category, end_date, volume, price_yes
        FROM markets WHERE resolved = 0 AND end_date > ?
        AND id NOT IN (SELECT DISTINCT market_id FROM predictions)
        ORDER BY end_date ASC LIMIT ?
    """, (now_iso, market_limit))
    markets = [dict(zip(["id", "question", "category", "end_date", "volume", "price_yes"], row))
               for row in cursor.fetchall()]

    if not markets:
        print("No unresolved markets found. Run fetch_markets.py first.")
        db.close()
        return

    print(f"Running {len(agents)} agents against {len(markets)} markets (cycle {cycle})")
    if btc_data:
        print(f"  BTC: ${btc_data['current_price']:,.0f} | 1h: {btc_data['1h_change_pct']:+.3f}%")

    for market in markets:
        print(f"\n  Market: {market['question'][:60]}...")
        print(f"  Price:  {market['price_yes']:.0%}")

        # Collect predictions from all agents
        cycle_predictions = []
        for agent_name, agent_prompt in agents.items():
            try:
                prediction = get_prediction(
                    client, agent_name, agent_prompt, market,
                    btc_context=btc_context, macro_context=macro_context
                )
                cycle_predictions.append(prediction)
                est = prediction.get("estimate", "?")
                edge = prediction.get("edge", "?")
                conf = prediction.get("confidence", "?")
                print(f"    {agent_name:20s} → {est:.0%} (edge: {edge:+.0%}, {conf})")
            except Exception as e:
                print(f"    {agent_name:20s} → ERROR: {e}")

        # Compute conviction from all predictions
        conv = compute_conviction(cycle_predictions, macro_bias, rolling_bias)
        print(f"    {'CONVICTION':20s} → {conv['tier']} ({conv['score']}/5) | Ensemble: {conv['ensemble_estimate']:.0%} | Bet: ${conv['bet_size']}")

        # Store all predictions with conviction score
        for prediction in cycle_predictions:
            store_prediction(db, prediction, cycle, conviction_score=conv["score"])

    db.close()
    print(f"\nDone. Predictions stored in {DB_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, default=1, help="Cycle number")
    parser.add_argument("--markets", type=int, default=5, help="Max markets to predict")
    args = parser.parse_args()
    run_predictions(cycle=args.cycle, market_limit=args.markets)
