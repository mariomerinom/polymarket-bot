"""
validate_bybit_consensus.py — Does the perps-vs-spot consensus boost help?

The Bybit pipeline bumps conviction by +1 when `consensus.score == 2`
(perps and spot agreeing on streak direction). This script reads
`predictions_bybit.db`, extracts the `consensus` field from the
prediction's `reasoning` JSON, and compares WR on boosted vs
non-boosted bets.

Decision rule:
  * lift >= +2pp → keep boost
  * lift <  +2pp → kill boost (not worth the complexity)

Writes docs/research/bybit_consensus_validation_2026-04.md.

Usage:
    python3 tools/validate_bybit_consensus.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BYBIT_DB = ROOT / "data" / "predictions_bybit.db"
OUT = ROOT / "docs" / "research" / "bybit_consensus_validation_2026-04.md"


def main():
    db = sqlite3.connect(BYBIT_DB)
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT p.id, p.estimate, p.conviction_score, p.reasoning, m.outcome
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
          AND p.conviction_score >= 3
    """).fetchall()
    db.close()

    boosted, unboosted = [], []
    no_consensus = 0
    for r in rows:
        try:
            d = json.loads(r["reasoning"] or "{}")
        except Exception:
            no_consensus += 1
            continue
        cons = d.get("consensus")
        if cons is None:
            no_consensus += 1
            continue
        direction = "UP" if r["estimate"] > 0.5 else "DOWN"
        won = int(
            (direction == "UP" and r["outcome"] == 1)
            or (direction == "DOWN" and r["outcome"] == 0)
        )
        score = cons.get("score", 0)
        sources = cons.get("sources", 0)
        if sources >= 2 and score == 2:
            boosted.append(won)
        else:
            unboosted.append(won)

    def wr(lst):
        n = len(lst)
        w = sum(lst)
        return n, w, (w / n if n else 0.0)

    nb, wb, wrb = wr(boosted)
    nu, wu, wru = wr(unboosted)
    lift = (wrb - wru) * 100

    lines = []
    lines.append("# Bybit consensus boost validation — Phase 6")
    lines.append("")
    lines.append("Compares WR on bets where the perps-vs-spot consensus")
    lines.append("triggered a conviction boost (score == 2, sources >= 2)")
    lines.append("vs bets without the boost. Filter: conv >= 3, resolved.")
    lines.append("")
    lines.append("| Bucket | N | Wins | WR |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| Boosted (score=2) | {nb} | {wb} | {wrb*100:.1f}% |")
    lines.append(f"| Unboosted         | {nu} | {wu} | {wru*100:.1f}% |")
    lines.append(f"| No consensus data | {no_consensus} | — | — |")
    lines.append("")
    lines.append(f"**Lift: {lift:+.1f}pp**")
    lines.append("")
    lines.append("## Verdict")
    if nb < 20:
        lines.append(f"⚠️ Boosted sample too small (N={nb}). Need more data "
                     f"before a kill decision. Leave boost in place.")
    elif lift >= 2:
        lines.append(f"✅ Boost adds {lift:+.1f}pp — keep.")
    else:
        lines.append(f"❌ Boost lift {lift:+.1f}pp < 2pp threshold — "
                     f"recommend killing consensus boost in "
                     f"`ci_run_bybit.store_prediction_bybit`.")
    lines.append("")

    text = "\n".join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n")
    print(text)
    print()
    print(f"Report: {OUT}")


if __name__ == "__main__":
    main()
