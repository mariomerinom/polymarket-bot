"""
backtest_bybit.py — Walk-forward backtest of the Bybit momentum signal
on raw historical BTCUSDT perp candles.

This is Phase 2 of the Bybit pivot. Until now we assumed the Polymarket
momentum signal would transfer to perps; this script is the first time
we actually measure it on the underlying.

Pipeline:
  1. Paginate /v5/market/kline (public, no auth) for `--months` of 5m
     candles, stitching batches of 1000 together with the same schema
     the live pipeline sees.
  2. For each candle i, feed `candles[i - window : i + 1]` to
     `predict.compute_regime_from_candles` + `predict.momentum_signal`.
  3. On `should_trade`, enter a virtual position at `candles[i].close`
     and settle after `--hold` candles at `candles[i + hold].close`
     (or earlier on streak-break, to mirror the live exit gate).
  4. P&L uses `bybit_trade._compute_pnl` so fees + sizing match the
     live path exactly. Funding cost is intentionally NOT applied here
     (Phase 3 adds it); this is the pre-funding ceiling.
  5. Aggregate: total WR, P&L, trade count, regime breakdown,
     conviction breakdown, streak breakdown.

Usage:
    python3 tools/backtest_bybit.py --months 6
    python3 tools/backtest_bybit.py --months 1 --hold 6 --window 24
    python3 tools/backtest_bybit.py --csv data/bybit_5m_6mo.csv

The optional --csv cache avoids re-hitting Bybit on every run.

Decision gate: if realized WR on conv >= 3 bets over 6 months is < 55%,
the pivot thesis is in question and Phase 3+ should not ship.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import requests

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

from predict import compute_regime_from_candles, momentum_signal  # noqa: E402
from bybit_trade import _compute_pnl  # noqa: E402
from config import BYBIT_BET_SIZE  # noqa: E402

BYBIT_BASE = os.environ.get("BYBIT_BASE_URL", "https://api.bybit.com")
KLINE_URL = f"{BYBIT_BASE}/v5/market/kline"
PAGE = 1000  # Bybit kline max per request
INTERVAL_MIN = 5


# ── Candle fetch ─────────────────────────────────────────────────────────────

def _candle_from_raw(row) -> dict:
    ts = int(row[0])
    open_price = float(row[1])
    high = float(row[2])
    low = float(row[3])
    close = float(row[4])
    volume = float(row[5])
    body = abs(close - open_price)
    rng = high - low
    return {
        "ts": ts,
        "time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": round(volume, 2),
        "direction": "UP" if close >= open_price else "DOWN",
        "body_pct": round((close - open_price) / open_price * 100, 4) if open_price else 0.0,
        "wick_ratio": round(1.0 - (body / rng), 2) if rng > 0 else 0.0,
    }


def fetch_history(symbol: str, months: int, verbose: bool = True) -> List[dict]:
    """Paginate kline backwards in time until we have `months` of data."""
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30 * months)).timestamp() * 1000)
    candles: List[dict] = []
    seen = set()
    page = 0
    while end_ms > cutoff:
        page += 1
        params = {
            "category": "linear",
            "symbol": symbol,
            "interval": str(INTERVAL_MIN),
            "limit": PAGE,
            "end": end_ms,
        }
        resp = requests.get(KLINE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit error: {data.get('retMsg')}")
        raw = data.get("result", {}).get("list", [])
        if not raw:
            break
        # Bybit returns newest first; reverse to chronological then prepend.
        raw.sort(key=lambda r: int(r[0]))
        batch = [_candle_from_raw(r) for r in raw if int(r[0]) not in seen]
        if not batch:
            break
        for c in batch:
            seen.add(c["ts"])
        candles = batch + candles
        earliest = batch[0]["ts"]
        if verbose:
            print(f"  page {page}: {len(candles)} total, earliest="
                  f"{datetime.fromtimestamp(earliest / 1000, tz=timezone.utc).date()}")
        if earliest <= cutoff:
            break
        end_ms = earliest - 1
        time.sleep(0.15)  # be polite
    # Final chronological sort + dedup (paranoia)
    candles.sort(key=lambda c: c["ts"])
    return candles


# ── CSV cache ────────────────────────────────────────────────────────────────

CSV_FIELDS = ["ts", "time", "open", "high", "low", "close", "volume",
              "direction", "body_pct", "wick_ratio"]


def save_csv(candles: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for c in candles:
            w.writerow({k: c[k] for k in CSV_FIELDS})


def load_csv(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open() as f:
        for row in csv.DictReader(f):
            out.append({
                "ts": int(row["ts"]),
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "direction": row["direction"],
                "body_pct": float(row["body_pct"]),
                "wick_ratio": float(row["wick_ratio"]),
            })
    return out


# ── Walk-forward simulation ──────────────────────────────────────────────────

@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    side: str              # "Buy" | "Sell"
    entry_price: float
    exit_price: float
    pnl: float
    regime_label: str
    volatility: float
    streak: int
    exit_reason: str
    qty: float = BYBIT_BET_SIZE


def simulate(candles: List[dict], window: int, hold: int,
             min_streak: int = 3) -> List[Trade]:
    """Walk the tape. At each index, if signal fires and no open
    position, enter. Exit on hold ceiling or streak reversal.

    This mirrors `bybit_trade.check_exit_conditions` semantics:
      * time_ceiling: `hold` candles elapsed
      * streak_break: signal on a later candle flips direction
    """
    trades: List[Trade] = []
    open_trade: Optional[Trade] = None

    for i in range(window, len(candles) - 1):
        win = candles[i - window + 1 : i + 1]
        regime = compute_regime_from_candles(win)
        signal = momentum_signal(win, min_streak=min_streak)

        # Exit logic first — operates on any open trade
        if open_trade is not None:
            held = i - open_trade.entry_idx
            exit_now = False
            reason = ""
            if held >= hold:
                exit_now = True
                reason = "time_ceiling"
            elif signal.get("should_trade"):
                sig_side = "Buy" if signal["direction"] == "UP" else "Sell"
                if sig_side != open_trade.side:
                    exit_now = True
                    reason = "streak_break"
            if exit_now:
                open_trade.exit_idx = i
                open_trade.exit_price = candles[i]["close"]
                open_trade.pnl = _compute_pnl(
                    open_trade.side, open_trade.qty,
                    open_trade.entry_price, open_trade.exit_price,
                )
                open_trade.exit_reason = reason
                trades.append(open_trade)
                open_trade = None

        # Entry logic — only if flat and regime permits
        if open_trade is None and signal.get("should_trade"):
            if regime.get("is_mean_reverting"):
                continue
            side = "Buy" if signal["direction"] == "UP" else "Sell"
            open_trade = Trade(
                entry_idx=i,
                exit_idx=-1,
                side=side,
                entry_price=candles[i]["close"],
                exit_price=0.0,
                pnl=0.0,
                regime_label=regime.get("label", "UNKNOWN"),
                volatility=regime.get("volatility", 0.0),
                streak=int(signal.get("streak", 0)),
                exit_reason="",
            )

    # Force-close any dangling trade at the tape end
    if open_trade is not None:
        last = len(candles) - 1
        open_trade.exit_idx = last
        open_trade.exit_price = candles[last]["close"]
        open_trade.pnl = _compute_pnl(
            open_trade.side, open_trade.qty,
            open_trade.entry_price, open_trade.exit_price,
        )
        open_trade.exit_reason = "tape_end"
        trades.append(open_trade)

    return trades


# ── Reporting ────────────────────────────────────────────────────────────────

def summarize(trades: List[Trade], months: int) -> str:
    if not trades:
        return "No trades — backtest window produced zero signals."
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total_pnl = sum(t.pnl for t in trades)
    wr = len(wins) / len(trades) * 100

    lines = []
    lines.append(f"# Bybit perp backtest — {months}mo BTCUSDT 5m, momentum")
    lines.append("")
    lines.append(f"- Trades: **{len(trades)}**")
    lines.append(f"- Wins / Losses: {len(wins)} / {len(losses)}")
    lines.append(f"- Win rate: **{wr:.1f}%**")
    lines.append(f"- Total P&L (pre-funding): **${total_pnl:.2f}**")
    lines.append(f"- Avg P&L / trade: ${total_pnl / len(trades):.3f}")
    lines.append("")

    # Regime breakdown
    lines.append("## By regime label")
    lines.append("| Regime | Trades | WR | P&L |")
    lines.append("|---|---:|---:|---:|")
    by_regime: dict[str, list[Trade]] = {}
    for t in trades:
        by_regime.setdefault(t.regime_label, []).append(t)
    for label, group in sorted(by_regime.items(), key=lambda kv: -len(kv[1])):
        gw = sum(1 for t in group if t.pnl > 0)
        gp = sum(t.pnl for t in group)
        lines.append(f"| {label} | {len(group)} | {gw / len(group) * 100:.1f}% | ${gp:.2f} |")
    lines.append("")

    # Direction breakdown
    lines.append("## By direction")
    lines.append("| Side | Trades | WR | P&L |")
    lines.append("|---|---:|---:|---:|")
    for side in ("Buy", "Sell"):
        g = [t for t in trades if t.side == side]
        if not g:
            continue
        gw = sum(1 for t in g if t.pnl > 0)
        lines.append(f"| {side} | {len(g)} | {gw / len(g) * 100:.1f}% | ${sum(t.pnl for t in g):.2f} |")
    lines.append("")

    # Streak breakdown (treated as conviction proxy)
    lines.append("## By streak length (conviction proxy)")
    lines.append("| |streak| | Trades | WR | P&L |")
    lines.append("|---:|---:|---:|---:|")
    buckets = sorted({abs(t.streak) for t in trades})
    for b in buckets:
        g = [t for t in trades if abs(t.streak) == b]
        gw = sum(1 for t in g if t.pnl > 0)
        lines.append(f"| {b} | {len(g)} | {gw / len(g) * 100:.1f}% | ${sum(t.pnl for t in g):.2f} |")
    lines.append("")

    # Exit reasons
    lines.append("## By exit reason")
    lines.append("| Reason | Trades | WR | P&L |")
    lines.append("|---|---:|---:|---:|")
    by_reason: dict[str, list[Trade]] = {}
    for t in trades:
        by_reason.setdefault(t.exit_reason or "?", []).append(t)
    for reason, g in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        gw = sum(1 for t in g if t.pnl > 0)
        lines.append(f"| {reason} | {len(g)} | {gw / len(g) * 100:.1f}% | ${sum(t.pnl for t in g):.2f} |")
    lines.append("")

    # Decision gate
    lines.append("## Decision gate")
    if wr >= 55:
        lines.append(f"✅ WR {wr:.1f}% >= 55% — momentum signal holds on perps; continue pivot.")
    elif wr >= 52:
        lines.append(f"⚠️ WR {wr:.1f}% in 52–55% gray zone — continue only with tighter conviction gating.")
    else:
        lines.append(f"❌ WR {wr:.1f}% < 52% — Phase 2 gate FAILED. Pause pivot, re-examine signal.")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--window", type=int, default=24,
                    help="Candles fed to regime/signal at each step")
    ap.add_argument("--hold", type=int, default=6,
                    help="Max candles to hold before time-ceiling exit")
    ap.add_argument("--min-streak", type=int, default=3)
    ap.add_argument("--csv", type=Path, default=None,
                    help="Cache candles to/from this CSV file")
    ap.add_argument("--out", type=Path,
                    default=Path("docs/research/bybit_backtest_2026-04.md"))
    args = ap.parse_args()

    # Data
    if args.csv and args.csv.exists():
        print(f"Loading cached candles from {args.csv}")
        candles = load_csv(args.csv)
    else:
        print(f"Fetching {args.months}mo of {args.symbol} {INTERVAL_MIN}m candles "
              f"from Bybit...")
        candles = fetch_history(args.symbol, args.months)
        if args.csv:
            save_csv(candles, args.csv)
            print(f"Cached {len(candles)} candles to {args.csv}")
    if not candles:
        print("No candles fetched.")
        sys.exit(1)
    print(f"Loaded {len(candles)} candles "
          f"({datetime.fromtimestamp(candles[0]['ts'] / 1000, tz=timezone.utc).date()} → "
          f"{datetime.fromtimestamp(candles[-1]['ts'] / 1000, tz=timezone.utc).date()})")

    # Simulate
    trades = simulate(candles, window=args.window, hold=args.hold,
                      min_streak=args.min_streak)
    print(f"Simulated {len(trades)} trades")

    # Report
    report = summarize(trades, args.months)
    print()
    print(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report + "\n")
    print()
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
