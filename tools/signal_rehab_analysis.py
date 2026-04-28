"""
signal_rehab_analysis.py — diagnostic against 5 hypotheses about V4 decay.

Reads predictions.db (BTC) and predictions_eth.db (ETH), produces a single
markdown report + HTML render. Read-only — no DB writes.

Hypotheses (see chat 2026-04-28):
  H1 lab-to-production translation lying — does aggregate (always-fire) WR
     stay stable while conv>=3 WR drops? If yes, it's adverse selection on
     execution, not signal decay.
  H2 regime mix shift — does per-regime WR stay roughly stable while the
     regime-weighted mix shifts toward bad regimes?
  H3 cell decay — do specific (estimate_bucket × regime) cells survive?
     A "rehab via restriction" path exists if N≥30 cells stay >55% WR.
  H4 cross-asset asynchrony — does BTC decay while ETH still works (or
     vice versa)?
  H5 timing shift — did the cycle-to-prediction wall-clock delta change
     between strong-signal and decay eras?

Strong era:  2026-03-29 → 2026-04-06 (per PIVOT_OPTIONS, before the
             Apr 6 reversion to paper after adverse selection)
Decay era:   2026-04-07 → 2026-04-24
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DB_BTC = ROOT / "data" / "predictions.db"
DB_ETH = ROOT / "data" / "predictions_eth.db"

STRONG_START = "2026-03-29"
STRONG_END = "2026-04-06"
DECAY_START = "2026-04-07"
DECAY_END = "2026-04-24"


# ── Shared helpers ─────────────────────────────────────────────────


def _won(estimate: Optional[float], outcome: Optional[int]) -> Optional[bool]:
    """Match the project's WR formula: directional correctness."""
    if estimate is None or outcome is None:
        return None
    if estimate > 0.5 and outcome == 1:
        return True
    if estimate < 0.5 and outcome == 0:
        return True
    return False


def _wr(wins: int, losses: int) -> Optional[float]:
    n = wins + losses
    return round(100.0 * wins / n, 1) if n else None


def _iso_week(date_str: str) -> str:
    """Bucket date YYYY-MM-DD to its ISO week starting Monday."""
    d = datetime.fromisoformat(date_str.replace("T", " ").split(" ")[0])
    monday = d - __import__("datetime").timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


# ── H1 — lab vs production ─────────────────────────────────────────


def h1_lab_vs_production(db, agent: str) -> dict:
    """Compare aggregate (always-fire) WR vs conv>=3 (production) WR by week."""
    sql = """
        SELECT date(p.predicted_at) AS d, p.conviction_score AS conv,
               p.estimate, m.resolved, m.outcome
        FROM predictions p LEFT JOIN markets m ON p.market_id = m.id
        WHERE p.agent = ? AND p.predicted_at >= '2026-03-29'
              AND m.resolved = 1
        ORDER BY d ASC
    """
    by_week: dict = defaultdict(lambda: {
        "lab_wins": 0, "lab_losses": 0,
        "prod_wins": 0, "prod_losses": 0,
    })
    for d, conv, est, resolved, outcome in db.execute(sql, (agent,)).fetchall():
        if resolved != 1:
            continue
        w = _won(est, outcome)
        if w is None:
            continue
        wk = _iso_week(d)
        # Lab cohort = ALL conviction levels (always-fire approximation)
        if w:
            by_week[wk]["lab_wins"] += 1
        else:
            by_week[wk]["lab_losses"] += 1
        # Production cohort = conv >= 3
        if conv is not None and conv >= 3:
            if w:
                by_week[wk]["prod_wins"] += 1
            else:
                by_week[wk]["prod_losses"] += 1

    rows = []
    for wk in sorted(by_week.keys()):
        v = by_week[wk]
        rows.append({
            "week_start": wk,
            "lab_n": v["lab_wins"] + v["lab_losses"],
            "lab_wr": _wr(v["lab_wins"], v["lab_losses"]),
            "prod_n": v["prod_wins"] + v["prod_losses"],
            "prod_wr": _wr(v["prod_wins"], v["prod_losses"]),
            "gap_pp": (
                round(_wr(v["prod_wins"], v["prod_losses"])
                      - _wr(v["lab_wins"], v["lab_losses"]), 1)
                if v["lab_wins"] + v["lab_losses"]
                and v["prod_wins"] + v["prod_losses"] else None
            ),
        })
    return {"agent": agent, "weekly": rows}


