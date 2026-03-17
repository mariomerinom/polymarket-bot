"""
conviction.py — Compute conviction score from independent signal layers.

Conviction measures agreement across:
1. Agent agreement (both agents point same direction)
2. Agent magnitude (average deviation from prior > 4pp)
3. Agent confidence (both agents say medium or high)
4. Macro alignment (micro signals agree with human macro bias)
5. Computed bias (rolling UP% confirms direction)

Score 0-5. Higher = more independent layers agree.
Only MEDIUM (3+) and HIGH (4+) tiers place bets. LOW tier is skipped
(backtest showed LOW conviction is consistently below 50% accuracy).
"""

import re
from pathlib import Path


CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_macro_bias():
    """Load human macro bias from config/macro_bias.md. Returns dict with prior, regime, bias, narrative."""
    macro_file = CONFIG_DIR / "macro_bias.md"
    if not macro_file.exists():
        return {"prior": 0.50, "regime": "UNKNOWN", "bias": "NEUTRAL", "narrative": ""}

    text = macro_file.read_text()

    # Parse structured headers
    prior = 0.50
    regime = "UNKNOWN"
    bias = "NEUTRAL"

    prior_match = re.search(r"##\s*Prior:\s*([\d.]+)", text)
    if prior_match:
        try:
            prior = float(prior_match.group(1))
        except ValueError:
            pass

    regime_match = re.search(r"##\s*Current Regime:\s*(\w+)", text)
    if regime_match:
        regime = regime_match.group(1).upper()

    bias_match = re.search(r"##\s*Direction Bias:\s*(\w+)", text)
    if bias_match:
        bias = bias_match.group(1).upper()

    # Everything after the headers is narrative context
    lines = text.split("\n")
    narrative_lines = []
    for line in lines:
        if not line.startswith("##") and line.strip():
            narrative_lines.append(line.strip())
    narrative = " ".join(narrative_lines)

    return {"prior": prior, "regime": regime, "bias": bias, "narrative": narrative}


def compute_conviction(predictions, macro_bias, rolling_bias=None):
    """
    Compute conviction score (0-5) from agent predictions and bias layers.

    Args:
        predictions: list of dicts with keys: agent, estimate, confidence
        macro_bias: dict from load_macro_bias() with prior, bias
        rolling_bias: dict from compute_rolling_bias() with blended UP%

    Returns:
        dict with score (0-5), direction ("UP"/"DOWN"/"NONE"), breakdown, ensemble_estimate
    """
    if not predictions:
        return {"score": 0, "direction": "NONE", "breakdown": {}, "ensemble_estimate": 0.5}

    prior = macro_bias.get("prior", 0.50)
    estimates = [p["estimate"] for p in predictions]
    confidences = [p.get("confidence", "low").lower() for p in predictions]

    # Weighted ensemble estimate (2-agent: contrarian leads)
    weights = {"contrarian": 0.55, "volume_wick": 0.45}
    total_w = 0
    weighted_sum = 0
    for p in predictions:
        w = weights.get(p["agent"], 1.0 / len(predictions))
        weighted_sum += w * p["estimate"]
        total_w += w
    ensemble_estimate = weighted_sum / total_w if total_w > 0 else 0.5

    # Determine ensemble direction
    if ensemble_estimate > 0.50:
        direction = "UP"
    elif ensemble_estimate < 0.50:
        direction = "DOWN"
    else:
        direction = "NONE"

    # --- Score each layer ---
    score = 0
    breakdown = {}

    # Layer 1: Agent Agreement — all point same direction
    all_up = all(e >= 0.50 for e in estimates)
    all_down = all(e < 0.50 for e in estimates)
    agent_agreement = all_up or all_down
    if agent_agreement:
        score += 1
    breakdown["agent_agreement"] = agent_agreement

    # Layer 2: Agent Magnitude — average deviation from prior > 4pp
    avg_deviation = abs(sum(estimates) / len(estimates) - prior)
    magnitude_strong = avg_deviation > 0.04
    if magnitude_strong:
        score += 1
    breakdown["agent_magnitude"] = round(avg_deviation, 4)
    breakdown["magnitude_strong"] = magnitude_strong

    # Layer 3: Agent Confidence — both agents say medium or high
    med_high_count = sum(1 for c in confidences if c in ("medium", "high"))
    confidence_strong = med_high_count >= 2  # With 2 agents, this means both
    if confidence_strong:
        score += 1
    breakdown["confidence_count"] = med_high_count
    breakdown["confidence_strong"] = confidence_strong

    # Layer 4: Macro Alignment — micro direction matches macro bias
    macro_direction = macro_bias.get("bias", "NEUTRAL").upper()
    macro_aligned = False
    if macro_direction == "UP" and direction == "UP":
        macro_aligned = True
    elif macro_direction == "DOWN" and direction == "DOWN":
        macro_aligned = True
    elif macro_direction == "NEUTRAL":
        macro_aligned = False  # NEUTRAL never adds conviction
    if macro_aligned:
        score += 1
    breakdown["macro_aligned"] = macro_aligned
    breakdown["macro_direction"] = macro_direction

    # Layer 5: Computed Bias — rolling UP% confirms direction
    computed_aligned = False
    if rolling_bias:
        blended = rolling_bias.get("blended", 0.5)
        if direction == "UP" and blended > 0.52:
            computed_aligned = True
        elif direction == "DOWN" and blended < 0.48:
            computed_aligned = True
        if computed_aligned:
            score += 1
        breakdown["computed_blended"] = blended
    breakdown["computed_aligned"] = computed_aligned

    # Determine conviction tier label
    if score <= 1:
        tier = "NO_BET"
    elif score == 2:
        tier = "LOW"
    elif score == 3:
        tier = "MEDIUM"
    else:
        tier = "HIGH"

    # Bet sizing — LOW is $0 (backtest: consistently <50% accuracy at LOW conviction)
    bet_sizes = {"NO_BET": 0, "LOW": 0, "MEDIUM": 75, "HIGH": 200}
    bet_size = bet_sizes.get(tier, 0)

    return {
        "score": score,
        "tier": tier,
        "direction": direction,
        "ensemble_estimate": round(ensemble_estimate, 4),
        "bet_size": bet_size,
        "breakdown": breakdown,
    }


def format_macro_for_prompt(macro_bias, rolling_bias=None):
    """Format macro bias context for injection into agent prompts."""
    lines = [
        "## Macro Context",
        f"- **Regime:** {macro_bias['regime']}",
        f"- **Direction Bias:** {macro_bias['bias']}",
        f"- **Prior (starting estimate):** {macro_bias['prior']:.2f}",
    ]

    if macro_bias.get("narrative"):
        lines.append(f"- **Narrative:** {macro_bias['narrative']}")

    if rolling_bias:
        lines.append("")
        lines.append("## Computed Bias (automatic sanity check)")
        for label in ("7d", "24h", "1h"):
            if label in rolling_bias:
                rb = rolling_bias[label]
                pct = rb.get("up_pct", 0.5) * 100
                n = rb.get("candles", 0)
                lines.append(f"- **{label} UP%:** {pct:.1f}% ({n} candles)")
        blended = rolling_bias.get("blended", 0.5) * 100
        lines.append(f"- **Blended:** {blended:.1f}% UP")

    lines.append("")
    lines.append("**Use the Prior as your starting estimate. Adjust based on micro signals only.**")

    return "\n".join(lines)
