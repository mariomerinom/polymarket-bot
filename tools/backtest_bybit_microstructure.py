"""
backtest_bybit_microstructure.py — Backtest signals derived from the
captured Bybit WebSocket microstructure tape against the 5m candle CSV.

Reads data/bybit_capture/{publicTrade,orderbook,liquidation,tickers}/
*.jsonl(.gz) files, bins events into 5m buckets aligned to the cached
bybit_5m_6mo.csv timestamps, then feeds the enriched windows through
the existing walk() harness in backtest_bybit_alt.py.

Signals implemented:

  1. cvd_divergence
     Cumulative Volume Delta = Σ(buy_taker_vol) − Σ(sell_taker_vol).
     Entry: price makes new N-bar high/low but CVD does NOT confirm
     (divergence) → fade the move.

  2. liq_cascade_fade
     Count of long/short liquidations in trailing K seconds. If long
     liquidations cluster above a percentile → BUY (shorts will cover
     into the cascade). If short liquidations cluster → SELL. This is
     the single most documented retail-accessible edge on Bybit.

  3. book_imbalance
     (bid_vol − ask_vol) / (bid_vol + ask_vol) averaged over top-N
     orderbook.50 levels across the bar window. Sustained imbalance
     above threshold → lean with it.

  4. taker_aggression
     Taker buy count / taker sell count ratio over the bar. Extreme
     ratios in either direction trigger momentum.

Because capture must run first (Phase B — 7-14 days minimum), this
script is designed to (a) run even when the capture directory is
empty — printing a clear "no data" banner — and (b) degrade gracefully
when only some topics have data. It emits a report to
docs/research/bybit_microstructure_backtest_2026-04.md that makes
the coverage and result per signal explicit.

Usage:
  python3 tools/backtest_bybit_microstructure.py
  python3 tools/backtest_bybit_microstructure.py --min-hours 12
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
SRC = TOOLS.parent / "src"
sys.path.insert(0, str(SRC))

from backtest_bybit import load_csv  # noqa: E402
from backtest_bybit_alt import walk, summarize, split_by_reason  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = ROOT / "data" / "bybit_capture"
BYBIT_CSV = ROOT / "data" / "bybit_5m_6mo.csv"
OUT = ROOT / "docs" / "research" / "bybit_microstructure_backtest_2026-04.md"

BAR_MS = 5 * 60 * 1000


# ── JSONL(.gz) iterator ─────────────────────────────────────────────────────

def iter_jsonl(path: Path) -> Iterable[dict]:
    """Stream-parse a .jsonl or .jsonl.gz file."""
    if path.suffix == ".gz":
        f = gzip.open(path, "rt", encoding="utf-8")
    else:
        f = path.open("r", encoding="utf-8")
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    finally:
        f.close()


def load_topic(topic: str) -> List[dict]:
    """Load all files for a topic in chronological order."""
    tdir = CAPTURE_DIR / topic
    if not tdir.exists():
        return []
    paths = sorted(tdir.glob("*.jsonl*"))
    out: List[dict] = []
    for p in paths:
        out.extend(iter_jsonl(p))
    return out


# ── Binning into 5m buckets ─────────────────────────────────────────────────

def bar_key(ts_ms: int) -> int:
    """Floor a ms timestamp to the enclosing 5m bar."""
    return (ts_ms // BAR_MS) * BAR_MS


def bin_public_trades(events: List[dict]) -> dict[int, dict]:
    """Returns {bar_ts: {buy_vol, sell_vol, buy_count, sell_count,
                         cvd_bar, max_trade_size}}."""
    out: dict[int, dict] = defaultdict(lambda: {
        "buy_vol": 0.0, "sell_vol": 0.0,
        "buy_count": 0, "sell_count": 0,
        "cvd_bar": 0.0, "max_trade_size": 0.0,
    })
    for ev in events:
        for t in ev.get("data", []) or []:
            ts = int(t.get("T", 0) or 0)
            side = t.get("S", "")
            size = float(t.get("v", 0) or 0)
            if ts == 0 or size == 0:
                continue
            b = out[bar_key(ts)]
            if side == "Buy":
                b["buy_vol"] += size
                b["buy_count"] += 1
                b["cvd_bar"] += size
            elif side == "Sell":
                b["sell_vol"] += size
                b["sell_count"] += 1
                b["cvd_bar"] -= size
            if size > b["max_trade_size"]:
                b["max_trade_size"] = size
    return out


def bin_liquidations(events: List[dict]) -> dict[int, dict]:
    """Returns {bar_ts: {liq_long_count, liq_long_usd,
                         liq_short_count, liq_short_usd}}.

    Note on 'side' semantics: Bybit publishes the side of the LIQUIDATED
    position. A liquidated long → a forced sell; a liquidated short →
    a forced buy. The cascade-fade signal takes the OPPOSITE side of
    the forced flow because the shorts/longs who triggered the cascade
    will cover.
    """
    out: dict[int, dict] = defaultdict(lambda: {
        "liq_long_count": 0, "liq_long_usd": 0.0,
        "liq_short_count": 0, "liq_short_usd": 0.0,
    })
    for ev in events:
        data = ev.get("data")
        if not data:
            continue
        rows = data if isinstance(data, list) else [data]
        for r in rows:
            ts = int(r.get("updatedTime") or r.get("T") or 0)
            side = r.get("side") or r.get("S") or ""
            size = float(r.get("size") or r.get("v") or 0)
            price = float(r.get("price") or r.get("p") or 0)
            if ts == 0 or size == 0:
                continue
            usd = size * price
            b = out[bar_key(ts)]
            if side == "Buy":  # long was liquidated (long = Buy side)
                b["liq_long_count"] += 1
                b["liq_long_usd"] += usd
            elif side == "Sell":
                b["liq_short_count"] += 1
                b["liq_short_usd"] += usd
    return out


def bin_orderbook(events: List[dict], depth: int = 10) -> dict[int, dict]:
    """Snapshot-based book imbalance averaged per bar. Uses bid/ask
    sums over top-`depth` levels from each snapshot/delta message, then
    averages within the bar."""
    sums: dict[int, dict] = defaultdict(lambda: {
        "imb_sum": 0.0, "imb_count": 0,
        "bid_depth_sum": 0.0, "ask_depth_sum": 0.0,
    })
    for ev in events:
        d = ev.get("data") or {}
        ts = int(ev.get("ts") or d.get("ts") or ev.get("_rx_ms") or 0)
        if ts == 0:
            continue
        bids = d.get("b", [])[:depth]
        asks = d.get("a", [])[:depth]
        try:
            bid_vol = sum(float(x[1]) for x in bids)
            ask_vol = sum(float(x[1]) for x in asks)
        except (IndexError, TypeError, ValueError):
            continue
        total = bid_vol + ask_vol
        if total <= 0:
            continue
        imb = (bid_vol - ask_vol) / total
        b = sums[bar_key(ts)]
        b["imb_sum"] += imb
        b["imb_count"] += 1
        b["bid_depth_sum"] += bid_vol
        b["ask_depth_sum"] += ask_vol

    out: dict[int, dict] = {}
    for k, b in sums.items():
        if b["imb_count"] == 0:
            continue
        out[k] = {
            "book_imbalance": b["imb_sum"] / b["imb_count"],
            "avg_bid_depth": b["bid_depth_sum"] / b["imb_count"],
            "avg_ask_depth": b["ask_depth_sum"] / b["imb_count"],
        }
    return out


def bin_tickers(events: List[dict]) -> dict[int, dict]:
    """Returns {bar_ts: {last_funding_rate, last_oi}} — the most recent
    snapshot within the bar."""
    out: dict[int, dict] = {}
    for ev in events:
        d = ev.get("data") or {}
        ts = int(ev.get("ts") or ev.get("_rx_ms") or 0)
        if ts == 0:
            continue
        k = bar_key(ts)
        rec = out.setdefault(k, {})
        if "fundingRate" in d:
            try:
                rec["last_funding_rate"] = float(d["fundingRate"])
            except (TypeError, ValueError):
                pass
        if "openInterest" in d:
            try:
                rec["last_oi"] = float(d["openInterest"])
            except (TypeError, ValueError):
                pass
    return out


# ── Enriched-candle builder ─────────────────────────────────────────────────

def enrich(candles: List[dict], topic_bins: dict[str, dict]) -> List[dict]:
    """Attach per-topic fields to each candle for bars where data exists.

    Returns a NEW list of dicts so the existing backtest_bybit_alt.walk
    harness can consume them unchanged. Candles without capture data are
    left as-is (signals should skip those bars)."""
    out = []
    for c in candles:
        merged = dict(c)
        for topic, binmap in topic_bins.items():
            row = binmap.get(c["ts"])
            if row:
                merged.update(row)
        out.append(merged)
    return out


def coverage_window(candles: List[dict]) -> tuple[Optional[int], Optional[int], int]:
    """Returns (first_ts, last_ts, n_bars_with_any_microstructure_field)."""
    first = last = None
    count = 0
    for c in candles:
        has = any(
            k in c for k in (
                "cvd_bar", "liq_long_count", "book_imbalance", "last_oi"
            )
        )
        if has:
            count += 1
            if first is None:
                first = c["ts"]
            last = c["ts"]
    return first, last, count


# ── Signal functions (plug into walk harness) ───────────────────────────────

def make_cvd_divergence_signal(*, lookback=20, div_pctile=0.90):
    """New N-bar high but CVD not confirming = fade."""
    def sig(window, *, spot_window=None, **_):
        if len(window) < lookback + 1:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        tail = window[-lookback:]
        # Require CVD presence on the trigger bar and lookback
        have_cvd = all("cvd_bar" in c for c in tail)
        if not have_cvd:
            return {"should_trade": False, "direction": None,
                    "reason": "no_cvd"}
        cur = window[-1]
        highs = [c["high"] for c in tail]
        lows = [c["low"] for c in tail]
        cvd_cum = [0.0] * lookback
        s = 0.0
        for i, c in enumerate(tail):
            s += c.get("cvd_bar", 0.0)
            cvd_cum[i] = s

        new_high = cur["close"] >= max(highs[:-1])
        new_low = cur["close"] <= min(lows[:-1])
        cvd_max = max(cvd_cum[:-1])
        cvd_min = min(cvd_cum[:-1])

        # Divergence: price extends but CVD doesn't
        if new_high and cvd_cum[-1] < cvd_max:
            return {"should_trade": True, "direction": "DOWN",
                    "reason": "cvd_bear_div"}
        if new_low and cvd_cum[-1] > cvd_min:
            return {"should_trade": True, "direction": "UP",
                    "reason": "cvd_bull_div"}
        return {"should_trade": False, "direction": None,
                "reason": "no_divergence"}
    return sig


def make_liq_cascade_signal(*, lookback=3, min_usd=500_000):
    """Cluster of liquidation flow over trailing `lookback` bars > threshold
    → take the OPPOSITE side of the forced flow."""
    def sig(window, *, spot_window=None, **_):
        if len(window) < lookback:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        tail = window[-lookback:]
        if not any("liq_long_usd" in c for c in tail):
            return {"should_trade": False, "direction": None,
                    "reason": "no_liq"}
        long_usd = sum(c.get("liq_long_usd", 0.0) for c in tail)
        short_usd = sum(c.get("liq_short_usd", 0.0) for c in tail)
        if long_usd >= min_usd and long_usd > short_usd * 2:
            # Longs getting liquidated (forced sells) → fade → BUY
            return {"should_trade": True, "direction": "UP",
                    "reason": f"long_cascade_{long_usd:.0f}"}
        if short_usd >= min_usd and short_usd > long_usd * 2:
            # Shorts getting squeezed (forced buys) → fade → SELL
            return {"should_trade": True, "direction": "DOWN",
                    "reason": f"short_cascade_{short_usd:.0f}"}
        return {"should_trade": False, "direction": None, "reason": "quiet"}
    return sig


def make_book_imbalance_signal(*, lookback=3, thresh=0.30):
    """Sustained book imbalance above threshold → lean with it."""
    def sig(window, *, spot_window=None, **_):
        if len(window) < lookback:
            return {"should_trade": False, "direction": None,
                    "reason": "no_history"}
        tail = window[-lookback:]
        imbs = [c.get("book_imbalance") for c in tail]
        if any(x is None for x in imbs):
            return {"should_trade": False, "direction": None,
                    "reason": "no_book"}
        if all(x >= thresh for x in imbs):
            return {"should_trade": True, "direction": "UP",
                    "reason": f"bid_heavy_{imbs[-1]:.2f}"}
        if all(x <= -thresh for x in imbs):
            return {"should_trade": True, "direction": "DOWN",
                    "reason": f"ask_heavy_{imbs[-1]:.2f}"}
        return {"should_trade": False, "direction": None,
                "reason": "balanced"}
    return sig


def make_taker_aggression_signal(*, ratio_thresh=3.0):
    """Extreme taker buy/sell ratio on the current bar → momentum."""
    def sig(window, *, spot_window=None, **_):
        cur = window[-1]
        bc = cur.get("buy_count")
        sc = cur.get("sell_count")
        if bc is None or sc is None:
            return {"should_trade": False, "direction": None,
                    "reason": "no_trades"}
        total = bc + sc
        if total < 50:
            return {"should_trade": False, "direction": None,
                    "reason": "thin_tape"}
        if sc > 0 and bc / sc >= ratio_thresh:
            return {"should_trade": True, "direction": "UP",
                    "reason": f"taker_buy_{bc}:{sc}"}
        if bc > 0 and sc / bc >= ratio_thresh:
            return {"should_trade": True, "direction": "DOWN",
                    "reason": f"taker_sell_{bc}:{sc}"}
        return {"should_trade": False, "direction": None,
                "reason": "balanced_tape"}
    return sig


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--min-hours", type=int, default=0,
        help="Minimum hours of capture required before running backtests. "
             "Script prints a 'not ready' notice below this threshold."
    )
    args = ap.parse_args()

    print(f"Loading {BYBIT_CSV}...")
    candles = load_csv(BYBIT_CSV)
    print(f"  {len(candles)} candles")

    # Check capture presence
    if not CAPTURE_DIR.exists():
        print(f"\n❌ Capture dir {CAPTURE_DIR} does not exist yet.")
        print("   Start the engine to begin capturing; see src/bybit_ws_capture.py")
        sys.exit(0)

    topic_files = {
        label: sorted((CAPTURE_DIR / label).glob("*.jsonl*"))
        for label in ("publicTrade", "orderbook", "liquidation", "tickers")
    }
    total_files = sum(len(v) for v in topic_files.values())
    print("\nCapture inventory:")
    for label, paths in topic_files.items():
        size_mb = sum(p.stat().st_size for p in paths) / 1e6
        print(f"  {label:12s}: {len(paths):4d} files, {size_mb:8.1f} MB")

    if total_files == 0:
        print("\n❌ Zero capture files. Run the engine for ≥24h and retry.")
        write_notready_report("no_files")
        sys.exit(0)

    print("\nLoading and binning microstructure events...")
    pt_events = load_topic("publicTrade")
    print(f"  publicTrade: {len(pt_events)} events")
    liq_events = load_topic("liquidation")
    print(f"  liquidation: {len(liq_events)} events")
    ob_events = load_topic("orderbook")
    print(f"  orderbook:   {len(ob_events)} events")
    tk_events = load_topic("tickers")
    print(f"  tickers:     {len(tk_events)} events")

    pt_bin = bin_public_trades(pt_events)
    liq_bin = bin_liquidations(liq_events)
    ob_bin = bin_orderbook(ob_events)
    tk_bin = bin_tickers(tk_events)

    topic_bins = {
        "publicTrade": pt_bin,
        "liquidation": liq_bin,
        "orderbook": ob_bin,
        "tickers": tk_bin,
    }
    for label, bm in topic_bins.items():
        print(f"  bars with {label}: {len(bm)}")

    enriched = enrich(candles, topic_bins)
    first_ts, last_ts, n_covered = coverage_window(enriched)
    hours_covered = (
        (last_ts - first_ts) / 3_600_000 if first_ts and last_ts else 0
    )
    print(f"\nCoverage: {n_covered} bars, {hours_covered:.1f}h elapsed")
    if first_ts:
        print(f"  first: {datetime.fromtimestamp(first_ts/1000, tz=timezone.utc)}")
        print(f"  last:  {datetime.fromtimestamp(last_ts/1000, tz=timezone.utc)}")

    if hours_covered < args.min_hours:
        print(f"\n⚠️  Coverage below --min-hours={args.min_hours}. "
              f"Running anyway with whatever data exists.")

    # Trim enriched candles to the covered window so the walk doesn't
    # waste cycles on pre-capture bars.
    if first_ts is not None:
        enriched = [c for c in enriched if c["ts"] >= first_ts]
        print(f"  trimmed to {len(enriched)} bars in coverage window")

    if len(enriched) < 100:
        print("\n❌ Coverage window too short (<100 bars). Retry later.")
        write_notready_report("short_window", hours_covered=hours_covered)
        sys.exit(0)

    # ── Run signals ─────────────────────────────────────────────────────
    results = []

    print("\n=== CVD divergence ===")
    sig = make_cvd_divergence_signal(lookback=20)
    trades = walk(enriched, signal_fn=sig, signal_name="cvd_div",
                  window=24, hold=12)
    s = summarize(trades, "cvd_div")
    results.append(("cvd_div", trades, s))
    print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    for min_usd in (250_000, 500_000, 1_000_000):
        name = f"liq_cascade_{min_usd//1000}k"
        print(f"\n=== Liquidation cascade fade (min=${min_usd:,}) ===")
        sig = make_liq_cascade_signal(lookback=3, min_usd=min_usd)
        trades = walk(enriched, signal_fn=sig, signal_name=name,
                      window=6, hold=6)
        s = summarize(trades, name)
        results.append((name, trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    for thresh in (0.20, 0.30, 0.40):
        name = f"book_imb_{int(thresh*100)}"
        print(f"\n=== Book imbalance (thresh={thresh}) ===")
        sig = make_book_imbalance_signal(lookback=3, thresh=thresh)
        trades = walk(enriched, signal_fn=sig, signal_name=name,
                      window=6, hold=6)
        s = summarize(trades, name)
        results.append((name, trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    for ratio in (2.5, 3.0, 4.0):
        name = f"taker_agg_{str(ratio).replace('.','p')}"
        print(f"\n=== Taker aggression (ratio≥{ratio}) ===")
        sig = make_taker_aggression_signal(ratio_thresh=ratio)
        trades = walk(enriched, signal_fn=sig, signal_name=name,
                      window=6, hold=6)
        s = summarize(trades, name)
        results.append((name, trades, s))
        print(f"  n={s['n']}  WR={s['wr']:.2f}%  P&L=${s['pnl']:+.2f}")

    write_full_report(results, hours_covered, topic_bins)


def write_notready_report(reason: str, hours_covered: float = 0.0):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Bybit microstructure backtest — NOT READY",
        "",
        f"Reason: `{reason}`",
        f"Hours of capture elapsed: {hours_covered:.1f}",
        "",
        "Start the engine with `src/bybit_ws_capture.py` running "
        "(already supervised by `botsy_engine.py` if this branch is live) "
        "and re-run this script after ≥24h of capture. For CVD and book "
        "imbalance signals, ≥7 days is recommended; for liquidation "
        "cascade statistics, ≥14 days is recommended.",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"Report: {OUT}")


def write_full_report(results, hours_covered, topic_bins):
    lines = [
        "# Bybit microstructure signals — backtest",
        "",
        f"Capture window: {hours_covered:.1f} hours.",
        "Signals tested on enriched 5m candles (candle OHLCV + CVD + "
        "liquidation aggregates + avg book imbalance + taker counts).",
        "",
        "## Inventory",
        "| Topic | Bars with data |",
        "|---|--:|",
    ]
    for label, bm in topic_bins.items():
        lines.append(f"| {label} | {len(bm)} |")
    lines.append("")
    lines.append("## Results")
    lines.append("| Signal | N | WR | P&L | Avg/trade |")
    lines.append("|--------|--:|---:|----:|----------:|")
    for name, _, s in results:
        if s["n"] == 0:
            lines.append(f"| {name} | 0 | — | — | — |")
            continue
        lines.append(
            f"| {name} | {s['n']} | {s['wr']:.2f}% | ${s['pnl']:+.2f} | "
            f"${s.get('avg', 0):+.3f} |"
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
                f"P&L=${s['pnl']:+.2f} — forward-test candidate"
            )
    else:
        lines.append(
            "❌ No microstructure signal clears 55% WR on N≥100 with "
            "positive P&L in the captured window. Either the window is "
            "too short (re-run after more capture) or the microstructure "
            "data class is also dead on this venue at 5m. If the latter "
            "holds after ≥14 days of capture, the exhaustive-negative "
            "conclusion extends to L2 + taker flow + liquidations + "
            "intra-bar funding, which is the strongest possible negative "
            "result on Bybit BTCUSDT 5m."
        )
    lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    print(f"\nReport: {OUT}")


if __name__ == "__main__":
    main()
