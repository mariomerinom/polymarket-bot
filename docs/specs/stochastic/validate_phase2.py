#!/usr/bin/env python3
"""
Phase 2 Diagnostic Validator
=============================
Parses DIAG log lines, validates data quality, computes statistics,
applies decision rules, and outputs an actionable verdict.

Usage:
    python validate_phase2.py --log-file logs/loop.log
    python validate_phase2.py --log-file logs/loop.log --min-samples 30
    python validate_phase2.py --log-file logs/loop.log --output report.md

The script produces:
  1. Data quality checks (are the logs trustworthy?)
  2. Statistical summaries (percentiles, distributions)
  3. Hypothesis tests (Mann-Whitney U for conviction vs drift)
  4. Decision verdicts (what to build next)
  5. A recommended fill strategy (one sentence)
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# 1. PARSING
# ---------------------------------------------------------------------------

DIAG_PATTERNS = {
    "decision_delay": re.compile(
        r"DIAG\|(?:decision_delay_ms|snapshot_age_ms)=(?P<age>[\d.]+)\|market=(?P<market>\S+)"
    ),
    "drift": re.compile(
        r"DIAG\|conv=(?P<conv>\d+)\|drift=(?P<drift>[\d.]+)"
    ),
    "rtt": re.compile(
        r"DIAG\|order_rtt_ms=(?P<rtt>[\d.]+)\|status=(?P<status>\S+)"
    ),
}


@dataclass
class DiagData:
    decision_delays: list = field(default_factory=list)
    drift_by_conv: dict = field(default_factory=lambda: defaultdict(list))
    rtts: list = field(default_factory=list)
    rtt_statuses: list = field(default_factory=list)
    markets_seen: set = field(default_factory=set)
    line_count: int = 0
    parse_errors: int = 0


def parse_logs(log_path: str) -> DiagData:
    data = DiagData()
    with open(log_path, "r") as f:
        for line in f:
            if "DIAG|" not in line:
                continue
            data.line_count += 1
            matched = False

            m = DIAG_PATTERNS["decision_delay"].search(line)
            if m:
                data.decision_delays.append(float(m.group("age")))
                data.markets_seen.add(m.group("market"))
                matched = True

            m = DIAG_PATTERNS["drift"].search(line)
            if m:
                conv = int(m.group("conv"))
                drift = float(m.group("drift"))
                data.drift_by_conv[conv].append(drift)
                matched = True

            m = DIAG_PATTERNS["rtt"].search(line)
            if m:
                data.rtts.append(float(m.group("rtt")))
                data.rtt_statuses.append(m.group("status"))
                matched = True

            if not matched:
                data.parse_errors += 1

    return data


# ---------------------------------------------------------------------------
# 2. DATA QUALITY CHECKS
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    check: str
    passed: bool
    detail: str


def run_quality_checks(data: DiagData, min_samples: int) -> list[QualityResult]:
    checks = []

    # Check 1: Did we get any data at all?
    checks.append(QualityResult(
        "DIAG lines found",
        data.line_count > 0,
        f"{data.line_count} lines parsed, {data.parse_errors} errors"
    ))

    # Check 2: Enough decision-delay samples?
    checks.append(QualityResult(
        "Decision delay samples",
        len(data.decision_delays) >= min_samples,
        f"{len(data.decision_delays)} samples (need {min_samples})"
    ))

    # Check 3: Enough drift samples per conviction tier?
    conv_tiers = [3, 4, 5]
    for tier in conv_tiers:
        n = len(data.drift_by_conv.get(tier, []))
        checks.append(QualityResult(
            f"Conv={tier} drift samples",
            n >= min_samples,
            f"{n} samples (need {min_samples})"
        ))

    # Check 4: Any RTT data? (only exists if orders were submitted)
    checks.append(QualityResult(
        "Order RTT samples",
        len(data.rtts) >= 1,
        f"{len(data.rtts)} samples (need >= 1; 0 is expected if no orders submitted)"
    ))

    # Check 5: Decision delays are plausible (not negative, not > 1 hour)
    if data.decision_delays:
        bad = [a for a in data.decision_delays if a < 0 or a > 3_600_000]
        checks.append(QualityResult(
            "Decision delay plausibility",
            len(bad) == 0,
            f"{len(bad)} implausible values (negative or > 1h)"
        ))

    # Check 6: Drift values are plausible (0 to 1 for prediction market prices)
    all_drifts = [d for dlist in data.drift_by_conv.values() for d in dlist]
    if all_drifts:
        bad = [d for d in all_drifts if d < 0 or d > 1.0]
        checks.append(QualityResult(
            "Drift value plausibility",
            len(bad) == 0,
            f"{len(bad)} values outside [0, 1.0]"
        ))

    # Check 7: Multiple markets observed (not just one)
    checks.append(QualityResult(
        "Market diversity",
        len(data.markets_seen) > 1,
        f"{len(data.markets_seen)} unique markets"
    ))

    return checks


# ---------------------------------------------------------------------------
# 3. STATISTICAL ANALYSIS
# ---------------------------------------------------------------------------

def percentiles(arr, ps=(50, 95, 99)):
    if not arr:
        return {p: None for p in ps}
    return {p: float(np.percentile(arr, p)) for p in ps}


def mann_whitney_u(a, b):
    """
    Manual Mann-Whitney U test (no scipy dependency).
    Returns U statistic and approximate p-value (normal approximation).
    """
    if len(a) < 5 or len(b) < 5:
        return None, None

    n1, n2 = len(a), len(b)
    combined = [(v, 0) for v in a] + [(v, 1) for v in b]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (handle ties with average rank)
    ranks = []
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2  # 1-indexed average
        for k in range(i, j):
            ranks.append((avg_rank, combined[k][1]))
        i = j

    r1 = sum(r for r, g in ranks if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    # Normal approximation
    mu = n1 * n2 / 2
    sigma = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sigma == 0:
        return u, 1.0
    z = (u - mu) / sigma
    # Two-tailed p-value from z (using error function approximation)
    p = 2 * (1 - 0.5 * (1 + _erf(abs(z) / np.sqrt(2))))
    return u, p


def _erf(x):
    """Approximation of the error function (Abramowitz & Stegun)."""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    t = 1.0 / (1.0 + p * abs(x))
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * np.exp(-x * x)
    return y if x >= 0 else -y


@dataclass
class AnalysisResult:
    decision_delay_pcts: dict
    rtt_pcts: dict
    drift_stats: dict  # {conv: {median, mean, std, n}}
    mw_u: float
    mw_p: float
    conv3_median: float
    conv5_median: float


def run_analysis(data: DiagData) -> AnalysisResult:
    decision_delay_pcts = percentiles(data.decision_delays)
    rtt_pcts = percentiles(data.rtts)

    drift_stats = {}
    for conv in sorted(data.drift_by_conv.keys()):
        arr = data.drift_by_conv[conv]
        if arr:
            drift_stats[conv] = {
                "median": float(np.median(arr)),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "n": len(arr),
            }

    conv3 = data.drift_by_conv.get(3, [])
    conv5 = data.drift_by_conv.get(5, [])
    u, p = mann_whitney_u(conv3, conv5)

    return AnalysisResult(
        decision_delay_pcts=decision_delay_pcts,
        rtt_pcts=rtt_pcts,
        drift_stats=drift_stats,
        mw_u=u,
        mw_p=p,
        conv3_median=float(np.median(conv3)) if conv3 else None,
        conv5_median=float(np.median(conv5)) if conv5 else None,
    )


# ---------------------------------------------------------------------------
# 4. DECISION RULES
# ---------------------------------------------------------------------------

@dataclass
class Verdict:
    tension: str
    metric: str
    value: str
    conclusion: str
    action: str
    confidence: str  # "high", "medium", "low"


def apply_decisions(analysis: AnalysisResult) -> list[Verdict]:
    verdicts = []

    # --- Tension 2: Decision delay ---
    p95_delay = analysis.decision_delay_pcts.get(95)
    if p95_delay is not None:
        if p95_delay < 30_000:
            verdicts.append(Verdict(
                "Decision Delay",
                "p95 decision delay",
                f"{p95_delay:.0f}ms",
                "Decision delay is acceptable",
                "Continue collecting; investigate true orderbook age separately.",
                "high"
            ))
        else:
            verdicts.append(Verdict(
                "Decision Delay",
                "p95 decision delay",
                f"{p95_delay:.0f}ms",
                "Dispatch/pipeline fanout is delaying decisions",
                "Decompose engine runtime before changing execution formulas.",
                "high"
            ))
    else:
        verdicts.append(Verdict(
            "Decision Delay",
            "p95 decision delay",
            "NO DATA",
            "Cannot determine",
            "Continue collecting data.",
            "low"
        ))

    # --- Tension 1: Conviction in slippage formula ---
    if analysis.mw_p is not None:
        if analysis.mw_p < 0.05 and analysis.conv5_median > analysis.conv3_median:
            verdicts.append(Verdict(
                "Conviction vs Drift",
                "Mann-Whitney p-value",
                f"p={analysis.mw_p:.4f} (conv5 median={analysis.conv5_median:.4f} > conv3={analysis.conv3_median:.4f})",
                "High conviction predicts worse adverse selection",
                "EXCLUDE conviction from slippage formula. Use microstructure only.",
                "high"
            ))
        elif analysis.mw_p < 0.05 and analysis.conv5_median < analysis.conv3_median:
            verdicts.append(Verdict(
                "Conviction vs Drift",
                "Mann-Whitney p-value",
                f"p={analysis.mw_p:.4f} (conv5 median={analysis.conv5_median:.4f} < conv3={analysis.conv3_median:.4f})",
                "High conviction predicts LESS adverse selection",
                "Conviction additive bonus is defensible (Grok approach).",
                "high"
            ))
        else:
            verdicts.append(Verdict(
                "Conviction vs Drift",
                "Mann-Whitney p-value",
                f"p={analysis.mw_p:.4f}" if analysis.mw_p else "insufficient samples",
                "No significant difference between conviction tiers",
                "Use conviction as ceiling/governor (Gemini approach).",
                "medium"
            ))
    else:
        verdicts.append(Verdict(
            "Conviction vs Drift",
            "Mann-Whitney p-value",
            "INSUFFICIENT DATA (need >= 5 samples per tier)",
            "Cannot determine",
            "Continue collecting data.",
            "low"
        ))

    # --- Cancel-replace feasibility ---
    p95_rtt = analysis.rtt_pcts.get(95)
    if p95_rtt is not None:
        if p95_rtt < 500:
            verdicts.append(Verdict(
                "Cancel-Replace Feasibility",
                "p95 order RTT",
                f"{p95_rtt:.0f}ms",
                "Cancel-replace cycles are viable",
                "Build cancel-replace into Phase 3. Maker logic is feasible.",
                "high"
            ))
        elif p95_rtt < 1000:
            verdicts.append(Verdict(
                "Cancel-Replace Feasibility",
                "p95 order RTT",
                f"{p95_rtt:.0f}ms",
                "Cancel-replace is tight but possible",
                "Limit to 2 cancel-replace cycles max. Maker logic is marginal.",
                "medium"
            ))
        else:
            verdicts.append(Verdict(
                "Cancel-Replace Feasibility",
                "p95 order RTT",
                f"{p95_rtt:.0f}ms",
                "Cancel-replace is impractical",
                "Skip cancel-replace. Stay taker with dynamic slippage. Maker logic is not viable.",
                "high"
            ))
    else:
        verdicts.append(Verdict(
            "Cancel-Replace Feasibility",
            "p95 order RTT",
            "NO DATA (no orders submitted)",
            "Cannot determine — expected if no live orders during collection window",
            "Need at least 1 order submission to measure. May require manual test order.",
            "low"
        ))

    return verdicts


# ---------------------------------------------------------------------------
# 5. COMPOSITE RECOMMENDATION
# ---------------------------------------------------------------------------

def composite_recommendation(verdicts: list[Verdict]) -> str:
    """
    Combine the three verdicts into a single recommended fill strategy.
    """
    staleness = next((v for v in verdicts if v.tension == "Decision Delay"), None)
    conviction = next((v for v in verdicts if v.tension == "Conviction vs Drift"), None)
    rtt = next((v for v in verdicts if v.tension == "Cancel-Replace Feasibility"), None)

    # Check if we have enough data to make any recommendation
    low_confidence = [v for v in verdicts if v.confidence == "low"]
    if len(low_confidence) >= 2:
        return (
            "INSUFFICIENT DATA — cannot make a reliable recommendation. "
            "Continue collecting diagnostic data. "
            f"Missing: {', '.join(v.tension for v in low_confidence)}"
        )

    parts = []

    # Infrastructure decision
    if staleness and staleness.value != "NO DATA":
        p95 = float(staleness.value.replace("ms", ""))
        if p95 > 2000:
            parts.append("BLOCK: Fix infrastructure first (Phase 3 websocket). Fill formula alone won't help.")
            return " → ".join(parts)
        elif p95 > 500:
            parts.append("Deploy fill formula now AND fast-track Phase 3.")
        else:
            parts.append("Infrastructure is adequate. Deploy fill formula.")

    # Fill strategy selection
    # Option 1: Simple limit (if staleness is low and we want speed)
    # Option 2: Dynamic microstructure (if we want precision)
    # Option 3: Dynamic + conviction ceiling (if conviction data supports it)
    if conviction:
        if "EXCLUDE" in conviction.action:
            parts.append("Formula: microstructure-only (no conviction). Or: simple limit min(estimate, 0.95).")
        elif "ceiling" in conviction.action.lower():
            parts.append("Formula: microstructure base + conviction ceiling (Gemini approach).")
        elif "additive" in conviction.action.lower() or "Grok" in conviction.action:
            parts.append("Formula: microstructure + conviction additive bonus (Grok approach).")

    # Execution strategy
    if rtt and "viable" in rtt.conclusion.lower():
        parts.append("Execution: maker-first with cancel-replace escalation to taker.")
    elif rtt and "tight" in rtt.conclusion.lower():
        parts.append("Execution: maker-first, 2 cycles max, then cross spread.")
    elif rtt and "impractical" in rtt.conclusion.lower():
        parts.append("Execution: taker with dynamic slippage. No maker logic.")
    else:
        parts.append("Execution: pending RTT data. Default to taker with formula.")

    return " → ".join(parts)


# ---------------------------------------------------------------------------
# 6. OUTPUT
# ---------------------------------------------------------------------------

def format_report(
    data: DiagData,
    quality: list[QualityResult],
    analysis: AnalysisResult,
    verdicts: list[Verdict],
    recommendation: str,
) -> str:
    lines = []
    lines.append("# Phase 2 Diagnostic Validation Report")
    lines.append(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # Data quality
    lines.append("## 1. Data Quality")
    lines.append("")
    all_passed = all(q.passed for q in quality)
    for q in quality:
        icon = "PASS" if q.passed else "FAIL"
        lines.append(f"- [{icon}] {q.check}: {q.detail}")
    lines.append("")
    if not all_passed:
        lines.append("> **WARNING:** Some quality checks failed. Verdicts below may be unreliable.")
        lines.append("")

    # Statistics
    lines.append("## 2. Statistics")
    lines.append("")
    lines.append("### Decision Delay")
    lines.append("")
    lines.append("| Percentile | Value |")
    lines.append("|------------|-------|")
    for p in (50, 95, 99):
        v = analysis.decision_delay_pcts.get(p)
        lines.append(f"| p{p} | {v:.0f}ms |" if v is not None else f"| p{p} | — |")
    lines.append("")

    lines.append("### Order RTT")
    lines.append("")
    lines.append("| Percentile | Value |")
    lines.append("|------------|-------|")
    for p in (50, 95, 99):
        v = analysis.rtt_pcts.get(p)
        lines.append(f"| p{p} | {v:.0f}ms |" if v is not None else f"| p{p} | — |")
    lines.append("")

    lines.append("### Conviction vs Price Drift")
    lines.append("")
    lines.append("| Conv Tier | Median Drift | Mean Drift | Std Dev | Samples |")
    lines.append("|-----------|-------------|-----------|---------|---------|")
    for conv in sorted(analysis.drift_stats.keys()):
        s = analysis.drift_stats[conv]
        lines.append(f"| {conv} | {s['median']:.4f} | {s['mean']:.4f} | {s['std']:.4f} | {s['n']} |")
    lines.append("")
    if analysis.mw_p is not None:
        lines.append(f"**Mann-Whitney U (conv=3 vs conv=5):** p={analysis.mw_p:.4f}")
        sig = "significant" if analysis.mw_p < 0.05 else "not significant"
        lines.append(f"Result: {sig} at alpha=0.05")
    else:
        lines.append("**Mann-Whitney U:** insufficient data")
    lines.append("")

    # Verdicts
    lines.append("## 3. Verdicts")
    lines.append("")
    for v in verdicts:
        icon = {"high": "HIGH", "medium": "MED", "low": "LOW"}[v.confidence]
        lines.append(f"### {v.tension} [{icon} confidence]")
        lines.append(f"- **Metric:** {v.metric} = {v.value}")
        lines.append(f"- **Conclusion:** {v.conclusion}")
        lines.append(f"- **Action:** {v.action}")
        lines.append("")

    # Composite recommendation
    lines.append("## 4. Recommendation")
    lines.append("")
    lines.append(f"**{recommendation}**")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Phase 2 Diagnostic Validator")
    parser.add_argument("--log-file", required=True, help="Path to DIAG log file")
    parser.add_argument("--min-samples", type=int, default=20, help="Minimum samples per metric (default: 20)")
    parser.add_argument("--output", help="Write markdown report to file (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Also output verdicts as JSON")
    args = parser.parse_args()

    # Parse
    print(f"Parsing {args.log_file}...", file=sys.stderr)
    data = parse_logs(args.log_file)
    print(f"  {data.line_count} DIAG lines, {data.parse_errors} parse errors", file=sys.stderr)

    # Quality checks
    quality = run_quality_checks(data, args.min_samples)
    failed = [q for q in quality if not q.passed]
    if failed:
        print(f"  WARNING: {len(failed)} quality checks failed", file=sys.stderr)

    # Analysis
    analysis = run_analysis(data)

    # Decisions
    verdicts = apply_decisions(analysis)

    # Composite
    recommendation = composite_recommendation(verdicts)
    print(f"\n  RECOMMENDATION: {recommendation}\n", file=sys.stderr)

    # Report
    report = format_report(data, quality, analysis, verdicts, recommendation)
    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    # Optional JSON
    if args.json:
        verdict_dicts = [
            {"tension": v.tension, "metric": v.metric, "value": v.value,
             "conclusion": v.conclusion, "action": v.action, "confidence": v.confidence}
            for v in verdicts
        ]
        json_out = {
            "recommendation": recommendation,
            "verdicts": verdict_dicts,
            "quality_passed": all(q.passed for q in quality),
        }
        json_path = (args.output or "phase2_verdict") + ".json"
        Path(json_path).write_text(json.dumps(json_out, indent=2))
        print(f"JSON written to {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