# ── H2 — regime mix shift ──────────────────────────────────────────


def h2_regime_shift(db, agent: str) -> dict:
    """Per-(regime × week) WR for conv>=3 bets, plus regime mix percentages."""
    sql = """
        SELECT date(p.predicted_at) AS d, p.regime, p.estimate,
               p.conviction_score, m.resolved, m.outcome
        FROM predictions p LEFT JOIN markets m ON p.market_id = m.id
        WHERE p.agent = ? AND p.predicted_at >= '2026-03-29'
        ORDER BY d ASC
    """
    cells: dict = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})
    week_totals: dict = defaultdict(int)

    for d, regime, est, conv, resolved, outcome in db.execute(
        sql, (agent,)
    ).fetchall():
        regime = regime or "unknown"
        wk = _iso_week(d)
        cells[(wk, regime)]["total"] += 1
        week_totals[wk] += 1
        if resolved != 1 or conv is None or conv < 3:
            continue
        w = _won(est, outcome)
        if w is None:
            continue
        if w:
            cells[(wk, regime)]["wins"] += 1
        else:
            cells[(wk, regime)]["losses"] += 1

    rows = []
    for (wk, regime), v in sorted(cells.items()):
        bets = v["wins"] + v["losses"]
        if bets == 0:
            continue
        rows.append({
            "week_start": wk,
            "regime": regime,
            "bets": bets,
            "wr_pct": _wr(v["wins"], v["losses"]),
            "predictions_total": v["total"],
            "regime_share_pct": (
                round(100.0 * v["total"] / week_totals[wk], 1)
                if week_totals[wk] else None
            ),
        })
    return {"agent": agent, "cells": rows}


# ── H3 — cell decay ────────────────────────────────────────────────


def _estimate_bucket(est: Optional[float]) -> str:
    if est is None:
        return "unknown"
    if est < 0.4:
        return "<0.4"
    if est < 0.5:
        return "0.4-0.5"
    if est < 0.6:
        return "0.5-0.6"
    if est < 0.7:
        return "0.6-0.7"
    if est < 0.8:
        return "0.7-0.8"
    return ">=0.8"


def h3_cell_decay(db, agent: str) -> dict:
    """Per-(estimate × regime) WR in strong era vs decay era for conv>=3."""
    sql = """
        SELECT p.predicted_at, p.regime, p.estimate, p.conviction_score,
               m.resolved, m.outcome
        FROM predictions p LEFT JOIN markets m ON p.market_id = m.id
        WHERE p.agent = ? AND p.predicted_at >= ? AND p.predicted_at <= ?
              AND p.conviction_score >= 3 AND m.resolved = 1
    """

    def _bucket_era(start: str, end: str) -> dict:
        cells: dict = defaultdict(lambda: {"w": 0, "l": 0})
        for predicted_at, regime, est, conv, resolved, outcome in db.execute(
            sql, (agent, f"{start}T00:00:00", f"{end}T23:59:59")
        ).fetchall():
            w = _won(est, outcome)
            if w is None:
                continue
            key = (_estimate_bucket(est), regime or "unknown")
            if w:
                cells[key]["w"] += 1
            else:
                cells[key]["l"] += 1
        return cells

    strong = _bucket_era(STRONG_START, STRONG_END)
    decay = _bucket_era(DECAY_START, DECAY_END)
    keys = set(strong.keys()) | set(decay.keys())

    rows = []
    for k in sorted(keys):
        s = strong[k]
        d = decay[k]
        s_n = s["w"] + s["l"]
        d_n = d["w"] + d["l"]
        rows.append({
            "estimate_bucket": k[0],
            "regime": k[1],
            "strong_n": s_n,
            "strong_wr": _wr(s["w"], s["l"]),
            "decay_n": d_n,
            "decay_wr": _wr(d["w"], d["l"]),
            "delta_pp": (
                round(_wr(d["w"], d["l"]) - _wr(s["w"], s["l"]), 1)
                if s_n and d_n else None
            ),
        })
    # Surface durability candidates: cells where decay_wr stayed >55% on N>=20
    survivors = [
        r for r in rows
        if r["decay_n"] >= 20 and (r["decay_wr"] or 0) >= 55
    ]
    return {"agent": agent, "all_cells": rows, "survivors": survivors}


