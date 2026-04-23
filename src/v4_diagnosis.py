"""
v4_diagnosis.py — One-shot LLM diagnosis of V4 momentum decay.

Called manually (not per-cycle). Assembles a deterministic bundle from
predictions.db over a user-specified window, sends it to the shared DO
Serverless Inference client with a structured-output schema, renders the
response into a markdown report at docs/analysis/.

Purpose: feed the 2026-04-28 pivot commitment decision with a dated-onset
hypothesis + regime correlation, cross-referenced against whatever news
signal the LLM can surface. LLM output is a PRIOR to compare against our
independent read — never a source of truth.

NO AGENT BIAS: the output schema explicitly excludes buy/sell/direction
recommendations. The model classifies decay vs reverting, proposes an
onset date, and flags regime correlation — it does not say what to do.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import llm_inference

_log = logging.getLogger("v4_diagnosis")


# ── Bundle builder ─────────────────────────────────────────────────


def build_bundle(
    db,
    start: str,
    end: str,
    min_conviction: int = 3,
    agent_filter: Optional[str] = None,
) -> dict:
    """
    Aggregate predictions into a deterministic bundle the LLM can reason over.

    Args:
      start, end: YYYY-MM-DD inclusive UTC.
      min_conviction: filter to bets that actually fired (conv >= N).
      agent_filter: optional agent name ('btc', 'eth', ...) to slice on.

    Returns a dict with:
      window, summary, per_day, per_day_per_regime, per_regime_overall
    """
    params = [f"{start}T00:00:00", f"{end}T23:59:59", min_conviction]
    sql = """
        SELECT
            date(p.predicted_at) AS d,
            p.regime AS regime,
            p.estimate AS estimate,
            p.agent AS agent,
            m.resolved AS resolved,
            m.outcome AS outcome
        FROM predictions p
        LEFT JOIN markets m ON p.market_id = m.id
        WHERE p.predicted_at >= ?
          AND p.predicted_at <= ?
          AND p.conviction_score >= ?
    """
    if agent_filter:
        sql += " AND p.agent = ?"
        params.append(agent_filter)
    sql += " ORDER BY d ASC"

    per_day = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0, "unresolved": 0})
    per_regime = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})
    per_cell = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})

    total_bets = 0
    total_wins = 0

    for row in db.execute(sql, params).fetchall():
        d, regime, estimate, _agent, resolved, outcome = row
        if d is None:
            continue
        regime = regime or "unknown"

        per_day[d]["total"] += 1
        per_regime[regime]["total"] += 1
        per_cell[(d, regime)]["total"] += 1
        total_bets += 1

        if not resolved:
            per_day[d]["unresolved"] += 1
            continue

        won = (
            (estimate is not None and estimate > 0.5 and outcome == 1)
            or (estimate is not None and estimate < 0.5 and outcome == 0)
        )
        if won:
            per_day[d]["wins"] += 1
            per_regime[regime]["wins"] += 1
            per_cell[(d, regime)]["wins"] += 1
            total_wins += 1
        else:
            per_day[d]["losses"] += 1
            per_regime[regime]["losses"] += 1
            per_cell[(d, regime)]["losses"] += 1

    def _wr(w: int, t: int) -> Optional[float]:
        return round(100.0 * w / t, 1) if t > 0 else None

    per_day_list = [
        {
            "date": d,
            "wins": v["wins"],
            "losses": v["losses"],
            "total": v["total"],
            "unresolved": v["unresolved"],
            "wr_pct": _wr(v["wins"], v["wins"] + v["losses"]),
        }
        for d, v in sorted(per_day.items())
    ]

    per_regime_list = [
        {
            "regime": r,
            "wins": v["wins"],
            "losses": v["losses"],
            "total": v["total"],
            "wr_pct": _wr(v["wins"], v["wins"] + v["losses"]),
        }
        for r, v in sorted(per_regime.items(), key=lambda kv: -kv[1]["total"])
    ]

    per_cell_list = [
        {
            "date": d,
            "regime": r,
            "wins": v["wins"],
            "losses": v["losses"],
            "total": v["total"],
            "wr_pct": _wr(v["wins"], v["wins"] + v["losses"]),
        }
        for (d, r), v in sorted(per_cell.items())
    ]

    return {
        "window": {"start": start, "end": end},
        "summary": {
            "total_bets": total_bets,
            "total_wins": total_wins,
            "overall_wr_pct": _wr(total_wins, total_bets),
            "min_conviction": min_conviction,
            "agent_filter": agent_filter,
        },
        "per_day": per_day_list,
        "per_regime_overall": per_regime_list,
        "per_day_per_regime": per_cell_list,
    }


# ── LLM orchestration ─────────────────────────────────────────────────


_SCHEMA = {
    "required": [
        "onset_date_hypothesis",
        "regime_correlation",
        "news_correlation",
        "decay_vs_reverting",
        "confidence",
        "recommended_action",
    ]
}


_SYSTEM_PROMPT_GUIDANCE = """
You are a quantitative analyst diagnosing a momentum-trading-signal
decay. You do NOT recommend buy/sell decisions. You describe patterns
and propose a single onset-date hypothesis based on the win-rate timeline
provided, correlate the decay with regime labels, and assess whether the
pattern looks like decay (structural loss of edge) vs reverting
(temporary loss recoverable in other regimes).

