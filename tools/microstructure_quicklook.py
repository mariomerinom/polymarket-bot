"""
microstructure_quicklook.py — Daily health check for the Bybit
microstructure capture.

Read-only, no signal computation. Answers: "is the capture alive,
how much have we collected, and is each topic accumulating at the
expected rate?" Designed to be runnable any time without crashing
when capture is empty or partial.

Outputs (stdout + optional report file):

  - Hours of coverage per topic (calendar hours, not message count)
  - Total bytes per topic (gzipped + uncompressed current hour)
  - Message rate (msgs/min) per topic over the last 60 min
  - Liquidation event count + last-seen timestamp
  - Disk pressure: total capture dir size, projected 14-day footprint
  - Day-N readiness: red/amber/green for the Phase D decision gate

Decision colors:

  GREEN  capture has >= 7 calendar days AND all four topics nonempty
         (excluding liquidation, which is event-driven and may legitimately
         be empty for hours at a time)
  AMBER  capture has 1–7 days OR one topic is silent
  RED    capture dir missing, no files, or > 1 topic silent

Usage:
    python3 tools/microstructure_quicklook.py
    python3 tools/microstructure_quicklook.py --out docs/research/microstructure_quicklook.md
"""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR = ROOT / "data" / "bybit_capture"
TOPICS = ["publicTrade", "orderbook", "liquidation", "tickers"]


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _open_any(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _scan_topic(topic_dir: Path) -> dict:
    if not topic_dir.exists():
        return {
            "exists": False, "files": 0, "bytes": 0, "hours_covered": 0,
            "first_hour": None, "last_hour": None, "msgs_last_60m": 0,
            "last_event_ts_ms": None,
        }
    files = sorted(topic_dir.glob("*.jsonl*"))
    total_bytes = sum(f.stat().st_size for f in files)
    hours = sorted({f.stem.replace(".jsonl", "") for f in files})
    first_hour = hours[0] if hours else None
    last_hour = hours[-1] if hours else None

    # Sample last hour for msg rate + freshness
    msgs_last_60m = 0
    last_event_ts_ms = None
    if files:
        latest = files[-1]
        try:
            with _open_any(latest) as fh:
                for line in fh:
                    msgs_last_60m += 1
                    try:
                        obj = json.loads(line)
                        ts = obj.get("_rx_ms")
                        if ts and (last_event_ts_ms is None or ts > last_event_ts_ms):
                            last_event_ts_ms = ts
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

    return {
        "exists": True,
        "files": len(files),
        "bytes": total_bytes,
        "hours_covered": len(hours),
        "first_hour": first_hour,
        "last_hour": last_hour,
        "msgs_last_60m": msgs_last_60m,
        "last_event_ts_ms": last_event_ts_ms,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="Optional path to also write the report markdown")
    ap.add_argument("--capture-dir", default=str(CAPTURE_DIR))
    args = ap.parse_args()

    cap = Path(args.capture_dir)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    if not cap.exists():
        body = (
            "# Microstructure quicklook — RED\n\n"
            f"Capture dir not found: `{cap}`\n\n"
            "Engine restart needed, or `bybit_microstructure_feed` is "
            "not running. See `src/bybit_ws_capture.py`.\n"
        )
        print(body)
        if args.out:
            Path(args.out).write_text(body)
        return

    stats = {t: _scan_topic(cap / t) for t in TOPICS}

    # Color logic
    silent = [t for t in ("publicTrade", "orderbook", "tickers")
              if stats[t]["msgs_last_60m"] == 0]
    coverage_hours = max(s["hours_covered"] for s in stats.values()) if stats else 0
    if not any(s["exists"] for s in stats.values()) or len(silent) > 1:
        color, gloss = "RED", "capture down or > 1 topic silent"
    elif coverage_hours < 24 * 7 or silent:
        color, gloss = "AMBER", "still warming up or one topic silent"
    else:
        color, gloss = "GREEN", "ready for Phase D backtest"

    # Disk pressure
    total_bytes = sum(s["bytes"] for s in stats.values())
    days_so_far = max(coverage_hours / 24.0, 0.01)
    projected_14d = total_bytes / days_so_far * 14.0

    lines = [
        f"# Microstructure quicklook — {color}",
        "",
        f"_{datetime.now(timezone.utc).isoformat()} — {gloss}_",
        "",
        f"- Capture dir: `{cap}`",
        f"- Total disk: **{_human_bytes(total_bytes)}**",
        f"- Coverage (max across topics): **{coverage_hours}h** (~{coverage_hours/24:.1f} days)",
        f"- Projected 14-day footprint: **{_human_bytes(projected_14d)}**",
        "",
        "## Per-topic",
        "| Topic | Files | Bytes | Hours | First | Last | Msgs/last-hr | Last rx |",
        "|---|--:|--:|--:|---|---|--:|---|",
    ]
    for t in TOPICS:
        s = stats[t]
        last_rx = "—"
        if s["last_event_ts_ms"]:
            age_s = (now_ms - s["last_event_ts_ms"]) / 1000
            last_rx = f"{age_s:.0f}s ago"
        lines.append(
            f"| {t} | {s['files']} | {_human_bytes(s['bytes'])} | "
            f"{s['hours_covered']} | {s['first_hour'] or '—'} | "
            f"{s['last_hour'] or '—'} | {s['msgs_last_60m']} | {last_rx} |"
        )
    lines.append("")

    if silent:
        lines.append(f"⚠️ Silent topics in last hour: **{', '.join(silent)}**")
        lines.append("")

    # Phase D readiness
    lines.append("## Phase D readiness")
    if coverage_hours >= 24 * 14:
        lines.append("✅ ≥14 calendar days captured. Run `tools/backtest_bybit_microstructure.py`.")
    elif coverage_hours >= 24 * 7:
        lines.append(
            f"⚠️ {coverage_hours/24:.1f} days captured. Day-7 preliminary "
            "backtest is meaningful but not the final decision. Re-run "
            "at day 14."
        )
    else:
        lines.append(
            f"⏳ Only {coverage_hours/24:.1f} days captured. "
            f"Day-7 check unlocks at ~7d, Phase D decision at 14d."
        )

    body = "\n".join(lines) + "\n"
    print(body)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(body)
        print(f"Report: {args.out}")


if __name__ == "__main__":
    main()
