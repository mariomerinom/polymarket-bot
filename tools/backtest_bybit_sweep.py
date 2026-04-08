"""
backtest_bybit_sweep.py — Parameter sweep over cached Bybit 5m data.

Phase 2 backtest on 5m bars returned 28.6% WR. Before killing the
Bybit pivot we test whether the signal works on DIFFERENT assumptions:

  * bar size     : 5m, 15m, 1h (5m is resampled for the latter two)
  * min_streak   : 3, 4, 5
  * hold ceiling : 3, 6, 12, 24 candles
  * entry rule   : ride (current) | fade (contrarian)
  * exit rule    : streak_break | time_only
                 | trailing_0p5 | trailing_1p0 (percent of entry)

The goal is to find any cell of the grid where WR >= 52% on
N >= 100 trades. If nothing clears that bar, the momentum signal is
well and truly dead on perps and the pivot is over.

Reads data/bybit_5m_6mo.csv (written by tools/backtest_bybit.py).
Writes docs/research/bybit_backtest_sweep_2026-04.md with the ranked
grid and a one-line verdict.

Usage:
    python3 tools/backtest_bybit_sweep.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from predict import compute_regime_from_candles, momentum_signal  # noqa: E402
from bybit_trade import _compute_pnl  # noqa: E402
from config import BYBIT_BET_SIZE  # noqa: E402

from backtest_bybit import load_csv  # noqa: E402


# ── Resample 5m → N-minute ───────────────────────────────────────────────────

def resample(candles: List[dict], factor: int) -> List[dict]:
    """Aggregate `factor` consecutive 5m candles into one. factor=1 → no-op."""
    if factor == 1:
        return candles
    out = []
    for i in range(0, len(candles) - factor + 1, factor):
        chunk = candles[i : i + factor]
        o = chunk[0]["open"]
        c = chunk[-1]["close"]
        h = max(x["high"] for x in chunk)
        lo = min(x["low"] for x in chunk)
        v = sum(x["volume"] for x in chunk)
        body = abs(c - o)
        rng = h - lo
        out.append({
            "ts": chunk[0]["ts"],
            "time": chunk[0]["time"],
            "open": o, "high": h, "low": lo, "close": c,
            "volume": v,
            "direction": "UP" if c >= o else "DOWN",
            "body_pct": round((c - o) / o * 100, 4) if o else 0.0,
            "wick_ratio": round(1.0 - body / rng, 2) if rng > 0 else 0.0,
        })
    return out


# ── Walk with pluggable entry + exit rules ───────────────────────────────────

@dataclass
class Trade:
    side: str
    entry: float
    exit: float
    pnl: float
    regime: str
    streak: int
    reason: str


def simulate(candles, *, window, hold, min_streak, entry_mode, exit_mode):
    trades: List[Trade] = []
    open_t: Optional[Trade] = None
    entry_i = -1
    trail_peak = 0.0  # for trailing stop

    for i in range(window, len(candles) - 1):
        win = candles[i - window + 1 : i + 1]
        regime = compute_regime_from_candles(win)
        signal = momentum_signal(win, min_streak=min_streak)
        price = candles[i]["close"]

        # Exit
        if open_t is not None:
            held = i - entry_i
            reason = ""
            exit_now = False

            if exit_mode == "streak_break" and signal.get("should_trade"):
                sig_side = "Buy" if signal["direction"] == "UP" else "Sell"
                if sig_side != open_t.side:
                    exit_now, reason = True, "streak_break"

            if not exit_now and exit_mode.startswith("trailing_"):
                pct = float(exit_mode.split("_")[1].replace("p", ".")) / 100
                if open_t.side == "Buy":
                    trail_peak = max(trail_peak, price)
                    if price <= trail_peak * (1 - pct):
                        exit_now, reason = True, "trail_stop"
                else:
                    trail_peak = min(trail_peak, price)
                    if price >= trail_peak * (1 + pct):
                        exit_now, reason = True, "trail_stop"

            if not exit_now and held >= hold:
                exit_now, reason = True, "time_ceiling"

            if exit_now:
                pnl = _compute_pnl(open_t.side, BYBIT_BET_SIZE, open_t.entry, price)
                trades.append(Trade(open_t.side, open_t.entry, price, pnl,
                                    open_t.regime, open_t.streak, reason))
                open_t = None

        # Entry
        if open_t is None and signal.get("should_trade") and not regime.get("is_mean_reverting"):
            if entry_mode == "ride":
                side = "Buy" if signal["direction"] == "UP" else "Sell"
            elif entry_mode == "fade":
                side = "Sell" if signal["direction"] == "UP" else "Buy"
            else:
                continue
            open_t = Trade(side, price, 0.0, 0.0,
                           regime.get("label", "?"),
                           int(signal.get("streak", 0)), "")
            entry_i = i
            trail_peak = price

    return trades


# ── Grid runner ──────────────────────────────────────────────────────────────

def run_grid(c5m: List[dict]) -> List[dict]:
    bar_factors = {"5m": 1, "15m": 3, "1h": 12}
    holds = [3, 6, 12, 24]
    streaks = [3, 4, 5]
    entries = ["ride", "fade"]
    exits = ["streak_break", "time_only", "trailing_0p5", "trailing_1p0"]

    results = []
    cache = {}
    for bar, factor in bar_factors.items():
        if factor not in cache:
            cache[factor] = resample(c5m, factor)
        candles = cache[factor]
        for hold in holds:
            for streak in streaks:
                for entry in entries:
                    for exit_mode in exits:
                        trades = simulate(
                            candles, window=24, hold=hold,
                            min_streak=streak,
                            entry_mode=entry, exit_mode=exit_mode,
                        )
                        if not trades:
                            continue
                        wins = sum(1 for t in trades if t.pnl > 0)
                        pnl = sum(t.pnl for t in trades)
                        wr = wins / len(trades) * 100
                        results.append({
                            "bar": bar, "hold": hold, "streak": streak,
                            "entry": entry, "exit": exit_mode,
                            "n": len(trades), "wr": wr, "pnl": pnl,
                        })
                        print(f"  {bar:3s} hold={hold:2d} str={streak} "
                              f"{entry:4s} {exit_mode:13s}  "
                              f"n={len(trades):5d}  WR={wr:5.1f}%  "
                              f"P&L=${pnl:8.2f}")
    return results


def report(results: List[dict]) -> str:
    # Filter to meaningful sample size
    kept = [r for r in results if r["n"] >= 100]
    kept.sort(key=lambda r: -r["wr"])

    lines = []
    lines.append("# Bybit perp signal sweep — 6mo BTCUSDT")
    lines.append("")
    lines.append("Grid over bar size × hold × min_streak × entry × exit.")
    lines.append("Filtered to cells with N >= 100 trades.")
    lines.append("")
    lines.append("## Top 25 by WR")
    lines.append("| Bar | Hold | Streak | Entry | Exit | N | WR | P&L |")
    lines.append("|---|---:|---:|---|---|---:|---:|---:|")
    for r in kept[:25]:
        lines.append(
            f"| {r['bar']} | {r['hold']} | {r['streak']} | {r['entry']} | "
            f"{r['exit']} | {r['n']} | {r['wr']:.1f}% | ${r['pnl']:.2f} |"
        )
    lines.append("")
    lines.append("## Top 10 by P&L")
    by_pnl = sorted(kept, key=lambda r: -r["pnl"])[:10]
    lines.append("| Bar | Hold | Streak | Entry | Exit | N | WR | P&L |")
    lines.append("|---|---:|---:|---|---|---:|---:|---:|")
    for r in by_pnl:
        lines.append(
            f"| {r['bar']} | {r['hold']} | {r['streak']} | {r['entry']} | "
            f"{r['exit']} | {r['n']} | {r['wr']:.1f}% | ${r['pnl']:.2f} |"
        )
    lines.append("")

    best_wr = kept[0] if kept else None
    best_pnl = by_pnl[0] if by_pnl else None
    lines.append("## Verdict")
    if best_wr is None:
        lines.append("No cell had >= 100 trades.")
    else:
        lines.append(
            f"Best WR cell: **{best_wr['wr']:.1f}%** ({best_wr['bar']}, hold={best_wr['hold']}, "
            f"streak={best_wr['streak']}, {best_wr['entry']}/{best_wr['exit']}, "
            f"N={best_wr['n']}, P&L=${best_wr['pnl']:.2f})"
        )
        lines.append(
            f"Best P&L cell: **${best_pnl['pnl']:.2f}** ({best_pnl['bar']}, hold={best_pnl['hold']}, "
            f"streak={best_pnl['streak']}, {best_pnl['entry']}/{best_pnl['exit']}, "
            f"N={best_pnl['n']}, WR={best_pnl['wr']:.1f}%)"
        )
        lines.append("")
        if best_wr["wr"] >= 55:
            lines.append("✅ A cell clears the 55% bar — investigate further, "
                         "confirm with an out-of-sample split, then rebuild the pivot.")
        elif best_wr["wr"] >= 52:
            lines.append("⚠️ Gray zone (52–55%). Worth a forward paper test on the "
                         "winning cell before committing more build effort.")
        else:
            lines.append("❌ No cell clears 52%. Momentum is dead on perps across "
                         "every combination tested. Kill the pivot or try a "
                         "fundamentally different signal family.")
    return "\n".join(lines)


def main():
    csv_path = Path("data/bybit_5m_6mo.csv")
    if not csv_path.exists():
        print(f"Missing {csv_path} — run tools/backtest_bybit.py first")
        sys.exit(1)
    print(f"Loading {csv_path}...")
    c5m = load_csv(csv_path)
    print(f"{len(c5m)} 5m candles loaded.")
    print()
    print("Running sweep (288 cells max):")
    results = run_grid(c5m)
    print()
    out = Path("docs/research/bybit_backtest_sweep_2026-04.md")
    text = report(results)
    out.write_text(text + "\n")
    print(text)
    print()
    print(f"Report: {out}")


if __name__ == "__main__":
    main()