Output JSON with these exact keys:
  - onset_date_hypothesis: "YYYY-MM-DD" string or null (the day WR broke down)
  - regime_correlation: object mapping regime_label -> short description of
    how WR behaves in that regime over the window
  - news_correlation: string or null (based only on publicly-known crypto
    events in the window; do not fabricate)
  - decay_vs_reverting: one of ["decaying", "reverting", "ambiguous"]
  - confidence: one of ["low", "medium", "high"]
  - recommended_action: one of ["continue", "restrict", "pivot", "wait"]
    where "pivot" means the signal no longer has durable edge

Keep all text fields under 280 chars. Unknown/null fields must be null.
""".strip()


def _build_prompt(bundle: dict) -> str:
    """Flatten the bundle into a single prompt string."""
    return (
        _SYSTEM_PROMPT_GUIDANCE
        + "\n\n---\nDATA BUNDLE:\n"
        + json.dumps(bundle, indent=2)
        + "\n\nReturn only the JSON object."
    )


def _render_markdown(
    bundle: dict, llm_output: dict, start: str, end: str
) -> str:
    summary = bundle.get("summary", {})
    lines = [
        f"# V4 Momentum Decay Diagnosis — {start} to {end}",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary (quant)",
        "",
        f"- Total bets (conv ≥ {summary.get('min_conviction')}): {summary.get('total_bets')}",
        f"- Total wins: {summary.get('total_wins')}",
        f"- Overall WR: {summary.get('overall_wr_pct')}%",
        "",
        "## Per-regime aggregates",
        "",
        "| Regime | Bets | Wins | Losses | WR |",
        "|--------|------|------|--------|----|",
    ]
    for r in bundle.get("per_regime_overall", []):
        lines.append(
            f"| {r['regime']} | {r['total']} | {r['wins']} | {r['losses']} |"
            f" {r['wr_pct']}% |"
        )

    lines += [
        "",
        "## LLM diagnosis",
        "",
        f"- **Onset date hypothesis:** {llm_output.get('onset_date_hypothesis')}",
        f"- **Decay vs reverting:** {llm_output.get('decay_vs_reverting')}",
        f"- **Confidence:** {llm_output.get('confidence')}",
        f"- **Recommended action:** {llm_output.get('recommended_action')}",
        "",
        "### Regime correlation",
        "",
    ]
    reg_corr = llm_output.get("regime_correlation") or {}
    if isinstance(reg_corr, dict):
        for k, v in reg_corr.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append(str(reg_corr))

    news = llm_output.get("news_correlation")
    if news:
        lines += ["", "### News correlation", "", str(news)]

    lines += [
        "",
        "---",
        "*Disclaimer: LLM output is a prior to compare against independent",
        "quant analysis, not a source of truth. See `CLAUDE.md` — no agent bias.*",
        "",
    ]
    return "\n".join(lines)


def diagnose_momentum_decay(
    db,
    start: str,
    end: str,
    min_conviction: int = 3,
    agent_filter: Optional[str] = None,
    output_path: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Build a bundle, call the LLM, render markdown, return the result dict.

    Returns: {"bundle": ..., "llm_output": ..., "output_path": ...}
    """
    bundle = build_bundle(
        db, start=start, end=end,
        min_conviction=min_conviction, agent_filter=agent_filter,
    )
    prompt = _build_prompt(bundle)

    llm_output = llm_inference.classify_structured(
        prompt, schema=_SCHEMA, model=model, max_tokens=1024, temperature=0.1
    )

    md = _render_markdown(bundle, llm_output, start, end)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(md)
        _log.info("wrote v4_diagnosis report to %s", output_path)

    return {
        "bundle": bundle,
        "llm_output": llm_output,
        "output_path": output_path,
    }


if __name__ == "__main__":
    # Manual entry: python3 -m v4_diagnosis 2026-03-15 2026-04-23 [btc]
    import argparse
    import sqlite3

    parser = argparse.ArgumentParser()
    parser.add_argument("start")
    parser.add_argument("end")
    parser.add_argument("--agent", default=None)
    parser.add_argument("--db", default="data/predictions.db")
    parser.add_argument(
        "--output",
        default=f"docs/analysis/v4_decay_diagnosis_{datetime.now().strftime('%Y-%m-%d')}.md",
    )
    parser.add_argument("--min-conv", type=int, default=3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db = sqlite3.connect(args.db)
    out = diagnose_momentum_decay(
        db,
        start=args.start,
        end=args.end,
        min_conviction=args.min_conv,
        agent_filter=args.agent,
        output_path=args.output,
    )
    print(f"[v4_diagnosis] wrote {out['output_path']}")
    print(json.dumps(out["llm_output"], indent=2))