# ── H4 — cross-asset asynchrony ────────────────────────────────────


def h4_cross_asset(db_btc, db_eth) -> dict:
    """Per-week WR for BTC momentum_rule vs ETH momentum_eth (conv>=3)."""
    out: dict = {}
    for label, db, agent in [
        ("BTC", db_btc, "momentum_rule"),
        ("ETH", db_eth, "momentum_eth"),
    ]:
        sql = """
            SELECT date(p.predicted_at) AS d, p.estimate, p.conviction_score,
                   m.resolved, m.outcome
            FROM predictions p LEFT JOIN markets m ON p.market_id = m.id
            WHERE p.agent = ? AND p.predicted_at >= '2026-03-29'
                  AND p.conviction_score >= 3 AND m.resolved = 1
        """
        weekly: dict = defaultdict(lambda: {"w": 0, "l": 0})
        for d, est, conv, resolved, outcome in db.execute(
            sql, (agent,)
        ).fetchall():
            w = _won(est, outcome)
            if w is None:
                continue
            wk = _iso_week(d)
            if w:
                weekly[wk]["w"] += 1
            else:
                weekly[wk]["l"] += 1
        out[label] = {
            wk: {
                "n": v["w"] + v["l"],
                "wr": _wr(v["w"], v["l"]),
            }
            for wk, v in sorted(weekly.items())
        }
    return out


# ── H5 — timing shift ──────────────────────────────────────────────


