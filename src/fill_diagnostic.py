"""
fill_diagnostic.py — Parse DIAG lines from VPS logs, compute summary statistics,
output decision table for Phase 2 of the unified VPS + websocket spec.

Usage:
    python src/fill_diagnostic.py --log-file logs/loop.log
    python src/fill_diagnostic.py --log-file logs/loop.log --min-samples 20 --markdown

Reads DIAG| lines emitted by trade.py and produces:
  - snapshot_age_ms: p50, p95, p99
  - order_rtt_ms: p50, p95, p99
  - price_drift grouped by conviction tier: median, mean, std
  - Mann-Whitney U test: conv=3 drift vs conv=5 drift
  - Auto-generated decision verdicts from spec decision rules
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def parse_diag_lines(log_path):
    """Parse all DIAG| lines from a log file into structured data."""
    snapshot_ages = []
    rtt_values = []
    drift_by_conv = defaultdict(list)

    with open(log_path, "r") as f:
        for line in f:
            if "DIAG|" not in line:
                continue

            # Diagnostic A: snapshot_age_ms
            m = re.search(r"DIAG\|snapshot_age_ms=(\d+)", line)
            if m and "conv=" not in line and "order_rtt" not in line:
                snapshot_ages.append(float(m.group(1)))

            # Diagnostic B: conviction + drift
            m = re.search(
                r"DIAG\|conv=(\d+)\|drift=([\d.]+)\|snapshot_age_ms=(\d+)",
                line,
            )
            if m:
                conv = int(m.group(1))
                drift = float(m.group(2))
                drift_by_conv[conv].append(drift)

            # Diagnostic C: order_rtt_ms
            m = re.search(r"DIAG\|order_rtt_ms=(\d+)", line)
            if m:
                rtt_values.append(float(m.group(1)))

    return snapshot_ages, rtt_values, drift_by_conv


def percentiles(values, label=""):
    """Compute p50, p95, p99 for a list of values."""
    if not values:
        return {"p50": None, "p95": None, "p99": None, "count": 0}
    arr = np.array(values)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "count": len(arr),
    }


def mann_whitney_test(a, b):
    """Run Mann-Whitney U test. Returns (U statistic, p-value) or None."""
    if len(a) < 5 or len(b) < 5:
        return None
    try:
        from scipy.stats import mannwhitneyu
        stat, p = mannwhitneyu(a, b, alternative="two-sided")
        return {"U": float(stat), "p": float(p)}
    except ImportError:
        # scipy not available — skip statistical test
        return None


def staleness_verdict(p95):
    """Apply spec decision rule for snapshot staleness."""
    if p95 is None:
        return "insufficient data"
    if p95 < 500:
        return "minor — websocket rewrite is optimization, not urgent"
    if p95 <= 2000:
        return "gray zone — deploy formula now, accelerate Phase 3"
    return "root cause — Phase 3 websocket rewrite is mandatory"


def conviction_verdict(mw_result, drift_by_conv):
    """Apply spec decision rule for conviction vs drift."""
    if mw_result is None:
        return "insufficient data"
    median_3 = float(np.median(drift_by_conv.get(3, [0]))) if drift_by_conv.get(3) else None
    median_5 = float(np.median(drift_by_conv.get(5, [0]))) if drift_by_conv.get(5) else None
    if mw_result["p"] < 0.05 and median_5 and median_3 and median_5 > median_3:
        return "exclude conviction from pricing — use microstructure only"
    if mw_result["p"] >= 0.05:
        return "no significant difference — use conviction as ceiling/governor"
    return "conviction additive bonus is defensible"


def rtt_verdict(p95):
    """Apply spec decision rule for cancel-replace feasibility."""
    if p95 is None:
        return "insufficient data"
    if p95 < 500:
        return "cancel-replace cycles are viable — build into Phase 3"
    if p95 <= 1000:
        return "possible but tight — limit to 2 cycles max"
    return "impractical on this API — skip cancel-replace"


def generate_report(snapshot_ages, rtt_values, drift_by_conv, min_samples=20):
    """Generate the full diagnostic report as markdown."""
    snap_stats = percentiles(snapshot_ages)
    rtt_stats = percentiles(rtt_values)

    lines = []
    lines.append("## Fill Diagnostic (Phase 2)\n")

    # Snapshot age + RTT table
    lines.append("| Metric | p50 | p95 | p99 | Samples |")
    lines.append("|--------|-----|-----|-----|---------|")
    if snap_stats["count"] > 0:
        lines.append(f"| Snapshot age (ms) | {snap_stats['p50']:.0f} | {snap_stats['p95']:.0f} | {snap_stats['p99']:.0f} | {snap_stats['count']} |")
    else:
        lines.append("| Snapshot age (ms) | — | — | — | 0 |")
    if rtt_stats["count"] > 0:
        lines.append(f"| Order RTT (ms) | {rtt_stats['p50']:.0f} | {rtt_stats['p95']:.0f} | {rtt_stats['p99']:.0f} | {rtt_stats['count']} |")
    else:
        lines.append("| Order RTT (ms) | — | — | — | 0 |")
    lines.append("")

    # Conviction drift table
    lines.append("| Conv Tier | Median Drift | Mean Drift | Std | Samples |")
    lines.append("|-----------|-------------|------------|-----|---------|")
    for conv in sorted(drift_by_conv.keys()):
        vals = drift_by_conv[conv]
        arr = np.array(vals)
        lines.append(f"| {conv} | {np.median(arr):.4f} | {np.mean(arr):.4f} | {np.std(arr):.4f} | {len(vals)} |")
    if not drift_by_conv:
        lines.append("| — | — | — | — | 0 |")
    lines.append("")

    # Mann-Whitney test
    mw = mann_whitney_test(
        drift_by_conv.get(3, []),
        drift_by_conv.get(5, []),
    )
    if mw:
        lines.append(f"Mann-Whitney U (conv=3 vs conv=5): U={mw['U']:.1f}, p={mw['p']:.4f}\n")
    else:
        n3 = len(drift_by_conv.get(3, []))
        n5 = len(drift_by_conv.get(5, []))
        lines.append(f"Mann-Whitney U: insufficient data (conv=3: {n3} samples, conv=5: {n5} samples, need >= 5 each)\n")

    # Decision verdicts
    lines.append("### Decisions")
    total_samples = snap_stats["count"] + rtt_stats["count"] + sum(len(v) for v in drift_by_conv.values())
    if total_samples < min_samples:
        lines.append(f"Collecting data ({total_samples} samples so far, need >= {min_samples})\n")
    else:
        sv = staleness_verdict(snap_stats["p95"])
        cv = conviction_verdict(mw, drift_by_conv)
        rv = rtt_verdict(rtt_stats["p95"])
        lines.append(f"- Snapshot staleness p95={snap_stats['p95']:.0f}ms: **{sv}**")
        lines.append(f"- Conviction vs drift: **{cv}**")
        lines.append(f"- Order RTT p95={rtt_stats['p95']:.0f}ms: **{rv}**" if rtt_stats["p95"] else f"- Order RTT: **{rv}**")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Phase 2 fill diagnostic analysis")
    parser.add_argument("--log-file", required=True, help="Path to VPS log file")
    parser.add_argument("--min-samples", type=int, default=20, help="Min samples before generating verdicts")
    parser.add_argument("--markdown", action="store_true", help="Output as markdown (default: text)")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        sys.exit(1)

    snapshot_ages, rtt_values, drift_by_conv = parse_diag_lines(log_path)

    print(f"Parsed: {len(snapshot_ages)} snapshot_age, {len(rtt_values)} rtt, "
          f"{sum(len(v) for v in drift_by_conv.values())} drift samples")
    print()

    report = generate_report(snapshot_ages, rtt_values, drift_by_conv, args.min_samples)
    print(report)


if __name__ == "__main__":
    main()
