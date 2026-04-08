"""
backtest_bybit_regime_cut.py — Re-cut the 6mo Bybit momentum backtest by
daily regime (trend_label × velocity bucket) to test the hypothesis that
the headline 63% WR was a chop-regime artifact.

Hypothesis (from 12-day live decay analysis, 2026-04-08):
  BTC 5m momentum signal wins in chop, loses on strong trending days —
  the inverse of its design intent. If true, the 6mo backtest WR should
  also collapse when conditioned on trend_label='up'/'down' with high
  velocity, and be inflated by chop days.

Pipeline:
  1. Reuse `backtest_bybit.simulate` on cached `data/bybit_5m_6mo.csv`.
  2. For each trade, map entry_idx → UTC date, join to `asset_daily`
     (asset='BTC') to pull trend_label, velocity, realized_vol, range_pct.
  3. Pivot WR + P&L + N by:
       - trend_label (chop / up / down)
       - velocity bucket (|v|<0.3, 0.3-0.8, 0.8-1.5, >1.5)
       - trend_label × velocity bucket
  4. Write report to docs/research/btc5m_regime_cut_2026-04.md.

Runs offline from the CSV cache — no network.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
SRC = ROOT / "src"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(SRC))

from backtest_bybit import load_csv, simulate  # noqa: E402

CSV = ROOT / "data" / "bybit_5m_6mo.csv"
DAILY_DB = ROOT / "data" / "asset_daily.db"
OUT = ROOT / "docs" / "research" / "btc5m_regime_cut_2026-04.md"

VEL_BUCKETS = [
    ("flat |v|<0.3", 0.0, 0.3),
    ("mild 0.3-0.8", 0.3, 0.8),
    ("strong 0.8-1.5", 0.8, 1.5),
    ("extreme >1.5", 1.5, 1e9),
]


def vel_bucket(v: float) -> str:
    av = abs(v)
    for name, lo, hi in VEL_BUCKETS:
        if lo <= av < hi:
            return name
    return "unknown"


def load_daily():
    conn = sqlite3.connect(DAILY_DB)
    rows = conn.execute(
        "SELECT date, trend_label, velocity, realized_vol, range_pct, "
        "intraday_drift, velocity_zscore, range_zscore "
        "FROM asset_daily WHERE asset='BTC'"
    ).fetchall()
    conn.close()
    return {
        r[0]: {
            "trend": r[1], "vel": r[2] or 0.0, "rv": r[3] or 0.0,
            "rng": r[4] or 0.0, "drift": r[5] or 0.0,
            "v_z": r[6], "r_z": r[7],
        }
        for r in rows
    }


def fmt_row(name, n, wr, pnl):
    return f"| {name} | {n} | {wr:.1f}% | ${pnl:+.2f} |"


def pivot(trades, key_fn, title):
    groups: dict[str, list] = {}
    for t in trades:
        k = key_fn(t)
        if k is None:
            continue
        groups.setdefault(k, []).append(t)
    lines = [f"## {title}", "| Bucket | N | WR | P&L |", "|---|--:|--:|--:|"]
    for k in sorted(groups.keys()):
        g = groups[k]
        wr = sum(1 for t in g if t.pnl > 0) / len(g) * 100
        pnl = sum(t.pnl for t in g)
        lines.append(fmt_row(k, len(g), wr, pnl))
    lines.append("")
    return lines


def main():
    print(f"Loading {CSV}...")
    candles = load_csv(CSV)
    print(f"  {len(candles)} candles")

    print("Simulating momentum walk (window=24, hold=6, min_streak=3)...")
    trades = simulate(candles, window=24, hold=6, min_streak=3)
    print(f"  {len(trades)} trades")

    print(f"Loading daily regime from {DAILY_DB}...")
    daily = load_daily()
    print(f"  {len(daily)} BTC daily rows")

    # Attach regime per trade via entry_idx → UTC date
    enriched = []
    missing = 0
    for t in trades:
        ts = candles[t.entry_idx]["ts"]
        d = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        reg = daily.get(d)
        if reg is None:
            missing += 1
            continue
        t.day = d
        t.trend = reg["trend"] or "unknown"
        t.vel = reg["vel"]
        t.vel_bkt = vel_bucket(reg["vel"])
        t.rv = reg["rv"]
        t.v_z = reg["v_z"]
        t.r_z = reg["r_z"]
        enriched.append(t)
    print(f"  enriched {len(enriched)} / {len(trades)} ({missing} missing daily)")

    wins = sum(1 for t in enriched if t.pnl > 0)
    total_wr = wins / len(enriched) * 100 if enriched else 0
    total_pnl = sum(t.pnl for t in enriched)

    lines = [
        "# BTC 5m momentum — 6mo backtest regime cut",
        "",
        "Re-cut of `tools/backtest_bybit.py` output conditioned on",
        "`data/asset_daily.db` trend_label and velocity buckets. Tests",
        "the hypothesis (from 2026-04-08 live decay analysis) that the",
        "headline 6mo WR was a chop-regime artifact: the signal wins in",
        "chop and loses in trends — the inverse of its design intent.",
        "",
        f"- Trades (enriched): **{len(enriched)}**",
        f"- Overall WR: **{total_wr:.1f}%**",
        f"- Overall P&L: **${total_pnl:+.2f}**",
        "",
    ]
    lines += pivot(enriched, lambda t: t.trend, "By trend_label")
    lines += pivot(enriched, lambda t: t.vel_bkt, "By velocity bucket")
    lines += pivot(
        enriched, lambda t: f"{t.trend} / {t.vel_bkt}",
        "By trend_label × velocity bucket",
    )

    # ── Rank-gate simulation (option #4) ────────────────────────────────
    # Restrict to trades whose day has a computed zscore (≥5d history).
    ranked = [t for t in enriched if t.v_z is not None and t.r_z is not None]
    lines.append("## Rank-based gate (velocity_zscore / range_zscore)")
    lines.append(
        f"Trades with both zscores computed (≥5d trailing history): "
        f"**{len(ranked)}**"
    )
    lines.append("")
    lines.append(
        "Gate: skip trade if `abs(velocity_zscore) ≥ v_thresh` OR "
        "`range_zscore ≥ r_thresh`. Rationale: high-velocity / wide-range "
        "days are where the 12-day live tape saw momentum collapse."
    )
    lines.append("")
    lines.append(
        "| v_thresh | r_thresh | Kept | Skipped | WR kept | P&L kept | "
        "WR skipped | P&L skipped |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|--:|--:|")
    for v_th, r_th in [
        (99.0, 99.0),  # no gate baseline
        (2.0, 2.5),
        (1.5, 2.0),
        (1.0, 1.5),
        (1.5, 99.0),  # velocity gate only
        (99.0, 2.0),  # range gate only
    ]:
        kept = [
            t for t in ranked
            if abs(t.v_z) < v_th and t.r_z < r_th
        ]
        skipped = [t for t in ranked if t not in kept]

        def _wr(g):
            return (
                sum(1 for t in g if t.pnl > 0) / len(g) * 100
                if g else 0.0
            )

        def _pnl(g):
            return sum(t.pnl for t in g)
        lines.append(
            f"| {v_th} | {r_th} | {len(kept)} | {len(skipped)} | "
            f"{_wr(kept):.1f}% | ${_pnl(kept):+.2f} | "
            f"{_wr(skipped):.1f}% | ${_pnl(skipped):+.2f} |"
        )
    lines.append("")

    # Verdict
    by_trend = {}
    for t in enriched:
        by_trend.setdefault(t.trend, []).append(t)
    chop = by_trend.get("chop", [])
    up = by_trend.get("up", [])
    down = by_trend.get("down", [])

    def wr_of(g):
        return sum(1 for t in g if t.pnl > 0) / len(g) * 100 if g else 0

    lines.append("## Verdict")
    if chop and (up or down):
        chop_wr = wr_of(chop)
        trend_wr = wr_of(up + down)
        delta = chop_wr - trend_wr
        lines.append(
            f"- chop WR: **{chop_wr:.1f}%** (N={len(chop)})"
        )
        lines.append(
            f"- trending WR (up+down): **{trend_wr:.1f}%** "
            f"(N={len(up) + len(down)})"
        )
        lines.append(f"- chop − trend gap: **{delta:+.1f} pts**")
        lines.append("")
        if delta >= 5:
            lines.append(
                "⚠️ **Hypothesis supported.** The 6mo backtest was "
                "chop-inflated. The signal is materially weaker on "
                "trending days than the headline WR implies. The live "
                "decay from Apr 4–7 (consecutive trending-up days, "
                "velocity peaking at 1.77) is consistent with this cut."
            )
        elif delta <= -5:
            lines.append(
                "❓ **Hypothesis inverted.** Backtest shows signal stronger "
                "in trends than chop — contradicts the live 12-day cut. "
                "Possible explanation: 6mo tape had different trend "
                "character (magnitude vs direction)."
            )
        else:
            lines.append(
                f"➖ **No material regime skew in the 6mo backtest** "
                f"(chop−trend gap {delta:+.1f} pts within noise). The "
                f"live Apr 4–7 collapse must be explained by something "
                f"other than trend_label alone — candidates: realized_vol "
                f"regime shift, range_pct tail, or drawdown clustering."
            )
    lines.append("")

    text = "\n".join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n")
    print()
    print(text)
    print(f"\nReport: {OUT}")


if __name__ == "__main__":
    main()