def h5_timing(db, agent: str) -> dict:
    """Did predicted_at-modulo-5min change between eras?

    The btc_5m pipeline fires on the bybit_spot 5m candle close, so
    predicted_at should be a small offset (1-5s) past each :00, :05, :10
    boundary. If that offset grew between strong and decay eras, the
    cycle is slower — possibly missing fast price moves.
    """
    sql = """
        SELECT p.predicted_at FROM predictions p
        WHERE p.agent = ? AND p.predicted_at >= ? AND p.predicted_at <= ?
        ORDER BY RANDOM() LIMIT 200
    """

    def _offsets(start, end):
        offs = []
        for (predicted_at,) in db.execute(
            sql, (agent, f"{start}T00:00:00", f"{end}T23:59:59")
        ).fetchall():
            try:
                t = datetime.fromisoformat(predicted_at.replace("Z", "+00:00"))
                seconds_past_5min = (t.minute % 5) * 60 + t.second
                offs.append(seconds_past_5min)
            except Exception:
                continue
        return offs

    strong = _offsets(STRONG_START, STRONG_END)
    decay = _offsets(DECAY_START, DECAY_END)

    def _summary(offs):
        if not offs:
            return None
        offs = sorted(offs)
        return {
            "n": len(offs),
            "median_s": offs[len(offs) // 2],
            "p90_s": offs[int(len(offs) * 0.9)],
            "p99_s": offs[int(len(offs) * 0.99)],
        }

    return {
        "agent": agent,
        "strong": _summary(strong),
        "decay": _summary(decay),
    }


# ── Markdown rendering ─────────────────────────────────────────────


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def render(report: dict) -> str:
    h1, h2, h3, h4, h5 = (
        report["h1"], report["h2"], report["h3"], report["h4"], report["h5"]
    )
    h1_eth, h2_eth, h3_eth = (
        report["h1_eth"], report["h2_eth"], report["h3_eth"]
    )
    lines = [
        f"# Signal Rehabilitation Analysis — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        "",
        "Five hypotheses about the V4 momentum decay, measured against "
        "predictions.db (BTC) and predictions_eth.db (ETH). All numbers "
        "are conviction>=3 unless noted (production cohort).",
        "",
        f"**Strong era:** {STRONG_START} → {STRONG_END}",
        f"**Decay era:** {DECAY_START} → {DECAY_END}",
        "",
        "---",
        "",
        "## H1 — Lab-to-production translation lying?",
        "",
        "*If aggregate (all-conviction) WR stays stable while conv≥3 WR "
        "drops, the signal still has edge — adverse selection is eating "
        "production fills.*",
        "",
        "### BTC (momentum_rule)",
        "",
        _table(
            ["week", "lab N", "lab WR%", "prod N", "prod WR%", "gap (pp)"],
            [[r["week_start"], r["lab_n"], r["lab_wr"],
              r["prod_n"], r["prod_wr"], r["gap_pp"]]
             for r in h1["weekly"]],
        ),
        "",
        "### ETH (momentum_eth)",
        "",
        _table(
            ["week", "lab N", "lab WR%", "prod N", "prod WR%", "gap (pp)"],
            [[r["week_start"], r["lab_n"], r["lab_wr"],
              r["prod_n"], r["prod_wr"], r["gap_pp"]]
             for r in h1_eth["weekly"]],
        ),
        "",
        "**How to read:** if `lab WR%` stays roughly constant week-over-week "
        "while `prod WR%` declines, H1 is supported — the signal hasn't "
        "decayed, just our subset of it that fires conviction>=3 has gotten "
        "worse. If both decline together, the signal itself is the problem.",
        "",
        "---",
        "",
        "## H2 — Regime mix shift",
        "",
        "*Per-regime WR by week + regime share of all predictions. If a "
        "regime's WR is stable but its share grew (or another regime's "
        "share grew where WR was always bad), the signal is fine — the "
        "market shifted under it.*",
        "",
        "### BTC",
        "",
        _table(
            ["week", "regime", "bets (conv≥3)", "WR%", "regime share"],
            [[r["week_start"], r["regime"], r["bets"], r["wr_pct"],
              f"{r['regime_share_pct']}%" if r["regime_share_pct"] else None]
             for r in h2["cells"]],
        ),
        "",
        "### ETH",
        "",
        _table(
            ["week", "regime", "bets (conv≥3)", "WR%", "regime share"],
            [[r["week_start"], r["regime"], r["bets"], r["wr_pct"],
              f"{r['regime_share_pct']}%" if r["regime_share_pct"] else None]
             for r in h2_eth["cells"]],
        ),
        "",
        "---",
        "",
        "## H3 — Cell decay (estimate × regime)",
        "",
        "*Strong-era WR vs decay-era WR per (estimate_bucket × regime) "
        "cell. Cells where decay-era WR stayed >55% on N>=20 are listed "
        "as `survivors` — production-restriction targets.*",
        "",
        "### BTC survivors (decay-era N≥20, WR≥55%)",
        "",
    ]
    if h3["survivors"]:
        lines.append(_table(
            ["estimate", "regime", "strong N", "strong WR%",
             "decay N", "decay WR%", "delta (pp)"],
            [[r["estimate_bucket"], r["regime"], r["strong_n"], r["strong_wr"],
              r["decay_n"], r["decay_wr"], r["delta_pp"]]
             for r in h3["survivors"]],
        ))
    else:
        lines.append("**No BTC cells survived** the decay-era N≥20 + WR≥55% bar. "
                     "Restriction-based rehabilitation has no target for BTC "
                     "based on (estimate × regime) alone.")
    lines += [
        "",
        "### ETH survivors (decay-era N≥20, WR≥55%)",
        "",
    ]
    if h3_eth["survivors"]:
        lines.append(_table(
            ["estimate", "regime", "strong N", "strong WR%",
             "decay N", "decay WR%", "delta (pp)"],
            [[r["estimate_bucket"], r["regime"], r["strong_n"], r["strong_wr"],
              r["decay_n"], r["decay_wr"], r["delta_pp"]]
             for r in h3_eth["survivors"]],
        ))
    else:
        lines.append("**No ETH cells survived** the bar.")

    lines += [
        "",
        "### BTC: full table (all cells)",
        "",
        "<details><summary>expand</summary>",
        "",
        _table(
            ["estimate", "regime", "strong N", "strong WR%",
             "decay N", "decay WR%", "delta (pp)"],
            [[r["estimate_bucket"], r["regime"], r["strong_n"], r["strong_wr"],
              r["decay_n"], r["decay_wr"], r["delta_pp"]]
             for r in h3["all_cells"]],
        ),
        "",
        "</details>",
        "",
        "---",
        "",
        "## H4 — Cross-asset asynchrony (BTC vs ETH)",
        "",
        "*Per-week conviction>=3 WR for both assets, side by side. If one "
        "kept its edge while the other lost it, capital should follow the "
        "live signal.*",
        "",
    ]
    btc_wks = h4.get("BTC", {})
    eth_wks = h4.get("ETH", {})
    all_wks = sorted(set(btc_wks.keys()) | set(eth_wks.keys()))
    rows_h4 = []
    for wk in all_wks:
        b = btc_wks.get(wk, {})
        e = eth_wks.get(wk, {})
        delta = (
            round(e.get("wr") - b.get("wr"), 1)
            if e.get("wr") is not None and b.get("wr") is not None else None
        )
        rows_h4.append([
            wk,
            b.get("n", 0), b.get("wr"),
            e.get("n", 0), e.get("wr"),
            delta,
        ])
    lines.append(_table(
        ["week", "BTC N", "BTC WR%", "ETH N", "ETH WR%", "ETH-BTC (pp)"],
        rows_h4,
    ))

    lines += [
        "",
        "---",
        "",
        "## H5 — Timing shift",
        "",
        "*Median seconds past each 5-minute boundary for prediction "
        "writes, sampled randomly from each era. If decay-era predictions "
        "are systematically later within the cycle, slower dispatch "
        "could be missing fast price moves.*",
        "",
        _table(
            ["era", "n", "median (s)", "p90 (s)", "p99 (s)"],
            [
                ["strong",
                 (h5["strong"] or {}).get("n"),
                 (h5["strong"] or {}).get("median_s"),
                 (h5["strong"] or {}).get("p90_s"),
                 (h5["strong"] or {}).get("p99_s")],
                ["decay",
                 (h5["decay"] or {}).get("n"),
                 (h5["decay"] or {}).get("median_s"),
                 (h5["decay"] or {}).get("p90_s"),
                 (h5["decay"] or {}).get("p99_s")],
            ],
        ),
        "",
        "---",
        "",
        "## How to use this",
        "",
        "1. Read H1 first. It either explains everything (signal still good, "
        "execution broken) or rules out the cheap fix.",
        "2. If H1 doesn't explain it, look at H2. Stable regime-WR + shifted "
        "regime mix is also recoverable — just restrict trading to the "
        "regimes that work.",
        "3. H3 is the granular rehab list. Surviving cells with N≥20 "
        "are concrete production-restriction candidates.",
        "4. H4 tells you whether the answer is asset-specific. ETH 5m had a "
        "positive 7d signal EHR going into the outage; that may persist.",
        "5. H5 is a sanity check — if timing shifted dramatically, fix that "
        "before anything else.",
        "",
        "*Note: pre-Apr-24 data only. The 2026-04-24/28 disk-full outage "
        "produced no predictions during that window. Apr 28 onward is "
        "fresh data accumulating from the recovered engine.*",
        "",
    ]
    return "\n".join(lines)


# ── Entry point ────────────────────────────────────────────────────


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-md", default=None)
    args = parser.parse_args()

    out_md = args.out_md or str(
        ROOT / "docs" / "analysis" / f"signal_rehab_{datetime.now():%Y-%m-%d}.md"
    )

    db_btc = sqlite3.connect(str(DB_BTC))
    db_eth = sqlite3.connect(str(DB_ETH))
    try:
        report = {
            "h1": h1_lab_vs_production(db_btc, "momentum_rule"),
            "h1_eth": h1_lab_vs_production(db_eth, "momentum_eth"),
            "h2": h2_regime_shift(db_btc, "momentum_rule"),
            "h2_eth": h2_regime_shift(db_eth, "momentum_eth"),
            "h3": h3_cell_decay(db_btc, "momentum_rule"),
            "h3_eth": h3_cell_decay(db_eth, "momentum_eth"),
            "h4": h4_cross_asset(db_btc, db_eth),
            "h5": h5_timing(db_btc, "momentum_rule"),
        }
    finally:
        db_btc.close()
        db_eth.close()

    md = render(report)
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text(md)
    print(f"wrote {out_md}")
    print(f"  H1 BTC weeks: {len(report['h1']['weekly'])}")
    print(f"  H1 ETH weeks: {len(report['h1_eth']['weekly'])}")
    print(f"  H2 BTC cells: {len(report['h2']['cells'])}")
    print(f"  H3 BTC survivors: {len(report['h3']['survivors'])}")
    print(f"  H3 ETH survivors: {len(report['h3_eth']['survivors'])}")
    print(f"  H4 weeks: {len(set(report['h4'].get('BTC', {}).keys()) | set(report['h4'].get('ETH', {}).keys()))}")
    print(f"  H5: strong n={(report['h5']['strong'] or {}).get('n')}, "
          f"decay n={(report['h5']['decay'] or {}).get('n')}")


if __name__ == "__main__":
    run()
