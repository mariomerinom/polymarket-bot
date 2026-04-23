"""
arb_classifier.py — LLM classification of arb_divergence rows.

At the Phase 0 decision gate (≥48h + regime coverage — see
docs/plans/groovy-squishing-scott.md), per-regime divergence counts alone
cannot tell us whether an observed divergence is (a) Polymarket lagging
Bybit spot (tractable arb), (b) our σ estimator being mildly off
(tractable, model refinement), or (c) Polymarket participants pricing
information we don't see (adverse selection — untradable).

Those three classes have opposite Go/Abandon implications despite producing
identical raw divergence numbers. This module samples high-divergence rows
at the decision gate and asks the LLM to classify them into one of four
buckets. Aggregate class distribution feeds the decision.

Usage (manual, at Phase 0 decision gate):
    python3 -m arb_classifier --n 50 --min-edge 0.02

NO AGENT BIAS: the schema forbids buy/sell output. The classifier names
the CAUSE of a divergence; it does not say whether to trade it. Go/Abandon
is a human decision informed by the distribution.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import llm_inference

_log = logging.getLogger("arb_classifier")

# ── Schema ──────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS arb_divergence_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    divergence_id INTEGER NOT NULL,
    class TEXT NOT NULL,
    rationale TEXT,
    confidence TEXT,
    llm_model TEXT,
    classified_at TEXT NOT NULL,
    FOREIGN KEY (divergence_id) REFERENCES arb_divergence(id)
);
CREATE INDEX IF NOT EXISTS idx_arb_cls_divergence
    ON arb_divergence_classifications(divergence_id);
CREATE INDEX IF NOT EXISTS idx_arb_cls_class
    ON arb_divergence_classifications(class);
"""


def init_table(db) -> None:
    """Create arb_divergence_classifications if not present. Idempotent."""
    for stmt in SCHEMA_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            db.execute(s)
    db.commit()


# ── Row sampling ──────────────────────────────────────────────────────


_SAMPLE_COLUMNS = [
    "id", "timestamp", "cycle", "pipeline", "market_id", "market_class",
    "asset", "direction_sense", "window_open_at", "window_close_at",
    "window_total_seconds", "time_to_expiry_seconds", "window_has_opened",
    "bybit_spot", "open_spot", "r_so_far", "realized_vol_annual",
    "sigma_window", "fair_p", "mkt_mid", "mkt_best_bid", "mkt_best_ask",
    "mkt_spread", "orderbook_age_ms", "divergence", "abs_divergence",
    "would_arb_side", "would_arb_edge", "regime_label", "daily_regime_label",
]


def sample_high_divergence_rows(
    db,
    n: int = 50,
    min_edge: float = 0.02,
    regime_filter: Optional[str] = None,
    since: Optional[str] = None,
) -> list[dict]:
    """
    Return up to `n` rows from arb_divergence, filtered by edge and regime,
    ordered by abs_divergence descending.
    """
    cols = ", ".join(_SAMPLE_COLUMNS)
    sql = (
        f"SELECT {cols} FROM arb_divergence "
        f"WHERE would_arb_edge > ? "
    )
    params: list = [min_edge]
    if regime_filter is not None:
        sql += "AND regime_label = ? "
        params.append(regime_filter)
    if since is not None:
        sql += "AND timestamp >= ? "
        params.append(since)
    sql += "ORDER BY abs_divergence DESC LIMIT ?"
    params.append(n)

    # dict-row access
    prev_factory = db.row_factory
    db.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    finally:
        db.row_factory = prev_factory
    return rows


# ── Prompt + classification ──────────────────────────────────────────


_SCHEMA = {"required": ["class", "rationale", "confidence"]}


