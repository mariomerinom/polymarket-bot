"""
backtest_bybit_oos.py — Out-of-sample confirmation for the sweep winner.

The parameter sweep surfaced exactly one cell that cleared the 55% WR
bar on N >= 100 trades (6mo BTCUSDT 1h):

    bar=1h  hold=24  min_streak=3  entry=fade  exit=time_only
    N=126   WR=56.3%   P&L=+$42.09

That's suspiciously fragile for a 6-month, thin-N, in-sample win. This
script splits the 6mo history in half (oldest → newest) and runs the
same winner on EACH half independently, plus a final alternating
month split (odd months train, even months test). If the cell holds
above 52% on BOTH halves, we have a weak but real lead. If it dies on
either half, the in-sample win was curve-fit.

Usage:
    python3 tools/backtest_bybit_oos.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from backtest_bybit import load_csv  # noqa: E402
from backtest_bybit_sweep import resample, simulate  # noqa: E402

WINNER = dict(hold=24, min_streak=3, entry_mode="fade", exit_mode="time_only")


def _wr_pnl(trades):
    if not trades:
        return (0, 0.0, 0.0)
    wins = sum(1 for t in trades if t.pnl > 0)
    pnl = sum(t.pnl for t in trades)
    return (len(trades), wins / len(trades) * 100, pnl)


def run(slice_candles, label):
    trades = simulate(slice_candles, window=24, **WINNER)
    n, wr, pnl = _wr_pnl(trades)
    print(f"  {label:25s}  N={n:5d}  WR={wr:5.1f}%  P&L=${pnl:8.2f}")
    return {"label": label, "n": n, "wr": wr, "pnl": pnl}


def main():
    csv_path = Path("data/bybit_5m_6mo.csv")
    c5m = load_csv(csv_path)
    # Winner is 1h bar → factor 12
    c1h = resample(c5m, 12)
    print(f"{len(c1h)} 1h candles loaded "
          f"({datetime.fromtimestamp(c1h[0]['ts']/1000, tz=timezone.utc).date()} → "
          f"{datetime.fromtimestamp(c1h[-1]['ts']/1000, tz=timezone.utc).date()})")
    print()
    print(f"Winner cell: {WINNER}")
    print()

    results = []

    # Full (sanity replay)
    results.append(run(c1h, "Full 6mo"))

    # Chronological halves
    mid = len(c1h) // 2
    results.append(run(c1h[:mid], "First half (older)"))
    results.append(run(c1h[mid:], "Second half (newer)"))

    # Quarterly splits
    q = len(c1h) // 4
    for i in range(4):
        lo = i * q
        hi = (i + 1) * q if i < 3 else len(c1h)
        results.append(run(c1h[lo:hi], f"Q{i+1}"))

    # Month-alternating split
    def _month(ts_ms):
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).month
    odd = [c for c in c1h if _month(c["ts"]) % 2 == 1]
    even = [c for c in c1h if _month(c["ts"]) % 2 == 0]
    print()
    results.append(run(odd, "Odd months"))
    results.append(run(even, "Even months"))

    print()
    # Verdict: need EVERY chronological half and EVERY quarter >= 52%
    halves = [r for r in results if "half" in r["label"]]
    quarters = [r for r in results if r["label"].startswith("Q")]

    passed_halves = all(r["wr"] >= 52 for r in halves) and all(r["pnl"] >= 0 for r in halves)
    passed_quarters = sum(1 for r in quarters if r["wr"] >= 52)

    print("Verdict")
    print("-------")
    if passed_halves and passed_quarters >= 3:
        print("✅ Winner survives OOS. Worth a forward paper test + rebuild pivot.")
    elif passed_halves:
        print(f"⚠️ Halves survive but only {passed_quarters}/4 quarters do — fragile.")
    else:
        print("❌ Winner is curve-fit. At least one half below 52% or PnL negative. "
              "Kill this lead — do not rebuild pivot on it.")

    # Write report
    lines = ["# Bybit perp — OOS confirmation of sweep winner", ""]
    lines.append(f"Winner cell: `{WINNER}` + `window=24`")
    lines.append("")
    lines.append("| Split | N | WR | P&L |")
    lines.append("|---|---:|---:|---:|")
    for r in results:
        lines.append(f"| {r['label']} | {r['n']} | {r['wr']:.1f}% | ${r['pnl']:.2f} |")
    lines.append("")
    lines.append("## Verdict")
    if passed_halves and passed_quarters >= 3:
        lines.append("✅ Survives OOS.")
    elif passed_halves:
        lines.append(f"⚠️ Halves survive but only {passed_quarters}/4 quarters.")
    else:
        lines.append("❌ Curve-fit; at least one chronological half fails the 52% bar.")
    Path("docs/research/bybit_backtest_oos_2026-04.md").write_text("\n".join(lines) + "\n")
    print()
    print("Report: docs/research/bybit_backtest_oos_2026-04.md")


if __name__ == "__main__":
    main()
