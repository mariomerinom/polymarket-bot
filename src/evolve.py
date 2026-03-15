"""
evolve.py — The autoresearch feedback loop.

Identifies the worst-performing agent, uses Claude to generate ONE targeted
prompt modification, applies it, and tracks the change for later evaluation.

This is the equivalent of modifying train.py in Karpathy's autoresearch,
but instead of modifying model code, we modify agent prompts.
"""

import anthropic
import json
import sqlite3
import shutil
from datetime import datetime, timezone
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

from score import calculate_brier_scores, get_agent_brier

DB_PATH = Path(__file__).parent.parent / "data" / "predictions.db"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
EVOLUTION_LOG = Path(__file__).parent.parent / "data" / "evolution_log.json"
MODEL = "claude-sonnet-4-6"
BRIER_IMPROVEMENT_THRESHOLD = 0.01  # Must improve by at least this much to keep


def load_evolution_log():
    if EVOLUTION_LOG.exists():
        return json.loads(EVOLUTION_LOG.read_text())
    return []


def save_evolution_log(log):
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    EVOLUTION_LOG.write_text(json.dumps(log, indent=2))


def find_worst_agent(db):
    """Identify the agent with the highest average Brier score."""
    results = calculate_brier_scores(db)
    if not results:
        return None, None

    worst_agent = max(results.items(), key=lambda x: x[1]["total_brier"] / x[1]["markets"])
    agent_name = worst_agent[0]
    avg_brier = worst_agent[1]["total_brier"] / worst_agent[1]["markets"]
    return agent_name, avg_brier


def get_agent_mistakes(db, agent_name, limit=5):
    """Get the agent's worst predictions for analysis."""
    cursor = db.execute("""
        SELECT m.question, p.estimate, m.outcome, m.price_yes,
               (p.estimate - m.outcome) * (p.estimate - m.outcome) AS brier,
               p.reasoning
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND p.agent = ?
        ORDER BY brier DESC
        LIMIT ?
    """, (agent_name, limit))
    return cursor.fetchall()


def generate_prompt_modification(client, agent_name, current_prompt, mistakes):
    """Use Claude to generate ONE targeted prompt modification as structured JSON."""
    mistakes_text = ""
    for m in mistakes:
        question, estimate, outcome, market_price, brier, reasoning = m
        mistakes_text += f"""
- Market: {question}
  Agent predicted: {estimate:.0%}, Market was: {market_price:.0%}, Actual outcome: {'YES' if outcome == 1 else 'NO'}
  Brier score: {brier:.4f}
  Reasoning: {reasoning[:200] if reasoning else 'N/A'}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""You are optimizing an AI agent's prompt for prediction market accuracy.

## Current Prompt
```
{current_prompt}
```

## Agent's Worst Predictions
{mistakes_text}

## Task
Analyze the pattern of errors above. Identify ONE specific weakness in the prompt that led to these mistakes.

Return your answer as a JSON object with exactly these fields:
- "diagnosis": What systematic error is this agent making? (1-2 sentences)
- "old_text": The exact text to find in the current prompt (must match exactly, including whitespace)
- "new_text": The replacement text
- "expected_effect": How this should improve predictions (1 sentence)

IMPORTANT: Make only ONE change. Keep it small and targeted. The goal is incremental improvement, not a rewrite.
IMPORTANT: "old_text" must be a verbatim substring of the current prompt so it can be found with a simple string search.

Return ONLY the JSON object, no markdown fences, no extra text."""
        }]
    )

    return json.loads(response.content[0].text)


def apply_modification(agent_name, modification):
    """
    Auto-apply a structured prompt modification.
    modification is a dict with keys: diagnosis, old_text, new_text, expected_effect.
    Returns True if the change was applied, False if old_text was not found.
    """
    prompt_path = PROMPTS_DIR / f"{agent_name}.md"
    backup_path = PROMPTS_DIR / f"{agent_name}.md.backup"

    # Always backup before modifying
    shutil.copy2(prompt_path, backup_path)

    current_prompt = prompt_path.read_text()
    old_text = modification["old_text"]
    new_text = modification["new_text"]

    if old_text not in current_prompt:
        print(f"\n  WARNING: old_text not found in {prompt_path}. Skipping modification.")
        print(f"  Backup preserved at: {backup_path}")
        return False

    updated_prompt = current_prompt.replace(old_text, new_text, 1)
    prompt_path.write_text(updated_prompt)

    print(f"\n  Prompt modified: {prompt_path}")
    print(f"  Backup saved to: {backup_path}")
    print(f"  To revert: cp {backup_path} {prompt_path}")
    return True


def evolve(cycle):
    """Main evolution step: find worst agent, generate modification, log it."""
    db = sqlite3.connect(DB_PATH)
    client = anthropic.Anthropic()

    # Find worst performer
    worst_agent, brier_before = find_worst_agent(db)
    if not worst_agent:
        print("No resolved markets yet. Nothing to evolve.")
        return

    print(f"\nCycle {cycle}: Evolving worst agent")
    print(f"  Worst agent:  {worst_agent}")
    print(f"  Avg Brier:    {brier_before:.4f}")

    # Get mistakes and current prompt
    mistakes = get_agent_mistakes(db, worst_agent)
    prompt_path = PROMPTS_DIR / f"{worst_agent}.md"
    current_prompt = prompt_path.read_text()

    # Generate modification
    print(f"  Generating prompt modification...")
    modification = generate_prompt_modification(client, worst_agent, current_prompt, mistakes)

    print(f"\n  Diagnosis: {modification['diagnosis']}")
    print(f"  Expected effect: {modification['expected_effect']}")

    applied = apply_modification(worst_agent, modification)

    if applied:
        print(f"\n  Change applied:")
        print(f"    - Replaced: {modification['old_text'][:80]}...")
        print(f"    + With:     {modification['new_text'][:80]}...")

    # Log the evolution — store a readable summary, not raw JSON
    modification_summary = (
        f"Diagnosis: {modification['diagnosis']}\n"
        f"Old text: {modification['old_text']}\n"
        f"New text: {modification['new_text']}\n"
        f"Expected effect: {modification['expected_effect']}"
    )

    log = load_evolution_log()
    log.append({
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": worst_agent,
        "brier_before": brier_before,
        "brier_after": None,  # Filled after next scoring round
        "modification": modification_summary,
        "applied": applied,
        "kept": None,  # Filled after evaluation
    })
    save_evolution_log(log)

    print(f"\n  Evolution logged. Run predictions for cycle {cycle + 1},")
    print(f"  then score to see if {worst_agent} improved.")

    db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycle", type=int, required=True, help="Current cycle number")
    args = parser.parse_args()
    evolve(cycle=args.cycle)