_SYSTEM_GUIDANCE = """
You classify the CAUSE of a Polymarket ↔ Bybit probability divergence.
You do NOT recommend buy/sell decisions.

You will receive one row of observed divergence data: Bybit spot price,
Polymarket market mid, our computed fair probability (Φ-based), window
timing, regime labels. Your job is to pick exactly one CAUSE class:

  "lag"
      Polymarket hadn't repriced yet against a recent spot move.
      Typical signature: large r_so_far, market_mid near 0.5 when fair_p
      is far from 0.5, late in window. Tractable for arb — Polymarket
      will converge to fair shortly.

  "model_error"
      Our σ estimator is mismatched to actual near-window vol. Typical
      signature: fair_p extreme while Polymarket is calmly pricing ~0.5
      and there has been little r_so_far. Suggests our vol term is too
      small or too big. Tractable via model refinement.

  "adverse_selection"
      Polymarket is pricing information our fair-p model can't see
      (incoming news, order flow we don't observe). Typical signature:
      market_mid has moved sharply in a direction Bybit spot has NOT
      confirmed yet; market participants appear to know something. Not
      tractable for arb.

  "other"
      Insufficient data, malformed row, ambiguous case.

Output JSON with exactly:
  - class: one of ["lag", "model_error", "adverse_selection", "other"]
  - rationale: < 280 chars, referencing the specific field values
  - confidence: one of ["low", "medium", "high"]
""".strip()


def _build_prompt(row: dict) -> str:
    """Single divergence row -> LLM prompt."""
    slim = {k: row.get(k) for k in _SAMPLE_COLUMNS}
    return (
        _SYSTEM_GUIDANCE
        + "\n\n---\nDIVERGENCE ROW:\n"
        + json.dumps(slim, indent=2, default=str)
        + "\n\nReturn only the JSON object."
    )


def classify_one(
    db, divergence_row: dict, model: Optional[str] = None
) -> dict:
    """Classify one row. Writes classification + calibration log."""
    prompt = _build_prompt(divergence_row)
    out = llm_inference.classify_structured(
        prompt,
        schema=_SCHEMA,
        model=model,
        max_tokens=512,
        temperature=0.1,
    )

    div_id = divergence_row["id"]
    db.execute(
        """INSERT INTO arb_divergence_classifications
           (divergence_id, class, rationale, confidence, llm_model, classified_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            div_id,
            out.get("class", "other"),
            out.get("rationale"),
            out.get("confidence"),
            model or llm_inference._get_default_model(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()

    llm_inference.log_calibration(
        db,
        task_name="arb_classifier",
        input_ref=f"divergence_id:{div_id}",
        llm_output=out,
        actual_outcome=None,  # back-filled later once market resolves
    )
    return out


def classify_divergences(
    db,
    n: int = 50,
    min_edge: float = 0.02,
    regime_filter: Optional[str] = None,
    since: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Orchestrator: sample N high-divergence rows, classify each, return
    aggregate distribution.

    Returns:
      {
        "n_sampled": int,
        "n_classified": int,
        "class_counts": {"lag": k1, "model_error": k2, ...},
        "class_fractions": {"lag": 0.x, ...},
        "regime_filter": regime_filter,
        "min_edge": min_edge,
        "since": since,
      }
    """
    init_table(db)
    llm_inference.init_table(db)

    rows = sample_high_divergence_rows(
        db, n=n, min_edge=min_edge, regime_filter=regime_filter, since=since
    )

    counts: dict = {}
    n_classified = 0
    for r in rows:
        try:
            out = classify_one(db, r, model=model)
            cls = out.get("class", "other")
            counts[cls] = counts.get(cls, 0) + 1
            n_classified += 1
        except llm_inference.LLMError as e:
            _log.warning("LLM failed on divergence_id=%s: %s", r.get("id"), e)

    fractions = {
        k: round(v / n_classified, 3) for k, v in counts.items()
    } if n_classified else {}

    return {
        "n_sampled": len(rows),
        "n_classified": n_classified,
        "class_counts": counts,
        "class_fractions": fractions,
        "regime_filter": regime_filter,
        "min_edge": min_edge,
        "since": since,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/predictions.db")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--min-edge", type=float, default=0.02)
    parser.add_argument("--regime", default=None)
    parser.add_argument("--since", default=None,
                        help="ISO timestamp; only classify rows after this")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    db = sqlite3.connect(args.db)
    result = classify_divergences(
        db, n=args.n, min_edge=args.min_edge,
        regime_filter=args.regime, since=args.since,
    )
    print(json.dumps(result, indent=2))
