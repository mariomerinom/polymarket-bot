"""
calibrate_bybit_conviction.py — Do Bybit conviction tiers actually predict outcomes?

Reads data/predictions_bybit.db joined to data/asset_daily.db. For every
resolved prediction groups by (conviction_score, day_trend_label, vol_bucket)
and reports n / WR / EV / breakeven. Output is a single markdown table
written to docs/research/bybit_conviction_calibration_2026-04.md.

This is an analysis-only script — no DB writes, no code changes elsewhere.

Usage:
    python3 tools/calibrate_bybit_conviction.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BYBIT_DB = ROOT / "data" / "predictions_bybit.db"
ASSET_DB = ROOT / "data" / "asset_daily.db"
OUT = ROOT / "docs" / "research" / "bybit_conviction_calibration_2026-04.md"

# Bybit bet sizing for EV calc — nominal paper size
BET_USD = 25.0
# Approx edge-per-win at WR=W:  EV = W*BET - (1-W)*BET = (2W - 1) * BET
# Breakeven WR for symmetric: 0.50.


def vol_bucket(v, low, mid):
    if v is None:
        return "—"
    if v <= low:
        return "vol_low"
    if v <= mid:
        return "vol_mid"
    return "vol_hi"


def main():
    db = sqlite3.connect(BYBIT_DB)
    db.row_factory = sqlite3.Row
    if ASSET_DB.exists():
        db.execute("ATTACH DATABASE ? AS ad", (str(ASSET_DB),))
        has_ad = True
    else:
        has_ad = False

    sql = """
        SELECT p.id, p.conviction_score, p.estimate, p.regime,
               m.outcome,
               {trend} AS trend_label,
               {rv}    AS realized_vol
        FROM predictions p
        JOIN markets m ON p.market_id = m.id
        {join}
        WHERE m.resolved = 1 AND m.outcome IS NOT NULL
          AND p.conviction_score >= 1
    """
    if has_ad:
        sql = sql.format(
            trend="ad.trend_label",
            rv="ad.realized_vol",
            join="LEFT JOIN ad.asset_daily ad "
                 "ON ad.asset='BTC' AND ad.date=substr(p.predicted_at,1,10)",
        )
    else:
        sql = sql.format(trend="NULL", rv="NULL", join="")

    rows = [dict(r) for r in db.execute(sql).fetchall()]
    db.close()

    if not rows:
        print("No resolved Bybit predictions — aborting.")
        return

    # vol terciles
    vols = sorted(r["realized_vol"] for r in rows if r["realized_vol"] is not None)
    if len(vols) >= 3:
        lo = vols[len(vols) // 3]
        mi = vols[(2 * len(vols)) // 3]
    else:
        lo = mi = float("inf")

    for r in rows:
        r["direction"] = "UP" if r["estimate"] > 0.5 else "DOWN"
        r["won"] = int(
            (r["direction"] == "UP" and r["outcome"] == 1)
            or (r["direction"] == "DOWN" and r["outcome"] == 0)
        )
        r["vol_bucket"] = vol_bucket(r["realized_vol"], lo, mi)
        r["trend_label"] = r["trend_label"] or "—"

    # Group by conviction only
    by_conv: dict[int, list] = {}
    for r in rows:
        by_conv.setdefault(r["conviction_score"], []).append(r)

    def summary(bucket):
        n = len(bucket)
        wins = sum(r["won"] for r in bucket)
        wr = wins / n if n else 0.0
        ev = (2 * wr - 1) * BET_USD
        return n, wr, ev

    lines = []
    lines.append("# Bybit conviction calibration — Phase 5")
    lines.append("")
    lines.append(f"Source: `{BYBIT_DB.name}` × `{ASSET_DB.name}`")
    lines.append(f"Resolved rows: **{len(rows)}**. Bet size assumption: ${BET_USD}.")
    lines.append("Breakeven WR (symmetric binary): **50.0%**.")
    lines.append("")
    lines.append("## By conviction tier")
    lines.append("| Conviction | N | WR | EV/bet | Verdict |")
    lines.append("|---:|---:|---:|---:|---|")
    for conv in sorted(by_conv.keys()):
        n, wr, ev = summary(by_conv[conv])
        verdict = (
            "edge" if wr >= 0.55 and n >= 30
            else "below breakeven" if wr < 0.50
            else "marginal"
        )
        lines.append(f"| {conv} | {n} | {wr*100:.1f}% | ${ev:+.2f} | {verdict} |")
    lines.append("")

    # Group by (conviction, trend_label)
    lines.append("## By conviction × day trend")
    lines.append("| Conv | Trend | N | WR | EV/bet |")
    lines.append("|---:|---|---:|---:|---:|")
    cells = {}
    for r in rows:
        key = (r["conviction_score"], r["trend_label"])
        cells.setdefault(key, []).append(r)
    for (conv, trend), bucket in sorted(cells.items()):
        if len(bucket) < 10:
            continue
        n, wr, ev = summary(bucket)
        lines.append(f"| {conv} | {trend} | {n} | {wr*100:.1f}% | ${ev:+.2f} |")
    lines.append("")

    # Group by (conviction, vol_bucket)
    lines.append("## By conviction × vol bucket")
    lines.append("| Conv | Vol | N | WR | EV/bet |")
    lines.append("|---:|---|---:|---:|---:|")
    cells2 = {}
    for r in rows:
        key = (r["conviction_score"], r["vol_bucket"])
        cells2.setdefault(key, []).append(r)
    for (conv, vol), bucket in sorted(cells2.items()):
        if len(bucket) < 10:
            continue
        n, wr, ev = summary(bucket)
        lines.append(f"| {conv} | {vol} | {n} | {wr*100:.1f}% | ${ev:+.2f} |")
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    best_conv = max(by_conv.keys())
    n, wr, _ = summary(by_conv[best_conv])
    if wr >= 0.55 and n >= 50:
        lines.append(f"✅ Top tier (conv={best_conv}) clears 55% on N={n}. Keep tiers.")
    elif wr >= 0.52:
        lines.append(f"⚠️ Top tier (conv={best_conv}) marginal "
                     f"({wr*100:.1f}% on N={n}). Worth more data.")
    else:
        lines.append(f"❌ Top tier (conv={best_conv}) below breakeven "
                     f"({wr*100:.1f}% on N={n}). Tiers do not discriminate — "
                     f"consistent with Phase 2 sweep finding that no parameter "
                     f"combination produces stable edge on Bybit 5m perps.")
    lines.append("")

    text = "\n".join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n")
    print(text)
    print()
    print(f"Report: {OUT}")


if __name__ == "__main__":
    main()
