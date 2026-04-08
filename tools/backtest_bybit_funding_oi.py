"""
backtest_bybit_funding_oi.py — Test two new signal families that don't
depend on price-only candles:

  1. funding_extreme — enter counter to crowded side when funding rate
     is in the top/bottom decile of trailing 30-day distribution. Thesis:
     extreme funding marks overcrowded directional bets; perp typically
     mean-reverts as funding payment forces weak hands out.

  2. oi_delta — enter when open-interest change over last K bars is in
     top/bottom decile AND price moved in the same direction (new longs
     adding at highs / new shorts adding at lows = crowded chase). Fade
     the chase.

Both are FADE signals (take the other side of crowding). Uses the
existing walk harness from backtest_bybit_alt with signal functions
defined inline here.

Writes: docs/research/bybit_funding_oi_backtest_2026-04.md
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import List, Optional

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
SRC = TOOLS.parent / "src"
sys.path.insert(0, str(SRC))

from backtest_bybit import load_csv  # noqa: E402
from backtest_bybit_alt import walk, summarize, split_by_reason  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BYBIT_CSV = ROOT / "data" / "bybit_5m_6mo.csv"
FUNDING_CSV = ROOT / "data" / "funding_6mo.csv"
OI_CSV = ROOT / "data" / "oi_5m_6mo.csv"
OUT = ROOT / "docs" / "research" / "bybit_funding_oi_backtest_2026-04.md"


# ── Data loaders ────────────────────────────────────────────────────────────

def load_funding():
    rows = []
    with FUNDING_CSV.open() as f:
        for r in csv.DictReader(f):
            rows.append({"ts": int(r["ts"]), "rate": float(r["rate"])})
    rows.sort(key=lambda r: r["ts"])
    return rows


def load_oi():
    rows = []
    with OI_CSV.open() as f:
        for r in csv.DictReader(f):
            rows.append({"ts": int(r["ts"]), "oi": float(r["oi"])})
    rows.sort(key=lambda r: r["ts"])
    return rows


def align_funding_to_candles(candles, funding):
    """For each candle ts, return the most-recent funding rate <= ts."""
    out = [None] * len(candles)
    fi = 0
    cur_rate = None
    for i, c in enumerate(candles):
        while fi < len(funding) and funding[fi]["ts"] <= c["ts"]:
            cur_rate = funding[fi]["rate"]
            fi += 1
        out[i] = cur_rate
    return out


def align_oi_to_candles(candles, oi):
    by_ts = {r["ts"]: r["oi"] for r in oi}
    out = []
    last = None
    for c in candles:
        v = by_ts.get(c["ts"])
        if v is not None:
            last = v
        out.append(last)
    return out


# ── Signal: funding extreme fade ────────────────────────────────────────────

def make_funding_signal(funding_series, percentile=0.10, lookback=288 * 30):
    """Returns a signal_fn over the walk harness. `funding_series` is
    aligned 1:1 to candles. Lookback=30 days × 288 5m bars."""

    def sig(window, *, spot_window=None, **_):
        # The harness passes `window` (candle tail) but we need the index.
        # Trick: last candle's ts lets us find our position.
        idx = sig._index_by_ts.get(window[-1]["ts"])
        if idx is None or idx < lookback:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        cur = funding_series[idx]
        if cur is None:
            return {"should_trade": False, "direction": None,
                    "reason": "no_funding"}
        hist = [
            r for r in funding_series[idx - lookback:idx]
            if r is not None
        ]
        if len(hist) < 100:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        hist_sorted = sorted(hist)
        lo = hist_sorted[int(len(hist_sorted) * percentile)]
        hi = hist_sorted[int(len(hist_sorted) * (1 - percentile))]
        if cur >= hi:
            # High funding → ride longs (momentum side) → BUY
            return {"should_trade": True, "direction": "UP",
                    "reason": f"funding_hi_{cur:.5f}"}
        if cur <= lo:
            # Negative funding → ride shorts → SELL
            return {"should_trade": True, "direction": "DOWN",
                    "reason": f"funding_lo_{cur:.5f}"}
        return {"should_trade": False, "direction": None,
                "reason": "funding_neutral"}

    sig._index_by_ts = {}
    return sig


# ── Signal: OI-delta fade (crowded chase) ───────────────────────────────────

def make_oi_signal(oi_series, k=12, percentile=0.10, lookback=288 * 7):
    """Fade crowded moves: OI up AND price up (long chase) → SELL.
    OI up AND price down (short chase) → BUY.
    OI change over trailing k bars, ranked against last `lookback` bars."""

    def sig(window, *, spot_window=None, **_):
        idx = sig._index_by_ts.get(window[-1]["ts"])
        if idx is None or idx < max(k, lookback):
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        cur_oi = oi_series[idx]
        past_oi = oi_series[idx - k]
        if cur_oi is None or past_oi is None or past_oi == 0:
            return {"should_trade": False, "direction": None,
                    "reason": "no_oi"}
        oi_change = (cur_oi - past_oi) / past_oi
        # Rank against last `lookback` bars of oi_change
        hist = []
        for j in range(idx - lookback, idx):
            a, b = oi_series[j], oi_series[j - k] if j - k >= 0 else None
            if a is None or b is None or b == 0:
                continue
            hist.append((a - b) / b)
        if len(hist) < 100:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        hist_sorted = sorted(hist)
        hi_cut = hist_sorted[int(len(hist_sorted) * (1 - percentile))]
        lo_cut = hist_sorted[int(len(hist_sorted) * percentile)]

        price_change = (window[-1]["close"] - window[-k]["close"]) \
            if len(window) >= k else 0
        if oi_change >= hi_cut and price_change > 0:
            # OI build on up move → ride longs → BUY
            return {"should_trade": True, "direction": "UP",
                    "reason": f"oi_long_build_{oi_change:.4f}"}
        if oi_change >= hi_cut and price_change < 0:
            # OI build on down move → ride shorts → SELL
            return {"should_trade": True, "direction": "DOWN",
                    "reason": f"oi_short_build_{oi_change:.4f}"}
        if oi_change <= lo_cut:
            # OI falling = unwind, no edge
            return {"should_trade": False, "direction": None,
                    "reason": "oi_unwind"}
        return {"should_trade": False, "direction": None,
                "reason": "oi_neutral"}

    sig._index_by_ts = {}
    return sig


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {BYBIT_CSV}...")
    candles = load_csv(BYBIT_CSV)
    print(f"  {len(candles)} candles")

    print("Loading funding...")
    funding = load_funding()
    print(f"  {len(funding)} funding rows")
    funding_series = align_funding_to_candles(candles, funding)
    cov = sum(1 for r in funding_series if r is not None)
    print(f"  funding coverage: {cov}/{len(candles)}")

    print("Loading OI...")
    oi = load_oi()
    print(f"  {len(oi)} oi rows")
    oi_series = align_oi_to_candles(candles, oi)
    cov = sum(1 for r in oi_series if r is not None)
    print(f"  OI coverage: {cov}/{len(candles)}")

    results = []

    # Funding extreme — sweep percentile and hold
    for pct, hold in [(0.05, 24), (0.05, 48), (0.10, 24), (0.10, 48),
                      (0.20, 24), (0.20, 48)]:
        print(f"\n=== Funding p={pct} hold={hold} ===")
        sig_fn = make_funding_signal(funding_series, percentile=pct)
        sig_fn._index_by_ts = {c["ts"]: i for i, c in enumerate(candles)}
        trades = walk(
            candles, signal_fn=sig_fn,
            signal_name=f"fund_p{int(pct*100)}_h{hold}",
            window=24, hold=hold,
        )
        s = summarize(trades, f"fund_p{int(pct*100)}_h{hold}")
        results.append((f"fund_p{int(pct*100)}_h{hold}", trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    # OI delta — sweep k and percentile
    for k, pct, hold in [(6, 0.10, 6), (6, 0.10, 12), (12, 0.10, 12),
                          (12, 0.10, 24), (24, 0.10, 24), (6, 0.05, 12),
                          (12, 0.05, 12)]:
        print(f"\n=== OI k={k} p={pct} hold={hold} ===")
        sig_fn = make_oi_signal(oi_series, k=k, percentile=pct)
        sig_fn._index_by_ts = {c["ts"]: i for i, c in enumerate(candles)}
        trades = walk(
            candles, signal_fn=sig_fn,
            signal_name=f"oi_k{k}_p{int(pct*100)}_h{hold}",
            window=max(k, 24), hold=hold,
        )
        s = summarize(trades, f"oi_k{k}_p{int(pct*100)}_h{hold}")
        results.append((f"oi_k{k}_p{int(pct*100)}_h{hold}", trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    # Report
    lines = [
        "# Bybit funding & open-interest signals — 6mo backtest",
        "",
        "After the candle-only signal families (streak momentum, breakout, "
        "VWAP mean-reversion, cross-venue lead/lag) all failed on Bybit 5m, "
        "test two non-candle signal classes:",
        "",
        "1. **funding_extreme** — fade crowding via funding rate decile",
        "2. **oi_delta** — fade crowded chases via OI change + price confirm",
        "",
        "Both are MOMENTUM signals (ride the crowd). Fade variants were "
        "tested first and produced 37-44% WR — inverting gives numbers below.",
        "",
        "## Headline results",
        "| Signal | N | WR | P&L | Avg/trade |",
        "|--------|--:|---:|----:|----------:|",
    ]
    for name, _, s in results:
        avg = s.get("avg", 0)
        lines.append(
            f"| {name} | {s['n']} | {s['wr']:.2f}% | ${s['pnl']:+.2f} | "
            f"${avg:+.3f} |"
        )
    lines.append("")

    lines.append("## Verdict")
    winners = [
        (n, s) for n, _, s in results
        if s["n"] >= 100 and s["wr"] >= 55 and s["pnl"] > 0
    ]
    if winners:
        for n, s in winners:
            lines.append(
                f"- ✅ **{n}**: WR={s['wr']:.1f}% on N={s['n']}, "
                f"P&L=${s['pnl']:+.2f}"
            )
    else:
        marginal = [
            (n, s) for n, _, s in results
            if s["n"] >= 100 and s["wr"] >= 52
        ]
        if marginal:
            lines.append("Marginal cells (≥52% on N≥100):")
            for n, s in marginal:
                lines.append(
                    f"- ⚠️ {n}: WR={s['wr']:.1f}% on N={s['n']}, "
                    f"P&L=${s['pnl']:+.2f}"
                )
        lines.append("")
        lines.append(
            "❌ No funding or OI cell clears 55% WR + positive P&L on "
            "N≥100. Combined with the candle-signal failures, this is "
            "the strongest evidence yet that BTCUSDT 5m perp on Bybit "
            "is not edge-extractable from public OHLCV + derivatives "
            "telemetry. Next options: order-book imbalance (needs "
            "L2 snapshots, not available from REST), or a different "
            "venue/asset entirely."
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
