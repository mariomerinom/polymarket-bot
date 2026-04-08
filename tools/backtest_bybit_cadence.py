"""
backtest_bybit_cadence.py — Re-test VWAP mean-reversion at 15m and 1h.

The 5m sweep in backtest_bybit_alt.py proved VWAP-MR has structural
edge on reverting trades (99-100% WR on mean_revert exits) but the
non-reverting half is unhedgeable at 5m — every stop level makes P&L
monotonically worse. The diagnostic hypothesis is that reversion
horizon may align with a longer bar size: give the winners more room
to outrun fees, and reduce the number of micro-trend bars that look
like mean-reversion setups but are actually trend continuation.

Pipeline:
  1. Load cached 5m CSV.
  2. Resample to 15m and 1h bars (3x and 12x aggregation).
  3. Re-run VWAP-MR signal + walk harness at each cadence.
  4. Sweep entry_z and hold, compare to the 5m baseline.

Writes: docs/research/bybit_cadence_sweep_2026-04.md
Usage: python3 tools/backtest_bybit_cadence.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
SRC = TOOLS.parent / "src"
sys.path.insert(0, str(SRC))

from backtest_bybit import load_csv  # noqa: E402
from backtest_bybit_alt import walk, summarize, split_by_reason  # noqa: E402
from signals_bybit import vwap_mr_signal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BYBIT_CSV = ROOT / "data" / "bybit_5m_6mo.csv"
OUT = ROOT / "docs" / "research" / "bybit_cadence_sweep_2026-04.md"


def resample(candles_5m: List[dict], factor: int) -> List[dict]:
    """Aggregate N consecutive 5m candles into one bar. Only emit a bar
    when timestamps are contiguous (gap = 300_000 ms)."""
    out: List[dict] = []
    i = 0
    n = len(candles_5m)
    step_ms = 300_000
    while i + factor <= n:
        chunk = candles_5m[i:i + factor]
        # contiguity check
        contiguous = all(
            chunk[j + 1]["ts"] - chunk[j]["ts"] == step_ms
            for j in range(factor - 1)
        )
        if not contiguous:
            i += 1
            continue
        o = chunk[0]["open"]
        c = chunk[-1]["close"]
        h = max(x["high"] for x in chunk)
        lo = min(x["low"] for x in chunk)
        vol = sum(x["volume"] for x in chunk)
        body = abs(c - o)
        rng = h - lo
        out.append({
            "ts": chunk[0]["ts"],
            "time": datetime.fromtimestamp(
                chunk[0]["ts"] / 1000, tz=timezone.utc
            ).isoformat(),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": round(vol, 2),
            "direction": "UP" if c >= o else "DOWN",
            "body_pct": round((c - o) / o * 100, 4) if o else 0.0,
            "wick_ratio": round(1.0 - (body / rng), 2) if rng > 0 else 0.0,
        })
        i += factor
    return out


def sweep_cadence(candles, label, lines):
    """Run a small VWAP-MR sweep on the given candle series."""
    lines.append(f"## {label}  (N candles = {len(candles)})")
    lines.append("")
    lines.append("| entry_z | hold | stop | N | WR | P&L | mean_revert | stop/time |")
    lines.append("|---:|---:|---:|---:|---:|---:|---|---|")
    configs = []
    for entry_z in (2.0, 2.5, 3.0):
        for hold in (12, 24, 48):
            for stop in (None, 2.0, 3.0):
                configs.append((entry_z, hold, stop))
    best = None
    for entry_z, hold, stop in configs:
        trades = walk(
            candles,
            signal_fn=vwap_mr_signal,
            signal_name=f"{label}_z{entry_z}_h{hold}_s{stop}",
            window=48, hold=hold, exit_on_reversion=True,
            signal_kwargs={"entry_z": entry_z},
            stop_sd_mult=stop,
        )
        s = summarize(trades, "")
        if not trades:
            continue
        buckets = split_by_reason(trades)
        mr = buckets.get("mean_revert", [])
        mr_wr = sum(1 for t in mr if t.pnl > 0) / len(mr) * 100 if mr else 0
        mr_pnl = sum(t.pnl for t in mr)
        other = [
            t for t in trades
            if t.reason in ("stop_loss", "time_ceiling")
        ]
        other_pnl = sum(t.pnl for t in other)
        lines.append(
            f"| {entry_z} | {hold} | {stop} | {s['n']} | {s['wr']:.1f}% | "
            f"${s['pnl']:+.0f} | {len(mr)}@{mr_wr:.0f}% ${mr_pnl:+.0f} | "
            f"{len(other)} ${other_pnl:+.0f} |"
        )
        if s["n"] >= 50 and s["pnl"] > (best["pnl"] if best else -1e9):
            best = {**s, "entry_z": entry_z, "hold": hold, "stop": stop}
    lines.append("")
    if best:
        lines.append(
            f"**Best cell @ {label}:** z={best['entry_z']} hold={best['hold']} "
            f"stop={best['stop']} → N={best['n']} WR={best['wr']:.1f}% "
            f"P&L=${best['pnl']:+.2f}"
        )
    else:
        lines.append(f"**No tradable cells at {label}.**")
    lines.append("")
    return best


def main():
    if not BYBIT_CSV.exists():
        print(f"Missing {BYBIT_CSV}")
        sys.exit(1)
    print(f"Loading {BYBIT_CSV}...")
    c5 = load_csv(BYBIT_CSV)
    print(f"  5m: {len(c5)} candles")

    print("Resampling to 15m...")
    c15 = resample(c5, 3)
    print(f"  15m: {len(c15)} candles")

    print("Resampling to 1h...")
    c60 = resample(c5, 12)
    print(f"  1h: {len(c60)} candles")

    lines = [
        "# Bybit VWAP-MR cadence sweep — 5m / 15m / 1h",
        "",
        "The 5m VWAP-MR sweep found mean_revert exits at 99-100% WR but "
        "the non-reverting half losing 0% WR at every stop level. "
        "Hypothesis: reversion horizon is longer than 5m × hold; test at "
        "15m and 1h bars where the same `hold` N covers 3x/12x real time.",
        "",
    ]

    best_5m = sweep_cadence(c5, "5m baseline", lines)
    best_15m = sweep_cadence(c15, "15m", lines)
    best_1h = sweep_cadence(c60, "1h", lines)

    lines.append("## Verdict")
    winners = [
        (lab, b) for lab, b in
        [("5m", best_5m), ("15m", best_15m), ("1h", best_1h)]
        if b and b["wr"] >= 55 and b["pnl"] > 0 and b["n"] >= 100
    ]
    if winners:
        for lab, b in winners:
            lines.append(
                f"- ✅ **{lab}**: z={b['entry_z']} hold={b['hold']} "
                f"stop={b['stop']} → WR={b['wr']:.1f}% on N={b['n']} "
                f"(P&L=${b['pnl']:+.2f})"
            )
    else:
        lines.append(
            "❌ No cadence × parameter cell clears the 55% WR / N≥100 bar. "
            "Longer bars reduce sample size proportionally (~3x, ~12x) "
            "without fixing the asymmetric tail. Reversion horizon is not "
            "the constraint — the losing half is genuine trend regime."
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
