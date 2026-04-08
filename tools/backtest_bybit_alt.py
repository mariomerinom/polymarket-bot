"""
backtest_bybit_alt.py — Pluggable backtest harness for alternative
Bybit signal families (NOT streak momentum).

Reads cached Bybit 5m CSV (and optionally a spot CSV for lead/lag),
accepts a signal function from tools/signals_bybit.py, walks the tape
with a simple time-ceiling exit, and reports WR / P&L / regime
breakdown. Writes a combined report to
docs/research/bybit_alt_signals_backtest_2026-04.md.

Usage:
    python3 tools/backtest_bybit_alt.py
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from bybit_trade import _compute_pnl  # noqa: E402
from config import BYBIT_BET_SIZE  # noqa: E402

from backtest_bybit import load_csv  # noqa: E402
from signals_bybit import (  # noqa: E402
    volbreakout_signal,
    vwap_mr_signal,
    xexch_leadlag_signal,
)


ROOT = Path(__file__).resolve().parent.parent
BYBIT_CSV = ROOT / "data" / "bybit_5m_6mo.csv"
SPOT_CSV = ROOT / "data" / "spot_5m_6mo.csv"
OUT = ROOT / "docs" / "research" / "bybit_alt_signals_backtest_2026-04.md"


@dataclass
class Trade:
    side: str
    entry: float
    exit: float
    pnl: float
    reason: str
    signal: str


def walk(candles, *, signal_fn, signal_name, window, hold, spot_candles=None,
         signal_kwargs=None, exit_on_reversion=False, stop_sd_mult=None):
    """Walk the tape, entering on signal_fn hits, exiting on time ceiling
    or (optionally) on z-score/price crossing vwap (for vwap_mr)."""
    signal_kwargs = signal_kwargs or {}
    trades: List[Trade] = []
    open_t: Optional[Trade] = None
    entry_i = -1
    entry_vwap = None
    entry_sd = None

    n = len(candles)
    for i in range(window, n - 1):
        win = candles[i - window + 1 : i + 1]
        price = candles[i]["close"]

        spot_win = None
        if spot_candles is not None:
            spot_win = spot_candles[i - window + 1 : i + 1]

        # ── Exit ────────────────────────────────────────────────────────
        if open_t is not None:
            held = i - entry_i
            exit_now = False
            reason = ""
            if exit_on_reversion and entry_vwap is not None:
                # Exit when price crosses back through entry vwap
                if open_t.side == "Buy" and price >= entry_vwap:
                    exit_now, reason = True, "mean_revert"
                elif open_t.side == "Sell" and price <= entry_vwap:
                    exit_now, reason = True, "mean_revert"
            if (not exit_now and stop_sd_mult is not None
                    and entry_sd is not None and entry_vwap is not None):
                stop_dist = stop_sd_mult * entry_sd
                if open_t.side == "Buy" and price <= open_t.entry - stop_dist:
                    exit_now, reason = True, "stop_loss"
                elif open_t.side == "Sell" and price >= open_t.entry + stop_dist:
                    exit_now, reason = True, "stop_loss"
            if not exit_now and held >= hold:
                exit_now, reason = True, "time_ceiling"

            if exit_now:
                pnl = _compute_pnl(
                    open_t.side, BYBIT_BET_SIZE, open_t.entry, price,
                )
                trades.append(Trade(
                    open_t.side, open_t.entry, price, pnl,
                    reason, signal_name,
                ))
                open_t = None
                entry_vwap = None
                entry_sd = None

        # ── Entry ───────────────────────────────────────────────────────
        if open_t is None:
            sig = signal_fn(win, spot_window=spot_win, **signal_kwargs)
            if sig.get("should_trade"):
                side = "Buy" if sig["direction"] == "UP" else "Sell"
                open_t = Trade(side, price, 0.0, 0.0, "", signal_name)
                entry_i = i
                meta = sig.get("meta") or {}
                entry_vwap = meta.get("vwap")
                entry_sd = meta.get("sd")

    return trades


def summarize(trades: List[Trade], label: str):
    if not trades:
        return {"label": label, "n": 0, "wr": 0.0, "pnl": 0.0}
    wins = sum(1 for t in trades if t.pnl > 0)
    pnl = sum(t.pnl for t in trades)
    wr = wins / len(trades) * 100
    return {
        "label": label, "n": len(trades), "wr": wr, "pnl": pnl,
        "avg": pnl / len(trades),
    }


def split_by_reason(trades):
    buckets = {}
    for t in trades:
        b = buckets.setdefault(t.reason, [])
        b.append(t)
    return buckets


def align_spot_to_bybit(bybit, spot):
    """Align spot candles to bybit timestamps by forward-filling spot
    to each bybit ts. Returns list parallel to bybit."""
    spot_by_ts = {c["ts"]: c for c in spot}
    aligned = []
    last = None
    for c in bybit:
        s = spot_by_ts.get(c["ts"])
        if s is not None:
            last = s
        aligned.append(last)
    return aligned


def main():
    if not BYBIT_CSV.exists():
        print(f"Missing {BYBIT_CSV} — run tools/backtest_bybit.py first")
        sys.exit(1)

    print(f"Loading {BYBIT_CSV}...")
    bybit = load_csv(BYBIT_CSV)
    print(f"  {len(bybit)} bybit candles")

    spot_aligned = None
    if SPOT_CSV.exists():
        spot = load_csv(SPOT_CSV)
        print(f"  {len(spot)} spot candles")
        spot_aligned = align_spot_to_bybit(bybit, spot)
        coverage = sum(1 for s in spot_aligned if s is not None)
        print(f"  spot alignment: {coverage}/{len(bybit)} "
              f"({coverage/len(bybit)*100:.1f}%)")
    else:
        print(f"  {SPOT_CSV} not present — skipping xexch_leadlag")

    results = []

    # ── Signal 1: Volatility Breakout ──────────────────────────────────
    print("\n=== Volatility Breakout ===")
    trades = walk(
        bybit, signal_fn=volbreakout_signal, signal_name="volbreakout",
        window=100, hold=6,
    )
    s = summarize(trades, "volbreakout")
    results.append(("volbreakout", trades, s))
    print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    # ── Signal 2: VWAP Mean Reversion ──────────────────────────────────
    # Sweep hold ceiling: the initial z=2/hold=12 run showed 98.6% WR on
    # mean_revert exits but 31% on time_ceiling exits — i.e. the reversion
    # works, we were just cutting trades off too early.
    sweep = []
    for entry_z in (2.0, 2.5, 3.0):
        for hold in (48, 96):
            for stop in (1.0, 1.5, 2.0, 3.0, None):
                sweep.append((entry_z, hold, stop))
    for entry_z, hold, stop in sweep:
        tag = f"z{str(entry_z).replace('.','p')}_h{hold}_s{'none' if stop is None else str(stop).replace('.','p')}"
        name = f"vwap_mr_{tag}"
        print(f"\n=== VWAP-MR z={entry_z} hold={hold} stop={stop} ===")
        trades = walk(
            bybit, signal_fn=vwap_mr_signal, signal_name=name,
            window=48, hold=hold, exit_on_reversion=True,
            signal_kwargs={"entry_z": entry_z},
            stop_sd_mult=stop,
        )
        s = summarize(trades, name)
        results.append((name, trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    # ── Signal 3: Cross-exchange Lead/Lag ──────────────────────────────
    if spot_aligned is not None:
        print("\n=== Cross-Exchange Lead/Lag (spot streak=2) ===")
        trades = walk(
            bybit, signal_fn=xexch_leadlag_signal, signal_name="xexch_2",
            window=20, hold=3, spot_candles=spot_aligned,
            signal_kwargs={"spot_streak_min": 2, "bybit_max_streak": 0},
        )
        s = summarize(trades, "xexch_2")
        results.append(("xexch_2", trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

        print("\n=== Cross-Exchange Lead/Lag (spot streak=3) ===")
        trades = walk(
            bybit, signal_fn=xexch_leadlag_signal, signal_name="xexch_3",
            window=20, hold=3, spot_candles=spot_aligned,
            signal_kwargs={"spot_streak_min": 3, "bybit_max_streak": 1},
        )
        s = summarize(trades, "xexch_3")
        results.append(("xexch_3", trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    # ── Report ─────────────────────────────────────────────────────────
    lines = []
    lines.append("# Bybit alternative signals — backtest on 6mo BTCUSDT")
    lines.append("")
    lines.append("After Phase 2 proved streak momentum (ride & fade) is")
    lines.append("dead on Bybit 5m perps, three alternative signal")
    lines.append("families were implemented and backtested on the same")
    lines.append("cached 6-month 5m CSV.")
    lines.append("")
    lines.append("Bet size: ${:.0f}. P&L includes round-trip fees via "
                 "`bybit_trade._compute_pnl`.".format(BYBIT_BET_SIZE))
    lines.append("")
    lines.append("## Headline results")
    lines.append("| Signal | N | WR | P&L | Avg/trade |")
    lines.append("|--------|--:|---:|----:|----------:|")
    for name, _, s in results:
        avg = s.get("avg", 0)
        lines.append(
            f"| {name} | {s['n']} | {s['wr']:.2f}% | ${s['pnl']:+.2f} | "
            f"${avg:+.3f} |"
        )
    lines.append("")

    lines.append("## Exit-reason breakdown")
    for name, trades, _ in results:
        if not trades:
            continue
        buckets = split_by_reason(trades)
        lines.append(f"### {name}")
        lines.append("| Exit reason | N | WR | P&L |")
        lines.append("|---|--:|---:|---:|")
        for reason, bucket in sorted(buckets.items()):
            s = summarize(bucket, reason)
            lines.append(
                f"| {reason} | {s['n']} | {s['wr']:.2f}% | ${s['pnl']:+.2f} |"
            )
        lines.append("")

    lines.append("## Verdict")
    any_winner = False
    for name, _, s in results:
        if s["n"] >= 100 and s["wr"] >= 55 and s["pnl"] > 0:
            lines.append(
                f"✅ **{name}** clears 55% on N={s['n']} "
                f"with P&L=${s['pnl']:.2f} — worth forward testing."
            )
            any_winner = True
        elif s["n"] >= 100 and s["wr"] >= 52:
            lines.append(
                f"⚠️ **{name}** marginal ({s['wr']:.1f}% on N={s['n']}). "
                f"Not worth committing to alone."
            )
    if not any_winner:
        lines.append("")
        lines.append(
            "❌ No alternative signal clears 55% WR. The momentum family "
            "was dead; these three families are also dead on this venue "
            "at 5m cadence after fees. Options: different bar size, "
            "different venue, or fundamentally different data (order "
            "book, open interest, funding)."
        )
    lines.append("")

    text = "\n".join(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text + "\n")
    print()
    print(text)
    print()
    print(f"Report: {OUT}")


if __name__ == "__main__":
    main()
